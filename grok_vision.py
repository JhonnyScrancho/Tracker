import base64
import requests
from typing import List, Dict, Optional
from datetime import datetime
import streamlit as st
from openai import OpenAI
import re

class GrokVision:
    def __init__(self, api_key: str):
        """
        Inizializza il client Grok Vision
        Args:
            api_key: Chiave API Grok
        """
        self.api_key = api_key
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1"
        )
        self.model = "grok-vision-beta"
        
    def _encode_image_url(self, image_url: str) -> Optional[str]:
        """
        Scarica un'immagine da URL e la codifica in base64
        Args:
            image_url: URL dell'immagine da scaricare
        Returns:
            Stringa base64 dell'immagine o None in caso di errore
        """
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            encoded_string = base64.b64encode(response.content).decode("utf-8")
            return f"data:image/jpeg;base64,{encoded_string}"
        except Exception as e:
            st.error(f"❌ Errore nel download/encoding dell'immagine: {str(e)}")
            return None

    def _is_valid_italian_plate(self, text: str) -> bool:
        """Valida il formato targa italiana"""
        patterns = [
            r'^[A-Z]{2}[0-9]{3}[A-Z]{2}$',  # Standard moderno (AA000BB)
            r'^[A-Z]{2}[0-9]{4}[A-Z]$'       # Formato precedente (AA0000B)
        ]
        text = text.upper().replace(' ', '')
        return any(re.match(pattern, text) for pattern in patterns)

    def _extract_plate_from_response(self, response_text: str) -> tuple[Optional[str], float]:
        """
        Estrae la targa e la confidenza dalla risposta del modello
        Args:
            response_text: Testo della risposta da analizzare
        Returns:
            Tupla (targa, confidenza) o (None, 0) se non trovata
        """
        # Cerca qualsiasi sequenza che assomigli a una targa
        text = response_text.upper()
        patterns = [
            r'[A-Z]{2}\s*\d{3}\s*[A-Z]{2}',  # Formato moderno
            r'[A-Z]{2}\s*\d{4}\s*[A-Z]'      # Formato precedente
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                plate = re.sub(r'\s+', '', match.group(0))
                if self._is_valid_italian_plate(plate):
                    # Calcola un punteggio di confidenza basato sul contesto
                    confidence = 0.9  # Alta confidenza di default per match esatti
                    if "NON SONO SICURO" in text or "POTREBBE ESSERE" in text:
                        confidence *= 0.7
                    if "TARGA" in text and "VISIBILE" in text:
                        confidence *= 1.2
                    return plate, min(confidence, 1.0)
                    
        return None, 0.0

    def analyze_batch(self, images: List[str]) -> Optional[Dict]:
        """
        Analizza un batch di immagini con Grok Vision
        Args:
            images: Lista di URL immagini
        Returns:
            Dizionario con i risultati dell'analisi
        """
        try:
            best_plate = None
            best_confidence = 0
            best_image_index = None
            vehicle_type = None

            for idx, image_url in enumerate(images):
                st.write(f"🔍 Analisi immagine {idx+1}/{len(images)}...")
                
                # Codifica l'immagine in base64
                base64_image = self._encode_image_url(image_url)
                if not base64_image:
                    continue

                # Prepara il messaggio per l'API
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": base64_image,
                                    "detail": "high",
                                },
                            },
                            {
                                "type": "text",
                                "text": "Analizza questa immagine di un veicolo. Se vedi una targa italiana, scrivila. "
                                       "Indica anche il tipo di veicolo (es. auto, moto, furgone).",
                            },
                        ],
                    }
                ]

                # Invia la richiesta all'API
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.01,
                )

                # Analizza la risposta
                response_text = response.choices[0].message.content
                plate, confidence = self._extract_plate_from_response(response_text)
                
                # Aggiorna il migliore risultato se necessario
                if plate and confidence > best_confidence:
                    best_plate = plate
                    best_confidence = confidence
                    best_image_index = idx
                    
                # Estrai il tipo di veicolo se non ancora trovato
                if not vehicle_type and "TIPO DI VEICOLO:" in response_text.upper():
                    vehicle_type = response_text.split("TIPO DI VEICOLO:")[1].split("\n")[0].strip()

            # Prepara il risultato finale
            result = {
                'plate': best_plate,
                'plate_confidence': best_confidence,
                'vehicle_type': vehicle_type,
                'best_image_index': best_image_index
            }

            if best_plate:
                st.success(f"✅ Targa rilevata: {best_plate} (confidenza: {best_confidence:.2%})")
            else:
                st.warning("⚠️ Nessuna targa rilevata nelle immagini")

            return result

        except Exception as e:
            st.error(f"❌ Errore Grok Vision: {str(e)}")
            return None