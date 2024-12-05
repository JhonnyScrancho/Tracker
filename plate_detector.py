import time
from typing import Optional
from datetime import datetime
import streamlit as st
import cv2
from platerecognizer_service import PlateRecognizerService

class PlateDetector:
    def __init__(self):
        """Inizializza il detector con PlateRecognizer"""
        try:
            self.service = PlateRecognizerService()
            if not self.service.validate_api_key():
                st.error("❌ API Key PlateRecognizer non valida")
                self.service = None
            self.results_cache = {}
        except Exception as e:
            st.error(f"❌ Errore inizializzazione PlateRecognizer: {str(e)}")
            self.service = None

    def detect_plate_from_url(self, image_url: str) -> Optional[str]:
        """Rileva targa usando PlateRecognizer"""
        try:
            if not self.service:
                return None

            # Prova rilevamento
            result = self.service.detect_from_url(
                image_url,
                regions=['it']  # Limitato a targhe italiane
            )
            
            if result and result.score > 0.7:  # Soglia minima confidenza
                return result.plate
                
            return None
            
        except Exception as e:
            st.error(f"❌ Errore nel rilevamento targa: {str(e)}")
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
        if self.service:
            self.service.clear_cache()