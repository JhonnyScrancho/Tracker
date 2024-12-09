from datetime import datetime
import time
import streamlit as st
import sys
from pathlib import Path

from utils.formatting import format_dealer_name

# Aggiungi la directory root al PYTHONPATH
root_dir = Path(__file__).parent
sys.path.append(str(root_dir))

# Import componenti esistenti
from components.sidebar import show_sidebar
from services.tracker import AutoTracker

# Nuovi import
from components.anomaly_dashboard import show_anomaly_dashboard
from services.analytics_service import AnalyticsService
from services.alerts import AlertSystem
from components.reports import generate_weekly_report, show_trend_analysis
from components.vehicle_comparison import show_comparison_view

st.set_page_config(
    page_title="Auto Tracker",
    page_icon="🚗",
    layout="wide"
)

# CSS
st.markdown("""
    <style>
    /* Container base */
    .stExpander { width: 100% !important; }
    .element-container { width: 100% !important; }
    .stMarkdown { width: 100% !important; }

    /* Log Container con altezza fissa */
    .log-container {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 0.25rem;
        padding: 1rem;
        margin: 1rem 0;
        height: 500px;
        overflow-y: auto;
        overflow-x: hidden;
        width: 100% !important;
        font-family: monospace;
        font-size: 0.875rem;
        line-height: 1.4;
        white-space: pre-wrap;
        word-wrap: break-word;
    }

    /* Log entries */
    .log-entry {
        margin: 0.2rem 0;
        padding: 0.2rem 0;
        border-bottom: 1px solid #eee;
    }
    .log-info { color: #0d6efd; }
    .log-success { color: #28a745; }
    .log-warning { color: #ffc107; }
    .log-error { color: #dc3545; }

    /* DataFrames e Tabelle */
    .dataframe {
        width: 100%;
        margin: 0.5em 0;
        border-collapse: collapse;
        font-size: 14px;
    }
    .dataframe th {
        background-color: var(--background-color);
        padding: 8px;
        font-weight: 600;
        text-align: left;
        border-bottom: 2px solid #dee2e6;
        white-space: nowrap;
    }
    .dataframe td {
        padding: 8px;
        vertical-align: middle;
        border-bottom: 1px solid #eee;
    }

    /* Colonne specifiche */
    .col-foto { width: auto !important; padding: 5px !important; }
    .col-id { width: auto !important; }
    .col-targa { width: auto !important; text-align: center !important; }
    .col-modello { min-width: auto !important; }
    .col-prezzo { width: auto !important; text-align: right !important; }
    .col-km { width: auto !important; text-align: right !important; }
    .col-data { width: auto !important; text-align: center !important; }
    .col-carburante { width: auto !important; }
    .col-link { width: auto !important; text-align: center !important; }

    /* Immagini e ID */
    .table-img {
        max-width: 200px !important;
        height: auto;
        object-fit: cover;
        border-radius: 4px;
    }
    .listing-id {
        font-family: monospace;
        border-radius: 4px;
        font-size: 0.8em;
    }

    /* Sidebar e Navigation */
    .dealer-button {
        margin-bottom: 0.5rem;
        width: 100%;
    }

    /* Notifications */
    .notification {
        padding: 1rem;
        margin-bottom: 1rem;
        border-radius: 0.5rem;
    }
    .notification.success {
        background-color: #d1fae5;
        border: 1px solid #34d399;
    }
    .notification.error {
        background-color: #fee2e2;
        border: 1px solid #f87171;
    }

    /* Anomalie e Variazioni */
    .price-anomaly { 
        color: #dc3545 !important; 
        font-weight: bold; 
    }
    .mileage-anomaly { 
        color: #dc3545 !important; 
        font-weight: bold; 
    }
    .plate-edited { 
        background-color: #fff3cd; 
    }
    .reappeared { 
        background-color: #cfe2ff; 
    }
    .discount { 
        color: #198754 !important; 
    }

    /* Visualizzazione delle variazioni */
    .variation-positive {
        color: #198754;
        font-weight: bold;
    }
    .variation-negative {
        color: #dc3545;
        font-weight: bold;
    }

    /* Stili di base per metriche */
    .metric-container {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
    }

    /* Stili tabella annunci rimossi */
    .removed-listing {
        background-color: #fff3cd;
        padding: 0.5rem;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)

class AutoTrackerApp:
    def __init__(self):
        """Inizializzazione dell'applicazione"""
        self.tracker = AutoTracker()
        self.analytics = AnalyticsService(self.tracker)
        self.alert_system = AlertSystem(self.tracker)
        self.init_session_state()

    def init_session_state(self):
        """Inizializza lo stato dell'applicazione"""
        if 'app_state' not in st.session_state:
            st.session_state.app_state = {
                'update_status': {},
                'settings_status': {},
                'notifications': [],
                'selected_view': 'dashboard'
            }

    def show_notification(self, message, type="info"):
        """Mostra una notifica all'utente"""
        if type == "success":
            st.success(message)
        elif type == "error":
            st.error(message)
        else:
            st.info(message)

    def check_scheduler(self):
        """Controlla ed esegue eventuali task schedulati"""
        try:
            # Recupera configurazione scheduler
            scheduler_config = self.tracker.get_scheduler_config()
            
            if not scheduler_config or not scheduler_config.get('enabled'):
                return
                
            now = datetime.now()
            last_update = scheduler_config.get('last_update')
            
            if not last_update or last_update.date() < now.date():
                scheduled_time = now.replace(
                    hour=scheduler_config.get('hour', 1),
                    minute=scheduler_config.get('minute', 0)
                )

                if now >= scheduled_time:
                    dealers = self.tracker.get_dealers()
                    
                    for dealer in dealers:
                        try:
                            # Esegue lo scrape
                            listings = self.tracker.scrape_dealer(dealer['url'])
                            if listings:
                                self.tracker.save_listings(listings)
                                self.tracker.mark_inactive_listings(
                                    dealer['id'], 
                                    [l['id'] for l in listings]
                                )
                                
                                # Nuovo: analizza anomalie dopo aggiornamento
                                self.alert_system.check_alert_conditions(dealer['id'])
                                
                        except Exception as e:
                            st.error(f"❌ Errore scrape dealer {dealer['id']}: {str(e)}")
                            continue

                    self.tracker.save_scheduler_config({
                        'last_update': now
                    })
                    
                    st.success(f"✅ Aggiornamento completato per {len(dealers)} dealer")
                
        except Exception as e:
            st.error(f"❌ Errore durante l'esecuzione scheduler: {str(e)}")

    
    def run(self):
        """Esegue l'applicazione"""
        dealers = self.tracker.get_dealers()
        
        # Controlla scheduler e mostra notifiche
        self.check_scheduler()
        self.alert_system.show_notifications()
        
        # Mostra la sidebar
        selected_dealer = show_sidebar(self.tracker)

        # Main content
        if not dealers:
            st.title("👋 Benvenuto in Auto Tracker")
            st.info("Aggiungi un concessionario nella sezione impostazioni per iniziare")
            self.show_settings()
        else:
            # Controlla query params
            dealer_id = st.query_params.get("dealer_id")
            view = st.query_params.get("view", "dashboard")

            if dealer_id == "settings":
                self.show_settings()
            elif dealer_id:
                # Menu di navigazione per viste dealer
                view = st.radio(
                    "Seleziona Vista",
                    ["Dashboard", "Anomalie", "Confronti", "Report", "Analisi"],
                    horizontal=True,
                    key="dealer_view"
                )
                
                if view == "Dashboard":
                    self.show_dealer_view(dealer_id)
                elif view == "Anomalie":
                    show_anomaly_dashboard(self.tracker, dealer_id)
                elif view == "Confronti":
                    listings = self.tracker.get_active_listings(dealer_id)
                    show_comparison_view(self.tracker, listings)
                elif view == "Report":
                    report = generate_weekly_report(self.tracker, dealer_id)
                    show_trend_analysis(self.tracker.get_dealer_history(dealer_id))
                elif view == "Analisi":
                    insights = self.analytics.get_market_insights(dealer_id)
                    self.show_market_analysis(dealer_id, insights)
            else:
                self.show_home()

            self._handle_notifications()

        # Footer con info aggiornamento
        st.divider()
        with st.container():
            col1, col2 = st.columns(2)
            with col1:
                scheduler_config = self.tracker.get_scheduler_config()
                if scheduler_config and scheduler_config.get('enabled'):
                    st.caption("🤖 Aggiornamento automatico attivo")
                else:
                    st.caption("🤖 Aggiornamento automatico disattivato")
            
            with col2:
                if scheduler_config:
                    last_update = scheduler_config.get('last_update')
                    if last_update:
                        st.caption(f"📅 Ultimo aggiornamento: {last_update.strftime('%d/%m/%Y %H:%M')}")

    
    def show_market_analysis(self, dealer_id: str, insights: dict):
        """Mostra analisi di mercato dettagliata"""
        st.title("📊 Analisi di Mercato")
        
        # Overview
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "Tasso Riapparizioni",
                f"{insights['patterns'].get('reappearance_rate', 0):.1f}%"
            )
        with col2:
            st.metric(
                "Cambi Prezzo/Giorno",
                f"{insights['patterns'].get('avg_price_changes', 0):.1f}"
            )
        with col3:
            st.metric(
                "Durata Media Annunci",
                f"{insights['patterns'].get('listing_duration', 0):.0f} giorni"
            )
        
        # Raccomandazioni
        if insights.get('recommendations'):
            st.subheader("📋 Raccomandazioni")
            for rec in insights['recommendations']:
                with st.expander(f"{'🔴' if rec['priority'] == 'high' else '🟡'} {rec['message']}"):
                    st.write(f"Priorità: {rec['priority'].title()}")
                    st.write(f"Tipo: {rec['type']}")

        # Pattern sospetti
        if insights.get('suspicious'):
            st.subheader("⚠️ Pattern Sospetti")
            for pattern in insights['suspicious']:
                with st.expander(f"{pattern['type'].replace('_', ' ').title()}"):
                    if 'listing_id' in pattern:
                        st.write(f"Annuncio: {pattern['listing_id']}")
                    if 'confidence' in pattern:
                        st.progress(pattern['confidence'])
    
    
    def show_home(self):
        """Mostra la home page"""
        st.title("🏠 Dashboard")
        
        dealers = self.tracker.get_dealers()
        if not dealers:
            st.info("👋 Aggiungi un concessionario per iniziare")
            return
        
        # Bottone aggiornamento massivo
        if st.button("🔄 Aggiorna Tutto", use_container_width=False):
            with st.status("⏳ Aggiornamento in corso...", expanded=True) as status:
                try:
                    total_listings = 0
                    
                    # Aggiorna ogni dealer
                    for dealer in dealers:
                        st.write(f"📥 Aggiornamento {dealer['url']}...")
                        try:
                            listings = self.tracker.scrape_dealer(dealer['url'])
                            if listings:
                                # Salva nuovi annunci
                                self.tracker.save_listings(listings)
                                # Marca inattivi quelli non più presenti
                                self.tracker.mark_inactive_listings(dealer['id'], [l['id'] for l in listings])
                                total_listings += len(listings)
                                st.success(f"✅ Aggiornati {len(listings)} annunci per {dealer['url']}")
                            else:
                                st.warning(f"⚠️ Nessun annuncio trovato per {dealer['url']}")
                        except Exception as e:
                            st.error(f"❌ Errore per {dealer['url']}: {str(e)}")
                            continue
                    
                    status.update(label=f"✅ Aggiornamento completato! Processati {total_listings} annunci totali", state="complete")
                    
                    # Aggiorna timestamp ultimo aggiornamento
                    self.tracker.save_scheduler_config({
                        'last_update': datetime.now()
                    })
                    
                except Exception as e:
                    status.update(label=f"❌ Errore durante l'aggiornamento: {str(e)}", state="error")
            
        # Statistiche globali
        total_cars = 0
        total_value = 0
        
        for dealer in dealers:
            listings = self.tracker.get_active_listings(dealer['id'])
            total_cars += len(listings)
            total_value += sum(l.get('original_price', 0) for l in listings if l.get('original_price'))
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🏢 Concessionari", len(dealers))
        with col2:    
            st.metric("🚗 Auto Totali", total_cars)
        with col3:
            st.metric("💰 Valore Totale", f"€{total_value:,.0f}".replace(",", "."))
            
        # Lista dealers
        st.subheader("🏢 Concessionari Monitorati")
        
        for dealer in dealers:
            with st.expander(f"**{format_dealer_name(dealer['url'])}** - {dealer['url']}", expanded=False):
                if dealer.get('last_update'):
                    st.caption(f"Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")
                    
                listings = self.tracker.get_active_listings(dealer['id'])
                if listings:
                    st.write(f"📊 {len(listings)} annunci attivi")
                    
                    # Stats concessionario
                    dealer_value = sum(l.get('original_price', 0) for l in listings if l.get('original_price'))
                    missing_plates = len([l for l in listings if not l.get('plate')])
                    
                    cols = st.columns(3)
                    with cols[0]:
                        st.metric("💰 Valore Totale", f"€{dealer_value:,.0f}".replace(",", "."))
                    with cols[1]:
                        st.metric("🔍 Targhe Mancanti", missing_plates)
                        
                    # Bottone navigazione
                    if st.button("🔍 Vedi Dettagli", key=f"view_{dealer['id']}", use_container_width=True):
                        st.query_params["dealer_id"] = dealer['id']
                        st.rerun()
                else:
                    st.info("ℹ️ Nessun annuncio attivo")

    def show_dealer_view(self, dealer_id):
        """Mostra la vista del dealer"""
        from components import stats, plate_editor, filters, tables
        
        # Recupera dealer
        dealers = self.tracker.get_dealers()
        dealer = next((d for d in dealers if d['id'] == dealer_id), None)
        
        if not dealer:
            st.error("❌ Concessionario non trovato")
            return
            
        # Header
        st.title(f"🏢 {format_dealer_name(dealer['url'])}")
        st.caption(dealer['url'])
        
        if dealer.get('last_update'):
            st.info(f"📅 Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")
            
        # Bottone aggiorna
        if st.button("🔄 Aggiorna Annunci", use_container_width=True):
            with st.status("⏳ Aggiornamento in corso...", expanded=True) as status:
                try:
                    listings = self.tracker.scrape_dealer(dealer['url'])
                    if listings:
                        for listing in listings:
                            listing['dealer_id'] = dealer['id']
                        self.tracker.save_listings(listings)
                        self.tracker.mark_inactive_listings(dealer['id'], [l['id'] for l in listings])
                        status.update(label="✅ Aggiornamento completato!", state="complete")
                        st.rerun()
                    else:
                        status.update(label="⚠️ Nessun annuncio trovato", state="error")
                except Exception as e:
                    status.update(label=f"❌ Errore: {str(e)}", state="error")
                    
        # Statistiche dealer
        stats.show_dealer_overview(self.tracker, dealer_id)
        
        # Filtri
        active_filters = filters.show_filters()
        
        # Lista annunci
        listings = self.tracker.get_active_listings(dealer_id)
        if listings:
            # Applica filtri
            if active_filters:
                if active_filters.get('min_price'):
                    listings = [l for l in listings if l.get('original_price', 0) >= active_filters['min_price']]
                if active_filters.get('max_price'):
                    listings = [l for l in listings if l.get('original_price', 0) <= active_filters['max_price']]
                if active_filters.get('missing_plates_only'):
                    listings = [l for l in listings if not l.get('plate')]
                
            # Tabella annunci
            tables.show_listings_table(listings)
            
            # Editor targhe
            plate_editor.show_plate_editor(self.tracker, listings)
            
            # Grafici
            stats.show_dealer_insights(self.tracker, dealer_id)
        else:
            st.warning("⚠️ Nessun annuncio attivo")

    def show_settings(self):
        """Mostra la pagina impostazioni"""
        st.title("⚙️ Impostazioni")
        
        # Form aggiunta dealer
        st.header("➕ Aggiungi Concessionario")
        with st.form("add_dealer"):
            url = st.text_input(
                "URL",
                placeholder="https://www.autoscout24.it/concessionari/esempio"
            )
            
            no_targa = st.checkbox(
                "NO Targa",
                help="Seleziona se il concessionario non mostra le targhe dei veicoli"
            )
            
            if st.form_submit_button("Aggiungi", use_container_width=True):
                try:
                    dealer_id = url.split('/')[-1]
                    if not dealer_id:
                        st.error("❌ URL non valido")
                    else:
                        self.tracker.save_dealer(dealer_id, url, no_targa)
                        st.success("✅ Concessionario aggiunto")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ Errore: {str(e)}")

        # Sezione Scheduling
        st.header("⏰ Aggiornamento Automatico")
        
        # Recupera configurazione attuale
        config = self.tracker.get_scheduler_config()
        
        with st.form("scheduler_config"):
            enabled = st.toggle(
                "Abilita aggiornamento automatico",
                value=config.get('enabled', False)
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                hour = st.number_input(
                    "Ora esecuzione (0-23)",
                    min_value=0,
                    max_value=23,
                    value=config.get('hour', 1)
                )
                
            with col2:
                minute = st.number_input(
                    "Minuto esecuzione (0-59)",
                    min_value=0,
                    max_value=59,
                    value=config.get('minute', 0)
                )
                
            if st.form_submit_button("Salva Configurazione", use_container_width=True):
                try:
                    new_config = {
                        'enabled': enabled,
                        'hour': hour,
                        'minute': minute,
                        'last_update': config.get('last_update'),
                        'updated_at': datetime.now()
                    }
                    
                    self.tracker.save_scheduler_config(new_config)
                    st.success("✅ Configurazione scheduler salvata")
                    
                except Exception as e:
                    st.error(f"❌ Errore nel salvataggio: {str(e)}")
                    
        # Lista dealers esistenti
        dealers = self.tracker.get_dealers()
        if dealers:
            st.header("📋 Concessionari Attivi")
            
            for dealer in dealers:
                with st.expander(dealer['url']):
                    st.write(f"ID: {dealer['id']}")
                    if dealer.get('last_update'):
                        st.caption(f"Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")
                    
                    # Switch NO Targa con key unica
                    no_targa_key = f"no_targa_{dealer['id']}"
                    no_targa = st.checkbox(
                        "NO Targa",
                        value=dealer.get('no_targa', False),
                        key=no_targa_key
                    )
                    
                    # Se il valore cambia, aggiorna il dealer
                    if no_targa != dealer.get('no_targa', False):
                        self.tracker.update_dealer_settings(dealer['id'], {'no_targa': no_targa})
                        st.success("✅ Impostazioni aggiornate")
                    
                    # Gestione rimozione con form dedicato per ogni dealer
                    with st.form(f"remove_form_{dealer['id']}"):
                        col1, col2 = st.columns([3,1])
                        with col2:
                            delete_type = st.radio(
                                "Tipo eliminazione",
                                ["Soft", "Hard"],
                                horizontal=True,
                                key=f"delete_type_{dealer['id']}"
                            )
                            
                            confirm = st.checkbox(
                                "Conferma eliminazione", 
                                key=f"confirm_{dealer['id']}"
                            )
                            
                            submit = st.form_submit_button(
                                "❌ Rimuovi",
                                use_container_width=True,
                                type="primary"
                            )
                            
                            if submit and confirm:
                                hard_delete = (delete_type == "Hard")
                                self.tracker.remove_dealer(dealer['id'], hard_delete=hard_delete)
                                message = "✅ Concessionario e dati eliminati" if hard_delete else "✅ Concessionario nascosto"
                                st.success(message)
                                time.sleep(0.5)  # Breve pausa per mostrare il messaggio
                                st.rerun()
                            elif submit and not confirm:
                                st.error("❌ Conferma l'eliminazione")

    def _handle_notifications(self):
        """Gestisce le notifiche pendenti"""
        if 'notifications' in st.session_state.app_state:
            notifications = st.session_state.app_state['notifications']
            while notifications:
                notification = notifications.pop(0)
                self.show_notification(
                    notification['message'], 
                    notification['type']
                )

def main():
    app = AutoTrackerApp()
    app.run()

if __name__ == "__main__":
    main()