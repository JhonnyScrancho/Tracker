from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
from PIL import Image, ImageEnhance
import requests
from io import BytesIO
import re
import streamlit as st
from typing import Optional, Dict
from datetime import datetime
import time
import cv2
import numpy as np

class PlateDetector:
    def __init__(self):
        """Inizializza il detector con Azure Computer Vision"""
        try:
            self.client = ComputerVisionClient(
                endpoint=st.secrets["azure"]["endpoint"],
                credentials=CognitiveServicesCredentials(st.secrets["azure"]["key"])
            )
            self.results_cache = {}
        except Exception as e:
            st.error(f"Errore inizializzazione Azure Vision: {str(e)}")
            self.client = None

    def _preprocess_image(self, image_url: str) -> Optional[bytes]:
        """Preprocessa l'immagine per migliorare il riconoscimento"""
        try:
            # Download immagine
            response = requests.get(image_url)
            img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            # Converti in HSV
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            
            # Range per il blu della targa italiana
            lower_blue = np.array([100, 50, 50])
            upper_blue = np.array([130, 255, 255])
            
            # Crea maschera per area blu
            mask = cv2.inRange(hsv, lower_blue, upper_blue)
            
            # Trova i contorni
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Trova il contorno più grande (probabile targa)
            if contours:
                c = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(c)
                
                # Espandi leggermente l'area
                padding = 10
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(img.shape[1] - x, w + 2*padding)
                h = min(img.shape[0] - y, h + 2*padding)
                
                # Estrai la regione della targa
                plate_region = img[y:y+h, x:x+w]
                
                # Applica correzioni
                plate_region = cv2.convertScaleAbs(plate_region, alpha=1.2, beta=30)  # Aumenta contrasto e luminosità
                
                # Converti in bytes per Azure
                _, buffer = cv2.imencode('.jpg', plate_region)
                return BytesIO(buffer.tobytes())
            
            return BytesIO(response.content)  # Ritorna immagine originale se non trova la targa
            
        except Exception as e:
            st.warning(f"Errore nel preprocessing: {str(e)}")
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
                plate = match.group(0)
                # Verifica ulteriore per targhe italiane
                if any(c in 'IOQU' for c in plate[:2]):  # Caratteri non usati nelle targhe
                    continue
                return plate
                
        return None

    def detect_plate_from_url(self, image_url: str, 
                            progress_bar: Optional[st.progress] = None) -> Optional[str]:
        """Rileva targa usando Azure Computer Vision con preprocessing"""
        try:
            # Check cache
            if image_url in self.results_cache:
                cached = self.results_cache[image_url]
                if 'plate' in cached:
                    age = (datetime.now() - cached['timestamp']).total_seconds()
                    if age < 3600:  # Cache valida per 1 ora
                        return cached['plate']
            
            if progress_bar:
                progress_bar.progress(0.2, "Preprocessando immagine...")

            # Preprocessa immagine
            processed_image = self._preprocess_image(image_url)
            if not processed_image:
                return None

            if progress_bar:
                progress_bar.progress(0.4, "Analizzando con Azure...")

            # Esegui OCR sull'immagine preprocessata
            result = self.client.read_in_stream(processed_image, raw=True)
            
            # Get the operation location
            operation_location = result.headers["Operation-Location"]
            operation_id = operation_location.split("/")[-1]

            # Attendi il completamento
            while True:
                get_text_result = self.client.get_read_result(operation_id)
                if get_text_result.status not in ['notStarted', 'running']:
                    break
                if progress_bar:
                    progress_bar.progress(0.6, "Elaborazione in corso...")
                time.sleep(1)

            if get_text_result.status == OperationStatusCodes.succeeded:
                if progress_bar:
                    progress_bar.progress(0.8, "Analizzando risultati...")
                    
                text_results = []
                for text_result in get_text_result.analyze_result.read_results:
                    for line in text_result.lines:
                        text_results.append(line.text)
                        if plate := self._validate_plate(line.text):
                            self.results_cache[image_url] = {
                                'plate': plate,
                                'timestamp': datetime.now()
                            }
                            
                            if progress_bar:
                                progress_bar.progress(1.0, f"✅ Targa trovata: {plate}")
                            return plate
                
                # Debug: mostra tutti i testi trovati
                st.write("Testi rilevati:", text_results)

            if progress_bar:
                progress_bar.progress(1.0, "❌ Nessuna targa trovata")
            return None
            
        except Exception as e:
            st.error(f"Errore nel rilevamento targa: {str(e)}")
            return None

    def detect_with_retry(self, image_url: str, max_retries: int = 2) -> Optional[str]:
        """Esegue il rilevamento con retry automatici"""
        for attempt in range(max_retries):
            try:
                progress_bar = st.progress(0)
                progress_text = st.empty()
                
                progress_bar.progress(0.2, f"Tentativo {attempt + 1}/{max_retries}")
                
                if plate := self.detect_plate_from_url(image_url, progress_bar):
                    progress_text.success(f"✅ Targa rilevata al tentativo {attempt + 1}")
                    return plate
                
                progress_text.warning(f"⚠️ Tentativo {attempt + 1} fallito, riprovo...")
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