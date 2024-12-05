from typing import Dict, List, Optional
from firebase_admin import credentials, initialize_app, firestore
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import streamlit as st
import pandas as pd
import firebase_admin
import re
import time
import cv2
import numpy as np
from services.vision_service import VisionService


class AutoTracker:
    def __init__(self):
        # Firebase initialization
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
        
        # Vision Service initialization with graceful fallback
        self.vision = None
        try:
            if 'vision' in st.secrets and 'api_key' in st.secrets['vision']:
                api_key = st.secrets['vision']['api_key']
                self.vision = VisionService(api_key)
            else:
                st.warning("⚠️ Configurazione Vision Service mancante - alcune funzionalità saranno disabilitate")
        except Exception as e:
            st.warning(f"⚠️ Vision Service non disponibile: {str(e)}")

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
        """Scarica e analizza tutti gli annunci di un concessionario"""
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
            if not articles:
                st.warning("⚠️ Nessun annuncio trovato nella pagina")
                return []

            st.write(f"🚗 Trovati {len(articles)} annunci da processare")

            # Recupera gli annunci esistenti e loro dati
            existing_listings = {l['id']: l for l in self.get_active_listings(dealer_id)}

            # Inizializza il servizio di visione solo se necessario
            vision_service = None
            if self.vision and 'vision' in st.secrets and 'api_key' in st.secrets['vision']:
                vision_service = VisionService(st.secrets["vision"]["api_key"])

            for idx, article in enumerate(articles, 1):
                try:
                    st.write(f"📝 [{idx}/{len(articles)}] Processando annuncio...")
                    
                    # Identificazione annuncio
                    listing_id = article.get('id', '')
                    existing_listing = existing_listings.get(listing_id)
                    
                    # Estrazione URL e titolo
                    url_elem = article.select_one('a.dp-link.dp-listing-item-title-wrapper')
                    if not url_elem or 'href' not in url_elem.attrs:
                        url_elem = article.select_one('.dp-listing-item-title-wrapper a')
                        if not url_elem or 'href' not in url_elem.attrs:
                            st.warning("⚠️ URL non trovato per questo annuncio")
                            continue

                    url = f"https://www.autoscout24.it{url_elem['href']}"
                    title_elem = url_elem.select_one('h2')
                    version_elem = url_elem.select_one('.version')
                    
                    title = title_elem.text.strip() if title_elem else "N/D"
                    version = version_elem.text.strip() if version_elem else ""
                    full_title = f"{title} {version}".strip()

                    # ESTRAZIONE PREZZI
                    price_section = article.select_one('[data-testid="price-section"]')
                    prices = {
                        'original_price': None,
                        'discounted_price': None,
                        'has_discount': False,
                        'discount_percentage': None
                    }

                    if price_section:
                        discount_price = price_section.select_one('.discount-price, .dp-listing-item__superdeal-strikethrough div')
                        if discount_price:
                            prices['original_price'] = self._extract_price(discount_price.text)
                            prices['has_discount'] = True
                            
                            current_price = price_section.select_one('.dp-listing-item__superdeal-highlight-price-span, .current-price')
                            if current_price:
                                prices['discounted_price'] = self._extract_price(current_price.text)
                                
                                if prices['original_price'] and prices['discounted_price']:
                                    prices['discount_percentage'] = round(
                                        ((prices['original_price'] - prices['discounted_price']) / 
                                        prices['original_price'] * 100),
                                        1
                                    )
                        else:
                            regular_price = price_section.select_one('.dp-listing-item__price')
                            if regular_price:
                                prices['original_price'] = self._extract_price(regular_price.text)

                    # Estrazione dettagli veicolo
                    details = self._extract_vehicle_details(article)

                    # Gestione immagini e analisi visione
                    images = []
                    vision_results = {}
                    
                    if existing_listing and existing_listing.get('plate'):
                        # Se l'annuncio esiste già e ha una targa, mantieni i dati delle immagini esistenti
                        st.info(f"ℹ️ Annuncio {listing_id} già presente con targa - mantengo dati immagini esistenti")
                        images = existing_listing.get('image_urls', [])
                        vision_results = {
                            'plate': existing_listing.get('plate'),
                            'plate_confidence': existing_listing.get('plate_confidence', 0),
                            'vehicle_type': existing_listing.get('vehicle_type'),
                            'last_plate_analysis': existing_listing.get('last_plate_analysis'),
                        }
                    else:
                        # Nuovo annuncio o annuncio esistente senza targa
                        if not existing_listing:
                            st.write("🆕 Nuovo annuncio, recupero immagini...")
                        else:
                            st.write("🔄 Annuncio esistente senza targa, recupero immagini...")
                            
                        images = self.get_listing_images(url)
                        if images and vision_service:
                            vision_results = vision_service.analyze_vehicle_images(images)
                            if vision_results and vision_results.get('plate'):
                                st.success(f"✅ Targa rilevata: {vision_results['plate']} (confidenza: {vision_results['plate_confidence']:.2%})")
                            else:
                                st.warning("⚠️ Nessuna targa rilevata nelle immagini")
                                
                    # Creazione dizionario annuncio
                    listing = {
                        'id': listing_id,
                        'title': full_title,
                        'url': url,
                        'original_price': prices['original_price'],
                        'discounted_price': prices['discounted_price'],
                        'has_discount': prices['has_discount'],
                        'discount_percentage': prices['discount_percentage'],
                        'dealer_id': dealer_id,
                        'image_urls': images,
                        'mileage': details['mileage'],
                        'registration': details['registration'],
                        'power': details['power'],
                        'fuel': details['fuel'],
                        'transmission': details['transmission'],
                        'consumption': details['consumption'],
                        'plate': vision_results.get('plate'),
                        'plate_confidence': vision_results.get('plate_confidence', 0),
                        'vehicle_type': vision_results.get('vehicle_type'),
                        'last_plate_analysis': datetime.now() if vision_results else existing_listing.get('last_plate_analysis') if existing_listing else None,
                        'vision_cache': {
                            'results': vision_results,
                            'last_price': prices['original_price'],
                            'timestamp': datetime.now().isoformat()
                        } if vision_results else existing_listing.get('vision_cache') if existing_listing else {},
                        'scrape_date': datetime.now(),
                        'active': True
                    }

                    # Se è un aggiornamento di un annuncio esistente, mantieni alcuni campi importanti
                    if existing_listing:
                        if existing_listing.get('plate_edited'):
                            listing['plate'] = existing_listing['plate']
                            listing['plate_edited'] = True
                            listing['plate_edit_date'] = existing_listing.get('plate_edit_date')
                        if existing_listing.get('first_seen'):
                            listing['first_seen'] = existing_listing['first_seen']
                        if existing_listing.get('notes'):
                            listing['notes'] = existing_listing['notes']

                    listings.append(listing)
                    st.write(f"✅ Annuncio processato: {full_title}")
                    
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

    def _extract_vehicle_details(self, article) -> dict:
        """Estrae i dettagli del veicolo dall'articolo"""
        details = {
            'mileage': None,
            'registration': None,
            'power': None,
            'fuel': None,
            'transmission': None,
            'consumption': None
        }

        details_items = article.select('.dp-listing-item__detail-item')
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
                
        return details

    def _should_reanalyze_listing(self, last_analysis, plate_confidence, current_price, cached_price) -> bool:
        """Determina se un annuncio necessita di rianalisi"""
        if not last_analysis:
            return True
            
        try:
            last_analysis_date = datetime.fromisoformat(last_analysis)
            days_since_analysis = (datetime.now() - last_analysis_date).days
            
            # Rianalizza se:
            # 1. L'ultima analisi è vecchia (>30 giorni)
            if days_since_analysis > 30:
                return True
                
            # 2. La confidenza della targa è bassa (<90%)
            if plate_confidence < 0.9:
                return True
                
            # 3. Il prezzo è cambiato significativamente (>15%)
            if cached_price and current_price:
                price_change = abs((current_price - cached_price) / cached_price * 100)
                if price_change > 15:
                    return True
                    
            return False
            
        except Exception as e:
            st.error(f"Errore nella valutazione rianalisi: {str(e)}")
            return True

    def _get_with_retry(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Esegue una richiesta GET con retry"""
        for attempt in range(max_retries):
            try:
                self._wait_rate_limit() # Usa il rate limiting esistente
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                if attempt == max_retries - 1:
                    st.error(f"❌ Errore nella richiesta HTTP: {str(e)}")
                    return None
                time.sleep(2 ** attempt)  # Backoff esponenziale
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
            st.error(f"❌ Errore nell'analisi dell'immagine {img_url}: {str(e)}")
            return 0.0

    def get_listing_images(self, listing_url: str) -> list:
        """
        Recupera e analizza le immagini dell'annuncio, ordinandole per probabilità di contenere una targa.
        Limita il recupero alle prime 10 immagini per ottimizzare le performance.
        """
        try:
            st.write("🔍 Analisi immagini annuncio...")
            st.write(f"📍 URL: {listing_url}")
            
            response = self._get_with_retry(listing_url)
            if not response:
                return []

            soup = BeautifulSoup(response, 'lxml')
            images = []
            MAX_IMAGES = 10

            # Lista di selettori in ordine di specificità
            selectors = [
                '.image-gallery-slides picture.ImageWithBadge_picture__XJG24 img',
                '.image-gallery-slides img',
                '.Gallery_gallery__ppyDW img',
                'img[src*="/auto/"]'
            ]

            st.write(f"📸 Raccolta prime {MAX_IMAGES} immagini disponibili...")
            found_urls = set()  # Per tenere traccia degli URL già processati
            
            for selector in selectors:
                if len(found_urls) >= MAX_IMAGES:
                    break
                    
                elements = soup.select(selector)
                
                for img in elements:
                    if len(found_urls) >= MAX_IMAGES:
                        break
                        
                    if img.get('src'):
                        img_url = img['src']
                        # Normalizza URL per la massima qualità
                        base_url = re.sub(r'/\d+x\d+\.(webp|jpg)', '', img_url)
                        if not base_url.endswith('.jpg'):
                            base_url += '.jpg'
                                
                        if base_url not in found_urls:
                            found_urls.add(base_url)
                            # Analizza la probabilità di contenere una targa
                            st.write(f"Analisi immagine {len(found_urls)}/{MAX_IMAGES}...")
                            plate_likelihood = self._analyze_image_for_plate_likelihood(base_url)
                            images.append({
                                'url': base_url,
                                'plate_likelihood': plate_likelihood,
                                'index': len(found_urls)
                            })

            st.write(f"\n📊 Totale immagini trovate: {len(images)}")
            
            # Ordina per probabilità e prendi le migliori 3
            best_images = sorted(images, key=lambda x: x['plate_likelihood'], reverse=True)[:3]
            
            st.write("\n🏆 TOP 3 immagini selezionate:")
            for i, img in enumerate(best_images, 1):
                st.write(f"{i}. Immagine {img['index']} - Score: {img['plate_likelihood']:.2f}")
                st.image(img['url'], caption=f"Immagine #{img['index']} (Score: {img['plate_likelihood']:.2f})", width=300)

            return [img['url'] for img in best_images]  # Ritorna solo gli URL delle migliori immagini

        except Exception as e:
            st.error(f"❌ Errore nel recupero immagini: {str(e)}")
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
            
            # Normalizzazione completa dei dati prima del salvataggio
            normalized_listing = {
                'id': listing['id'],
                'active': True,
                'dealer_id': listing['dealer_id'],
                'title': listing.get('title', ''),
                'url': listing.get('url', ''),  # Aggiunto campo url
                'original_price': float(listing.get('original_price', 0)) if listing.get('original_price') else None,
                'discounted_price': float(listing.get('discounted_price', 0)) if listing.get('discounted_price') else None,
                'has_discount': bool(listing.get('has_discount', False)),
                'mileage': int(listing.get('mileage', 0)) if listing.get('mileage') else None,
                'registration': listing.get('registration'),
                'fuel': listing.get('fuel'),
                'power': listing.get('power'),
                'transmission': listing.get('transmission'),  # Aggiunto campo transmission
                'consumption': listing.get('consumption'),    # Aggiunto campo consumption
                'image_urls': listing.get('image_urls', []),
                'plate': listing.get('plate'),               # Aggiunto campo plate
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
                'event': 'update',
                'listing_details': {
                    'plate': normalized_listing['plate'],
                    'title': normalized_listing['title']
                }
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
                    'event': 'removed',
                    'listing_details': doc.to_dict()
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
        
    def update_plate(self, listing_id: str, new_plate: str):
        """
        Aggiorna la targa di un annuncio
        
        Args:
            listing_id: ID dell'annuncio
            new_plate: Nuova targa
        """
        try:
            # Validazione della targa
            if new_plate and not re.match(r'^[A-Z]{2}\d{3,4}[A-Z]{2}$', new_plate.upper()):
                st.error("❌ Formato targa non valido")
                return False

            # Aggiorna il documento
            self.db.collection('listings').document(listing_id).update({
                'plate': new_plate.upper() if new_plate else None,
                'plate_edited': True,
                'plate_edit_date': datetime.now()
            })
            
            return True
            
        except Exception as e:
            st.error(f"❌ Errore nell'aggiornamento della targa: {str(e)}")
            return False
    
    def validate_image_url(self, url: str) -> bool:
        """Verifica che l'URL dell'immagine sia valido e accessibile"""
        try:
            response = requests.head(url, timeout=5)
            return (response.status_code == 200 and 
                   'image' in response.headers.get('content-type', ''))
        except Exception:
            return False    
        
    def get_dealer_history(self, dealer_id: str):
        """
        Recupera lo storico completo di un dealer
        
        Args:
            dealer_id: ID del concessionario
            
        Returns:
            Lista di eventi storici ordinati per data
        """
        try:
            history = self.db.collection('history')\
                .where('dealer_id', '==', dealer_id)\
                .order_by('date')\
                .stream()
            
            history_data = []
            for event in history:
                event_data = event.to_dict()
                # Ensure all events have required fields
                event_data['id'] = event.id
                event_data['dealer_id'] = dealer_id
                event_data['date'] = event_data.get('date', datetime.now())
                event_data['event'] = event_data.get('event', 'unknown')
                event_data['price'] = event_data.get('price', 0)
                event_data['discounted_price'] = event_data.get('discounted_price')
                history_data.append(event_data)
                
            return history_data
            
        except Exception as e:
            st.error(f"❌ Errore nel recupero dello storico: {str(e)}")
            return []    
        
    def get_scheduler_config(self):
        """Recupera la configurazione dello scheduler"""
        try:
            doc = self.db.collection('config').document('scheduler').get()
            if doc.exists:
                return doc.to_dict()
            return {
                'enabled': False,
                'hour': 1,
                'minute': 0,
                'last_update': None
            }
        except Exception as e:
            st.error(f"❌ Errore nel recupero configurazione scheduler: {str(e)}")
            return {
                'enabled': False,
                'hour': 1,
                'minute': 0,
                'last_update': None
            }


    def save_scheduler_config(self, config: dict):
        """Salva la configurazione dello scheduler"""
        try:
            self.db.collection('config').document('scheduler').set(config, merge=True)
        except Exception as e:
            st.error(f"❌ Errore nel salvataggio configurazione scheduler: {str(e)}")

    def _schedule_next_update(self, hour: int, minute: int):
        """Pianifica il prossimo aggiornamento automatico"""
        try:
            now = datetime.now()
            next_run = now.replace(hour=hour, minute=minute)
            
            # Se l'orario è già passato per oggi, pianifica per domani
            if next_run < now:
                next_run = next_run.replace(day=next_run.day + 1)
                
            # Salva l'orario del prossimo aggiornamento
            self.db.collection('config').document('scheduler').update({
                'next_update': next_run
            })
            
        except Exception as e:
            st.error(f"❌ Errore nella pianificazione: {str(e)}")    