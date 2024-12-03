from firebase_admin import credentials, initialize_app, firestore
from bs4 import BeautifulSoup
import requests
from datetime import datetime
import streamlit as st
import firebase_admin

class AutoTracker:
    def __init__(self):
        """Initialize Firebase connection with proper error handling"""
        try:
            # Check if Firebase is already initialized
            firebase_admin.get_app()
        except ValueError:
            # Only initialize if not already done
            try:
                # Create proper credential dictionary
                firebase_creds = {
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
                
                cred = credentials.Certificate(firebase_creds)
                initialize_app(cred)
            except Exception as e:
                st.error(f"Firebase initialization error: {str(e)}")
                st.error("Please check your .streamlit/secrets.toml configuration")
                raise
            
        self.db = firestore.client()
    
    def scrape_dealer(self, dealer_url: str):
        """Scrape dealer page with improved error handling"""
        if not dealer_url:
            st.warning("Please provide a dealer URL")
            return []

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'it-IT,it;q=0.9'
        }
        
        try:
            response = requests.get(dealer_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            listings = []
            dealer_id = dealer_url.split('/')[-1]
            
            for item in soup.select('article[class*="ListItem"]'):
                try:
                    title_elem = item.select_one('h2[class*="Title"]')
                    title = title_elem.text.strip() if title_elem else "Titolo non disponibile"
                    
                    price_elem = item.select_one('span[class*="Price"]')
                    price_text = price_elem.text.strip() if price_elem else ""
                    price = self._extract_price(price_text)
                    
                    link_elem = item.select_one('a[href*="/annuncio/"]')
                    url = f"https://www.autoscout24.it{link_elem['href']}" if link_elem else None
                    
                    img_elem = item.select_one('img[src*="/images/"]')
                    image_url = img_elem['src'] if img_elem else None
                    
                    # Extract plate from URL or title
                    plate = None
                    if url:
                        plate = self._extract_plate(url)
                    if not plate and title:
                        plate = self._extract_plate(title)
                    
                    if plate:
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
                    st.error(f"Error parsing listing: {str(e)}")
                    continue
            
            return listings
            
        except requests.RequestException as e:
            st.error(f"Error during scraping: {str(e)}")
            return []
        except Exception as e:
            st.error(f"Unexpected error: {str(e)}")
            return []

    def _extract_plate(self, text):
        """Extract license plate from text using regex"""
        import re
        # Match Italian license plate formats
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

    def _extract_price(self, text):
        """Extract price from text"""
        import re
        if not text:
            return None
            
        price_text = re.sub(r'[^\d.]', '', text)
        try:
            return float(price_text)
        except ValueError:
            return None

    def save_listings(self, listings):
        """Save listings to Firebase with batch write"""
        batch = self.db.batch()
        timestamp = datetime.now()

        for listing in listings:
            doc_ref = self.db.collection('listings').document(listing['plate'])
            
            batch.set(doc_ref, {
                **listing,
                'last_seen': timestamp,
                'active': True
            }, merge=True)
            
            history_ref = self.db.collection('history').document()
            batch.set(history_ref, {
                'plate': listing['plate'],
                'dealer_id': listing['dealer_id'],
                'appearance_date': timestamp
            })

        batch.commit()

    def mark_inactive_listings(self, dealer_id: str, active_plates: list):
        """Mark listings as inactive if they're no longer present"""
        listings_ref = self.db.collection('listings')
        query = listings_ref.where('dealer_id', '==', dealer_id).where('active', '==', True)
        
        for doc in query.stream():
            if doc.id not in active_plates:
                doc.reference.update({
                    'active': False,
                    'disappearance_date': datetime.now()
                })

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
            
            # Calculate reappearances
            history = self.db.collection('history')\
                .where('dealer_id', '==', dealer_id)\
                .stream()
            
            plates_history = {}
            for event in history:
                event_data = event.to_dict()
                plate = event_data['plate']
                if plate not in plates_history:
                    plates_history[plate] = []
                plates_history[plate].append(event_data)
            
            # Count plates that have reappeared
            stats['reappeared_plates'] = len([p for p in plates_history.values() if len(p) > 1])
            
            # Calculate average listing duration
            if stats['total_active'] > 0:
                total_duration = 0
                count = 0
                for plate_events in plates_history.values():
                    if len(plate_events) > 1:
                        first = min(e['appearance_date'] for e in plate_events)
                        last = max(e['appearance_date'] for e in plate_events)
                        duration = (last - first).days
                        total_duration += duration
                        count += 1
                
                if count > 0:
                    stats['avg_listing_duration'] = total_duration / count
            
        except Exception as e:
            st.error(f"Error calculating statistics: {str(e)}")
        
        return stats