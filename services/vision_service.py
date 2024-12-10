from typing import List, Dict, Optional
from datetime import datetime
import cv2
import numpy as np
import requests
from services.grok_vision import GrokVision
import streamlit as st

class VisionService:
    def __init__(self, api_key: str = None):
        """
        Inizializza il servizio di visione con gestione graceful della mancanza di API key
        Args:
            api_key: Chiave API opzionale per il servizio di visione
        """
        self.api_key = api_key
        self.grok = GrokVision(api_key) if api_key else None
        self.is_available = bool(api_key)
        
    def analyze_image_for_plate_likelihood(self, img_url: str) -> float:
        """
        Analizza un'immagine per determinare la probabilità che contenga una targa
        """
        try:
            # Scarica l'immagine
            response = requests.get(img_url)
            img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            if img is None:
                return 0.0
            
            # Analisi dell'immagine
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
            
            # Ricerca rettangoli simili a targhe
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
            st.error(f"❌ Errore analisi immagine: {str(e)}")
            return 0.0

    def prioritize_images(self, images: List[str]) -> List[str]:
        """
        Ordina le immagini per probabilità di contenere una targa
        """
        scored_images = []
        for img in images:
            score = self.analyze_image_for_plate_likelihood(img)
            scored_images.append((score, img))
            st.write(f"📊 Score immagine: {score:.2f} - {img}")
        
        # Prendi le migliori 3 immagini
        best_images = [img for score, img in sorted(scored_images, reverse=True)[:3]]
        st.write(f"✅ Selezionate {len(best_images)} migliori immagini")
        return best_images

    def analyze_vehicle_images(self, images: List[str]) -> Dict:
        """
        Analizza le immagini di un veicolo con fallback su analisi locale se Grok non è disponibile
        """
        try:
            # Prioritizza le immagini
            best_images = self.prioritize_images(images)
            
            # Se Grok è disponibile, usa quello
            if self.is_available and self.grok:
                st.write("🔍 Invio immagini a Grok Vision...")
                results = self.grok.analyze_batch(best_images)
                
                if results and results.get('plate'):
                    st.success(f"✅ Targa rilevata: {results['plate']} (confidenza: {results['plate_confidence']:.2%})")
                else:
                    st.warning("⚠️ Nessuna targa rilevata")
                    
                return results if results else {}
            
            # Altrimenti usa solo l'analisi locale
            st.info("ℹ️ Usando solo analisi locale delle immagini")
            return {
                'plate': None,
                'plate_confidence': 0,
                'best_images': best_images
            }
            
        except Exception as e:
            st.error(f"❌ Errore analisi veicolo: {str(e)}")
            return {}