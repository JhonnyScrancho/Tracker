import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
import requests
from io import BytesIO
import re
import numpy as np
import cv2
import streamlit as st
from typing import Optional, List, Tuple, Dict
import time
from datetime import datetime

class PlateDetector:
    def __init__(self):
        """Inizializza il detector con configurazioni ottimizzate per targhe italiane"""
        # Configurazione OCR multimodale
        self.tesseract_configs = [
            '--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',  # Uniforma trattamento
            '--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',  # Per blocchi di testo
            '--oem 3 --psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',  # Una parola
            '--oem 3 --psm 13 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'  # Raw line
        ]
        
        # Parametri preprocessing configurabili
        self.preprocessing_params = {
            'target_width': 1200,
            'target_height': 800,
            'contrast_range': [1.5, 2.0, 2.5],
            'brightness_range': [1.0, 1.2, 1.4],
            'sharpness_range': [1.5, 2.0, 2.5],
            'gamma_range': [0.8, 1.0, 1.2],
            'blur_kernels': [(3,3), (5,5), (7,7)],
            'canny_thresholds': [(50,150), (100,200), (150,250)]
        }
        
        # Parametri per rilevamento banda blu
        self.blue_ranges = [
            # Mattina/Mezzogiorno
            {'lower': np.array([100, 50, 50]), 'upper': np.array([130, 255, 255])},
            # Pomeriggio/Sera
            {'lower': np.array([100, 30, 30]), 'upper': np.array([140, 255, 255])},
            # Ombra/Nuvoloso
            {'lower': np.array([90, 40, 40]), 'upper': np.array([150, 255, 255])}
        ]
        
        # Cache risultati per ottimizzazione
        self.results_cache = {}

    def _download_image(self, image_url: str) -> Optional[Image.Image]:
        """Download immagine con gestione errori e cache"""
        try:
            # Check cache
            if image_url in self.results_cache:
                return self.results_cache[image_url]['image']
                
            # Download con timeout
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            # Converti in PIL Image
            image = Image.open(BytesIO(response.content))
            
            # Cache result
            self.results_cache[image_url] = {'image': image, 'timestamp': datetime.now()}
            
            return image
        except Exception as e:
            st.warning(f"Errore nel download dell'immagine: {str(e)}")
            return None

    def _enhance_image(self, image: Image.Image, params: Dict) -> List[Image.Image]:
        """Applica diverse combinazioni di enhancement per massimizzare il successo"""
        enhanced_images = []
        
        # Ridimensiona per processamento uniforme
        aspect = image.width / image.height
        new_width = self.preprocessing_params['target_width']
        new_height = int(new_width / aspect)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Applica combinazioni di enhancement
        for contrast in params['contrast_range']:
            for brightness in params['brightness_range']:
                for sharpness in params['sharpness_range']:
                    for gamma in params['gamma_range']:
                        try:
                            # Converti in scala di grigi
                            img = image.convert('L')
                            
                            # Applica correzione gamma
                            img = Image.fromarray(
                                np.array(img) ** gamma * (255 / (255 ** gamma))
                                .astype(np.uint8)
                            )
                            
                            # Applica enhancement sequenziale
                            img = ImageEnhance.Contrast(img).enhance(contrast)
                            img = ImageEnhance.Brightness(img).enhance(brightness)
                            img = ImageEnhance.Sharpness(img).enhance(sharpness)
                            
                            enhanced_images.append(img)
                        except Exception as e:
                            st.warning(f"Errore in enhancement: {str(e)}")
                            continue
                            
        return enhanced_images

    def _find_plate_regions(self, np_image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Trova possibili regioni targa usando multiple tecniche"""
        regions = []
        
        # Converte in HSV per rilevamento colore
        hsv = cv2.cvtColor(np_image, cv2.COLOR_RGB2HSV)
        
        # Prova diversi range di blu
        for blue_range in self.blue_ranges:
            try:
                # Crea maschera per regioni blu
                mask = cv2.inRange(hsv, blue_range['lower'], blue_range['upper'])
                
                # Applica morphological operations
                kernel = np.ones((5,5), np.uint8)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
                
                # Trova contorni
                contours, _ = cv2.findContours(
                    mask,
                    cv2.RETR_EXTERNAL,
                    cv2.CHAIN_APPROX_SIMPLE
                )
                
                # Filtra per proporzioni targa italiana (520x110 mm)
                target_ratio = 4.7  # 520/110
                ratio_tolerance = 0.8
                
                for cnt in contours:
                    x, y, w, h = cv2.boundingRect(cnt)
                    ratio = w / h if h != 0 else 0
                    area = w * h
                    
                    if (abs(ratio - target_ratio) < ratio_tolerance and 
                        area > 1000):  # Filtra regioni troppo piccole
                        
                        # Espandi leggermente la regione
                        x = max(0, x - 10)
                        y = max(0, y - 10)
                        w = min(np_image.shape[1] - x, w + 20)
                        h = min(np_image.shape[0] - y, h + 20)
                        
                        regions.append((x, y, w, h))
                
            except Exception as e:
                st.warning(f"Errore in find_plate_regions: {str(e)}")
                continue
                
        return regions

    def _validate_plate(self, text: str) -> Optional[str]:
        """Valida e formatta la targa con controlli migliorati"""
        if not text:
            return None
            
        # Pulizia testo
        text = ''.join(c for c in text.upper() if c.isalnum())
        
        # Pattern targhe italiane
        patterns = [
            # Formato corrente (AA000AA)
            r'^[ABCDEFGHJKLMNPRSTVWXYZ]{2}[0-9]{3}[ABCDEFGHJKLMNPRSTVWXYZ]{2}$',
            
            # Formato precedente (AA000AA) con varianti
            r'^[A-Z]{2}[0-9]{3,5}[A-Z]{0,2}$',
            
            # Formati speciali
            r'^[A-Z]{2,3}[0-9]{2,5}$',  # Targhe storiche/speciali
            r'^[A-Z]{2}[0-9]{4}[A-Z]$'   # Altri formati validi
        ]
        
        # Controlli validità
        for pattern in patterns:
            if match := re.match(pattern, text):
                plate = match.group(0)
                
                # Controlli addizionali
                if len(plate) < 6 or len(plate) > 8:
                    continue
                    
                # Controllo caratteri non validi
                invalid_chars = {'I', 'O', 'Q', 'U'}
                if any(c in invalid_chars for c in plate[:2]):
                    continue
                    
                return plate
                
        return None

    def detect_plate_from_url(self, image_url: str, 
                            progress_bar: Optional[st.progress] = None) -> Optional[str]:
        """Pipeline principale di rilevamento targa con feedback visivo"""
        try:
            # Check cache
            if image_url in self.results_cache:
                cached = self.results_cache[image_url]
                if 'plate' in cached:
                    age = (datetime.now() - cached['timestamp']).total_seconds()
                    if age < 3600:  # Cache valida per 1 ora
                        return cached['plate']
            
            # Download immagine
            if progress_bar:
                progress_bar.progress(0.1, "Scaricando immagine...")
                
            image = self._download_image(image_url)
            if image is None:
                return None

            # Converti in array numpy per OpenCV
            np_image = np.array(image)
            
            if progress_bar:
                progress_bar.progress(0.3, "Cercando regioni targa...")
            
            # Trova possibili regioni targa
            plate_regions = self._find_plate_regions(np_image)
            
            if progress_bar:
                progress_bar.progress(0.5, "Analizzando regioni...")
            
            # Processa ogni regione trovata
            for x, y, w, h in plate_regions:
                region = Image.fromarray(np_image[y:y+h, x:x+w])
                
                # Applica diverse combinazioni di enhancement
                enhanced_regions = self._enhance_image(region, self.preprocessing_params)
                
                # Prova OCR con diverse configurazioni
                for enhanced in enhanced_regions:
                    for config in self.tesseract_configs:
                        try:
                            text = pytesseract.image_to_string(
                                enhanced,
                                config=config
                            ).strip()
                            
                            if plate := self._validate_plate(text):
                                # Cache risultato
                                self.results_cache[image_url]['plate'] = plate
                                self.results_cache[image_url]['timestamp'] = datetime.now()
                                
                                if progress_bar:
                                    progress_bar.progress(1.0, f"Targa trovata: {plate}")
                                return plate
                                
                        except Exception as e:
                            st.warning(f"Errore OCR: {str(e)}")
                            continue

            # Se non trova nulla, prova sull'immagine intera
            if progress_bar:
                progress_bar.progress(0.8, "Analizzando immagine intera...")
                
            image_full = Image.fromarray(np_image)
            enhanced_full = self._enhance_image(image_full, self.preprocessing_params)
            
            for enhanced in enhanced_full:
                for config in self.tesseract_configs:
                    try:
                        text = pytesseract.image_to_string(enhanced, config=config)
                        if plate := self._validate_plate(text):
                            # Cache risultato
                            self.results_cache[image_url]['plate'] = plate
                            self.results_cache[image_url]['timestamp'] = datetime.now()
                            
                            if progress_bar:
                                progress_bar.progress(1.0, f"Targa trovata: {plate}")
                            return plate
                    except Exception as e:
                        continue
            
            if progress_bar:
                progress_bar.progress(1.0, "Nessuna targa trovata")
            return None
            
        except Exception as e:
            st.error(f"Errore nel rilevamento targa: {str(e)}")
            return None

    def detect_with_retry(self, image_url: str, max_retries: int = 3) -> Optional[str]:
        """Esegue il rilevamento con retry automatici e parametri adattivi"""
        original_params = self.preprocessing_params.copy()
        
        for attempt in range(max_retries):
            try:
                # Progress bar per feedback visivo
                progress_bar = st.progress(0)
                progress_text = st.empty()
                
                progress_bar.progress(0.2, f"Tentativo {attempt + 1}/{max_retries}")
                
                if plate := self.detect_plate_from_url(image_url, progress_bar):
                    progress_text.success(f"✅ Targa rilevata al tentativo {attempt + 1}")
                    return plate
                    
                # Adatta parametri per il prossimo tentativo
                if attempt == 0:
                    self.preprocessing_params['contrast_range'] = [x + 0.3 for x in self.preprocessing_params['contrast_range']]
                    self.preprocessing_params['brightness_range'] = [x + 0.2 for x in self.preprocessing_params['brightness_range']]
                elif attempt == 1:
                    self.preprocessing_params['contrast_range'] = [x - 0.6 for x in self.preprocessing_params['contrast_range']]
                    self.preprocessing_params['brightness_range'] = [x - 0.4 for x in self.preprocessing_params['brightness_range']]
                    self.preprocessing_params['sharpness_range'] = [x + 0.5 for x in self.preprocessing_params['sharpness_range']]
                
                progress_text.warning(f"⚠️ Tentativo {attempt + 1} fallito, modifico parametri...")
                time.sleep(1)  # Pausa tra tentativi
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    st.error(f"❌ Tutti i tentativi falliti: {str(e)}")
                    self.preprocessing_params = original_params
                    return None
                time.sleep(1)
        
        self.preprocessing_params = original_params
        return None

    def clear_cache(self):
        """Pulisce la cache dei risultati"""
        self.results_cache = {}