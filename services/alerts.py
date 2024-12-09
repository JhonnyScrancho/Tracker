import pandas as pd 
import streamlit as st
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from utils.datetime_utils import calculate_date_diff, get_current_time, normalize_datetime, normalize_df_dates

class AlertSystem:
    def __init__(self, tracker):
        self.tracker = tracker
        self.initialize_session_state()

    def initialize_session_state(self):
        """Inizializza lo stato delle notifiche nella sessione"""
        if 'notifications' not in st.session_state:
            st.session_state.notifications = []
        if 'read_notifications' not in st.session_state:
            st.session_state.read_notifications = set()
        if 'last_check' not in st.session_state:
            st.session_state.last_check = {}
        if 'alert_settings' not in st.session_state:
            st.session_state.alert_settings = {
                'price_threshold': 20,  # Variazione prezzo % 
                'removal_threshold': 5,  # Numero rimozioni in 24h
                'check_interval': 3600,  # Secondi tra controlli
                'enabled_types': {
                    'price_alert': True,
                    'duplicate': True,
                    'removal_alert': True,
                    'reappearance': True
                }
            }

    def add_notification(self, message: str, alert_type: str, details: Dict):
        """
        Aggiunge una nuova notifica
        
        Args:
            message: Messaggio della notifica
            alert_type: Tipo di alert
            details: Dettagli aggiuntivi dell'alert
        """
        if not st.session_state.alert_settings['enabled_types'].get(alert_type, True):
            return
            
        current_time = get_current_time()
        notification_id = f"{alert_type}_{current_time.timestamp()}"
        
        notification = {
            'id': notification_id,
            'message': message,
            'type': alert_type,
            'details': details,
            'timestamp': current_time,
            'priority': self._get_alert_priority(alert_type, details)
        }
        
        if not self._is_duplicate_notification(notification):
            st.session_state.notifications.append(notification)

    def mark_as_read(self, notification_id: str):
        """Marca una notifica come letta"""
        st.session_state.read_notifications.add(notification_id)

    def clear_all_notifications(self):
        """Rimuove tutte le notifiche"""
        st.session_state.notifications = []
        st.session_state.read_notifications = set()

    def get_unread_notifications(self):
        """Recupera le notifiche non lette ordinate per priorità"""
        unread = [n for n in st.session_state.notifications 
                 if n['id'] not in st.session_state.read_notifications]
        return sorted(unread, 
                     key=lambda x: (-x['priority'], x['timestamp']), 
                     reverse=True)

    def show_notifications(self):
        """Mostra le notifiche attive con gestione stato"""
        unread = self.get_unread_notifications()
        if not unread:
            return
            
        st.sidebar.markdown("---")
        col1, col2 = st.sidebar.columns([3, 1])
        
        with col1:
            st.subheader("🔔 Notifiche")
        with col2:
            if st.button("🗑️ Pulisci", key="clear_notifications"):
                self.clear_all_notifications()
                st.rerun()
        
        for notification in unread:
            with st.sidebar.expander(
                self._format_notification_title(notification), 
                expanded=True
            ):
                self._render_notification_content(notification)
                
                col1, col2 = st.columns([3, 1])
                with col2:
                    if st.button("✓", key=f"mark_read_{notification['id']}"):
                        self.mark_as_read(notification['id'])
                        st.rerun()

    def check_alert_conditions(self, dealer_id: str):
        """Controlla e genera alert per un dealer"""
        try:
            # Verifica intervallo minimo tra controlli
            current_time = get_current_time()
            last_check = st.session_state.last_check.get(dealer_id)
            
            if last_check:
                time_diff = calculate_date_diff(last_check, current_time)
                if time_diff and time_diff < st.session_state.alert_settings['check_interval']:
                    return

            # Recupera dati necessari
            listings = self.tracker.get_active_listings(dealer_id)
            if not listings:
                return

            # Check duplicati
            if st.session_state.alert_settings['enabled_types']['duplicate']:
                self._check_duplicates(listings)

            # Check variazioni prezzo
            if st.session_state.alert_settings['enabled_types']['price_alert']:
                self._check_price_variations(listings)

            # Check rimozioni
            if st.session_state.alert_settings['enabled_types']['removal_alert']:
                self._check_removals(dealer_id)

            # Check riapparizioni
            if st.session_state.alert_settings['enabled_types']['reappearance']:
                self._check_reappearances(dealer_id)

            # Aggiorna timestamp ultimo controllo
            st.session_state.last_check[dealer_id] = current_time

        except Exception as e:
            st.error(f"❌ Errore nel controllo alert: {str(e)}")

    def _check_duplicates(self, listings: List[Dict]):
        """Controlla presenza di duplicati"""
        duplicates = [l for l in listings if l.get('duplicate_of')]
        if duplicates:
            self.add_notification(
                f"Rilevati {len(duplicates)} annunci duplicati",
                'duplicate',
                {
                    'listings': [d['id'] for d in duplicates],
                    'details': [{
                        'id': d['id'],
                        'duplicate_of': d['duplicate_of'],
                        'title': d.get('title', 'N/D'),
                        'price': d.get('original_price')
                    } for d in duplicates]
                }
            )

    def _check_price_variations(self, listings: List[Dict]):
        """Controlla variazioni significative dei prezzi"""
        threshold = st.session_state.alert_settings['price_threshold']
        
        for listing in listings:
            if listing.get('price_history'):
                history = listing['price_history']
                if len(history) >= 2:
                    latest = history[-1]['price']
                    previous = history[-2]['price']
                    variation = abs((latest - previous) / previous * 100)
                    
                    if variation > threshold:
                        self.add_notification(
                            f"Variazione prezzo {variation:.1f}% per {listing.get('title', listing['id'])}",
                            'price_alert',
                            {
                                'listing_id': listing['id'],
                                'title': listing.get('title'),
                                'variation': variation,
                                'old_price': previous,
                                'new_price': latest,
                                'timestamp': get_current_time()
                            }
                        )

    def _check_removals(self, dealer_id: str):
        """Controlla rimozioni recenti"""
        threshold = st.session_state.alert_settings['removal_threshold']
        current_time = get_current_time()
        cutoff_time = current_time - timedelta(hours=24)
        
        history = self.tracker.get_dealer_history(dealer_id)
        if history:
            df_history = pd.DataFrame(history)
            df_history = normalize_df_dates(df_history)
            
            recent_removals = df_history[
                (df_history['event'] == 'removed') & 
                (df_history['date'] > cutoff_time)
            ]
            
            if len(recent_removals) >= threshold:
                self.add_notification(
                    f"Rilevate {len(recent_removals)} rimozioni nelle ultime 24h",
                    'removal_alert',
                    {
                        'removals': recent_removals.to_dict('records'),
                        'count': len(recent_removals),
                        'threshold': threshold,
                        'period': '24h'
                    }
                )

    def _check_reappearances(self, dealer_id: str):
        """Controlla veicoli riapparsi"""
        history = self.tracker.get_dealer_history(dealer_id)
        if not history:
            return
            
        df_history = pd.DataFrame(history)
        df_history = normalize_df_dates(df_history)
        reappeared = df_history[df_history['event'] == 'reappeared']
        
        for listing_id in reappeared['listing_id'].unique():
            listing_history = df_history[df_history['listing_id'] == listing_id]
            reapp_count = len(listing_history[listing_history['event'] == 'reappeared'])
            
            if reapp_count > 1:
                self.add_notification(
                    f"Veicolo riapparso {reapp_count} volte",
                    'reappearance',
                    {
                        'listing_id': listing_id,
                        'reappearance_count': reapp_count,
                        'history': listing_history.to_dict('records')
                    }
                )

    def _get_alert_priority(self, alert_type: str, details: Dict) -> int:
        """Determina la priorità dell'alert"""
        priorities = {
            'price_alert': lambda d: 2 if d.get('variation', 0) > 30 else 1,
            'duplicate': lambda d: 2 if len(d.get('listings', [])) > 3 else 1,
            'removal_alert': lambda d: 2 if d.get('count', 0) > 10 else 1,
            'reappearance': lambda d: 2 if d.get('reappearance_count', 0) > 3 else 1
        }
        
        priority_func = priorities.get(alert_type, lambda d: 1)
        return priority_func(details)

    def _is_duplicate_notification(self, new_notification: Dict) -> bool:
        """Verifica se una notifica simile esiste già"""
        current_time = get_current_time()
        
        for existing in st.session_state.notifications[-10:]:
            if (existing['type'] == new_notification['type'] and
                existing['details'].get('listing_id') == 
                new_notification['details'].get('listing_id')):
                
                time_diff = calculate_date_diff(existing['timestamp'], current_time)
                if time_diff and time_diff < 1:  # Meno di un giorno
                    return True
        return False

    def _format_notification_title(self, notification: Dict) -> str:
        """Formatta il titolo della notifica con icona appropriata"""
        icons = {
            'price_alert': '💰',
            'duplicate': '🔄',
            'removal_alert': '❌',
            'reappearance': '↩️'
        }
        priority_marker = '🔴' if notification['priority'] > 1 else '🟡'
        icon = icons.get(notification['type'], '❓')
        return f"{priority_marker} {icon} {notification['message']}"

    def _render_notification_content(self, notification: Dict):
        """Renderizza il contenuto della notifica in base al tipo"""
        details = notification['details']
        
        st.write(f"Data: {notification['timestamp'].strftime('%d/%m/%Y %H:%M')}")
        
        if notification['type'] == 'price_alert':
            st.write(f"Veicolo: {details.get('title', 'N/D')}")
            st.write(f"Variazione: {details['variation']:.1f}%")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"Prezzo precedente: €{details['old_price']:,.0f}")
            with col2:
                st.write(f"Nuovo prezzo: €{details['new_price']:,.0f}")
                
        elif notification['type'] == 'duplicate':
            st.write(f"Annunci coinvolti: {len(details['listings'])}")
            for dup in details.get('details', []):
                st.write(f"• {dup['title']} (€{dup['price']:,.0f})")
                
        elif notification['type'] == 'removal_alert':
            st.write(f"Totale rimozioni: {details['count']}")
            st.write(f"Periodo: ultime {details['period']}")
            
        elif notification['type'] == 'reappearance':
            st.write(f"Numero riapparizioni: {details['reappearance_count']}")
            if 'history' in details:
                last_event = details['history'][-1]
                st.write(f"Ultima riapparizione: {last_event['date']}")

        if 'listing_id' in details:
            st.caption(f"ID Annuncio: {details['listing_id']}")