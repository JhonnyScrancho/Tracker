import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import re
from typing import Optional, Dict, List, Set
from dataclasses import dataclass

@dataclass
class CarImage:
    url: str
    is_main: bool = False
    detected_plate: Optional[str] = None
    plate_score: float = 0.0

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
        # Cache per gli ID già processati
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
        
        # Flag per indicare se è un annuncio già esistente
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
        
        # Estrai la targa dal titolo solo se è un nuovo annuncio
        if not is_existing:
            car_data['plate'] = self._extract_plate(title_elem.text if title_elem else '')
            
        return car_data

    def _extract_plate(self, text):
        if not text:
            return None
        
        patterns = [
            r'[A-Z]{2}\s*\d{3}\s*[A-Z]{2}',
            r'[A-Z]{2}\s*\d{5}',
            r'[A-Z]{2}\s*\d{4}\s*[A-Z]{1,2}'
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
        
        Args:
            dealer_url: URL del concessionario
            existing_ids: Set di ID annunci già presenti nel database
        """
        html = self._get_with_retry(dealer_url)
        if not html:
            return []
            
        soup = BeautifulSoup(html, 'lxml')
        listings = []
        
        for listing_elem in soup.select('[data-testid="listing"]'):
            try:
                car_data = self.extract_car_data(listing_elem, existing_ids)
                
                # Se l'annuncio è nuovo, recupera tutte le informazioni
                if not car_data.get('is_existing'):
                    if car_data['url']:
                        images = self.get_listing_images(car_data['url'])
                        if images:
                            car_data['image_urls'] = [img.url for img in images]
                            
                    listings.append(car_data)
                else:
                    # Per annunci esistenti, aggiorna solo prezzo e titolo
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

    def get_listing_images(self, listing_url: str, min_images: int = 3) -> List[CarImage]:
        try:
            response = self._get_with_retry(listing_url)
            if not response:
                return []

            soup = BeautifulSoup(response, 'lxml')
            images = []

            # Gallery principale
            gallery_slides = soup.select('.image-gallery-slides picture.ImageWithBadge_picture__XJG24 img')
            for idx, img in enumerate(gallery_slides):
                if img.get('src'):
                    img_url = self._normalize_image_url(img['src'])
                    if img_url not in [i.url for i in images]:
                        images.append(CarImage(url=img_url, is_main=(idx == 0)))

            # Miniature se necessario
            if len(images) < min_images:
                thumbnails = soup.select('.image-gallery-thumbnails img')
                for img in thumbnails:
                    if img.get('src'):
                        img_url = self._normalize_image_url(img['src'])
                        if img_url not in [i.url for i in images]:
                            images.append(CarImage(url=img_url))

            # Altre immagini se ancora non bastano
            if len(images) < min_images:
                other_images = soup.select('img[src*="auto"]')
                for img in other_images:
                    if img.get('src'):
                        img_url = self._normalize_image_url(img['src'])
                        if img_url not in [i.url for i in images]:
                            images.append(CarImage(url=img_url))

            return images[:min_images]

        except Exception as e:
            print(f"Error getting listing images: {str(e)}")
            return []

    def _normalize_image_url(self, url: str) -> str:
        base_url = re.sub(r'/\d+x\d+\.(webp|jpg)', '', url)
        if not base_url.endswith('.jpg'):
            base_url += '.jpg'
        return base_url

    def extract_dealer_info(self, dealer_url: str) -> Dict:
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