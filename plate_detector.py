import time
from typing import Optional
from datetime import datetime
import streamlit as st
import requests
import cv2
import numpy as np
from openalpr import Alpr

class PlateDetectorALPR:
    def __init__(self):
        """Inizializza il detector con OpenALPR"""
        try:
            # Inizializza ALPR per targhe europee
            self.alpr = Alpr("eu", "/etc/openalpr/openalpr.conf", "/usr/share/openalpr/runtime_data")
            if not self.alpr.is_loaded():
                raise RuntimeError("Errore nel caricamento di OpenALPR")
            
            # Configura per targhe italiane
            self.alpr.set_top_n(5)
            self.alpr.set_default_region("it")
            
            self.results_cache = {}
        except Exception as e:
            st.error(f"Errore inizializzazione OpenALPR: {str(e)}")
            self.alpr = None

    def _validate_plate(self, text: str) -> Optional[str]:
        """Valida il formato targa italiana"""
        if not text:
            return None
            
        # Pulizia testo
        text = ''.join(c for c in text.upper() if c.isalnum())
        
        # Pattern targa italiana moderna (es. FL694XB)
        import re
        patterns = [
            r'^[ABCDEFGHJKLMNPRSTVWXYZ]{2}\d{3}[ABCDEFGHJKLMNPRSTVWXYZ]{2}$',  # Standard
            r'^[A-Z]{2}\d{5}$',                                                  # Vecchio formato
            r'^[A-Z]{2}\d{4}[A-Z]$'                                             # Formato speciale
        ]
        
        for pattern in patterns:
            if match := re.match(pattern, text):
                plate = match.group(0)
                # Verifica ulteriore per targhe italiane
                if any(c in 'IOQU' for c in plate[:2]):  # Caratteri non usati nelle targhe
                    continue
                return plate
                
        return None

    def detect_plate_from_url(self, image_url: str) -> Optional[str]:
        """Rileva targa usando OpenALPR"""
        try:
            # Check cache
            if image_url in self.results_cache:
                cached = self.results_cache[image_url]
                if 'plate' in cached:
                    age = (datetime.now() - cached['timestamp']).total_seconds()
                    if age < 3600:  # Cache valida per 1 ora
                        return cached['plate']

            # Scarica immagine
            response = requests.get(image_url)
            nparr = np.frombuffer(response.content, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            # Analisi con OpenALPR
            if self.alpr:
                results = self.alpr.recognize_ndarray(img)
                if results['results']:
                    # Prendi il risultato con confidence più alta
                    best_result = max(results['results'], key=lambda x: x['confidence'])
                    plate = best_result['plate']
                    
                    if validated_plate := self._validate_plate(plate):
                        # Salva in cache
                        self.results_cache[image_url] = {
                            'plate': validated_plate,
                            'timestamp': datetime.now()
                        }
                        return validated_plate

            return None
            
        except Exception as e:
            st.error(f"Errore nel rilevamento targa: {str(e)}")
            return None

    def detect_with_retry(self, image_url: str, max_retries: int = 2) -> Optional[str]:
        """Esegue il rilevamento con retry automatici"""
        for attempt in range(max_retries):
            try:
                if plate := self.detect_plate_from_url(image_url):
                    return plate
                time.sleep(1)
            except Exception as e:
                if attempt == max_retries - 1:
                    st.error(f"❌ Tutti i tentativi falliti: {str(e)}")
                    return None
                time.sleep(1)
        return None

    def __del__(self):
        """Cleanup quando l'oggetto viene distrutto"""
        if hasattr(self, 'alpr') and self.alpr:
            self.alpr.unload()

    def clear_cache(self):
        """Pulisce la cache dei risultati"""
        self.results_cache = {}