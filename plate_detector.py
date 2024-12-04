from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
from PIL import Image
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
            # Cache per ottimizzazione
            self.results_cache = {}
        except Exception as e:
            st.error(f"Errore inizializzazione Azure Vision: {str(e)}")
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
                return match.group(0)
                
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
                progress_bar.progress(0.2, "Analizzando immagine con Azure...")

            # Esegui OCR direttamente sull'URL
            result = self.client.read(url=image_url, raw=True)
            
            # Get the operation location (URL with ID da monitorare)
            operation_location = result.headers["Operation-Location"]
            operation_id = operation_location.split("/")[-1]

            # Attendi il completamento dell'analisi
            while True:
                get_text_result = self.client.get_read_result(operation_id)
                if get_text_result.status not in ['notStarted', 'running']:
                    break
                if progress_bar:
                    progress_bar.progress(0.5, "Elaborazione in corso...")
                time.sleep(1)

            # Analizza risultati
            if get_text_result.status == OperationStatusCodes.succeeded:
                if progress_bar:
                    progress_bar.progress(0.8, "Analizzando risultati...")
                    
                for text_result in get_text_result.analyze_result.read_results:
                    for line in text_result.lines:
                        # Valida solo se confidence alta
                        if line.appearance.confidence > 0.7:
                            if plate := self._validate_plate(line.text):
                                # Cache risultato
                                self.results_cache[image_url] = {
                                    'plate': plate,
                                    'timestamp': datetime.now(),
                                    'confidence': line.appearance.confidence
                                }
                                
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