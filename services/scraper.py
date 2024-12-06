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
        """Esegue una richiesta GET con retry e gestione errori migliorata"""
        for attempt in range(max_retries):
            try:
                self._wait_rate_limit()
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    st.error(f"❌ Errore nella richiesta HTTP a {url}: {str(e)}")
                    return None
                time.sleep(2 ** attempt)  # Backoff esponenziale
        return None

    def _wait_rate_limit(self):
        """Implementa rate limiting tra le richieste"""
        now = time.time()
        time_passed = now - self.last_request
        if time_passed < self.delay:
            time.sleep(self.delay - time_passed)
        self.last_request = time.time()

    def _analyze_image_for_plate_likelihood(self, img_url: str) -> float:
        """Analizza un'immagine per determinare la probabilità che contenga una targa"""
        try:
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
            
            # Calcola score finale pesato
            composition_score = min(h_ratio / 2, 1.0)  # Max 1.0
            plate_score = min(potential_plates / 3, 1.0)  # Max 1.0
            final_score = (composition_score * 0.6) + (plate_score * 0.4)
            
            return min(final_score, 1.0)
            
        except Exception as e:
            st.error(f"Errore nell'analisi dell'immagine {img_url}: {str(e)}")
            return 0.0

    def extract_car_data(self, listing_element, existing_ids: Set[str] = None) -> Dict:
        """Estrae i dati dell'auto con verifica anomalie"""
        listing_id = listing_element.get('id', '')
        title_elem = listing_element.select_one('[data-testid="title"]')
        price_elem = listing_element.select_one('[data-testid="price"]')
        img_elem = listing_element.select_one('img[src*="/auto/"]')
        link_elem = listing_element.select_one('a[href*="/auto/"]')
        
        is_existing = existing_ids and listing_id in existing_ids
        
        # Estrazione prezzi con verifica anomalie
        price_data = self._extract_price_data(price_elem)
        
        car_data = {
            'id': listing_id,
            'title': title_elem.text.strip() if title_elem else None,
            'url': link_elem['href'] if link_elem else None,
            'image_url': img_elem['src'] if img_elem else None,
            'scrape_date': datetime.now(),
            'is_existing': is_existing,
            'original_price': price_data.get('original_price'),
            'discounted_price': price_data.get('discounted_price'),
            'has_discount': price_data.get('has_discount', False),
            'discount_percentage': price_data.get('discount_percentage')
        }
        
        # Estrai dettagli veicolo
        details = self._extract_vehicle_details(listing_element)
        car_data.update(details)
        
        # Se nuovo annuncio, estrai targa dal titolo
        if not is_existing:
            car_data['plate'] = self._extract_plate(title_elem.text if title_elem else '')
            
        return car_data

    def _extract_vehicle_details(self, listing_element) -> Dict:
        """Estrae dettagli veicolo con validazione"""
        details = {
            'mileage': None,
            'registration': None,
            'power': None,
            'fuel': None,
            'transmission': None,
            'consumption': None,
            'features': []  # Nuovo: lista caratteristiche
        }

        try:
            details_items = listing_element.select('.dp-listing-item__detail-item')
            features_items = listing_element.select('.dp-listing-item__feature-item')
            
            # Estrai dettagli principali
            for item in details_items:
                text = item.text.strip()
                
                if text.endswith('km'):
                    try:
                        km_value = ''.join(c for c in text if c.isdigit())
                        details['mileage'] = int(km_value)
                    except ValueError:
                        st.write(f"⚠️ Non riesco a convertire il chilometraggio: {text}")
                
                elif '/' in text and len(text) <= 8:
                    details['registration'] = text
                
                elif 'CV' in text or 'KW' in text:
                    details['power'] = text
                
                elif any(fuel in text.lower() for fuel in ['benzina', 'diesel', 'elettrica', 'ibrida', 'gpl', 'metano']):
                    details['fuel'] = text
                
                elif any(trans in text.lower() for trans in ['manuale', 'automatico']):
                    details['transmission'] = text
                
                elif 'l/100' in text or 'kwh/100' in text:
                    details['consumption'] = text
            
            # Estrai caratteristiche aggiuntive
            for item in features_items:
                details['features'].append(item.text.strip())
                
        except Exception as e:
            st.error(f"Errore estrazione dettagli: {str(e)}")
            
        return details
    
    def _extract_price(self, text: str) -> Optional[float]:
        """Estrae e valida un prezzo dal testo"""
        if not text:
            return None
            
        try:
            # Rimuove caratteri non numerici mantenendo il punto decimale
            price_text = text.replace('€', '').replace('.', '').replace(',', '.')
            price_text = re.sub(r'[^\d.]', '', price_text)
            
            price = float(price_text)
            
            # Validazione base (prezzo ragionevole per un'auto)
            if price < 100 or price > 10000000:
                st.warning(f"⚠️ Prezzo anomalo rilevato: {price}€")
                return None
                
            return price
            
        except ValueError:
            return None
    
    def validate_image_url(self, url: str) -> bool:
        """Verifica che l'URL dell'immagine sia valido e accessibile"""
        try:
            response = requests.head(url, timeout=5)
            return (response.status_code == 200 and 
                   'image' in response.headers.get('content-type', ''))
        except Exception:
            return False
    
    def _extract_plate(self, text: str) -> Optional[str]:
        """Estrae e valida la targa"""
        if not text:
            return None
        
        patterns = [
            r'[A-Z]{2}\s*\d{3}\s*[A-Z]{2}',  # Formato moderno
            r'[A-Z]{2}\s*\d{4}\s*[A-Z]{1,2}'  # Formato precedente
        ]
        
        text = text.upper()
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                plate = re.sub(r'\s+', '', match.group(0))
                # Valida formato
                if re.match(r'^[A-Z]{2}\d{3}[A-Z]{2}$|^[A-Z]{2}\d{4}[A-Z]$', plate):
                    return plate
        return None

    def get_dealer_listings(self, dealer_url: str, existing_ids: Set[str] = None) -> List[Dict]:
        """Scarica e analizza gli annunci, ottimizzando per annunci già esistenti"""
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
                        # Analizza immagini e targa
                        images = self.get_listing_images(car_data['url'])
                        if images:
                            # Ordina immagini per probabilità targa
                            scored_images = []
                            for img_url in images:
                                score = self._analyze_image_for_plate_likelihood(img_url)
                                scored_images.append((score, img_url))
                            
                            # Prendi le migliori 3 immagini
                            best_images = [img for score, img in sorted(scored_images, reverse=True)[:3]]
                            car_data['image_urls'] = best_images
                            car_data['plate_likelihood_scores'] = [score for score, _ in sorted(scored_images, reverse=True)[:3]]
                            
                    listings.append(car_data)
                else:
                    st.write(f"Annuncio {car_data['id']} già esistente, aggiorno solo i dati base")
                    listings.append({
                        'id': car_data['id'],
                        'title': car_data['title'],
                        'price': car_data['price'],
                        'scrape_date': car_data['scrape_date'],
                        'is_update': True
                    })
                    
            except Exception as e:
                st.error(f"Error parsing listing: {str(e)}")
                continue
                
        return listings

    def get_listing_images(self, listing_url: str) -> list:
        """Recupera e analizza le immagini dell'annuncio"""
        try:
            st.write(f"📍 URL: {listing_url}")
            
            response = self._get_with_retry(listing_url)
            if not response:
                return []

            soup = BeautifulSoup(response, 'lxml')
            images = []
            MAX_IMAGES = 10
            found_urls = set()

            # Lista di selettori in ordine di specificità
            selectors = [
                '.image-gallery-slides picture.ImageWithBadge_picture__XJG24 img',
                '.image-gallery-slides img',
                '.Gallery_gallery__ppyDW img',
                'img[src*="/auto/"]'
            ]

            st.write(f"📸 Raccolta prime {MAX_IMAGES} immagini disponibili...")
            
            for selector in selectors:
                if len(found_urls) >= MAX_IMAGES:
                    break
                    
                elements = soup.select(selector)
                
                for img in elements:
                    if len(found_urls) >= MAX_IMAGES:
                        break
                        
                    if img.get('src'):
                        img_url = img['src']
                        # Normalizza URL
                        base_url = re.sub(r'/\d+x\d+\.(webp|jpg)', '', img_url)
                        if not base_url.endswith('.jpg'):
                            base_url += '.jpg'
                                
                        if base_url not in found_urls:
                            found_urls.add(base_url)
                            # Analizza probabilità targa
                            st.write(f"Analisi immagine {len(found_urls)}/{MAX_IMAGES}...")
                            images.append(base_url)

            st.write(f"✅ Recuperate {len(images)} immagini")
            return images

        except Exception as e:
            st.error(f"❌ Errore nel recupero immagini: {str(e)}")
            return []

    def extract_dealer_info(self, dealer_url: str) -> Dict:
        """Estrae informazioni dettagliate del concessionario"""
        html = self._get_with_retry(dealer_url)
        if not html:
            return {}
            
        soup = BeautifulSoup(html, 'lxml')
        
        info = {
            'name': None,
            'address': None,
            'phone': None,
            'website': None,
            'ratings': None,
            'opening_hours': None,
            'url': dealer_url,
            'scrape_date': datetime.now()
        }
        
        try:
            # Info di base
            name_elem = soup.select_one('[data-testid="dealer-name"]')
            address_elem = soup.select_one('[data-testid="dealer-address"]')
            
            info['name'] = name_elem.text.strip() if name_elem else None
            info['address'] = address_elem.text.strip() if address_elem else None
            
            # Info aggiuntive
            contact_section = soup.select_one('.dealer-contact-section')
            if contact_section:
                phone_elem = contact_section.select_one('.phone-number')
                website_elem = contact_section.select_one('.website-link')
                
                info['phone'] = phone_elem.text.strip() if phone_elem else None
                info['website'] = website_elem['href'] if website_elem else None
            
            # Rating e recensioni
            rating_section = soup.select_one('.dealer-rating-section')
            if rating_section:
                rating_elem = rating_section.select_one('.rating-value')
                reviews_elem = rating_section.select_one('.reviews-count')
                
                info['ratings'] = {
                    'value': float(rating_elem.text) if rating_elem else None,
                    'count': int(reviews_elem.text.split()[0]) if reviews_elem else None
                }
            
            # Orari apertura
            hours_section = soup.select_one('.opening-hours-section')
            if hours_section:
                hours_list = hours_section.select('.opening-hours-item')
                info['opening_hours'] = {}
                
                for item in hours_list:
                    day = item.select_one('.day').text.strip()
                    hours = item.select_one('.hours').text.strip()
                    info['opening_hours'][day] = hours
                    
        except Exception as e:
            st.error(f"Errore nell'estrazione info dealer: {str(e)}")
            
        return info
    
    def analyze_dealer_inventory(self, dealer_url: str) -> Dict:
        """Analizza l'inventario completo di un dealer"""
        listings = self.get_dealer_listings(dealer_url)
        
        analysis = {
            'total_listings': len(listings),
            'price_range': {
                'min': None,
                'max': None,
                'avg': None
            },
            'brands': {},
            'fuel_types': {},
            'avg_mileage': None,
            'price_segments': {
                'budget': 0,      # < 15000
                'medium': 0,      # 15000-30000
                'premium': 0      # > 30000
            }
        }
        
        if not listings:
            return analysis
            
        # Analisi prezzi
        prices = [l['original_price'] for l in listings if l.get('original_price')]
        if prices:
            analysis['price_range']['min'] = min(prices)
            analysis['price_range']['max'] = max(prices)
            analysis['price_range']['avg'] = sum(prices) / len(prices)
            
            # Segmenti prezzo
            analysis['price_segments']['budget'] = len([p for p in prices if p < 15000])
            analysis['price_segments']['medium'] = len([p for p in prices if 15000 <= p <= 30000])
            analysis['price_segments']['premium'] = len([p for p in prices if p > 30000])
        
        # Analisi marche
        for listing in listings:
            if listing.get('title'):
                brand = listing['title'].split()[0].upper()
                analysis['brands'][brand] = analysis['brands'].get(brand, 0) + 1
        
        # Analisi carburante
        for listing in listings:
            if listing.get('fuel'):
                fuel = listing['fuel']
                analysis['fuel_types'][fuel] = analysis['fuel_types'].get(fuel, 0) + 1
        
        # Chilometraggio medio
        mileages = [l['mileage'] for l in listings if l.get('mileage')]
        if mileages:
            analysis['avg_mileage'] = sum(mileages) / len(mileages)
        
        return analysis

    def compare_with_competitors(self, dealer_url: str, model: str) -> List[Dict]:
        """Cerca annunci simili di altri concessionari per confronto"""
        # Implementazione base - da espandere in futuro
        similar_listings = []
        
        return similar_listings