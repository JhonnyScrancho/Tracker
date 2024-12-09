from datetime import datetime
import time
from typing import Dict, List
import pandas as pd
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
from components.anomaly_dashboard import show_anomaly_dashboard
from services.analytics_service import AnalyticsService
from components.reports import generate_weekly_report, show_trend_analysis
from components.vehicle_comparison import show_comparison_view
from services.alerts import AlertSystem
from utils.datetime_utils import get_current_time, calculate_date_diff, normalize_datetime

st.set_page_config(
    page_title="Auto Tracker",
    page_icon="🚗",
    layout="wide"
)

# CSS
st.markdown("""
    <style>
    .stExpander { width: 100% !important; }
    .element-container { width: 100% !important; }
    .stMarkdown { width: 100% !important; }
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
    .log-entry {
        margin: 0.2rem 0;
        padding: 0.2rem 0;
        border-bottom: 1px solid #eee;
    }
    .log-info { color: #0d6efd; }
    .log-success { color: #28a745; }
    .log-warning { color: #ffc107; }
    .log-error { color: #dc3545; }

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

    .col-foto { width: auto !important; padding: 5px !important; }
    .col-id { width: auto !important; }
    .col-targa { width: auto !important; text-align: center !important; }
    .col-modello { min-width: auto !important; }
    .col-prezzo { width: auto !important; text-align: right !important; }
    .col-km { width: auto !important; text-align: right !important; }
    .col-data { width: auto !important; text-align: center !important; }
    .col-carburante { width: auto !important; }
    .col-link { width: auto !important; text-align: center !important; }

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

    .dealer-button {
        margin-bottom: 0.5rem;
        width: 100%;
    }

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

    .variation-positive {
        color: #198754;
        font-weight: bold;
    }
    .variation-negative {
        color: #dc3545;
        font-weight: bold;
    }

    .metric-container {
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 0.5rem;
        background-color: #f8f9fa;
    }

    .removed-listing {
        background-color: #fff3cd;
        padding: 0.5rem;
        margin: 0.5rem 0;
        border-radius: 0.25rem;
    }
</style>
""", unsafe_allow_html=True)

def apply_listing_filters(df, min_price=0, max_price=0, dealer_filter=None):
    if min_price > 0:
        df = df[df['original_price'] >= min_price]
    if max_price > 0:
        df = df[df['original_price'] <= max_price]
    if dealer_filter:
        df = df[df['dealer_name'].isin(dealer_filter)]
    return df

def render_listings(df, tracker, show_dealer=False, key_prefix="home", on_view_click=None):
    if df.empty:
        st.info("Nessun annuncio trovato con i filtri selezionati")
        return
    for i, row in df.iterrows():
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3,2,2,2,1]) if show_dealer else st.columns([3,2,2,2,1])
            with col1:
                if row.get('image_urls'):
                    st.image(row['image_urls'][0], width=100)
                st.write(row.get('title', 'N/D'))

            with col2:
                st.metric("Prezzo", f"€{row.get('original_price', 0):,.0f}")
                if row.get('discounted_price'):
                    st.caption(f"Scontato: €{row['discounted_price']:,.0f}")

            with col3:
                st.write(f"🚗 Targa: {row.get('plate', 'N/D')}")
                if row.get('mileage'):
                    st.write(f"📏 KM: {row['mileage']:,}".replace(",", "."))
                if row.get('first_seen'):
                    try:
                        first_seen = normalize_datetime(row['first_seen'])
                        current_time = get_current_time()
                        days = calculate_date_diff(first_seen, current_time)
                        if days is not None:
                            st.write(f"⏱️ Online da: {days} giorni")
                    except Exception as e:
                        st.error(f"Errore calcolo durata: {str(e)}")

            if show_dealer:
                with col4:
                    st.write("📍 Dealer")
                    st.write(row['dealer_name'])
                with col5:
                    if st.button("🔍", key=f"{key_prefix}_view_{row['id']}", help="Vedi dettagli"):
                        if on_view_click:
                            on_view_click(row['id'])
            else:
                with col4:
                    st.write("Azioni")
                with col5:
                    if st.button("🔍", key=f"{key_prefix}_view_{row['id']}", help="Vedi dettagli"):
                        if on_view_click:
                            on_view_click(row['id'])

            st.divider()

class AutoTrackerApp:
    def __init__(self):
        self.tracker = AutoTracker()
        self.analytics = AnalyticsService(self.tracker)
        self.alert_system = AlertSystem(self.tracker)
        self.init_session_state()

    def init_session_state(self):
        if 'app_state' not in st.session_state:
            st.session_state.app_state = {
                'update_status': {},
                'settings_status': {},
                'notifications': [],
                'selected_view': 'dashboard',
                'log_history': [],
                'max_logs': 1000,
                'selected_listing_id': None,
                'selected_listing': None
            }

    def add_log(self, message: str, type: str = "info"):
        if 'log_history' not in st.session_state.app_state:
            st.session_state.app_state['log_history'] = []

        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'message': message,
            'type': type
        }

        st.session_state.app_state['log_history'].append(log_entry)

        max_logs = st.session_state.app_state.get('max_logs', 1000)
        while len(st.session_state.app_state['log_history']) > max_logs:
            st.session_state.app_state['log_history'].pop(0)

    def show_logs(self):
        with st.expander("📝 Log Operazioni", expanded=False):
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
        if type == "success":
            st.success(message)
        elif type == "error":
            st.error(message)
        else:
            st.info(message)

    def check_scheduler(self):
        try:
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
                            listings = self.tracker.scrape_dealer(dealer['url'])
                            if listings:
                                self.tracker.save_listings(listings)
                                self.tracker.mark_inactive_listings(
                                    dealer['id'],
                                    [l['id'] for l in listings]
                                )
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
        dealers = self.tracker.get_dealers()

        self.check_scheduler()
        self.alert_system.show_notifications()

        selected_dealer = show_sidebar(self.tracker)

        if dealers:
            for dealer in dealers:
                self.alert_system.check_alert_conditions(dealer['id'])

        if not dealers:
            st.title("👋 Benvenuto in Auto Tracker")
            st.info("Aggiungi un concessionario nella sezione impostazioni per iniziare")
            self.show_settings()
        else:
            dealer_id = st.query_params.get("dealer_id")
            view = st.query_params.get("view", "dashboard")

            if dealer_id == "settings":
                self.show_settings()
            elif dealer_id:
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
        st.title("📊 Analisi di Mercato")

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

        if insights.get('recommendations'):
            st.subheader("📋 Raccomandazioni")
            for rec in insights['recommendations']:
                with st.expander(f"{'🔴' if rec['priority'] == 'high' else '🟡'} {rec['message']}"):
                    st.write(f"Priorità: {rec['priority'].title()}")
                    st.write(f"Tipo: {rec['type']}")

        if insights.get('suspicious'):
            st.subheader("⚠️ Pattern Sospetti")
            for pattern in insights['suspicious']:
                with st.expander(f"{pattern['type'].replace('_', ' ').title()}"):
                    if 'listing_id' in pattern:
                        st.write(f"Annuncio: {pattern['listing_id']}")
                    if 'confidence' in pattern:
                        st.progress(pattern['confidence'])

    def show_listing_detail(self, listing_id: str):
        listing = self.tracker.get_listing_by_id(listing_id)
        if not listing:
            st.error("❌ Annuncio non trovato")
            return

        if st.button("← Torna alla lista"):
            st.session_state.app_state['selected_listing_id'] = None
            st.rerun()

        st.title(listing.get('title', 'N/D'))

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Prezzo", f"€{listing.get('original_price', 0):,.0f}")
            if listing.get('discounted_price'):
                st.metric("🏷️ Prezzo Scontato", f"€{listing['discounted_price']:,.0f}")
        with col2:
            st.metric("🚗 Targa", listing.get('plate', 'N/D'))
        with col3:
            if listing.get('mileage'):
                st.metric("📏 Chilometri", f"{listing['mileage']:,}".replace(",", "."))

        tab1, tab2, tab3, tab4 = st.tabs([
            "📸 Galleria",
            "📈 Andamento Prezzi",
            "🔄 Storico",
            "👯 Annunci Simili"
        ])

        with tab1:
            if listing.get('image_urls'):
                st.subheader("Galleria Immagini")
                cols = st.columns(3)
                for idx, img_url in enumerate(listing['image_urls'][:3]):
                    with cols[idx % 3]:
                        st.image(img_url)

        with tab2:
            st.subheader("Andamento Prezzi")
            history = self.tracker.get_listing_history(listing_id)
            if history:
                stats.create_price_history_chart(history)
                price_changes = [h for h in history if h['event'] == 'price_changed']
                if price_changes:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Variazioni Totali", len(price_changes))
                    with col2:
                        if len(price_changes) > 1:
                            price_list = [p['price'] for p in price_changes]
                            total_variation = ((price_list[-1] - price_list[0]) / price_list[0]) * 100
                            st.metric("Variazione Totale", f"{total_variation:+.1f}%")

        with tab3:
            st.subheader("Storico Eventi")
            history = self.tracker.get_listing_history(listing_id)
            if history:
                for event in sorted(history, key=lambda x: x['date'], reverse=True):
                    with st.expander(f"{event['date'].strftime('%d/%m/%Y %H:%M')} - {event['event'].title()}"):
                        if event['event'] == 'price_changed':
                            st.write(f"💰 Nuovo prezzo: €{event['price']:,.0f}")
                            if event.get('discounted_price'):
                                st.write(f"🏷️ Prezzo scontato: €{event['discounted_price']:,.0f}")
                        elif event['event'] == 'removed':
                            st.write("❌ Annuncio rimosso")
                        elif event['event'] == 'reappeared':
                            st.write("↩️ Annuncio riapparso")

        with tab4:
            st.subheader("Annunci Simili")
            similar_listings = self.tracker.find_similar_listings(listing_id)
            if similar_listings:
                for similar in similar_listings:
                    with st.expander(f"Match {similar['similarity_score']:.0%} - {similar['title']}"):
                        cols = st.columns([1, 2])
                        with cols[0]:
                            if similar.get('image_urls'):
                                st.image(similar['image_urls'][0])
                        with cols[1]:
                            st.write(f"🚗 Targa: {similar.get('plate', 'N/D')}")
                            st.write(f"💰 Prezzo: €{similar.get('original_price', 0):,.0f}")
                            st.write(f"📏 KM: {similar.get('mileage', 'N/D'):,}".replace(",", "."))
                            if similar.get('matching_features'):
                                st.write("\n✅ Caratteristiche Corrispondenti:")
                                for feature, match in similar['matching_features'].items():
                                    st.write(f"{'✓' if match else '✗'} {feature}")
            else:
                st.info("Nessun annuncio simile trovato")

    def show_home(self):
        st.title("🏠 Dashboard")
        dealers = self.tracker.get_dealers()
        if not dealers:
            st.info("👋 Aggiungi un concessionario per iniziare")
            return

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

        st.divider()

        st.header("📋 Tutti gli Annunci")

        all_listings = []
        for dealer in dealers:
            dealer_listings = self.tracker.get_active_listings(dealer['id'])
            for listing in dealer_listings:
                listing['dealer_name'] = dealer.get('url', '').split('/')[-1].upper()
            all_listings.extend(dealer_listings)

        df = pd.DataFrame(all_listings)

        with st.expander("🔍 Filtri", expanded=False):
            col1, col2, col3 = st.columns(3)
            with col1:
                min_price = st.number_input("Prezzo Minimo", min_value=0, step=1000)
            with col2:
                max_price = st.number_input("Prezzo Massimo", min_value=0, step=1000)
            with col3:
                dealer_filter = st.multiselect(
                    "Concessionario",
                    options=sorted(df['dealer_name'].unique())
                )

        df = apply_listing_filters(df, min_price, max_price, dealer_filter)

        def on_view_click(listing_id):
            st.session_state['selected_listing'] = listing_id
            st.rerun()

        render_listings(df, self.tracker, show_dealer=True, key_prefix="home", on_view_click=on_view_click)

        if st.session_state.get('selected_listing'):
            self.show_listing_details(st.session_state['selected_listing'])

    def show_listing_details(self, listing_id):
        self.show_listing_detail(listing_id)

    def show_dealer_view(self, dealer_id: str):
        dealers = self.tracker.get_dealers()
        dealer = next((d for d in dealers if d['id'] == dealer_id), None)

        if not dealer:
            st.error("❌ Concessionario non trovato")
            return

        st.title(f"🏢 {format_dealer_name(dealer['url'])}")
        st.caption(dealer['url'])

        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Dashboard",
            "🔍 Dettaglio Annunci",
            "⚠️ Duplicati",
            "📈 Analisi"
        ])

        with tab1:
            if dealer.get('last_update'):
                st.info(f"📅 Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")

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

            stats.show_dealer_overview(self.tracker, dealer_id)
            self.show_logs()

        with tab2:
            listings = self.tracker.get_active_listings(dealer_id)
            if not listings:
                st.info("Nessun annuncio disponibile")
                return

            with st.expander("🔍 Filtri", expanded=False):
                col1, col2 = st.columns(2)
                with col1:
                    min_price = st.number_input("Prezzo Minimo", min_value=0, step=1000, value=0)
                with col2:
                    max_price = st.number_input("Prezzo Massimo", min_value=0, step=1000, value=0)

            df = pd.DataFrame(listings)
            df = apply_listing_filters(df, min_price, max_price)

            st.write("### 📋 Lista Annunci")

            def on_view_click_dealer(listing_id):
                st.session_state.app_state['selected_listing_id'] = listing_id
                st.rerun()

            render_listings(df, self.tracker, show_dealer=False, key_prefix="dealer", on_view_click=on_view_click_dealer)

            if st.session_state.app_state.get('selected_listing_id'):
                self.show_listing_detail(st.session_state.app_state['selected_listing_id'])

        with tab3:
            st.write("### 🔄 Annunci Duplicati")
            self.show_duplicates_view(dealer_id)

        with tab4:
            st.write("### 📊 Analisi Trend")
            insights = self.analytics.get_market_insights(dealer_id)

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Tasso Riapparizione",
                    f"{insights['patterns'].get('reappearance_rate', 0):.1f}%"
                )
            with col2:
                st.metric(
                    "Variazioni Prezzo/Giorno",
                    f"{insights['patterns'].get('avg_price_changes', 0):.1f}"
                )
            with col3:
                st.metric(
                    "Durata Media Annunci",
                    f"{insights['patterns'].get('listing_duration', 0):.0f} giorni"
                )

            stats.show_dealer_insights(self.tracker, dealer_id)

    def show_duplicates_view(self, dealer_id: str):
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
        st.title("⚙️ Impostazioni")

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

        st.header("⏰ Aggiornamento Automatico")
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

        dealers = self.tracker.get_dealers()
        if dealers:
            st.header("📋 Concessionari Attivi")
            for dealer in dealers:
                with st.expander(dealer['url']):
                    st.write(f"ID: {dealer['id']}")
                    if dealer.get('last_update'):
                        st.caption(f"Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")

                    no_targa_key = f"no_targa_{dealer['id']}"
                    no_targa = st.checkbox(
                        "NO Targa",
                        value=dealer.get('no_targa', False),
                        key=no_targa_key
                    )

                    if no_targa != dealer.get('no_targa', False):
                        self.tracker.update_dealer_settings(dealer['id'], {'no_targa': no_targa})
                        st.success("✅ Impostazioni aggiornate")

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
                                time.sleep(0.5)
                                st.rerun()
                            elif submit and not confirm:
                                st.error("❌ Conferma l'eliminazione")

    def _handle_notifications(self):
        if 'notifications' in st.session_state.app_state:
            notifications = st.session_state.app_state['notifications']
            while notifications:
                notification = notifications.pop(0)
                self.show_notification(notification['message'], notification['type'])


def main():
    app = AutoTrackerApp()
    app.run()

if __name__ == "__main__":
    main()
