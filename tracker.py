from firebase_admin import credentials, initialize_app, firestore
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import streamlit as st

class AutoTracker:
    def __init__(self):
        # Inizializza Firebase
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": st.secrets["firebase"]["project_id"],
            "private_key": st.secrets["firebase"]["private_key"],
            "client_email": st.secrets["firebase"]["client_email"],
        })
        initialize_app(cred)
        self.db = firestore.client()
    
    def scrape_dealer(self, dealer_url: str):
        """Scraping della pagina del concessionario"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'it-IT,it;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        try:
            # Esegui la richiesta HTTP con gestione errori
            response = requests.get(dealer_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Parsing della pagina con BeautifulSoup
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Estrai gli annunci
            listings = []
            dealer_id = dealer_url.split('/')[-1]
            
            # Selettore per gli annunci (article con classe che contiene 'ListItem')
            for item in soup.select('article[class*="ListItem"]'):
                try:
                    # Estrai titolo
                    title_elem = item.select_one('h2[class*="Title"]')
                    title = title_elem.text.strip() if title_elem else "Titolo non disponibile"
                    
                    # Estrai prezzo
                    price_elem = item.select_one('span[class*="Price"]')
                    price_text = price_elem.text.strip() if price_elem else ""
                    price = self._extract_price(price_text)
                    
                    # Estrai URL annuncio e immagine
                    link_elem = item.select_one('a[href*="/annuncio/"]')
                    url = f"https://www.autoscout24.it{link_elem['href']}" if link_elem else None
                    
                    img_elem = item.select_one('img[src*="/images/"]')
                    image_url = img_elem['src'] if img_elem else None
                    
                    # Estrai targa dall'URL dell'annuncio o dal titolo
                    plate = None
                    if url:
                        # Prova a estrarre la targa dall'URL
                        plate = self._extract_plate(url)
                    if not plate and title:
                        # Se non trovata nell'URL, cerca nel titolo
                        plate = self._extract_plate(title)
                    
                    if plate:  # Aggiungi solo se abbiamo trovato una targa
                        listing = {
                            'plate': plate,
                            'title': title,
                            'price': price,
                            'dealer_id': dealer_id,
                            'url': url,
                            'image_url': image_url,
                            'scrape_date': datetime.now(),
                            'active': True
                        }
                        listings.append(listing)
                    
                except Exception as e:
                    st.error(f"Errore nel parsing di un annuncio: {str(e)}")
                    continue
            
            if not listings:
                st.warning("Nessun annuncio trovato con targa identificabile")
            
            return listings
            
        except requests.RequestException as e:
            st.error(f"Errore durante lo scraping: {str(e)}")
            return []
        except Exception as e:
            st.error(f"Errore imprevisto: {str(e)}")
            return []

    def _parse_listings(self, soup, dealer_url):
        """Estrae i dati degli annunci dalla pagina"""
        listings = []
        dealer_id = dealer_url.split('/')[-1]
        
        # Implementa qui la logica di parsing specifica per AutoScout24
        # Questo è uno schema base da adattare
        for item in soup.select('.listing-item'):  # Aggiorna il selettore
            listing = {
                'plate': self._extract_plate(item),
                'title': item.select_one('.title').text.strip(),
                'price': self._extract_price(item),
                'dealer_id': dealer_id,
                'url': item.select_one('a')['href'],
                'image_url': item.select_one('img')['src']
            }
            listings.append(listing)
        
        return listings

    def save_listings(self, listings):
        """Salva gli annunci in Firebase"""
        batch = self.db.batch()
        timestamp = datetime.now()

        for listing in listings:
            doc_ref = self.db.collection('listings').document(listing['plate'])
            
            # Aggiorna o crea l'annuncio
            batch.set(doc_ref, {
                **listing,
                'last_seen': timestamp,
                'active': True
            }, merge=True)
            
            # Aggiungi alla storia se è una nuova apparizione
            history_ref = self.db.collection('history').document()
            batch.set(history_ref, {
                'plate': listing['plate'],
                'dealer_id': listing['dealer_id'],
                'appearance_date': timestamp
            })

        batch.commit()

    def mark_inactive_listings(self, dealer_id: str, active_plates: list):
        """Marca come inattivi gli annunci non più presenti"""
        listings_ref = self.db.collection('listings')
        query = listings_ref.where('dealer_id', '==', dealer_id).where('active', '==', True)
        
        for doc in query.stream():
            if doc.id not in active_plates:
                doc.reference.update({
                    'active': False,
                    'disappearance_date': datetime.now()
                })

    def get_dealer_stats(self, dealer_id: str):
        """Recupera statistiche del concessionario"""
        stats = {
            'total_active': 0,
            'reappeared_plates': 0,
            'avg_listing_duration': 0
        }
        
        # Implementa qui le query per le statistiche
        # Questo è solo un esempio base
        listings_ref = self.db.collection('listings')
        active_listings = listings_ref.where('dealer_id', '==', dealer_id).where('active', '==', True).stream()
        stats['total_active'] = len(list(active_listings))
        
        return stats

    def _extract_plate(self, item):
        """Estrae la targa dall'annuncio"""
        # Implementa la logica specifica per estrarre la targa
        pass

    def _extract_price(self, item):
        """Estrae il prezzo dall'annuncio"""
        # Implementa la logica specifica per estrarre il prezzo
        pass