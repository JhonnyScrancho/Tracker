from firebase_admin import credentials, initialize_app, firestore
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import streamlit as st
import pandas as pd
import firebase_admin
import re
import time

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
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'it-IT,it;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        })
        self.last_request = 0
        self.delay = 3

    def _wait_rate_limit(self):
        """Implementa rate limiting tra le richieste"""
        now = time.time()
        time_passed = now - self.last_request
        if time_passed < self.delay:
            time.sleep(self.delay - time_passed)
        self.last_request = time.time()

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
        
        try:
            st.write("📥 Scaricando la pagina...")
            response = requests.get(dealer_url, headers=self.session.headers, timeout=30)
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
                    st.write(f"📝 [{idx}/{len(articles)}] Processando annuncio...")

                    # Titolo e versione
                    title_elem = article.select_one('.dp-listing-item-title-wrapper h2')
                    version_elem = article.select_one('.dp-listing-item-title-wrapper .version')
                    title = title_elem.text.strip() if title_elem else "N/D"
                    version = version_elem.text.strip() if version_elem else ""
                    
                    # URL annuncio e ID
                    listing_id = article.get('id', '')
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
                    # Proviamo diversi selettori comuni in ordine di specificità
                    image_selectors = [
                        '[data-testid="gallery-image"]',  # Se usano data attributes
                        '.dp-new-gallery__img',          # Se usano classi specifiche per la gallery
                        'article img[data-src]',         # Qualsiasi img con data-src nell'article
                        'article img[src*="/auto/"]',    # img con src contenente /auto/
                        '.dp-listing-item__gallery img'  # Struttura generale della gallery
                    ]

                    for selector in image_selectors:
                        img_elements = article.select(selector)
                        if img_elements:
                            st.write(f"Debug: Trovate immagini con selettore: {selector}")
                            for img in img_elements:
                                img_url = img.get('data-src') or img.get('src')
                                if img_url:
                                    if not img_url.startswith('http'):
                                        img_url = f"https:{img_url}"
                                    if img_url not in images:  # Evita duplicati
                                        images.append(img_url)
                            if images:  # Se abbiamo trovato immagini, usciamo dal loop
                                break

                    st.write(f"Debug: Trovate {len(images)} immagini per l'annuncio")

                    # Se ancora non abbiamo trovato immagini, prova un approccio più aggressivo
                    if not images:
                        st.write("Debug: Tentativo di recupero immagini con approccio alternativo")
                        # Cerca qualsiasi immagine che potrebbe essere correlata all'auto
                        for img in article.find_all('img'):
                            src = img.get('data-src') or img.get('src')
                            if src and ('/auto/' in src or '/images/' in src):
                                if not src.startswith('http'):
                                    src = f"https:{src}"
                                if src not in images:
                                    images.append(src)

                    # Prezzi
                    price_section = article.select_one('[data-testid="price-section"]')
                    prices = {
                        'original_price': None,
                        'discounted_price': None,
                        'has_discount': False
                    }
                    
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
                    details = {
                        'mileage': None,
                        'registration': None,
                        'power': None,
                        'fuel': None
                    }

                    details_items = article.select('.dp-listing-item__detail-item')
                    for item in details_items:
                        text = item.text.strip()
                        # Verifica se il testo contiene un numero seguito da "km"
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

                    # Equipaggiamenti
                    equipment = []
                    equip_list = article.select('.dp-listing-item__equipment-list li')
                    for item in equip_list:
                        equipment.append(item.text.strip())

                    # Creazione dizionario annuncio
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
                        'equipment': equipment,
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

    def _extract_price(self, text):
        if not text:
            return None
            
        text = text.replace('€', '').replace('.', '').replace(',', '.')
        text = re.sub(r'[^\d.]', '', text)
        
        try:
            return float(text)
        except ValueError:
            return None

    def save_listings(self, listings):
        """Salva o aggiorna gli annunci"""
        batch = self.db.batch()
        timestamp = datetime.now()
        
        print(f"Salvataggio di {len(listings)} annunci")
        
        for listing in listings:
            doc_ref = self.db.collection('listings').document(listing['id'])
            
            # Normalizza i dati prima del salvataggio
            normalized_listing = {
                'id': listing['id'],
                'active': True,
                'dealer_id': listing['dealer_id'],
                'title': listing.get('title', ''),
                'original_price': float(listing.get('original_price', 0)) if listing.get('original_price') else None,
                'discounted_price': float(listing.get('discounted_price', 0)) if listing.get('discounted_price') else None,
                'has_discount': bool(listing.get('has_discount', False)),
                'mileage': int(listing.get('mileage', 0)) if listing.get('mileage') else None,
                'registration': listing.get('registration'),
                'fuel': listing.get('fuel'),
                'power': listing.get('power'),
                'image_urls': listing.get('image_urls', []),
                'last_seen': timestamp
            }
            
            print(f"Debug - Normalized listing data: {normalized_listing}")
            
            # Se è un nuovo annuncio, aggiungi data creazione
            doc = doc_ref.get()
            if not doc.exists:
                normalized_listing['first_seen'] = timestamp
            
            batch.set(doc_ref, normalized_listing, merge=True)
            
            # Registra evento nello storico
            history_ref = self.db.collection('history').document()
            history_data = {
                'listing_id': listing['id'],
                'dealer_id': listing['dealer_id'],
                'price': normalized_listing['original_price'],
                'discounted_price': normalized_listing['discounted_price'],
                'date': timestamp,
                'event': 'update'
            }
            batch.set(history_ref, history_data)
        
        print("Esecuzione batch commit")
        batch.commit()
        print("Batch commit completato")

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
            'avg_listing_duration': 0,
            'total_discount_count': 0,
            'avg_discount_percentage': 0
        }
        
        try:
            # Recupera annunci attivi
            active_listings = self.db.collection('listings')\
                .where('dealer_id', '==', dealer_id)\
                .where('active', '==', True)\
                .stream()
            
            listings_list = list(active_listings)
            stats['total_active'] = len(listings_list)
            
            # Calcolo statistiche sconti
            discount_count = 0
            total_discount_percentage = 0
            
            for listing in listings_list:
                data = listing.to_dict()
                if data.get('has_discount') and data.get('original_price') and data.get('discounted_price'):
                    discount_count += 1
                    discount_percentage = ((data['original_price'] - data['discounted_price']) / 
                                        data['original_price'] * 100)
                    total_discount_percentage += discount_percentage
            
            stats['total_discount_count'] = discount_count
            if discount_count > 0:
                stats['avg_discount_percentage'] = total_discount_percentage / discount_count
            
            # Calcolo durata media annunci
            if stats['total_active'] > 0:
                total_duration = 0
                count = 0
                
                for listing in listings_list:
                    data = listing.to_dict()
                    if data.get('first_seen'):
                        duration = (datetime.now() - data['first_seen']).days
                        total_duration += duration
                        count += 1
                
                if count > 0:
                    stats['avg_listing_duration'] = total_duration / count
            
        except Exception as e:
            st.error(f"❌ Errore nel calcolo delle statistiche: {str(e)}")
        
        return stats

    def get_listing_history(self, dealer_id: str):
        """Recupera lo storico degli annunci di un dealer"""
        try:
            history = self.db.collection('history')\
                .where('dealer_id', '==', dealer_id)\
                .order_by('date')\
                .stream()
            return [event.to_dict() for event in history]
        except Exception as e:
            st.error(f"❌ Errore nel recupero dello storico: {str(e)}")
            return []

    def save_dealer(self, dealer_id: str, url: str):
        """Salva un nuovo concessionario"""
        self.db.collection('dealers').document(dealer_id).set({
            'url': url,
            'active': True,
            'created_at': datetime.now(),
            'last_update': datetime.now()
        }, merge=True)

    def get_dealers(self):
        """Recupera tutti i concessionari attivi"""
        dealers = self.db.collection('dealers')\
            .where('active', '==', True)\
            .stream()
        return [dealer.to_dict() | {'id': dealer.id} for dealer in dealers]

    def remove_dealer(self, dealer_id: str, hard_delete: bool = False):
        """
        Rimuove un concessionario
        
        Args:
            dealer_id: ID del concessionario
            hard_delete: Se True, elimina completamente i dati dal database
        """
        if not hard_delete:
            # Soft delete esistente
            self.db.collection('dealers').document(dealer_id).update({
                'active': False,
                'removed_at': datetime.now()
            })
            return
            
        # Hard delete
        batch = self.db.batch()
        
        # 1. Elimina il dealer
        dealer_ref = self.db.collection('dealers').document(dealer_id)
        batch.delete(dealer_ref)
        
        # 2. Elimina tutti gli annunci associati
        listings = self.db.collection('listings')\
            .where('dealer_id', '==', dealer_id)\
            .stream()
        
        for listing in listings:
            batch.delete(listing.reference)
        
        # 3. Elimina tutti i record storici
        history = self.db.collection('history')\
            .where('dealer_id', '==', dealer_id)\
            .stream()
        
        for record in history:
            batch.delete(record.reference)
        
        # Esegue tutte le operazioni in una singola transazione
        batch.commit()

    def get_listing_plate(self, listing_id: str):
        """Recupera la targa di un annuncio specifico"""
        try:
            doc = self.db.collection('listings').document(listing_id).get()
            if doc.exists:
                data = doc.to_dict()
                return data.get('plate')
            return None
        except Exception as e:
            print(f"Errore nel recupero della targa: {str(e)}")
            return None

    def get_active_listings(self, dealer_id: str):
        """
        Recupera gli annunci attivi di un concessionario
        
        Args:
            dealer_id: ID del concessionario
            
        Returns:
            Lista di annunci attivi
        """
        try:
            # Aggiungiamo log per debug
            print(f"Recupero annunci per dealer {dealer_id}")
            
            # Query per gli annunci attivi del dealer specifico
            listings_ref = self.db.collection('listings')
            query = listings_ref.where('dealer_id', '==', dealer_id).where('active', '==', True)
            
            # Esegui la query e converti i risultati in lista di dizionari
            listings = []
            docs = query.stream()
            
            for doc in docs:
                listing_data = doc.to_dict()
                listing_data['id'] = doc.id  # Aggiungi l'ID del documento
                listings.append(listing_data)
                
            print(f"Trovati {len(listings)} annunci attivi")
            if listings:
                print("Esempio struttura primo annuncio:", list(listings[0].keys()))
                
            return listings
            
        except Exception as e:
            print(f"Errore nel recupero degli annunci: {str(e)}")
            return []
        
    def validate_image_url(self, url: str) -> bool:
        """Verifica che l'URL dell'immagine sia valido e accessibile"""
        try:
            response = requests.head(url, timeout=5)
            return (response.status_code == 200 and 
                   'image' in response.headers.get('content-type', ''))
        except Exception:
            return False    