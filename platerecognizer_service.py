import streamlit as st
import requests
import time
from dataclasses import dataclass
from typing import Optional, List
import json

@dataclass
class PlateResult:
    plate: str
    score: float
    box: dict
    region: dict
    vehicle: dict

class PlateRecognizerService:
    def __init__(self):
        """Inizializza il servizio PlateRecognizer usando le credenziali da Streamlit secrets"""
        self.api_key = st.secrets["platerecognizer"]["api_key"]
        self.base_url = "https://api.platerecognizer.com/v1"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {self.api_key}',
            'Content-Type': 'application/json'
        })
        # Cache per risultati
        self.results_cache = {}

    def detect_from_url(self, image_url: str, regions: List[str] = None, cache_ttl: int = 3600) -> Optional[PlateResult]:
        """
        Rileva targa da URL immagine
        
        Args:
            image_url: URL dell'immagine
            regions: Lista di regioni da cercare (es. ['it'] per Italia)
            cache_ttl: Tempo di validità cache in secondi
            
        Returns:
            PlateResult o None se non trovata
        """
        try:
            # Check cache
            if image_url in self.results_cache:
                cached = self.results_cache[image_url]
                age = time.time() - cached['timestamp']
                if age < cache_ttl:
                    return cached['result']

            # Prepara payload
            payload = {
                'upload_url': image_url,
                'config': {
                    'region': regions or ['it'],  # Default a Italia
                    'mode': 'fast',
                    'min_dscore': 0.7,  # Soglia minima detection
                    'min_score': 0.7   # Soglia minima OCR
                }
            }

            # Chiamata API
            with st.spinner('🔍 Analisi targa in corso...'):
                response = self.session.post(
                    f'{self.base_url}/plate-reader/',
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

            # Processa risultati
            if data.get('results'):
                # Prendi il risultato con score più alto
                best_result = max(data['results'], key=lambda x: x['score'])
                
                result = PlateResult(
                    plate=best_result['plate'],
                    score=best_result['score'],
                    box=best_result['box'],
                    region=best_result.get('region', {}),
                    vehicle=best_result.get('vehicle', {})
                )
                
                # Salva in cache
                self.results_cache[image_url] = {
                    'result': result,
                    'timestamp': time.time()
                }
                
                return result
            
            return None

        except Exception as e:
            st.error(f"❌ Errore PlateRecognizer API: {str(e)}")
            return None

    def validate_api_key(self) -> bool:
        """Verifica che l'API key sia valida"""
        try:
            response = self.session.get(f'{self.base_url}/statistics/')
            return response.status_code == 200
        except:
            return False

    def get_statistics(self) -> dict:
        """Recupera statistiche dell'account"""
        try:
            response = self.session.get(f'{self.base_url}/statistics/')
            if response.status_code == 200:
                return response.json()
            return {}
        except:
            return {}

    def clear_cache(self):
        """Pulisce la cache dei risultati"""
        self.results_cache = {}