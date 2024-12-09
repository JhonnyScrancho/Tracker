from datetime import datetime
import time
from components import stats, tables
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
from components.anomaly_dashboard import show_anomaly_dashboard, show_listing_details
from services.analytics_service import AnalyticsService
from components.reports import generate_weekly_report, show_trend_analysis
from components.vehicle_comparison import show_comparison_view
from services.alerts import AlertSystem

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
                'selected_view': 'dashboard',
                'log_history': [],
                'max_logs': 1000,
                'selected_listing_id': None
            }


    def add_log(self, message: str, type: str = "info"):
        """Aggiunge un messaggio al log con mantenimento limite"""
        # Assicurati che log_history esista
        if 'log_history' not in st.session_state.app_state:
            st.session_state.app_state['log_history'] = []
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'message': message,
            'type': type
        }
        
        st.session_state.app_state['log_history'].append(log_entry)
        
        # Mantiene limite log
        max_logs = st.session_state.app_state.get('max_logs', 1000)
        while len(st.session_state.app_state['log_history']) > max_logs:
            st.session_state.app_state['log_history'].pop(0)

    def show_logs(self):
        """Mostra i log in un container scrollabile"""
        with st.expander("📝 Log Operazioni", expanded=False):
            # Verifica che log_history esista prima di usarlo
            if 'log_history' not in st.session_state.app_state:
                st.session_state.app_state['log_history'] = []

            log_html = """
                <div class="log-container">
                    {}
                </div>
            """.format(
                '\n'.join(
                    f'<div class="log-entry log-{log["type"]}">[{log["timestamp"]}] {log["message"]}</div>'
                    for log in st.session_state.app_state['log_history']
                )
            )
            st.markdown(log_html, unsafe_allow_html=True)
            
            if st.session_state.app_state['log_history']:
                if st.download_button(
                    "📥 Esporta Log",
                    '\n'.join(
                        f'[{log["timestamp"]}] {log["message"]}'
                        for log in st.session_state.app_state['log_history']
                    ),
                    file_name=f"autotracker_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                ):
                    st.success("✅ Log esportato con successo")
    
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

        # Controlla alert
        if dealers:
            for dealer in dealers:
                self.alert_system.check_alert_conditions(dealer['id'])

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
    
    
    def show_listing_detail(self, listing_id: str):
        """Mostra dettaglio completo di un annuncio"""
        listing = self.tracker.get_listing_by_id(listing_id)
        if not listing:
            st.error("❌ Annuncio non trovato")
            return

        st.subheader(listing.get('title', 'N/D'))

        tabs = st.tabs([
            "📊 Overview",
            "📈 Storico Prezzi",
            "🔄 Riapparizioni",
            "👯 Annunci Simili"
        ])

        with tabs[0]:
            cols = st.columns(3)
            with cols[0]:
                st.metric("💰 Prezzo", f"€{listing.get('original_price', 0):,.0f}")
            with cols[1]:
                st.metric("🚗 Targa", listing.get('plate', 'N/D'))
            with cols[2]:
                st.metric("📏 Chilometraggio", 
                         f"{listing.get('mileage', 0):,}".replace(",", "."))

            if listing.get('image_urls'):
                st.image(listing['image_urls'][0], width=400)

        with tabs[1]:
            history = self.tracker.get_listing_history(listing_id)
            if history:
                fig = stats.create_price_history_chart(history)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nessuno storico prezzi disponibile")

        with tabs[2]:
            reappearances = self.tracker.get_listing_reappearances(listing_id)
            if reappearances:
                for reapp in reappearances:
                    st.write(f"🔄 Rimosso il {reapp['removed_date'].strftime('%d/%m/%Y')}")
                    st.write(f"↩️ Riapparso il {reapp['reappeared_date'].strftime('%d/%m/%Y')}")
                    st.write(f"⏱️ Giorni offline: {reapp['days_offline']}")
                    st.divider()
            else:
                st.info("Nessuna riapparizione rilevata")

        with tabs[3]:
            similar = self.tracker.find_similar_listings(listing)
            if similar:
                for sim in similar:
                    with st.expander(f"{sim['title']} - {sim['similarity_score']:.0%} match"):
                        cols = st.columns(2)
                        with cols[0]:
                            st.write("🚗 Targa:", sim.get('plate', 'N/D'))
                            st.write("💰 Prezzo:", f"€{sim.get('original_price', 0):,.0f}")
                            if sim.get('image_urls'):
                                st.image(sim['image_urls'][0], width=200)
                        with cols[1]:
                            st.write("Caratteristiche corrispondenti:")
                            for feature, matches in sim['matching_features'].items():
                                st.write(f"{'✅' if matches else '❌'} {feature}")
            else:
                st.info("Nessun annuncio simile trovato")
    
    def show_home(self):
        """Mostra la home page con lista annunci centralizzata"""
        st.title("🏠 Dashboard")
        
        dealers = self.tracker.get_dealers()
        if not dealers:
            st.info("👋 Aggiungi un concessionario per iniziare")
            return

        # Statistiche globali in colonne
        total_cars = 0
        total_value = 0
        active_dealers = len(dealers)
        
        for dealer in dealers:
            listings = self.tracker.get_active_listings(dealer['id'])
            total_cars += len(listings)
            total_value += sum(l.get('original_price', 0) for l in listings if l.get('original_price'))

        cols = st.columns(3)
        with cols[0]:
            st.metric("🏢 Concessionari", active_dealers)
        with cols[1]:
            st.metric("🚗 Auto Totali", total_cars)
        with cols[2]:
            st.metric("💰 Valore Totale", f"€{total_value:,.0f}".replace(",", "."))

        # Lista completa annunci
        st.subheader("📋 Tutti gli Annunci")
        
        # Recupera tutti gli annunci attivi
        all_listings = []
        for dealer in dealers:
            dealer_listings = self.tracker.get_active_listings(dealer['id'])
            for listing in dealer_listings:
                listing['dealer_name'] = dealer.get('url', '').split('/')[-1].upper()
            all_listings.extend(dealer_listings)

        if all_listings:
            # Filtri
            col1, col2, col3 = st.columns(3)
            with col1:
                min_price = st.number_input("Prezzo Minimo", min_value=0, step=1000)
            with col2:
                max_price = st.number_input("Prezzo Massimo", min_value=0, step=1000)
            with col3:
                dealer_filter = st.multiselect(
                    "Concessionario",
                    options=list(set(l['dealer_name'] for l in all_listings))
                )

            # Applica filtri
            filtered_listings = [
                l for l in all_listings
                if (not min_price or l.get('original_price', 0) >= min_price) and
                   (not max_price or l.get('original_price', 0) <= max_price) and
                   (not dealer_filter or l['dealer_name'] in dealer_filter)
            ]

            # Gestione click su annuncio
            for listing in filtered_listings:
                with st.container():
                    cols = st.columns([3, 2, 2, 1])
                    with cols[0]:
                        st.write(listing.get('title', 'N/D'))
                    with cols[1]:
                        st.write(f"€{listing.get('original_price', 0):,.0f}")
                    with cols[2]:
                        st.write(listing['dealer_name'])
                    with cols[3]:
                        if st.button("🔍", key=f"view_{listing['id']}"):
                            st.session_state.app_state['selected_listing_id'] = listing['id']
                            st.rerun()
                st.divider()

            # Dettaglio annuncio se selezionato
            if st.session_state.app_state['selected_listing_id']:
                self.show_listing_detail(st.session_state.app_state['selected_listing_id'])    
    
    def show_dealer_view(self, dealer_id):
        """Mostra la vista del dealer con nuovo layout a tab"""
        # Recupera dealer
        dealers = self.tracker.get_dealers()
        dealer = next((d for d in dealers if d['id'] == dealer_id), None)
        
        if not dealer:
            st.error("❌ Concessionario non trovato")
            return
            
        # Header
        st.title(f"🏢 {format_dealer_name(dealer['url'])}")
        st.caption(dealer['url'])
        
        # Tabs principale
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Dashboard",
            "🔍 Dettaglio Annunci",
            "⚠️ Duplicati",
            "📈 Analisi"
        ])
        
        with tab1:
            # Overview principale
            if dealer.get('last_update'):
                st.info(f"📅 Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")
                
            # Bottone aggiorna
            if st.button("🔄 Aggiorna Annunci", use_container_width=True):
                with st.status("⏳ Aggiornamento in corso...", expanded=True) as status:
                    try:
                        self.add_log("Avvio aggiornamento annunci...")
                        listings = self.tracker.scrape_dealer(dealer['url'])
                        if listings:
                            self.tracker.save_listings(listings)
                            self.add_log(f"✅ Aggiornati {len(listings)} annunci")
                            status.update(label="✅ Aggiornamento completato!", state="complete")
                            st.rerun()
                        else:
                            self.add_log("⚠️ Nessun annuncio trovato", "warning")
                            status.update(label="⚠️ Nessun annuncio trovato", state="error")
                    except Exception as e:
                        self.add_log(f"❌ Errore: {str(e)}", "error")
                        status.update(label=f"❌ Errore: {str(e)}", state="error")

            # Statistiche dealer
            stats.show_dealer_overview(self.tracker, dealer_id)
            
        with tab2:
            # Lista annunci con possibilità di selezionare dettaglio
            listings = self.tracker.get_active_listings(dealer_id)
            if listings:
                # Selezione annuncio
                selected_listing = st.selectbox(
                    "Seleziona Annuncio",
                    options=[l['id'] for l in listings],
                    format_func=lambda x: next((l['title'] for l in listings if l['id'] == x), x)
                )
                
                if selected_listing:
                    # Mostra dettaglio annuncio
                    show_listing_details(self.tracker, selected_listing)
                
                # Tabella generale
                st.subheader("📋 Tutti gli Annunci")
                tables.show_listings_table(listings)
                
        with tab3:
            # Vista duplicati
            self.show_duplicates_view(dealer_id)
            
        with tab4:
            # Analisi trend
            stats.show_dealer_insights(self.tracker, dealer_id)
            
        # Log operazioni
        self.show_logs()

    def show_duplicates_view(self, dealer_id: str):
        """Mostra vista dedicata ai duplicati"""
        listings = self.tracker.get_active_listings(dealer_id)
        duplicates = [l for l in listings if l.get('duplicate_of')]
        
        if not duplicates:
            st.info("✅ Nessun duplicato rilevato")
            return
            
        st.warning(f"⚠️ Rilevati {len(duplicates)} annunci duplicati")
        
        for dup in duplicates:
            with st.expander(f"{dup.get('title', 'N/D')} - {dup['id']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("### Annuncio Duplicato")
                    st.write(f"ID: {dup['id']}")
                    st.write(f"Prezzo: €{dup.get('original_price', 0):,.0f}")
                    if dup.get('image_urls'):
                        st.image(dup['image_urls'][0], width=300)
                        
                with col2:
                    st.write("### Annuncio Originale")
                    original = self.tracker.get_listing_by_id(dup['duplicate_of'])
                    if original:
                        st.write(f"ID: {original['id']}")
                        st.write(f"Prezzo: €{original.get('original_price', 0):,.0f}")
                        if original.get('image_urls'):
                            st.image(original['image_urls'][0], width=300)

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