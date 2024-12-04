from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw
import numpy as np
from io import BytesIO
import requests
import re
import streamlit as st
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import time

class PlateDetector:
    def __init__(self):
        try:
            self.client = ComputerVisionClient(
                endpoint=st.secrets["azure"]["endpoint"],
                credentials=CognitiveServicesCredentials(st.secrets["azure"]["key"])
            )
            self.results_cache = {}
            self.debug_mode = False
        except Exception as e:
            st.error(f"Errore inizializzazione Azure Vision: {str(e)}")
            self.client = None

    def _detect_plate_area(self, img: Image.Image) -> Optional[Tuple[int, int, int, int]]:
        """
        Rileva l'area della targa nell'immagine usando caratteristiche specifiche
        
        Args:
            img: Immagine PIL
        Returns:
            Tuple (x1, y1, x2, y2) dell'area targa o None
        """
        try:
            # Converti in array numpy per elaborazione
            img_array = np.array(img)
            height, width = img_array.shape[:2]
            
            # Converti in scala di grigi
            if len(img_array.shape) == 3:
                gray = img.convert('L')
            else:
                gray = img
                
            # Applica edge detection
            edges = gray.filter(ImageFilter.FIND_EDGES)
            
            # Cerca rettangoli con proporzioni simili a targa italiana (520x110 mm)
            plate_ratio = 4.72  # 520/110
            tolerance = 0.5
            min_ratio = plate_ratio - tolerance
            max_ratio = plate_ratio + tolerance
            
            # Cerca aree candidate nella metà inferiore dell'immagine
            candidate_regions = []
            
            # Divide l'immagine in regioni e cerca pattern rettangolari
            for y in range(height // 2, height - 20, 20):
                for x in range(0, width - 40, 20):
                    # Analizza regione 100x300 px (approssimazione targa)
                    region = edges.crop((x, y, x + 300, y + 100))
                    region_array = np.array(region)
                    
                    # Calcola densità bordi nella regione
                    edge_density = np.mean(region_array)
                    
                    # Se la densità è alta, potrebbe essere una targa
                    if edge_density > 30:  # Soglia da calibrare
                        width_region = 300
                        height_region = 100
                        ratio = width_region / height_region
                        
                        if min_ratio <= ratio <= max_ratio:
                            score = edge_density * (1 - abs(ratio - plate_ratio))
                            candidate_regions.append({
                                'box': (x, y, x + width_region, y + height_region),
                                'score': score
                            })
            
            if candidate_regions:
                # Prendi la regione con score più alto
                best_region = max(candidate_regions, key=lambda x: x['score'])
                
                if self.debug_mode:
                    # Disegna rettangolo per debug
                    debug_img = img.copy()
                    draw = ImageDraw.Draw(debug_img)
                    draw.rectangle(best_region['box'], outline='red', width=2)
                    st.image(debug_img, caption="Area targa rilevata", use_column_width=True)
                
                return best_region['box']
            
            return None
            
        except Exception as e:
            if self.debug_mode:
                st.warning(f"Errore nel rilevamento area targa: {str(e)}")
            return None

    def _enhance_plate_image(self, img: Image.Image, plate_area: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
        """
        Migliora l'immagine della targa con preprocessing specializzato
        
        Args:
            img: Immagine PIL
            plate_area: Area della targa (x1, y1, x2, y2)
        Returns:
            Immagine migliorata
        """
        try:
            # Ritaglia area targa se specificata
            if plate_area:
                img = img.crop(plate_area)
                
            # Ridimensiona per dimensioni standard targa
            target_width = 400  # Larghezza ottimale per OCR
            ratio = target_width / img.width
            target_height = int(img.height * ratio)
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # Converti in scala di grigi
            img = img.convert('L')
            
            # Equalizza istogramma per migliorare contrasto
            img = ImageOps.equalize(img)
            
            # Aumenta nitidezza
            img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150))
            
            # Aumenta contrasto
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)
            
            # Riduci rumore
            img = img.filter(ImageFilter.MedianFilter(3))
            
            # Binarizzazione adattiva
            threshold = np.array(img).mean() - 10
            img = img.point(lambda x: 255 if x > threshold else 0)
            
            return img
            
        except Exception as e:
            if self.debug_mode:
                st.warning(f"Errore nel miglioramento immagine: {str(e)}")
            return img

    def detect_plate_from_url(self, image_url: str, 
                            progress_bar: Optional[st.progress] = None) -> Optional[str]:
        """Rileva targa usando strategia migliorata con rilevamento area"""
        try:
            if progress_bar:
                progress_bar.progress(0.2, "Scaricando immagine...")
            
            # Scarica immagine
            response = requests.get(image_url, timeout=10)
            img = Image.open(BytesIO(response.content))
            
            if progress_bar:
                progress_bar.progress(0.4, "Rilevando area targa...")
            
            # Rileva area targa
            plate_area = self._detect_plate_area(img)
            
            if progress_bar:
                progress_bar.progress(0.6, "Migliorando immagine...")
            
            # Migliora immagine
            enhanced_img = self._enhance_plate_image(img, plate_area)
            
            if self.debug_mode:
                st.image([img, enhanced_img], 
                        caption=['Originale', 'Migliorata'],
                        width=300)
            
            # Converti per Azure
            img_byte_arr = BytesIO()
            enhanced_img.save(img_byte_arr, format='JPEG', quality=95)
            img_byte_arr.seek(0)
            
            if progress_bar:
                progress_bar.progress(0.8, "Eseguendo OCR...")
            
            # Esegui OCR
            result = self.client.read_in_stream(img_byte_arr, raw=True)
            operation_location = result.headers["Operation-Location"]
            operation_id = operation_location.split("/")[-1]

            # Attendi risultato
            timeout = time.time() + 30
            while True:
                get_text_result = self.client.get_read_result(operation_id)
                if get_text_result.status not in ['notStarted', 'running']:
                    break
                if time.time() > timeout:
                    raise TimeoutError("Timeout nel riconoscimento")
                time.sleep(1)

            if get_text_result.status == OperationStatusCodes.succeeded:
                texts = []
                for text_result in get_text_result.analyze_result.read_results:
                    for line in text_result.lines:
                        if plate := self._validate_plate(line.text):
                            if progress_bar:
                                progress_bar.progress(1.0, f"✅ Targa trovata: {plate}")
                            return plate
                        texts.append(line.text)
                
                if self.debug_mode:
                    st.write("Testi rilevati:", texts)

            if progress_bar:
                progress_bar.progress(1.0, "❌ Nessuna targa trovata")
            return None
            
        except Exception as e:
            st.error(f"Errore nel rilevamento: {str(e)}")
            return None

    def _validate_plate(self, text: str) -> Optional[str]:
        """Validazione targa migliorata"""
        if not text:
            return None
            
        # Pulizia testo
        text = ''.join(c for c in text.upper() if c.isalnum())
        
        # Correzioni comuni
        corrections = {
            '0': 'O', 'O': '0',
            '1': 'I', 'I': '1',
            '5': 'S', 'S': '5',
            '8': 'B', 'B': '8'
        }
        
        # Prova varianti con correzioni
        texts_to_try = [text]
        for old, new in corrections.items():
            texts_to_try.append(text.replace(old, new))
        
        # Pattern targhe italiane
        patterns = [
            r'^[ABCDEFGHJKLMNPRSTVWXYZ]{2}\d{3}[ABCDEFGHJKLMNPRSTVWXYZ]{2}$',
            r'^[A-Z]{2}\d{5,6}$',
            r'^[A-Z]{2}\d{4}[A-Z]$'
        ]
        
        for test_text in texts_to_try:
            for pattern in patterns:
                if match := re.match(pattern, test_text):
                    plate = match.group(0)
                    # Verifica caratteri non validi
                    if any(c in 'IOQU' for c in plate[:2]):
                        continue
                    return plate
                    
        return None