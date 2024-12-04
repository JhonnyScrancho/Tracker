import pytesseract
from PIL import Image, ImageEnhance
import requests
from io import BytesIO
import re
import numpy as np
import streamlit as st
from typing import Optional, List, Tuple
try:
    from pyzbar.pyzbar import decode
    PYZBAR_AVAILABLE = True
except ImportError:
    print("Warning: pyzbar non disponibile. Il riconoscimento da barcode sarà disabilitato.")
    PYZBAR_AVAILABLE = False
    decode = None
import time
from collections import OrderedDict

class PlateCache:
    def __init__(self, max_size=1000):
        self.cache = OrderedDict()
        self.max_size = max_size
    
    def get(self, image_url: str) -> Optional[str]:
        """Recupera una targa dalla cache"""
        return self.cache.get(image_url)
        
    def set(self, image_url: str, plate: str):
        """Salva una targa in cache con gestione dimensione massima"""
        if len(self.cache) >= self.max_size:
            # Rimuovi entry più vecchia
            self.cache.popitem(last=False)
        self.cache[image_url] = plate

class PlateDetector:
    def __init__(self):
        """Initialize detector with optimized settings"""
        # Configurazione base Tesseract ottimizzata per targhe
        self.tesseract_config = '--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ' \
                               '-c tessedit_certainty_threshold=60'
        
        # Cache per risultati positivi
        self.plate_cache = PlateCache(max_size=1000)
        
        # Parametri di preprocessing configurabili
        self.preprocessing_params = {
            'target_width': 800,
            'target_height': 600,
            'contrast_factor': 1.5,
            'brightness_factor': 1.1
        }
        
        # Dimensioni standard targa italiana (proporzioni)
        self.plate_aspect_ratio = 4.7
        self.plate_aspect_tolerance = 0.5

    def _download_and_preprocess(self, image_url: str) -> Optional[Image.Image]:
        """Download e preprocessing ottimizzato dell'immagine"""
        try:
            # Download con timeout
            response = requests.get(image_url, timeout=5)
            response.raise_for_status()
            
            # Conversione in PIL Image
            image = Image.open(BytesIO(response.content))
            
            # Preprocessing base
            return self._preprocess_image(image)
            
        except Exception as e:
            st.warning(f"Errore nel download/preprocessing: {str(e)}")
            return None

    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """Preprocessing ottimizzato dell'immagine"""
        # Conversione in scala di grigi
        gray = image.convert('L')
        
        # Ridimensionamento ottimale
        w, h = gray.size
        ratio = min(
            self.preprocessing_params['target_width']/w,
            self.preprocessing_params['target_height']/h
        )
        new_size = (int(w*ratio), int(h*ratio))
        gray = gray.resize(new_size, Image.LANCZOS)
        
        # Miglioramento contrasto
        contrast = ImageEnhance.Contrast(gray)
        enhanced = contrast.enhance(self.preprocessing_params['contrast_factor'])
        
        # Miglioramento luminosità
        brightness = ImageEnhance.Brightness(enhanced)
        enhanced = brightness.enhance(self.preprocessing_params['brightness_factor'])
        
        return enhanced

    def _find_plate_regions(self, image: Image.Image) -> List[Image.Image]:
        """
        Cerca regioni che potrebbero contenere targhe basandosi sulle proporzioni
        Restituisce una lista di sottoimmagini candidate
        """
        width, height = image.size
        min_width = width // 8  # La targa dovrebbe essere almeno 1/8 della larghezza
        candidates = []
        
        # Converti in array numpy per analisi
        img_array = np.array(image)
        
        # Trova regioni con alto contrasto
        edges = np.gradient(img_array)
        edge_magnitude = np.sqrt(edges[0]**2 + edges[1]**2)
        
        # Trova aree rettangolari con proporzioni simili a targa
        regions = []  # Lista di (x, y, w, h)
        
        # Implementazione semplificata: divide l'immagine in regioni
        # e cerca quelle con proporzioni simili a una targa
        step_x = width // 4
        step_y = height // 4
        
        for y in range(0, height - step_y, step_y // 2):
            for x in range(0, width - step_x, step_x // 2):
                region_width = min(step_x, width - x)
                # Calcola altezza basata sul rapporto targa
                region_height = int(region_width / self.plate_aspect_ratio)
                
                if y + region_height <= height:
                    region = image.crop((x, y, x + region_width, y + region_height))
                    candidates.append(region)
        
        return candidates

    def _try_pyzbar(self, image: Image.Image) -> Optional[str]:
        """Try to find plate in QR codes or barcodes"""
        if not PYZBAR_AVAILABLE:
            return None
            
        try:
            decoded = decode(image)
            for d in decoded:
                text = d.data.decode()
                plate = self.validate_plate(text)
                if plate:
                    return plate
        except Exception as e:
            st.warning(f"Errore pyzbar: {str(e)}")
        return None

    def validate_plate(self, text: str) -> Optional[str]:
        """Validazione robusta della targa"""
        if not text:
            return None
        
        # Pulizia aggressiva
        text = ''.join(c for c in text.upper() if c.isalnum())
        
        # Pattern matching con priorità
        patterns = [
            (r'[A-Z]{2}\d{3}[A-Z]{2}', 0),     # Standard
            (r'[A-Z]{2}\d{4}[A-Z]', 1),         # Altri formati
            (r'[A-Z]{2}\d{5}', 2),              # Formato vecchio
            (r'[A-Z]{2}\d{4}[A-Z]{1,2}', 3)     # Altri formati validi
        ]
        
        # Prova tutti i pattern
        matches = []
        for pattern, priority in patterns:
            if match := re.search(pattern, text):
                matches.append((match.group(0), priority))
        
        # Ritorna il match con priorità più alta
        return min(matches, key=lambda x: x[1])[0] if matches else None

    def _adjust_params(self, attempt: int) -> None:
        """Aggiusta parametri di preprocessing per retry"""
        if attempt == 1:
            self.preprocessing_params['contrast_factor'] += 0.2
            self.preprocessing_params['brightness_factor'] += 0.1
        elif attempt == 2:
            self.preprocessing_params['contrast_factor'] -= 0.4
            self.preprocessing_params['brightness_factor'] -= 0.2

    def detect_plate_from_url(self, image_url: str, progress_bar: Optional[st.progress] = None) -> Optional[str]:
        """Pipeline principale di rilevamento targa"""
        try:
            # 1. Check cache
            if plate := self.plate_cache.get(image_url):
                if progress_bar:
                    progress_bar.progress(1.0, f"Trovata targa in cache: {plate}")
                return plate
            
            if progress_bar:
                progress_bar.progress(0.2, "Download e preprocessing...")
                
            # 2. Download e preprocessing
            image = self._download_and_preprocess(image_url)
            if image is None:
                return None
            
            if progress_bar:
                progress_bar.progress(0.4, "Cercando codici QR/barcode...")
                
            # 3. Prova pyzbar (più veloce)
            if plate := self._try_pyzbar(image):
                self.plate_cache.set(image_url, plate)
                if progress_bar:
                    progress_bar.progress(1.0, f"Trovata targa in barcode: {plate}")
                return plate
            
            if progress_bar:
                progress_bar.progress(0.6, "Cercando regioni targa...")
                
            # 4. Cerca regioni candidate
            plate_regions = self._find_plate_regions(image)
            
            if progress_bar:
                progress_bar.progress(0.8, "Eseguendo OCR...")
                
            # 5. OCR sulle regioni candidate
            for region in plate_regions:
                text = pytesseract.image_to_string(region, config=self.tesseract_config)
                if plate := self.validate_plate(text):
                    self.plate_cache.set(image_url, plate)
                    if progress_bar:
                        progress_bar.progress(1.0, f"Trovata targa: {plate}")
                    return plate
            
            if progress_bar:
                progress_bar.progress(1.0, "Nessuna targa trovata")
            return None
            
        except Exception as e:
            st.error(f"Errore nel rilevamento targa: {str(e)}")
            return None

    def detect_with_retry(self, image_url: str, max_retries: int = 2) -> Optional[str]:
        """Rileva targa con retry automatici"""
        original_params = self.preprocessing_params.copy()
        
        for attempt in range(max_retries):
            try:
                if plate := self.detect_plate_from_url(image_url):
                    return plate
                # Modifica parametri per il prossimo tentativo
                self._adjust_params(attempt)
            except Exception as e:
                if attempt == max_retries - 1:
                    st.error(f"Tutti i tentativi falliti: {str(e)}")
                    # Ripristina parametri originali
                    self.preprocessing_params = original_params
                    return None
                time.sleep(1)  # Pausa tra tentativi
                
        # Ripristina parametri originali
        self.preprocessing_params = original_params
        return None