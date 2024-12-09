import pandas as pd 
import streamlit as st
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from utils.datetime_utils import get_current_time, normalize_datetime, normalize_df_dates

class AlertSystem:
    def __init__(self, tracker):
        self.tracker = tracker
        self.initialize_session_state()

    def initialize_session_state(self):
        """Inizializza lo stato delle notifiche nella sessione"""
        if 'alerts' not in st.session_state:
            st.session_state.alerts = []

    def check_alert_conditions(self, dealer_id: str):
        """Controlla e genera alert per un dealer"""
        try:
            # Recupera dati con timestamp normalizzati
            current_time = get_current_time()
            listings = self.tracker.get_active_listings(dealer_id)
            if not listings:
                return
            
            # Check duplicati
            duplicates = [l for l in listings if l.get('duplicate_of')]
            if duplicates:
                self.add_notification(
                    f"Rilevati {len(duplicates)} annunci duplicati per il dealer {dealer_id}",
                    'duplicate',
                    {'listings': [d['id'] for d in duplicates]}
                )

            # Check variazioni prezzo
            for listing in listings:
                if listing.get('price_history'):
                    history = listing['price_history']
                    if len(history) >= 2:
                        latest = history[-1]['price']
                        previous = history[-2]['price']
                        variation = abs((latest - previous) / previous * 100)
                        if variation > 20:
                            self.add_notification(
                                f"Variazione prezzo significativa ({variation:.1f}%) per annuncio {listing['id']}",
                                'price_alert',
                                {
                                    'listing_id': listing['id'],
                                    'variation': variation,
                                    'old_price': previous,
                                    'new_price': latest
                                }
                            )

            # Check rimozioni
            cutoff_time = current_time - timedelta(hours=24)
            removed = self.tracker.get_dealer_history(dealer_id)
            if removed:
                df_removed = pd.DataFrame(removed)
                df_removed = normalize_df_dates(df_removed)
                recent_removals = df_removed[
                    (df_removed['event'] == 'removed') & 
                    (df_removed['date'] > cutoff_time)
                ]
                
                if len(recent_removals) >= 5:
                    self.add_notification(
                        f"Rilevate {len(recent_removals)} rimozioni nelle ultime 24 ore",
                        'removal_alert',
                        {'removals': recent_removals.to_dict('records')}
                    )

        except Exception as e:
            st.error(f"❌ Errore nel controllo alert: {str(e)}")

    def add_notification(self, message: str, alert_type: str, details: Dict):
        """Aggiunge una nuova notifica"""
        notification = {
            'id': datetime.now().timestamp(),
            'message': message,
            'type': alert_type,
            'details': details,
            'timestamp': get_current_time(),
            'read': False
        }
        
        st.session_state.alerts.append(notification)

    def show_notifications(self):
        """Mostra le notifiche attive"""
        if not st.session_state.alerts:
            return
            
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔔 Notifiche")
        
        for alert in sorted(
            st.session_state.alerts,
            key=lambda x: x['timestamp'],
            reverse=True
        ):
            if not alert['read']:
                with st.sidebar.expander(alert['message'], expanded=True):
                    st.write(f"Tipo: {alert['type']}")
                    st.write(f"Data: {alert['timestamp'].strftime('%d/%m/%Y %H:%M')}")
                    if st.button("✓ Segna come letta", key=f"mark_read_{alert['id']}"):
                        alert['read'] = True
                        st.rerun()

    def track_alert_history(self):
        """Mantiene uno storico degli alert"""
        if not hasattr(self, 'alert_history'):
            self.alert_history = []
            
        # Aggiungi nuovi alert allo storico
        for alert in st.session_state.alerts:
            if alert['read'] and alert not in self.alert_history:
                self.alert_history.append(alert)
        
        # Rimuovi alert letti dalla lista attiva
        st.session_state.alerts = [
            alert for alert in st.session_state.alerts 
            if not alert['read']
        ]

    def show_alerts(alerts: List[Dict]):
        """Visualizza gli alert attivi"""
        if not alerts:
            return

        st.sidebar.subheader("🚨 Alert Attivi")
        
        for alert in alerts:
            color = {
                'high': '#dc3545',
                'warning': '#ffc107',
                'info': '#0dcaf0'
            }.get(alert['severity'], '#6c757d')

            st.sidebar.markdown(
                f"""
                <div style="padding:10px;border-left:4px solid {color};margin-bottom:10px;">
                    <strong>{alert['message']}</strong><br>
                    <small>Tipo: {alert['type']}</small>
                </div>
                """,
                unsafe_allow_html=True
            )

    def get_recent_removals(tracker, dealer_id: str, hours: int = 24) -> List[Dict]:
        """Recupera annunci rimossi recentemente"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        try:
            history = tracker.db.collection('history')\
                .where('dealer_id', '==', dealer_id)\
                .where('event', '==', 'removed')\
                .where('date', '>', cutoff)\
                .stream()
                
            return [doc.to_dict() for doc in history]
            
        except Exception as e:
            st.error(f"❌ Errore recupero rimozioni: {str(e)}")
            return []    