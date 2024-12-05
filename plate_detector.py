import time
from typing import Optional, List
from datetime import datetime
import streamlit as st
from platerecognizer_service import PlateRecognizerService

class PlateDetector:
    def __init__(self):
        """Inizializza il detector con PlateRecognizer"""
        try:
            self.service = PlateRecognizerService()
            if not self.service.validate_api_key():
                st.warning("⚠️ Verifica la configurazione di PlateRecognizer nelle secrets")
                st.info("📝 Formato atteso in .streamlit/secrets.toml:\n[platerecognizer]\napi_key = \"token-api\"")
                self.service = None
        except Exception as e:
            st.error(f"❌ Errore inizializzazione PlateRecognizer: {str(e)}")
            self.service = None

    def detect_plate_from_url(self, image_url: str) -> Optional[str]:
        """Rileva targa usando PlateRecognizer con validazione migliorata"""
        try:
            if not self.service:
                return None

            # Log per debug
            st.write(f"🔍 Analisi immagine: {image_url}")
            
            # Prova rilevamento con validazione estesa
            result = self.service.detect_from_url(image_url)
            
            if result and result.score > 0.7:
                # Mostra tutti i candidati per debug
                if result.candidates:
                    st.write("🎯 Candidati rilevati:")
                    for idx, candidate in enumerate(result.candidates, 1):
                        st.write(f"{idx}. Targa: {candidate['plate']} (Score: {candidate['score']:.2f})")
                
                # Mostra dettagli veicolo se disponibili
                if result.vehicle:
                    st.write("🚗 Dettagli veicolo rilevati:", result.vehicle)
                
                return result.plate
                
            return None
            
        except Exception as e:
            st.error(f"❌ Errore nel rilevamento targa: {str(e)}")
            return None

    def detect_with_retry(self, image_url: str, max_retries: int = 3) -> Optional[str]:
        """Esegue il rilevamento con retry automatici e logging migliorato"""
        for attempt in range(max_retries):
            try:
                st.write(f"🔄 Tentativo {attempt + 1}/{max_retries}")
                
                if plate := self.detect_plate_from_url(image_url):
                    st.success(f"✅ Targa rilevata: {plate}")
                    return plate
                    
                if attempt < max_retries - 1:
                    st.info("⏳ Attendo prima del prossimo tentativo...")
                    time.sleep(2 * (attempt + 1))  # Backoff esponenziale
                    
            except Exception as e:
                st.error(f"❌ Errore nel tentativo {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    return None
                time.sleep(2 * (attempt + 1))
        
        st.warning("⚠️ Nessuna targa rilevata dopo tutti i tentativi")
        return None

    def clear_cache(self):
        """Pulisce la cache dei risultati"""
        if self.service:
            self.service.clear_cache()
            st.success("🧹 Cache pulita con successo")