import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import re
from typing import Optional, Dict, List

class AutoScoutScraper:
    def __init__(self, delay_between_requests: int = 3):
        """
        Inizializza lo scraper con rate limiting
        
        Args:
            delay_between_requests: Secondi di attesa tra le richieste
        """
        self.delay = delay_between_requests
        self.last_request = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'it-IT,it;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        })

    def _wait_for_rate_limit(self):
        """Implementa rate limiting tra le richieste"""
        now = time.time()
        time_passed = now - self.last_request
        if time_passed < self.delay:
            time.sleep(self.delay - time_passed)
        self.last_request = time.time()

    def _get_with_retry(self, url: str, max_retries: int = 3) -> Optional[str]:
        """
        Esegue GET con retry in caso di errore
        
        Args:
            url: URL da scaricare
            max_retries: Numero massimo di tentativi
            
        Returns:
            HTML della pagina o None in caso di errore
        """
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
                time.sleep(2 ** attempt)  # Exponential backoff
        return None

    def extract_car_data(self, listing_element) -> Dict:
        """
        Estrae i dati di un'auto da un elemento HTML
        
        Args:
            listing_element: Elemento BeautifulSoup dell'annuncio
            
        Returns:
            Dizionario con i dati dell'auto
        """
        # Estrai titolo e prezzo
        title_elem = listing_element.select_one('[data-testid="title"]')
        price_elem = listing_element.select_one('[data-testid="price"]')
        
        # Estrai targa dal titolo o dalla descrizione
        description = listing_element.select_one('[data-testid="description"]')
        plate = self._extract_plate(title_elem.text if title_elem else '') if title_elem else None
        if not plate and description:
            plate = self._extract_plate(description.text)
            
        # Estrai URL e immagine
        link_elem = listing_element.select_one('a[href*="/auto/"]')
        img_elem = listing_element.select_one('img[src*="/auto/"]')
        
        return {
            'title': title_elem.text.strip() if title_elem else None,
            'price': self._extract_price(price_elem.text) if price_elem else None,
            'plate': plate,
            'url': link_elem['href'] if link_elem else None,
            'image_url': img_elem['src'] if img_elem else None,
            'scrape_date': datetime.now()
        }

    def _extract_plate(self, text: str) -> Optional[str]:
        """
        Estrae la targa dal testo usando pattern matching
        
        Args:
            text: Testo da cui estrarre la targa
            
        Returns:
            Targa se trovata, altrimenti None
        """
        # Pattern per targhe italiane (XX000XX, XX00000, etc.)
        patterns = [
            r'[A-Z]{2}\s*\d{3}\s*[A-Z]{2}',  # Formato XX000XX
            r'[A-Z]{2}\s*\d{5}',              # Formato XX00000
            r'[A-Z]{2}\s*\d{4}\s*[A-Z]{1,2}'  # Altri formati comuni
        ]
        
        text = text.upper()
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                # Rimuovi spazi e normalizza
                return re.sub(r'\s+', '', match.group(0))
        return None

    def _extract_price(self, text: str) -> Optional[float]:
        """
        Estrae il prezzo dal testo
        
        Args:
            text: Testo contenente il prezzo
            
        Returns:
            Prezzo come float o None se non trovato
        """
        if not text:
            return None
            
        # Rimuovi caratteri non numerici eccetto il punto
        price_text = re.sub(r'[^\d.]', '', text)
        try:
            return float(price_text)
        except ValueError:
            return None

    def get_dealer_listings(self, dealer_url: str) -> List[Dict]:
        """
        Scarica e analizza tutti gli annunci di un concessionario
        
        Args:
            dealer_url: URL del concessionario
            
        Returns:
            Lista di dizionari con i dati delle auto
        """
        html = self._get_with_retry(dealer_url)
        if not html:
            return []
            
        soup = BeautifulSoup(html, 'lxml')
        listings = []
        
        # Selettore per gli elementi degli annunci
        for listing_elem in soup.select('[data-testid="listing"]'):
            try:
                car_data = self.extract_car_data(listing_elem)
                if car_data['plate']:  # Aggiungi solo se ha trovato una targa
                    listings.append(car_data)
            except Exception as e:
                print(f"Error parsing listing: {str(e)}")
                continue
                
        return listings

    def extract_dealer_info(self, dealer_url: str) -> Dict:
        """
        Estrae informazioni sul concessionario
        
        Args:
            dealer_url: URL del concessionario
            
        Returns:
            Dizionario con i dati del concessionario
        """
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