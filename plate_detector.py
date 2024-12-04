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

    def _enhance_image(self, image_url: str) -> Optional[BytesIO]:
        """Migliora la qualità dell'immagine usando PIL"""
        try:
            # Download immagine
            response = requests.get(image_url)
            img = Image.open(BytesIO(response.content))
            
            # Migliora contrasto
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)
            
            # Migliora luminosità
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(1.2)
            
            # Converti in bytes
            img_byte_arr = BytesIO()
            img.save(img_byte_arr, format=img.format if img.format else 'JPEG')
            img_byte_arr.seek(0)
            
            return img_byte_arr
            
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
        """Rileva targa usando Azure Computer Vision"""
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

            # Migliora qualità immagine
            enhanced_image = self._enhance_image(image_url)
            if not enhanced_image:
                if progress_bar:
                    progress_bar.progress(0.4, "Usando immagine originale...")
                # Usa URL originale se il preprocessing fallisce
                result = self.client.read(url=image_url, raw=True)
            else:
                # Usa immagine migliorata
                if progress_bar:
                    progress_bar.progress(0.4, "Analizzando con Azure...")
                result = self.client.read_in_stream(enhanced_image, raw=True)
            
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