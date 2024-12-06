import pandas as pd 
import streamlit as st
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class AlertSystem:
    def __init__(self, tracker):
        self.tracker = tracker
        self.initialize_session_state()

    def initialize_session_state(self):
        """Inizializza lo stato delle notifiche nella sessione"""
        if 'alerts' not in st.session_state:
            st.session_state.alerts = []
        if 'alert_rules' not in st.session_state:
            st.session_state.alert_rules = []

    def manage_alert_rules(self):
        """Gestisce le regole degli alert"""
        st.subheader("⚙️ Gestione Alert")
        
        # Form aggiunta regola
        with st.form("add_alert_rule"):
            col1, col2 = st.columns(2)
            
            with col1:
                alert_type = st.selectbox(
                    "Tipo Alert",
                    options=[
                        "price_change",
                        "reappearance",
                        "removal",
                        "suspicious_activity"
                    ]
                )
            
            with col2:
                threshold = st.number_input(
                    "Soglia",
                    min_value=0.0,
                    max_value=100.0,
                    value=10.0,
                    help="Soglia per l'attivazione dell'alert (es. variazione % prezzo)"
                )
            
            enabled = st.checkbox("Attivo", value=True)
            
            if st.form_submit_button("Aggiungi Regola"):
                new_rule = {
                    'id': datetime.now().timestamp(),
                    'type': alert_type,
                    'threshold': threshold,
                    'enabled': enabled,
                    'created_at': datetime.now()
                }
                st.session_state.alert_rules.append(new_rule)
                st.success("✅ Regola aggiunta")
        
        # Lista regole esistenti
        if st.session_state.alert_rules:
            st.write("📋 Regole Configurate")
            
            for rule in st.session_state.alert_rules:
                with st.expander(f"Regola: {rule['type']}"):
                    st.write(f"Soglia: {rule['threshold']}%")
                    st.write(f"Stato: {'Attivo' if rule['enabled'] else 'Disattivo'}")
                    if st.button("❌ Rimuovi", key=f"remove_{rule['id']}"):
                        st.session_state.alert_rules.remove(rule)
                        st.success("✅ Regola rimossa")
                        st.rerun()

    def check_alert_conditions(self, dealer_id: str):
        """Controlla le condizioni per gli alert"""
        if not st.session_state.alert_rules:
            return
            
        history = self.tracker.get_dealer_history(dealer_id)
        if not history:
            return
            
        # Analizza ultimi eventi
        recent_events = [
            event for event in history 
            if event['date'] >= datetime.now() - timedelta(hours=24)
        ]
        
        for rule in st.session_state.alert_rules:
            if not rule['enabled']:
                continue
                
            if rule['type'] == 'price_change':
                self._check_price_changes(recent_events, rule['threshold'])
            elif rule['type'] == 'reappearance':
                self._check_reappearances(recent_events)
            elif rule['type'] == 'removal':
                self._check_removals(recent_events)
            elif rule['type'] == 'suspicious_activity':
                self._check_suspicious_activity(recent_events, rule['threshold'])

    def _check_price_changes(self, events: List[Dict], threshold: float):
        """Controlla variazioni di prezzo significative"""
        price_changes = [
            event for event in events 
            if event['event'] == 'price_changed'
        ]
        
        for event in price_changes:
            if 'price' in event and 'previous_price' in event:
                variation = abs((event['price'] - event['previous_price']) / event['previous_price'] * 100)
                if variation >= threshold:
                    self.add_notification(
                        f"Variazione prezzo significativa ({variation:.1f}%) per annuncio {event['listing_id']}",
                        'price_alert',
                        event
                    )

    def _check_reappearances(self, events: List[Dict]):
        """Controlla riapparizioni di annunci"""
        reappearances = [
            event for event in events 
            if event['event'] == 'reappeared'
        ]
        
        for event in reappearances:
            self.add_notification(
                f"Annuncio riapparso: {event['listing_id']}",
                'reappearance_alert',
                event
            )

    def _check_removals(self, events: List[Dict]):
        """Controlla rimozioni di annunci"""
        removals = [
            event for event in events 
            if event['event'] == 'removed'
        ]
        
        if len(removals) >= 3:  # Alert se troppe rimozioni in 24h
            self.add_notification(
                f"Rilevate {len(removals)} rimozioni nelle ultime 24 ore",
                'removal_alert',
                {'removals': removals}
            )

    def _check_suspicious_activity(self, events: List[Dict], threshold: float):
        """Controlla attività sospette"""
        # Raggruppa eventi per annuncio
        from collections import defaultdict
        events_by_listing = defaultdict(list)
        
        for event in events:
            events_by_listing[event['listing_id']].append(event)
        
        # Cerca pattern sospetti
        for listing_id, listing_events in events_by_listing.items():
            if len(listing_events) >= threshold:
                self.add_notification(
                    f"Attività sospetta rilevata per annuncio {listing_id}",
                    'suspicious_alert',
                    {'events': listing_events}
                )

    def add_notification(self, message: str, alert_type: str, details: Dict):
        """Aggiunge una nuova notifica"""
        notification = {
            'id': datetime.now().timestamp(),
            'message': message,
            'type': alert_type,
            'details': details,
            'timestamp': datetime.now(),
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

def show_alerts_dashboard(alert_system):
    """Mostra dashboard degli alert"""
    st.title("📊 Dashboard Alert")
    
    # Gestione regole
    alert_system.manage_alert_rules()
    
    # Storico alert
    if alert_system.alert_history:
        st.subheader("📜 Storico Alert")
        
        df = pd.DataFrame(alert_system.alert_history)
        df['date'] = pd.to_datetime(df['timestamp'])
        
        # Grafico distribuzione
        fig = go.Figure()
        
        # Distribuzione alert per tipo
        alert_counts = df['type'].value_counts()
        
        fig.add_trace(go.Bar(
            x=alert_counts.index,
            y=alert_counts.values,
            text=alert_counts.values,
            textposition='auto',
        ))
        
        fig.update_layout(
            title="Distribuzione Alert per Tipo",
            xaxis_title="Tipo Alert",
            yaxis_title="Numero Alert",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Timeline alert
        timeline_fig = go.Figure()
        
        df_timeline = df.groupby([df['date'].dt.date, 'type']).size().reset_index(name='count')
        
        for alert_type in df['type'].unique():
            type_data = df_timeline[df_timeline['type'] == alert_type]
            timeline_fig.add_trace(go.Scatter(
                x=type_data['date'],
                y=type_data['count'],
                name=alert_type,
                mode='lines+markers'
            ))
            
        timeline_fig.update_layout(
            title="Timeline Alert",
            xaxis_title="Data",
            yaxis_title="Numero Alert",
            height=400,
            showlegend=True
        )
        
        st.plotly_chart(timeline_fig, use_container_width=True)
        
        # Tabella dettaglio
        st.subheader("📋 Dettaglio Alert")
        
        df_display = df[['message', 'type', 'timestamp']].copy()
        df_display['timestamp'] = df_display['timestamp'].dt.strftime('%d/%m/%Y %H:%M')
        df_display.columns = ['Messaggio', 'Tipo', 'Data']
        
        st.dataframe(
            df_display.sort_values('Data', ascending=False),
            hide_index=True,
            use_container_width=True
        )
        
        # Metriche aggregate
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_alerts = len(df)
            st.metric("Totale Alert", total_alerts)
            
        with col2:
            alerts_today = len(df[df['date'].dt.date == datetime.now().date()])
            st.metric("Alert Oggi", alerts_today)
            
        with col3:
            avg_daily = len(df) / (df['date'].max() - df['date'].min()).days
            st.metric("Media Giornaliera", f"{avg_daily:.1f}")

def export_alert_report(alert_history: List[Dict]) -> pd.DataFrame:
    """Genera report dettagliato degli alert"""
    if not alert_history:
        return pd.DataFrame()
        
    # Prepara dati
    rows = []
    for alert in alert_history:
        row = {
            'Data': alert['timestamp'],
            'Tipo': alert['type'],
            'Messaggio': alert['message']
        }
        
        # Aggiungi dettagli specifici per tipo
        details = alert['details']
        if alert['type'] == 'price_alert':
            row['Variazione'] = f"{details.get('variation', 0):.1f}%"
            row['Prezzo Precedente'] = details.get('previous_price', 'N/D')
            row['Nuovo Prezzo'] = details.get('price', 'N/D')
            
        elif alert['type'] == 'reappearance_alert':
            row['Giorni Assente'] = details.get('days_gone', 'N/D')
            row['Variazione Prezzo'] = details.get('price_variation', 'N/D')
            
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    # Calcola metriche aggiuntive
    summary = {
        'periodo_analisi': f"{df['Data'].min().strftime('%d/%m/%Y')} - {df['Data'].max().strftime('%d/%m/%Y')}",
        'totale_alert': len(df),
        'distribuzione_tipi': df['Tipo'].value_counts().to_dict(),
        'alert_per_giorno': len(df) / (df['Data'].max() - df['Data'].min()).days
    }
    
    return df, summary

def analyze_alert_patterns(alert_history: List[Dict]) -> Dict:
    """Analizza pattern negli alert"""
    if not alert_history:
        return {}
        
    df = pd.DataFrame(alert_history)
    patterns = {
        'time_patterns': {},
        'correlation_patterns': {},
        'frequency_patterns': {}
    }
    
    # Pattern temporali
    df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
    patterns['time_patterns'] = {
        'peak_hours': df.groupby('hour').size().nlargest(3).index.tolist(),
        'daily_distribution': df.groupby('hour').size().to_dict()
    }
    
    # Pattern correlazione
    if len(df) >= 2:
        alert_matrix = pd.crosstab(df['type'], df['type'].shift())
        patterns['correlation_patterns'] = {
            'common_sequences': alert_matrix.values.tolist(),
            'most_common_pair': alert_matrix.max().idxmax()
        }
    
    # Pattern frequenza
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    daily_counts = df.groupby('date').size()
    patterns['frequency_patterns'] = {
        'avg_daily': daily_counts.mean(),
        'std_daily': daily_counts.std(),
        'peak_days': daily_counts.nlargest(3).index.tolist()
    }
    
    return patterns