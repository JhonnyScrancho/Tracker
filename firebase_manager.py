from firebase_admin import credentials, initialize_app, firestore
from datetime import datetime
import streamlit as st

class FirebaseManager:
    def __init__(self):
        """Inizializza la connessione a Firebase"""
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": st.secrets["firebase"]["project_id"],
            "private_key": st.secrets["firebase"]["private_key"],
            "client_email": st.secrets["firebase"]["client_email"],
        })
        initialize_app(cred)
        self.db = firestore.client()

    def save_dealer(self, dealer_id: str, name: str, url: str):
        """Salva o aggiorna i dati del concessionario"""
        dealer_ref = self.db.collection('dealers').document(dealer_id)
        dealer_ref.set({
            'name': name,
            'url': url,
            'last_update': datetime.now(),
            'active': True
        }, merge=True)

    def save_car(self, car_data: dict):
        """Salva o aggiorna i dati di un'auto"""
        # Usa la targa come ID del documento
        car_ref = self.db.collection('cars').document(car_data['plate'])
        
        # Aggiungi timestamp
        car_data['last_update'] = datetime.now()
        
        # Se è un nuovo inserimento
        if not car_ref.get().exists:
            car_data['first_seen'] = datetime.now()
        
        car_ref.set(car_data, merge=True)

    def save_history(self, plate: str, dealer_id: str, status: str):
        """Registra un evento nella storia dell'auto"""
        self.db.collection('history').add({
            'plate': plate,
            'dealer_id': dealer_id,
            'status': status,  # 'listed' o 'removed'
            'timestamp': datetime.now()
        })

    def get_dealer_cars(self, dealer_id: str):
        """Recupera tutte le auto di un concessionario"""
        cars = self.db.collection('cars')\
            .where('dealer_id', '==', dealer_id)\
            .where('active', '==', True)\
            .stream()
        return [car.to_dict() for car in cars]

    def get_car_history(self, plate: str):
        """Recupera la storia di un'auto"""
        history = self.db.collection('history')\
            .where('plate', '==', plate)\
            .order_by('timestamp')\
            .stream()
        return [event.to_dict() for event in history]

    def get_dealer_stats(self, dealer_id: str):
        """Calcola le statistiche di un concessionario"""
        # Auto attualmente in vendita
        active_cars = self.db.collection('cars')\
            .where('dealer_id', '==', dealer_id)\
            .where('active', '==', True)\
            .stream()
        
        # Storia delle riapparizioni
        history = self.db.collection('history')\
            .where('dealer_id', '==', dealer_id)\
            .stream()
        
        # Organizzo i dati per la targa
        plates_history = {}
        for event in history:
            event_data = event.to_dict()
            plate = event_data['plate']
            if plate not in plates_history:
                plates_history[plate] = []
            plates_history[plate].append(event_data)

        # Calcolo statistiche
        stats = {
            'active_cars': len(list(active_cars)),
            'total_plates': len(plates_history),
            'reappeared_plates': len([p for p in plates_history.values() if len(p) > 2]),
            'history': plates_history
        }
        
        return stats

    def mark_car_inactive(self, plate: str):
        """Marca un'auto come non più in vendita"""
        car_ref = self.db.collection('cars').document(plate)
        car_ref.update({
            'active': False,
            'removal_date': datetime.now()
        })
        
        # Registra nella storia
        self.save_history(plate, car_ref.get().to_dict()['dealer_id'], 'removed')

    def get_suspicious_patterns(self, dealer_id: str, threshold_days: int = 30):
        """Identifica pattern sospetti di riapparizione"""
        history = self.db.collection('history')\
            .where('dealer_id', '==', dealer_id)\
            .order_by('timestamp')\
            .stream()
        
        patterns = []
        current_plate = None
        last_timestamp = None
        
        for event in history:
            event_data = event.to_dict()
            
            if current_plate != event_data['plate']:
                current_plate = event_data['plate']
                last_timestamp = event_data['timestamp']
                continue
                
            days_difference = (event_data['timestamp'] - last_timestamp).days
            if days_difference < threshold_days:
                patterns.append({
                    'plate': current_plate,
                    'reappearance_interval': days_difference,
                    'last_seen': event_data['timestamp']
                })
                
            last_timestamp = event_data['timestamp']
            
        return patterns