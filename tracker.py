from firebase_admin import credentials, initialize_app, firestore
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import streamlit as st
import pandas as pd
import firebase_admin
import re

class AutoTracker:
    def __init__(self):
        """Initialize Firebase connection with proper error handling"""
        try:
            firebase_admin.get_app()
        except ValueError:
            cred = credentials.Certificate(st.secrets["firebase"])
            initialize_app(cred)
        self.db = firestore.client()

    def scrape_dealer(self, dealer_url: str):
        """Scrape dealer page with detailed logging"""
        if not dealer_url:
            st.warning("Inserisci l'URL del concessionario")
            return []

        st.info("Inizio scraping della pagina...")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9'
        }
        
        try:
            st.write("Scaricando la pagina...")
            response = requests.get(dealer_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            total_results = soup.select_one(".dp-list__title__count")
            if total_results:
                st.write(f"Totale annunci trovati: {total_results.text}")
            
            listings = []
            dealer_id = dealer_url.split('/')[-1]

            articles = soup.select('article.dp-listing-item')
            st.write(f"Trovati {len(articles)} annunci da processare")

            for article in articles:
                try:
                    listing_id = article.get('id')
                    st.write(f"Processando annuncio ID: {listing_id}")

                    # Extract title, version and URL
                    title_elem = article.select_one('.dp-listing-item-title-wrapper h2')
                    version_elem = article.select_one('.dp-listing-item-title-wrapper .version')
                    title = title_elem.text.strip() if title_elem else "Titolo non disponibile"
                    version = version_elem.text.strip() if version_elem else ""
                    
                    url_elem = article.select_one('.dp-listing-item-title-wrapper a')
                    url = url_elem['href'] if url_elem else None
                    if url:
                        url = f"https://www.autoscout24.it{url}"

                    # Extract plate from URL or title
                    plate = None
                    if url:
                        plate = self._extract_plate(url)
                    if not plate and title:
                        plate = self._extract_plate(title)
                    if not plate:
                        plate = listing_id  # Use listing ID as fallback

                    # Get price
                    price_elem = article.select_one('[data-testid="price-section"] .dp-listing-item__price')
                    price_text = price_elem.text.strip() if price_elem else ""
                    price = self._extract_price(price_text)
                    
                    # Get images
                    images = []
                    img_elements = article.select('img.dp-new-gallery__img')
                    for img in img_elements:
                        if img.get('src'):
                            images.append(img['src'])
                    
                    # Get vehicle details
                    details = {'mileage': None, 'registration': None, 'power': None, 'fuel': None}
                    detail_items = article.select('.dp-listing-item__detail-item')
                    
                    for item in detail_items:
                        text = item.text.strip()
                        if 'km' in text:
                            details['mileage'] = self._extract_number(text)
                        elif '/' in text and len(text) <= 8:
                            details['registration'] = text
                        elif 'CV' in text or 'KW' in text:
                            details['power'] = text
                        elif any(fuel in text.lower() for fuel in ['benzina', 'diesel', 'elettrica', 'ibrida', 'gpl', 'metano']):
                            details['fuel'] = text

                    listing = {
                        'id': listing_id,
                        'plate': plate,
                        'title': title,
                        'version': version,
                        'price': price,
                        'dealer_id': dealer_id,
                        'images': images,
                        'url': url,
                        'mileage': details['mileage'],
                        'registration': details['registration'],
                        'power': details['power'],
                        'fuel': details['fuel'],
                        'scrape_date': datetime.now(),
                        'active': True
                    }
                    
                    listings.append(listing)
                    st.write(f"✓ Annuncio processato: {title}")
                    
                except Exception as e:
                    st.error(f"Errore nel parsing dell'annuncio: {str(e)}")
                    continue
                    
            st.success(f"Scraping completato. Trovati {len(listings)} annunci validi")
            return listings
            
        except requests.RequestException as e:
            st.error(f"Errore nella richiesta HTTP: {str(e)}")
            return []
        except Exception as e:
            st.error(f"Errore imprevisto: {str(e)}")
            return []

    def _extract_plate(self, text):
        """Extract plate from text using regex"""
        if not text:
            return None
        
        patterns = [
            r'[A-Z]{2}\s*\d{3}\s*[A-Z]{2}',  # Format XX000XX
            r'[A-Z]{2}\s*\d{5}',              # Format XX00000
            r'[A-Z]{2}\s*\d{4}\s*[A-Z]{1,2}'  # Other common formats
        ]
        
        text = text.upper()
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return re.sub(r'\s+', '', match.group(0))
        return None

    def save_listings(self, listings):
        """Save listings to Firebase with batch write"""
        batch = self.db.batch()
        timestamp = datetime.now()

        for listing in listings:
            doc_ref = self.db.collection('listings').document(listing['id'])
            
            listing['last_seen'] = timestamp
            batch.set(doc_ref, listing, merge=True)
            
            # Add to history
            history_ref = self.db.collection('history').document()
            history_data = {
                'listing_id': listing['id'],
                'dealer_id': listing['dealer_id'],
                'price': listing['price'],
                'date': timestamp,
                'event': 'listed'
            }
            batch.set(history_ref, history_data)

        batch.commit()

    def mark_inactive_listings(self, dealer_id: str, active_ids: list):
        """Mark listings as inactive if they're no longer present"""
        listings_ref = self.db.collection('listings')
        query = listings_ref.where('dealer_id', '==', dealer_id).where('active', '==', True)
        
        batch = self.db.batch()
        
        for doc in query.stream():
            if doc.id not in active_ids:
                # Update listing
                doc_ref = listings_ref.document(doc.id)
                batch.update(doc_ref, {
                    'active': False,
                    'deactivation_date': datetime.now()
                })
                
                # Add to history
                history_ref = self.db.collection('history').document()
                history_data = {
                    'listing_id': doc.id,
                    'dealer_id': dealer_id,
                    'date': datetime.now(),
                    'event': 'removed'
                }
                batch.set(history_ref, history_data)
                
        batch.commit()

    def get_dealer_stats(self, dealer_id: str):
        """Get dealer statistics"""
        stats = {
            'total_active': 0,
            'reappeared_plates': 0,
            'avg_listing_duration': 0
        }
        
        try:
            # Get active listings count
            active_listings = self.db.collection('listings')\
                .where('dealer_id', '==', dealer_id)\
                .where('active', '==', True)\
                .stream()
            stats['total_active'] = len(list(active_listings))
            
            # Calculate history stats
            history = self.db.collection('history')\
                .where('dealer_id', '==', dealer_id)\
                .stream()
            
            listings_history = {}
            for event in history:
                event_data = event.to_dict()
                listing_id = event_data['listing_id']
                if listing_id not in listings_history:
                    listings_history[listing_id] = []
                listings_history[listing_id].append(event_data)
            
            # Count reappeared listings
            stats['reappeared_plates'] = len([l for l in listings_history.values() if len(l) > 1])
            
            # Calculate average duration
            if stats['total_active'] > 0:
                total_duration = 0
                count = 0
                for listing_events in listings_history.values():
                    if len(listing_events) > 1:
                        first = min(e['date'] for e in listing_events)
                        last = max(e['date'] for e in listing_events)
                        duration = (last - first).days
                        total_duration += duration
                        count += 1
                
                if count > 0:
                    stats['avg_listing_duration'] = total_duration / count
            
        except Exception as e:
            st.error(f"Errore nel calcolo delle statistiche: {str(e)}")
        
        return stats

    def _extract_price(self, text):
        """Extract numeric price from text"""
        if not text:
            return None
            
        price_text = re.sub(r'[^\d.]', '', text)
        try:
            return float(price_text)
        except ValueError:
            return None
            
    def _extract_number(self, text):
        """Extract numeric value from text"""
        if not text:
            return None
            
        number = re.sub(r'[^\d]', '', text)
        try:
            return int(number)
        except ValueError:
            return None