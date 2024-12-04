import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import requests
from io import BytesIO
import re
import numpy as np
import cv2
import streamlit as st
from typing import Optional, List, Tuple
import time

class PlateDetector:
    def __init__(self):
        """Initialize detector with optimized settings"""
        # Configurazione OCR ottimizzata per targhe italiane
        self.tesseract_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        
        # Parametri di preprocessing configurabili
        self.preprocessing_params = {
            'target_width': 1200,  # Aumentato per maggiore dettaglio
            'target_height': 800,
            'contrast_factor': 1.8,
            'brightness_factor': 1.2,
            'sharpness_factor': 1.5
        }

    def _download_image(self, image_url: str) -> Optional[Image.Image]:
        """Download immagine con gestione errori"""
        try:
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))
        except Exception as e:
            st.warning(f"Errore nel download dell'immagine: {str(e)}")
            return None

    def _enhance_plate_region(self, image: Image.Image) -> Image.Image:
        """Migliora la qualità dell'immagine per OCR"""
        # Converti in scala di grigi
        gray = image.convert('L')
        
        # Applica sharpening per migliorare i bordi
        sharp = gray.filter(ImageFilter.SHARPEN)
        
        # Aumenta contrasto
        contrasted = ImageEnhance.Contrast(sharp).enhance(self.preprocessing_params['contrast_factor'])
        
        # Aumenta luminosità
        brightened = ImageEnhance.Brightness(contrasted).enhance(self.preprocessing_params['brightness_factor'])
        
        # Applica un ulteriore sharpening
        final = ImageEnhance.Sharpness(brightened).enhance(self.preprocessing_params['sharpness_factor'])
        
        return final

    def _find_blue_regions(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Trova regioni blu che potrebbero essere targhe"""
        # Converti in HSV per migliore rilevamento del colore
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        
        # Range del blu delle targhe italiane
        lower_blue = np.array([100, 50, 50])
        upper_blue = np.array([130, 255, 255])
        
        # Crea maschera per regioni blu
        mask = cv2.inRange(hsv, lower_blue, upper_blue)
        
        # Trova contorni
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filtra per proporzioni tipiche targa italiana (520x110 mm)
        plate_regions = []
        target_ratio = 4.7  # 520/110
        ratio_tolerance = 0.5
        
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            ratio = w / h if h != 0 else 0
            
            if abs(ratio - target_ratio) < ratio_tolerance:
                # Espandi leggermente la regione
                x = max(0, x - 5)
                y = max(0, y - 5)
                w = min(image.shape[1] - x, w + 10)
                h = min(image.shape[0] - y, h + 10)
                plate_regions.append((x, y, w, h))
        
        return plate_regions

    def detect_plate_from_url(self, image_url: str, progress_bar: Optional[st.progress] = None) -> Optional[str]:
        """Pipeline principale di rilevamento targa"""
        try:
            # Download immagine
            if progress_bar:
                progress_bar.progress(0.2, "Scaricando immagine...")
                
            image = self._download_image(image_url)
            if image is None:
                return None

            # Converte in array numpy per OpenCV
            np_image = np.array(image)
            
            if progress_bar:
                progress_bar.progress(0.4, "Cercando regioni targa...")
            
            # Trova possibili regioni targa
            plate_regions = self._find_blue_regions(np_image)
            
            if progress_bar:
                progress_bar.progress(0.6, "Analizzando regioni...")
            
            for x, y, w, h in plate_regions:
                # Estrai e preprocessa regione
                region = Image.fromarray(np_image[y:y+h, x:x+w])
                enhanced_region = self._enhance_plate_region(region)
                
                # Prova OCR con diverse configurazioni
                for psm in [7, 8, 6]:  # Prova diverse modalità di segmentazione
                    config = f'--oem 3 --psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                    text = pytesseract.image_to_string(enhanced_region, config=config).strip()
                    
                    # Valida il risultato
                    if plate := self._validate_plate(text):
                        if progress_bar:
                            progress_bar.progress(1.0, f"Targa trovata: {plate}")
                        return plate

            # Se non trova nulla, prova sull'immagine intera
            if progress_bar:
                progress_bar.progress(0.8, "Analizzando immagine intera...")
                
            enhanced_full = self._enhance_plate_region(image)
            text = pytesseract.image_to_string(enhanced_full, config=self.tesseract_config)
            
            if plate := self._validate_plate(text):
                if progress_bar:
                    progress_bar.progress(1.0, f"Targa trovata: {plate}")
                return plate
            
            if progress_bar:
                progress_bar.progress(1.0, "Nessuna targa trovata")
            return None
            
        except Exception as e:
            st.error(f"Errore nel rilevamento targa: {str(e)}")
            return None

    def _validate_plate(self, text: str) -> Optional[str]:
        """Valida e formatta la targa"""
        if not text:
            return None
        
        # Pulizia testo
        text = ''.join(c for c in text.upper() if c.isalnum())
        
        # Pattern targa italiana
        patterns = [
            r'[A-Z]{2}\d{3}[A-Z]{2}',     # Standard (AA000BB)
            r'[A-Z]{2}\d{5}',              # Vecchio formato
            r'[A-Z]{2}\d{4}[A-Z]{1,2}'     # Altri formati
        ]
        
        for pattern in patterns:
            if match := re.search(pattern, text):
                return match.group(0)
        
        return None

    def detect_with_retry(self, image_url: str, max_retries: int = 2) -> Optional[str]:
        """Rileva targa con retry automatici"""
        original_params = self.preprocessing_params.copy()
        
        for attempt in range(max_retries):
            try:
                if plate := self.detect_plate_from_url(image_url):
                    return plate
                    
                # Modifica parametri per il prossimo tentativo
                if attempt == 0:
                    self.preprocessing_params['contrast_factor'] += 0.3
                    self.preprocessing_params['brightness_factor'] += 0.2
                elif attempt == 1:
                    self.preprocessing_params['contrast_factor'] -= 0.6
                    self.preprocessing_params['brightness_factor'] -= 0.4
                    self.preprocessing_params['sharpness_factor'] += 0.5
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    st.error(f"Tutti i tentativi falliti: {str(e)}")
                    self.preprocessing_params = original_params
                    return None
                time.sleep(1)
        
        self.preprocessing_params = original_params
        return None