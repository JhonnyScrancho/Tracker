import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import re
import cv2
import numpy as np
from typing import Optional, Dict, List, Set
from dataclasses import dataclass
import streamlit as st

@dataclass
class CarImage:
    url: str
    is_main: bool = False
    detected_plate: Optional[str] = None
    plate_score: float = 0.0
    plate_likelihood: float = 0.0

class AutoScoutScraper:
    def __init__(self, delay_between_requests: int = 3):
        self.delay = delay_between_requests
        self.last_request = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'it-IT,it;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        })
        self.processed_ids: Set[str] = set()

    def _wait_for_rate_limit(self):
        now = time.time()
        time_passed = now - self.last_request
        if time_passed < self.delay:
            time.sleep(self.delay - time_passed)
        self.last_request = time.time()

    def _get_with_retry(self, url: str, max_retries: int = 3) -> Optional[str]:
        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()
                response = self.session.get(url)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    print(f"Error fetching {url}: {str(e)}")
                    return None
                time.sleep(2 ** attempt)
        return None

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
            
            # 1. Verifica se l'immagine è frontale/posteriore del veicolo
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
            
            # 2. Cerca rettangoli con proporzioni simili a targhe italiane (520x110 mm)
            plate_ratio = 4.7
            plate_ratio_tolerance = 0.5
            
            contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            potential_plates = 0
            
            # Dimensioni immagine per calcolo percentuali
            height, width = img.shape[:2]
            img_area = height * width
            
            for cnt in contours:
                x, y, w, h = cv2.boundingRect(cnt)
                if w > h:  # Solo rettangoli orizzontali
                    ratio = w/h
                    if abs(ratio - plate_ratio) < plate_ratio_tolerance:
                        area = w * h
                        area_percentage = (area / img_area) * 100
                        
                        # Una targa dovrebbe occupare tra lo 0.5% e il 5% dell'immagine
                        if 0.5 < area_percentage < 5:
                            potential_plates += 1
                            
                            # Analisi aggiuntiva della regione
                            roi = gray[y:y+h, x:x+w]
                            if roi.size > 0:
                                # Contrasto nella regione
                                contrast = np.std(roi)
                                # Presenza di testo (molti bordi)
                                roi_edges = cv2.Canny(roi, 50, 150)
                                edge_density = np.count_nonzero(roi_edges) / roi.size
                                
                                if contrast > 30 and edge_density > 0.1:
                                    potential_plates += 1
            
            # 3. Calcola score finale pesato
            composition_score = min(h_ratio / 2, 1.0)  # Max 1.0
            plate_score = min(potential_plates / 3, 1.0)  # Max 1.0
            
            final_score = (composition_score * 0.6) + (plate_score * 0.4)
            
            return min(final_score, 1.0)
            
        except Exception as e:
            print(f"Errore nell'analisi dell'immagine {img_url}: {str(e)}")
            return 0.0

    def extract_car_data(self, listing_element, existing_ids: Set[str] = None) -> Dict:
        """
        Estrae i dati dell'auto, controlla se l'ID esiste già
        
        Args:
            listing_element: Elemento BS4 dell'annuncio
            existing_ids: Set di ID già presenti nel database
        """
        listing_id = listing_element.get('id', '')
        title_elem = listing_element.select_one('[data-testid="title"]')
        price_elem = listing_element.select_one('[data-testid="price"]')
        img_elem = listing_element.select_one('img[src*="/auto/"]')
        link_elem = listing_element.select_one('a[href*="/auto/"]')
        
        is_existing = existing_ids and listing_id in existing_ids
        
        car_data = {
            'id': listing_id,
            'title': title_elem.text.strip() if title_elem else None,
            'price': self._extract_price(price_elem.text) if price_elem else None,
            'url': link_elem['href'] if link_elem else None,
            'image_url': img_elem['src'] if img_elem else None,
            'scrape_date': datetime.now(),
            'is_existing': is_existing
        }
        
        if not is_existing:
            car_data['plate'] = self._extract_plate(title_elem.text if title_elem else '')
            
        return car_data

    def _extract_plate(self, text):
        if not text:
            return None
        
        patterns = [
            r'[A-Z]{2}\s*\d{3}\s*[A-Z]{2}',  # Formato moderno (AA000BB)
            r'[A-Z]{2}\s*\d{4}\s*[A-Z]{1,2}'  # Formato precedente (AA0000B)
        ]
        
        text = text.upper()
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return re.sub(r'\s+', '', match.group(0))
        return None

    def _extract_price(self, text: str) -> Optional[float]:
        if not text:
            return None
        price_text = re.sub(r'[^\d.]', '', text)
        try:
            return float(price_text)
        except ValueError:
            return None

    def get_dealer_listings(self, dealer_url: str, existing_ids: Set[str] = None) -> List[Dict]:
        """
        Scarica e analizza gli annunci, ottimizzando per annunci già esistenti
        """
        html = self._get_with_retry(dealer_url)
        if not html:
            return []
            
        soup = BeautifulSoup(html, 'lxml')
        listings = []
        
        for listing_elem in soup.select('[data-testid="listing"]'):
            try:
                car_data = self.extract_car_data(listing_elem, existing_ids)
                
                if not car_data.get('is_existing'):
                    if car_data['url']:
                        images = self.get_listing_images(car_data['url'])
                        if images:
                            car_data['image_urls'] = [img['url'] for img in images]
                            car_data['plate_likelihood_scores'] = [img['plate_likelihood'] for img in images]
                            
                    listings.append(car_data)
                else:
                    print(f"Annuncio {car_data['id']} già esistente, aggiorno solo i dati base")
                    listings.append({
                        'id': car_data['id'],
                        'title': car_data['title'],
                        'price': car_data['price'],
                        'scrape_date': car_data['scrape_date'],
                        'is_update': True
                    })
                    
            except Exception as e:
                print(f"Error parsing listing: {str(e)}")
                continue
                
        return listings

    def get_listing_images(self, listing_url: str) -> List[Dict[str, float]]:
        """
        Recupera e analizza le prime 10 immagini dell'annuncio, ordinandole per probabilità di contenere una targa.
        """
        try:
            st.write(f"📷 Recupero immagini da {listing_url}")
            
            response = self._get_with_retry(listing_url)
            if not response:
                return []

            soup = BeautifulSoup(response, 'lxml')
            images = []
            MAX_IMAGES = 10  # Limitiamo a 10 immagini

            # Lista di selettori in ordine di specificità
            selectors = [
                '.image-gallery-slides picture.ImageWithBadge_picture__XJG24 img',
                '.image-gallery-slides img',
                '.Gallery_gallery__ppyDW img',
                'img[src*="/auto/"]'
            ]

            # Raccoglie le prime 10 immagini uniche
            for selector in selectors:
                if len(images) >= MAX_IMAGES:
                    break
                    
                elements = soup.select(selector)
                
                for img in elements:
                    if len(images) >= MAX_IMAGES:
                        break
                        
                    if img.get('src'):
                        img_url = img['src']
                        # Normalizza URL per la massima qualità
                        base_url = re.sub(r'/\d+x\d+\.(webp|jpg)', '', img_url)
                        if not base_url.endswith('.jpg'):
                            base_url += '.jpg'
                            
                        if base_url not in [img['url'] for img in images]:
                            # Analizza la probabilità di contenere una targa
                            plate_likelihood = self._analyze_image_for_plate_likelihood(base_url)
                            images.append({
                                'url': base_url,
                                'plate_likelihood': plate_likelihood
                            })
                            st.write(f"✅ Trovata immagine {len(images)}/10 con score {plate_likelihood:.2f}: {base_url}")

            # Ordina per probabilità e prendi le migliori 3
            best_images = sorted(images, key=lambda x: x['plate_likelihood'], reverse=True)[:3]
            
            st.write("📊 Migliori immagini selezionate:")
            for img in best_images:
                st.write(f"Score {img['plate_likelihood']:.2f}: {img['url']}")

            return best_images

        except Exception as e:
            st.write(f"❌ Errore nel recupero immagini: {str(e)}")
            return []

    def extract_dealer_info(self, dealer_url: str) -> Dict:
        """Estrae informazioni del concessionario"""
        html = self._get_with_retry(dealer_url)
        if not html:
            return {}
            
        soup = BeautifulSoup(html, 'lxml')
        
        name_elem = soup.select_one('[data-testid="dealer-name"]')
        address_elem = soup.select_one('[data-testid="dealer-address"]')
        
        return {
            'name': name_elem.text.strip() if name_elem else None,
            'address': address_elem.text.strip() if address_elem else None,
            'url': dealer_url,
            'scrape_date': datetime.now()
        }