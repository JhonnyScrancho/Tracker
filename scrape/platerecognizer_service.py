import streamlit as st
import requests
import time
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class PlateResult:
    plate: str
    score: float
    region: dict
    vehicle: dict
    candidates: List[dict]

class PlateRecognizerService:
    def __init__(self):
        """Inizializza il servizio PlateRecognizer usando le credenziali da Streamlit secrets"""
        self.api_key = st.secrets["platerecognizer"]["api_key"]
        self.base_url = "https://api.platerecognizer.com/v1"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {self.api_key}'
        })
        self.results_cache = {}

    def detect_from_url(self, image_url: str, cache_ttl: int = 3600) -> Optional[PlateResult]:
        """
        Rileva targa da URL immagine con configurazione ottimizzata per targhe italiane
        
        Args:
            image_url: URL dell'immagine
            cache_ttl: Tempo di validità cache in secondi
            
        Returns:
            PlateResult o None se non trovata
        """
        try:
            # Check cache
            if image_url in self.results_cache:
                cached = self.results_cache[image_url]
                if time.time() - cached['timestamp'] < cache_ttl:
                    return cached['result']

            # Configurazione ottimizzata per targhe italiane
            payload = {
                'upload_url': image_url,
                'config': {
                    'region': ['it'],  # Regione Italia
                    'mode': 'fast',
                    'min_dscore': 0.5,  # Ridotta sensibilità per detection
                    'min_score': 0.5,   # Ridotta soglia OCR
                    'platel_pattern': '[A-Z]{2}[0-9]{3,4}[A-Z]{2}',  # Pattern targa italiana
                    'return_all_candidates': True  # Ritorna tutte le possibili letture
                }
            }

            # Chiamata API con retry
            for attempt in range(3):
                try:
                    response = self.session.post(
                        f'{self.base_url}/plate-reader/',
                        json=payload,
                        timeout=10
                    )
                    response.raise_for_status()
                    data = response.json()
                    break
                except requests.RequestException as e:
                    if attempt == 2:  # Ultimo tentativo
                        st.error(f"❌ Errore chiamata API PlateRecognizer: {str(e)}")
                        return None
                    time.sleep(1 * (attempt + 1))  # Backoff incrementale

            # Processa e valida risultati
            if data.get('results'):
                best_result = max(data['results'], key=lambda x: x['score'])
                
                # Validazione extra per targhe italiane
                plate = best_result['plate'].upper()
                if not self._is_valid_italian_plate(plate):
                    st.warning(f"⚠️ Targa rilevata ({plate}) non valida per formato italiano")
                    return None
                
                result = PlateResult(
                    plate=plate,
                    score=best_result['score'],
                    region=best_result.get('region', {}),
                    vehicle=best_result.get('vehicle', {}),
                    candidates=best_result.get('candidates', [])
                )
                
                # Salva in cache
                self.results_cache[image_url] = {
                    'result': result,
                    'timestamp': time.time()
                }
                
                return result
            
            return None

        except Exception as e:
            st.error(f"❌ Errore nell'elaborazione della targa: {str(e)}")
            return None

    def _is_valid_italian_plate(self, plate: str) -> bool:
        """Validazione formato targa italiana"""
        import re
        # Pattern più stringente per targhe italiane
        patterns = [
            r'^[A-Z]{2}[0-9]{3}[A-Z]{2}$',  # Standard moderno (AA000BB)
            r'^[A-Z]{2}[0-9]{4}[A-Z]$'       # Formato precedente (AA0000B)
        ]
        return any(re.match(pattern, plate) for pattern in patterns)

    def validate_api_key(self) -> bool:
        """Verifica che l'API key sia valida e configurata correttamente"""
        try:
            response = self.session.get(
                f'{self.base_url}/statistics/',
                timeout=5
            )
            if response.status_code == 200:
                st.success("✅ API Key PlateRecognizer valida e funzionante")
                return True
            else:
                st.error(f"❌ API Key non valida (Status: {response.status_code})")
                return False
        except Exception as e:
            st.error(f"❌ Errore verifica API Key: {str(e)}")
            return False

    def get_statistics(self) -> dict:
        """Recupera statistiche dell'account"""
        try:
            response = self.session.get(
                f'{self.base_url}/statistics/',
                timeout=5
            )
            if response.status_code == 200:
                stats = response.json()
                st.info(f"📊 Chiamate rimanenti: {stats.get('total_calls', 0)}")
                return stats
            return {}
        except Exception as e:
            st.error(f"❌ Errore recupero statistiche: {str(e)}")
            return {}

    def clear_cache(self):
        """Pulisce la cache dei risultati"""
        self.results_cache = {}