from paddleocr import PaddleOCR
from PIL import Image
import requests
from io import BytesIO
import re
import numpy as np
import cv2
import streamlit as st
from typing import Optional, List, Dict
import time
from datetime import datetime

class PlateDetector:
    def __init__(self):
        """Inizializza il detector con PaddleOCR"""
        try:
            self.ocr = PaddleOCR(
                use_angle_cls=True,  # Rileva rotazione testo
                lang='en',           # Modello inglese (più accurato per targhe)
                show_log=False,      # Disabilita log
                use_gpu=False        # CPU only su Streamlit
            )
            # Cache per ottimizzazione
            self.results_cache = {}
        except Exception as e:
            st.error(f"Errore inizializzazione OCR: {str(e)}")
            self.ocr = None

    def _download_image(self, image_url: str) -> Optional[Image.Image]:
        """Download immagine con gestione errori e cache"""
        try:
            # Check cache
            if image_url in self.results_cache:
                return self.results_cache[image_url]['image']
                
            response = requests.get(image_url, timeout=10)
            response.raise_for_status()
            
            image = Image.open(BytesIO(response.content))
            
            # Cache result
            self.results_cache[image_url] = {
                'image': image, 
                'timestamp': datetime.now()
            }
            
            return image
        except Exception as e:
            st.warning(f"Errore nel download dell'immagine: {str(e)}")
            return None

    def _validate_plate(self, text: str) -> Optional[str]:
        """Valida il formato targa italiana"""
        if not text:
            return None
            
        # Pulizia testo
        text = ''.join(c for c in text.upper() if c.isalnum())
        
        # Pattern targa italiana moderna (es. FL694XB)
        patterns = [
            r'^[ABCDEFGHJKLMNPRSTVWXYZ]{2}\d{3}[ABCDEFGHJKLMNPRSTVWXYZ]{2}$',  # Standard
            r'^[A-Z]{2}\d{5}$',                                                  # Vecchio formato
            r'^[A-Z]{2}\d{4}[A-Z]$'                                             # Formato speciale
        ]
        
        for pattern in patterns:
            if match := re.match(pattern, text):
                return match.group(0)
                
        return None

    def detect_plate_from_url(self, image_url: str, 
                            progress_bar: Optional[st.progress] = None) -> Optional[str]:
        """Rileva targa usando PaddleOCR"""
        try:
            # Check cache
            if image_url in self.results_cache:
                cached = self.results_cache[image_url]
                if 'plate' in cached:
                    age = (datetime.now() - cached['timestamp']).total_seconds()
                    if age < 3600:  # Cache valida per 1 ora
                        return cached['plate']
            
            if progress_bar:
                progress_bar.progress(0.2, "Scaricando immagine...")
                
            # Download immagine
            image = self._download_image(image_url)
            if image is None:
                return None

            if progress_bar:
                progress_bar.progress(0.4, "Analizzando immagine...")

            # Converti in array numpy
            np_image = np.array(image)
            
            # Esegui OCR
            result = self.ocr.ocr(np_image, cls=True)
            
            if progress_bar:
                progress_bar.progress(0.6, "Processando risultati...")
            
            # Analizza risultati
            if result:
                texts = []
                for line in result:
                    for word_info in line:
                        text = word_info[1][0]  # Estrai testo rilevato
                        confidence = word_info[1][1]  # Confidence score
                        
                        # Valida solo se confidence alta
                        if confidence > 0.7:
                            texts.append(text)
                
                # Cerca targa nei testi trovati
                for text in texts:
                    if plate := self._validate_plate(text):
                        # Cache risultato
                        self.results_cache[image_url]['plate'] = plate
                        self.results_cache[image_url]['timestamp'] = datetime.now()
                        
                        if progress_bar:
                            progress_bar.progress(1.0, f"Targa trovata: {plate}")
                        return plate
            
            if progress_bar:
                progress_bar.progress(1.0, "Nessuna targa trovata")
            return None
            
        except Exception as e:
            st.error(f"Errore nel rilevamento targa: {str(e)}")
            return None

    def detect_with_retry(self, image_url: str, max_retries: int = 2) -> Optional[str]:
        """Esegue il rilevamento con retry automatici"""
        for attempt in range(max_retries):
            try:
                # Progress bar per feedback visivo
                progress_bar = st.progress(0)
                progress_text = st.empty()
                
                progress_bar.progress(0.2, f"Tentativo {attempt + 1}/{max_retries}")
                
                if plate := self.detect_plate_from_url(image_url, progress_bar):
                    progress_text.success(f"✅ Targa rilevata al tentativo {attempt + 1}")
                    return plate
                
                progress_text.warning(f"⚠️ Tentativo {attempt + 1} fallito, riprovo...")
                time.sleep(1)  # Pausa tra tentativi
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    st.error(f"❌ Tutti i tentativi falliti: {str(e)}")
                    return None
                time.sleep(1)
        
        return None

    def clear_cache(self):
        """Pulisce la cache dei risultati"""
        self.results_cache = {}