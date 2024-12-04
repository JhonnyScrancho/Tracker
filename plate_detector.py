import time
import boto3
import re
from typing import Optional
from datetime import datetime
import streamlit as st

class PlateDetector:
    def __init__(self):
        """Inizializza il detector con Amazon Rekognition"""
        try:
            # Inizializza client Rekognition con credenziali da Streamlit secrets
            self.client = boto3.client(
                'rekognition',
                aws_access_key_id=st.secrets["aws"]["access_key_id"],
                aws_secret_access_key=st.secrets["aws"]["secret_access_key"],
                region_name=st.secrets["aws"]["region"]
            )
            self.results_cache = {}
        except Exception as e:
            st.error(f"Errore inizializzazione Rekognition: {str(e)}")
            self.client = None

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
                plate = match.group(0)
                # Verifica ulteriore per targhe italiane
                if any(c in 'IOQU' for c in plate[:2]):  # Caratteri non usati nelle targhe
                    continue
                return plate
                
        return None

    def detect_plate_from_url(self, image_url: str) -> Optional[str]:
        """Rileva targa usando Amazon Rekognition"""
        try:
            # Check cache
            if image_url in self.results_cache:
                cached = self.results_cache[image_url]
                if 'plate' in cached:
                    age = (datetime.now() - cached['timestamp']).total_seconds()
                    if age < 3600:  # Cache valida per 1 ora
                        return cached['plate']

            # Scarica immagine
            import requests
            response = requests.get(image_url)
            image_bytes = response.content

            # Analisi con Rekognition
            response = self.client.detect_text(Image={'Bytes': image_bytes})
            
            # Processa risultati
            for detection in response['TextDetections']:
                if detection['Type'] == 'LINE':  # Cerca solo linee di testo complete
                    if plate := self._validate_plate(detection['DetectedText']):
                        # Salva in cache
                        self.results_cache[image_url] = {
                            'plate': plate,
                            'timestamp': datetime.now()
                        }
                        return plate

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

    def clear_cache(self):
        """Pulisce la cache dei risultati"""
        self.results_cache = {}