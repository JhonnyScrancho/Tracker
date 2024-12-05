# grok_vision.py
import base64
import requests
from typing import List, Dict, Optional
from datetime import datetime
import streamlit as st
from openai import OpenAI
import re
import cv2
import numpy as np

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
        
    def _analyze_image_for_plate_likelihood(self, img_url: str) -> float:
        """
        Analizza un'immagine per determinare la probabilità che contenga una targa visibile.
        Ritorna uno score da 0 a 1.
        """
        try:
            # Scarica l'immagine
            response = requests.get(img_url)
            img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if img is None:
                return 0.0
            
            # Converti in scala di grigi
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
            
            # Calcolo linee orizzontali/verticali
            horizontal_lines = 0
            vertical_lines = 0
            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    angle = abs(np.arctan2(y2-y1, x2-x1) * 180 / np.pi)
                    if angle < 30 or angle > 150:
                        horizontal_lines += 1
                    if 60 < angle < 120:
                        vertical_lines += 1
            
            h_ratio = horizontal_lines / (vertical_lines + 1)
            
            # Cerca rettangoli con proporzioni simili a targhe italiane
            height, width = img.shape[:2]
            img_area = height * width
            plate_ratio = 4.7
            plate_ratio_tolerance = 0.5
            
            contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            potential_plates = 0
            
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w > h:
                    ratio = w/h
                    if abs(ratio - plate_ratio) < plate_ratio_tolerance:
                        area = w * h
                        area_percentage = (area / img_area) * 100
                        if 0.5 < area_percentage < 5:
                            roi = gray[y:y+h, x:x+w]
                            if roi.size > 0:
                                contrast = np.std(roi)
                                roi_edges = cv2.Canny(roi, 50, 150)
                                edge_density = np.count_nonzero(roi_edges) / roi.size
                                if contrast > 30 and edge_density > 0.1:
                                    potential_plates += 1
            
            # Calcolo score finale
            composition_score = min(h_ratio / 2, 1.0)
            plate_score = min(potential_plates / 3, 1.0)
            final_score = (composition_score * 0.6) + (plate_score * 0.4)
            
            return min(final_score, 1.0)
            
        except Exception as e:
            st.error(f"❌ Errore nell'analisi dell'immagine {img_url}: {str(e)}")
            return 0.0

    def _encode_image_url(self, image_url: str) -> Optional[str]:
        """
        Scarica un'immagine da URL e la codifica in base64
        """
        try:
            response = requests.get(image_url)
            response.raise_for_status()
            encoded_string = base64.b64encode(response.content).decode("utf-8")
            return f"data:image/jpeg;base64,{encoded_string}"
        except Exception as e:
            st.error(f"❌ Errore nel download/encoding dell'immagine: {str(e)}")
            return None

    def analyze_batch(self, images: List[str]) -> Optional[Dict]:
        """
        Analizza un batch di immagini ottimizzando per costi
        """
        try:
            scored_images = []
            for idx, image_url in enumerate(images):
                likelihood = self._analyze_image_for_plate_likelihood(image_url)
                scored_images.append((likelihood, idx, image_url))
            
            # Ordina per probabilità decrescente
            scored_images.sort(reverse=True)
            
            # Prova con la migliore immagine
            for likelihood, idx, image_url in scored_images:
                st.write(f"🔍 Analisi immagine {idx+1} (score: {likelihood:.2f})...")
                
                # Codifica l'immagine in base64
                base64_image = self._encode_image_url(image_url)
                if not base64_image:
                    continue

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

                # Invia la richiesta
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.01,
                )

                # Analizza la risposta
                response_text = response.choices[0].message.content.upper()
                
                # Estrai targa
                plate = None
                confidence = 0.0
                
                patterns = [
                    r'[A-Z]{2}\s*\d{3}\s*[A-Z]{2}',  # Formato moderno
                    r'[A-Z]{2}\s*\d{4}\s*[A-Z]'      # Formato precedente
                ]
                
                for pattern in patterns:
                    matches = re.finditer(pattern, response_text)
                    for match in matches:
                        plate_candidate = re.sub(r'\s+', '', match.group(0))
                        # Verifica formato targa
                        if re.match(r'^[A-Z]{2}\d{3}[A-Z]{2}$|^[A-Z]{2}\d{4}[A-Z]$', plate_candidate):
                            plate = plate_candidate
                            confidence = 0.9
                            if "NON SONO SICURO" in response_text or "POTREBBE ESSERE" in response_text:
                                confidence *= 0.7
                            if "TARGA" in response_text and "VISIBILE" in response_text:
                                confidence *= 1.2
                            confidence = min(confidence, 1.0)
                            break
                
                # Se troviamo una targa con alta confidenza, ci fermiamo
                if plate and confidence > 0.8:
                    vehicle_type = None
                    if "TIPO DI VEICOLO:" in response_text:
                        vehicle_type = response_text.split("TIPO DI VEICOLO:")[1].split("\n")[0].strip()
                    
                    result = {
                        'plate': plate,
                        'plate_confidence': confidence,
                        'vehicle_type': vehicle_type,
                        'best_image_index': idx
                    }
                    
                    st.success(f"✅ Targa rilevata: {plate} (confidenza: {confidence:.2%})")
                    return result
                
                st.warning("⚠️ Targa non rilevata con sufficiente confidenza in questa immagine")
            
            st.warning("⚠️ Nessuna targa rilevata con sufficiente confidenza in tutte le immagini")
            return {
                'plate': None,
                'plate_confidence': 0,
                'vehicle_type': None,
                'best_image_index': None
            }

        except Exception as e:
            st.error(f"❌ Errore Grok Vision: {str(e)}")
            return None