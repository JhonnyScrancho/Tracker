from firebase_admin import credentials, initialize_app, firestore
from datetime import datetime
import streamlit as st

class FirebaseManager:
    def __init__(self):
        """Inizializza la connessione a Firebase"""
        try:
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": st.secrets["firebase"]["project_id"],
                "private_key": st.secrets["firebase"]["private_key"].replace('\\n', '\n'),
                "client_email": st.secrets["firebase"]["client_email"],
                "client_id": st.secrets["firebase"]["client_id"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
            })
            initialize_app(cred)
            self.db = firestore.client()
        except Exception as e:
            st.error(f"Errore connessione Firebase: {str(e)}")
            raise

    def save_dealer(self, dealer_id: str, url: str):
        """Salva o aggiorna i dati del concessionario"""
        self.db.collection('dealers').document(dealer_id).set({
            'url': url,
            'active': True,
            'last_update': datetime.now(),
            'created_at': datetime.now()
        }, merge=True)

    def get_dealers(self):
        """Recupera tutti i concessionari attivi"""
        dealers = self.db.collection('dealers')\
            .where('active', '==', True)\
            .stream()
        return [dealer.to_dict() | {'id': dealer.id} for dealer in dealers]

    def remove_dealer(self, dealer_id: str):
        """Rimuove un concessionario"""
        self.db.collection('dealers').document(dealer_id).update({
            'active': False,
            'removed_at': datetime.now()
        })

    def save_listings(self, listings: list):
        """Salva o aggiorna gli annunci"""
        batch = self.db.batch()
        for listing in listings:
            doc_ref = self.db.collection('listings').document(listing['id'])
            listing['last_update'] = datetime.now()
            
            # Se è un nuovo annuncio, aggiungi data creazione
            if not doc_ref.get().exists:
                listing['created_at'] = datetime.now()
            
            batch.set(doc_ref, listing, merge=True)
            
            # Registra evento nello storico
            history_ref = self.db.collection('history').document()
            history_data = {
                'listing_id': listing['id'],
                'dealer_id': listing['dealer_id'],
                'price': listing['original_price'],
                'discounted_price': listing['discounted_price'],
                'date': datetime.now(),
                'event': 'update'
            }
            batch.set(history_ref, history_data)
        
        batch.commit()

    def get_active_listings(self, dealer_id: str):
        """Recupera gli annunci attivi di un concessionario"""
        listings = self.db.collection('listings')\
            .where('dealer_id', '==', dealer_id)\
            .where('active', '==', True)\
            .stream()
        return [listing.to_dict() for listing in listings]

    def mark_inactive_listings(self, dealer_id: str, active_ids: list):
        """Marca come inattivi gli annunci non più presenti"""
        batch = self.db.batch()
        
        # Recupera annunci attivi non più presenti
        old_listings = self.db.collection('listings')\
            .where('dealer_id', '==', dealer_id)\
            .where('active', '==', True)\
            .stream()
        
        for listing in old_listings:
            if listing.id not in active_ids:
                # Marca annuncio come inattivo
                batch.update(listing.reference, {
                    'active': False,
                    'removed_at': datetime.now()
                })
                
                # Registra rimozione nello storico
                history_ref = self.db.collection('history').document()
                history_data = {
                    'listing_id': listing.id,
                    'dealer_id': dealer_id,
                    'date': datetime.now(),
                    'event': 'removed'
                }
                batch.set(history_ref, history_data)
        
        batch.commit()

    def get_dealer_stats(self, dealer_id: str):
        """Calcola statistiche per un concessionario"""
        stats = {
            'total_active': 0,
            'avg_listing_duration': 0,
            'total_discount_count': 0,
            'avg_discount_percentage': 0
        }
        
        # Conta annunci attivi
        active_listings = self.db.collection('listings')\
            .where('dealer_id', '==', dealer_id)\
            .where('active', '==', True)\
            .stream()
        
        listings_list = list(active_listings)
        stats['total_active'] = len(listings_list)
        
        # Calcola statistiche sconti
        total_discount = 0
        discount_count = 0
        
        for listing in listings_list:
            data = listing.to_dict()
            if data.get('discounted_price') and data.get('original_price'):
                discount = ((data['original_price'] - data['discounted_price']) / 
                          data['original_price'] * 100)
                total_discount += discount
                discount_count += 1
        
        stats['total_discount_count'] = discount_count
        if discount_count > 0:
            stats['avg_discount_percentage'] = total_discount / discount_count
        
        # Calcola durata media annunci
        if stats['total_active'] > 0:
            total_duration = 0
            count = 0
            
            for listing in listings_list:
                data = listing.to_dict()
                if data.get('created_at'):
                    duration = (datetime.now() - data['created_at']).days
                    total_duration += duration
                    count += 1
            
            if count > 0:
                stats['avg_listing_duration'] = total_duration / count
        
        return stats
    
    def get_dealer_history(self, dealer_id: str):
        """Recupera lo storico completo di un dealer"""
        history = self.db.collection('history')\
            .where('dealer_id', '==', dealer_id)\
            .order_by('date')\
            .stream()
        
        return [event.to_dict() for event in history]