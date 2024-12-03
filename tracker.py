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
        try:
            firebase_admin.get_app()
        except ValueError:
            cred_dict = {
                "type": "service_account",
                "project_id": st.secrets["firebase"]["project_id"],
                "private_key": st.secrets["firebase"]["private_key"].replace('\\n', '\n'),
                "client_email": st.secrets["firebase"]["client_email"],
                "client_id": st.secrets["firebase"]["client_id"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
            }
            cred = credentials.Certificate(cred_dict)
            initialize_app(cred)
        self.db = firestore.client()

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

    def scrape_dealer(self, dealer_url: str):
        if not dealer_url:
            st.warning("Inserisci l'URL del concessionario")
            return []

        st.info("🔍 Inizio scraping della pagina...")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9'
        }
        
        try:
            st.write("📥 Scaricando la pagina...")
            response = requests.get(dealer_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            total_results = soup.select_one(".dp-list__title__count")
            if total_results:
                st.write(f"📊 Totale annunci trovati: {total_results.text}")
            
            listings = []
            dealer_id = dealer_url.split('/')[-1]

            articles = soup.select('article.dp-listing-item')
            st.write(f"🚗 Trovati {len(articles)} annunci da processare")

            for idx, article in enumerate(articles, 1):
                try:
                    listing_id = article.get('id')
                    st.write(f"📝 [{idx}/{len(articles)}] Processando annuncio ID: {listing_id}")

                    # Titolo e versione
                    title_elem = article.select_one('.dp-listing-item-title-wrapper h2')
                    version_elem = article.select_one('.dp-listing-item-title-wrapper .version')
                    title = title_elem.text.strip() if title_elem else "Titolo non disponibile"
                    version = version_elem.text.strip() if version_elem else ""
                    
                    # URL annuncio
                    url_elem = article.select_one('.dp-listing-item-title-wrapper a')
                    url = f"https://www.autoscout24.it{url_elem['href']}" if url_elem and 'href' in url_elem.attrs else None
                    
                    # Estrazione targa
                    plate = None
                    if url:
                        plate = self._extract_plate(url)
                    if not plate and title:
                        plate = self._extract_plate(title)
                    if not plate:
                        plate = listing_id

                    # Immagini
                    images = []
                    img_elements = article.select('img[data-src]')  # Cerchiamo sia src che data-src
                    for img in img_elements:
                        img_url = img.get('data-src') or img.get('src')
                        if img_url and 'auto' in img_url:
                            images.append(img_url)

                    # Prezzi
                    prices = {'original_price': None, 'discounted_price': None, 'has_discount': False}
                    price_section = article.select_one('[data-testid="price-section"]')
                    
                    if price_section:
                        superdeal = price_section.select_one('.dp-listing-item__superdeal-container')
                        if superdeal:
                            original_price_elem = superdeal.select_one('.dp-listing-item__superdeal-strikethrough div')
                            if original_price_elem:
                                prices['original_price'] = self._extract_price(original_price_elem.text)
                            
                            discounted_price_elem = superdeal.select_one('.dp-listing-item__superdeal-highlight-price-span')
                            if discounted_price_elem:
                                prices['discounted_price'] = self._extract_price(discounted_price_elem.text)
                            prices['has_discount'] = True
                        else:
                            regular_price_elem = price_section.select_one('.dp-listing-item__price')
                            if regular_price_elem:
                                prices['original_price'] = self._extract_price(regular_price_elem.text)

                    # Dettagli veicolo
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
                        'original_price': prices['original_price'],
                        'discounted_price': prices['discounted_price'],
                        'has_discount': prices['has_discount'],
                        'dealer_id': dealer_id,
                        'image_urls': images,
                        'url': url,
                        'mileage': details['mileage'],
                        'registration': details['registration'],
                        'power': details['power'],
                        'fuel': details['fuel'],
                        'scrape_date': datetime.now(),
                        'active': True
                    }
                    listings.append(listing)
                    st.write(f"✅ Annuncio processato: {title}")
                    
                except Exception as e:
                    st.error(f"❌ Errore nel parsing dell'annuncio: {str(e)}")
                    continue
                    
            st.success(f"🎉 Scraping completato. Trovati {len(listings)} annunci validi")
            return listings
            
        except requests.RequestException as e:
            st.error(f"❌ Errore nella richiesta HTTP: {str(e)}")
            return []
        except Exception as e:
            st.error(f"❌ Errore imprevisto: {str(e)}")
            return []

    def save_listings(self, listings):
        batch = self.db.batch()
        timestamp = datetime.now()

        for listing in listings:
            doc_ref = self.db.collection('listings').document(listing['id'])
            
            listing['last_seen'] = timestamp
            batch.set(doc_ref, listing, merge=True)
            
            history_ref = self.db.collection('history').document()
            history_data = {
                'listing_id': listing['id'],
                'dealer_id': listing['dealer_id'],
                'original_price': listing['original_price'],
                'discounted_price': listing['discounted_price'],
                'has_discount': listing['has_discount'],
                'date': timestamp,
                'event': 'listed'
            }
            batch.set(history_ref, history_data)

        batch.commit()

    def mark_inactive_listings(self, dealer_id: str, active_ids: list):
        listings_ref = self.db.collection('listings')
        query = listings_ref.where('dealer_id', '==', dealer_id).where('active', '==', True)
        
        batch = self.db.batch()
        
        for doc in query.stream():
            if doc.id not in active_ids:
                doc_ref = listings_ref.document(doc.id)
                batch.update(doc_ref, {
                    'active': False,
                    'deactivation_date': datetime.now()
                })
                
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
        stats = {
            'total_active': 0,
            'reappeared_plates': 0,
            'avg_listing_duration': 0,
            'total_discount_count': 0,
            'avg_discount_percentage': 0
        }
        
        try:
            active_listings = self.db.collection('listings')\
                .where('dealer_id', '==', dealer_id)\
                .where('active', '==', True)\
                .stream()
            
            active_listings_list = list(active_listings)
            stats['total_active'] = len(active_listings_list)
            
            # Calcolo statistiche sconti
            discount_count = 0
            total_discount_percentage = 0
            
            for listing in active_listings_list:
                data = listing.to_dict()
                if data.get('has_discount') and data.get('original_price') and data.get('discounted_price'):
                    discount_count += 1
                    discount_percentage = ((data['original_price'] - data['discounted_price']) / data['original_price']) * 100
                    total_discount_percentage += discount_percentage
            
            stats['total_discount_count'] = discount_count
            if discount_count > 0:
                stats['avg_discount_percentage'] = total_discount_percentage / discount_count
            
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
            
            stats['reappeared_plates'] = len([l for l in listings_history.values() if len(l) > 1])
            
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
            st.error(f"❌ Errore nel calcolo delle statistiche: {str(e)}")
        
        return stats

    def _extract_price(self, text):
        if not text:
            return None
            
        text = text.replace('€', '').replace('.', '').replace(',', '.')
        text = re.sub(r'[^\d.]', '', text)
        
        try:
            return float(text)
        except ValueError:
            return None
            
    def _extract_number(self, text):
        if not text:
            return None
            
        number = re.sub(r'[^\d]', '', text)
        try:
            return int(number)
        except ValueError:
            return None