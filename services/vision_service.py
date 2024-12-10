from typing import List, Dict, Optional
from datetime import datetime
import cv2
import numpy as np
import requests
import streamlit as st
from services.grok_vision import GrokVision

class VisionService:
    def __init__(self, api_key: str = None):
        """
        Inizializza il servizio di visione con gestione ottimizzata delle risorse
        Args:
            api_key: Chiave API opzionale per il servizio di visione
        """
        self.api_key = api_key
        self.grok = GrokVision(api_key) if api_key else None
        self.is_available = bool(api_key)
        self._initialize_cache()
        
    def _initialize_cache(self):
        """Inizializza la cache del servizio"""
        if 'vision_cache' not in st.session_state:
            st.session_state.vision_cache = {
                'plate_detections': {},  # Cache rilevamenti targa
                'image_scores': {},      # Cache score immagini
                'last_cleanup': datetime.now()
            }

    def analyze_image_for_plate_likelihood(self, img_url: str) -> float:
        """
        Analizza un'immagine per determinare la probabilità che contenga una targa
        con cache e ottimizzazioni
        """
        # Check cache
        cache_key = f"score_{img_url}"
        if cache_key in st.session_state.vision_cache['image_scores']:
            return st.session_state.vision_cache['image_scores'][cache_key]
        
        try:
            # Scarica l'immagine con gestione errori
            try:
                response = requests.get(img_url, timeout=10)
                response.raise_for_status()
                img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
                img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            except requests.RequestException as e:
                st.error(f"❌ Errore download immagine: {str(e)}")
                return 0.0
            
            if img is None:
                return 0.0
            
            # Pre-processing immagine
            max_dimension = 800
            height, width = img.shape[:2]
            if max(height, width) > max_dimension:
                scale = max_dimension / max(height, width)
                img = cv2.resize(img, None, fx=scale, fy=scale)
            
            # Analisi multilivello
            score = 0.0
            
            # 1. Analisi composizione
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, 100, minLineLength=100, maxLineGap=10)
            
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
            composition_score = min(h_ratio / 2, 1.0)
            
            # 2. Ricerca rettangoli targhe
            height, width = img.shape[:2]
            img_area = height * width
            plate_ratio = 4.7  # Rapporto standard targa italiana
            plate_ratio_tolerance = 0.5
            
            contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            potential_plates = []
            
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w > h:  # Solo rettangoli orizzontali
                    ratio = w/h
                    if abs(ratio - plate_ratio) < plate_ratio_tolerance:
                        area = w * h
                        area_percentage = (area / img_area) * 100
                        
                        if 0.5 < area_percentage < 5:
                            roi = gray[y:y+h, x:x+w]
                            if roi.size > 0:
                                # Analisi avanzata ROI
                                contrast = np.std(roi)
                                roi_edges = cv2.Canny(roi, 50, 150)
                                edge_density = np.count_nonzero(roi_edges) / roi.size
                                
                                if contrast > 30 and edge_density > 0.1:
                                    potential_plates.append({
                                        'contrast': contrast,
                                        'edge_density': edge_density,
                                        'area_percentage': area_percentage
                                    })
            
            # Calcola score potenziali targhe
            plate_score = 0.0
            if potential_plates:
                best_plates = sorted(
                    potential_plates,
                    key=lambda x: (x['contrast'] * 0.4 + x['edge_density'] * 0.6),
                    reverse=True
                )[:3]
                
                plate_score = min(len(best_plates) / 3, 1.0)
            
            # Score finale pesato
            score = (composition_score * 0.4) + (plate_score * 0.6)
            
            # Cache result
            st.session_state.vision_cache['image_scores'][cache_key] = score
            
            return score
            
        except Exception as e:
            st.error(f"❌ Errore analisi immagine: {str(e)}")
            return 0.0

    def prioritize_images(self, images: List[str]) -> List[str]:
        """Ordina le immagini per probabilità di contenere una targa"""
        scored_images = []
        for img in images:
            score = self.analyze_image_for_plate_likelihood(img)
            scored_images.append((score, img))
            st.write(f"📊 Score immagine: {score:.2f} - {img}")
        
        # Seleziona le migliori 3 immagini
        best_images = [img for score, img in sorted(scored_images, reverse=True)[:3]]
        st.write(f"✅ Selezionate {len(best_images)} migliori immagini")
        return best_images

    def analyze_vehicle_images(self, images: List[str]) -> Dict:
        """Analizza le immagini di un veicolo con gestione errori e cache"""
        try:
            # Controlla cache immagini
            cache_key = '_'.join(images[:3])  # Usa prime 3 immagini come chiave
            if cache_key in st.session_state.vision_cache['plate_detections']:
                cached = st.session_state.vision_cache['plate_detections'][cache_key]
                # Verifica se cache è ancora valida (24h)
                if (datetime.now() - cached['timestamp']).total_seconds() < 86400:
                    st.write("🔄 Usando risultati cached")
                    return cached['results']
            
            # Prioritizza le immagini
            best_images = self.prioritize_images(images)
            
            # Se Grok è disponibile, usa quello
            if self.is_available and self.grok:
                st.write("🔍 Analisi con Grok Vision...")
                results = self.grok.analyze_batch(best_images)
                
                if results and results.get('plate'):
                    st.success(f"✅ Targa rilevata: {results['plate']} (confidenza: {results['plate_confidence']:.2%})")
                    # Cache risultati
                    st.session_state.vision_cache['plate_detections'][cache_key] = {
                        'results': results,
                        'timestamp': datetime.now()
                    }
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

    def cleanup_cache(self, max_age_hours: int = 24):
        """Pulisce la cache dei risultati vecchi"""
        try:
            current_time = datetime.now()
            
            # Pulisci cache rilevamenti
            for key in list(st.session_state.vision_cache['plate_detections'].keys()):
                entry = st.session_state.vision_cache['plate_detections'][key]
                if (current_time - entry['timestamp']).total_seconds() > max_age_hours * 3600:
                    del st.session_state.vision_cache['plate_detections'][key]
            
            # Pulisci cache score immagini
            st.session_state.vision_cache['image_scores'].clear()
            
            st.session_state.vision_cache['last_cleanup'] = current_time
            
        except Exception as e:
            st.error(f"❌ Errore pulizia cache: {str(e)}")