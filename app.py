from datetime import datetime
import streamlit as st
import sys
from pathlib import Path

# Aggiungi la directory root al PYTHONPATH
root_dir = Path(__file__).parent
sys.path.append(str(root_dir))

from components.sidebar import show_sidebar
from services.tracker import AutoTracker

st.set_page_config(
    page_title="Auto Tracker",
    page_icon="🚗",
    layout="wide"
)

# CSS
st.markdown("""
    <style>
        .stExpander { width: 100% !important; }
        .log-container {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 0.25rem;
            padding: 1rem;
            margin: 1rem 0;
            max-height: 400px;
            overflow-y: auto;
            width: 100% !important;
        }
        .element-container { width: 100% !important; }
        .stMarkdown { width: 100% !important; }
        
        .dataframe {
            width: 100%;
            margin: 0.5em 0;
            border-collapse: collapse;
            font-size: 14px;
        }
        .dataframe th {
            background-color: #f8f9fa;
            padding: 2px;
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
        .dataframe tr:hover {
            background-color: #f5f5f5;
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

        /* Stili per la sidebar */
        .dealer-button {
            margin-bottom: 0.5rem;
            width: 100%;
        }
        
        /* Stili per notifications */
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
    </style>
""", unsafe_allow_html=True)

class AutoTrackerApp:
    def __init__(self):
        """Inizializzazione dell'applicazione"""
        self.tracker = AutoTracker()
        self.init_session_state()

    def init_session_state(self):
        """Inizializza lo stato dell'applicazione"""
        if 'app_state' not in st.session_state:
            st.session_state.app_state = {
                'update_status': {},
                'settings_status': {},
                'notifications': []
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
            
            # Se non c'è stato un aggiornamento oggi
            if not last_update or last_update.date() < now.date():
                scheduled_time = now.replace(
                    hour=scheduler_config.get('hour', 1),
                    minute=scheduler_config.get('minute', 0)
                )

                # Se è l'ora di eseguire l'aggiornamento
                if now >= scheduled_time:
                    # Recupera tutti i dealer attivi
                    dealers = self.tracker.get_dealers()
                    
                    for dealer in dealers:
                        try:
                            # Esegue lo scrape
                            listings = self.tracker.scrape_dealer(dealer['url'])
                            if listings:
                                # Salva i nuovi annunci
                                self.tracker.save_listings(listings)
                                # Marca come inattivi gli annunci non più presenti
                                self.tracker.mark_inactive_listings(
                                    dealer['id'], 
                                    [l['id'] for l in listings]
                                )
                        except Exception as e:
                            st.error(f"❌ Errore scrape dealer {dealer['id']}: {str(e)}")
                            continue

                    # Aggiorna timestamp ultimo aggiornamento
                    self.tracker.save_scheduler_config({
                        'last_update': now
                    })
                    
                    st.success(f"✅ Aggiornamento completato per {len(dealers)} dealer")
                
        except Exception as e:
            st.error(f"❌ Errore durante l'esecuzione scheduler: {str(e)}")

    
    def run(self):
        """Esegue l'applicazione"""
        # Inizializza il tracker
        dealers = self.tracker.get_dealers()

        # Controlla scheduler
        self.check_scheduler()
        
        # Mostra la sidebar
        selected_dealer = show_sidebar(self.tracker)

        # Main content
        if not dealers:
            # Prima esecuzione - mostra welcome page
            st.title("👋 Benvenuto in Auto Tracker")
            st.info("Aggiungi un concessionario nella sezione impostazioni per iniziare")
            self.show_settings()
        else:
            # Controlla la query string per determinare la pagina da mostrare
            dealer_id = st.query_params.get("dealer_id")

            if dealer_id == "settings":  # Nuovo caso per le impostazioni
                self.show_settings()
            elif dealer_id:
                # Mostra la vista del dealer specifico
                self.show_dealer_view(dealer_id)
            else:
                # Mostra la home page
                self.show_home()

            # Gestione notifiche in session state
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

    def show_home(self):
        """Mostra la home page"""
        st.title("Dashboard")
        
        dealers = self.tracker.get_dealers()
        if not dealers:
            st.info("Aggiungi un concessionario per iniziare")
            return
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Concessionari", len(dealers))
            
        # Calcola totali
        total_cars = 0
        total_value = 0
        for dealer in dealers:
            listings = self.tracker.get_active_listings(dealer['id'])
            total_cars += len(listings)
            total_value += sum(l.get('original_price', 0) for l in listings if l.get('original_price'))
        
        with col2:    
            st.metric("Auto Totali", total_cars)
        with col3:
            st.metric("Valore Totale", f"€{total_value:,.0f}".replace(",", "."))
        
        # Bottone aggiornamento più discreto
        if st.button("Aggiorna Tutti", use_container_width=True):
            with st.status("Aggiornamento in corso", expanded=True) as status:
                try:
                    total_listings = 0
                    for dealer in dealers:
                        try:
                            listings = self.tracker.scrape_dealer(dealer['url'])
                            if listings:
                                self.tracker.save_listings(listings)
                                self.tracker.mark_inactive_listings(dealer['id'], [l['id'] for l in listings])
                                total_listings += len(listings)
                                st.write(f"Aggiornati {len(listings)} annunci per {dealer['id']}")
                        except Exception as e:
                            st.error(f"Errore: {str(e)}")
                            continue
                    
                    status.update(label=f"Completato - {total_listings} annunci aggiornati", state="complete")
                    self.tracker.save_scheduler_config({'last_update': datetime.now()})
                    
                except Exception as e:
                    status.update(label=f"Errore: {str(e)}", state="error")
        
        # Lista dealer
        st.subheader("Concessionari Monitorati")
        
        for dealer in dealers:
            with st.expander(f"{dealer['url'].split('/')[-1]} - {dealer['url']}", expanded=False):
                if dealer.get('last_update'):
                    st.caption(f"Aggiornato: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")
                
                listings = self.tracker.get_active_listings(dealer['id'])
                if listings:
                    col1, col2 = st.columns(2)
                    with col1:
                        dealer_value = sum(l.get('original_price', 0) for l in listings if l.get('original_price'))
                        st.metric("Valore", f"€{dealer_value:,.0f}".replace(",", "."))
                    with col2:
                        st.metric("Annunci", len(listings))
                    
                    if st.button("Dettagli", key=f"view_{dealer['id']}", use_container_width=True):
                        st.query_params["dealer_id"] = dealer['id']
                        st.rerun()
                else:
                    st.info("Nessun annuncio attivo")

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
        st.title(f"🏢 {dealer['url'].split('/')[-1].upper()}")
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
                "URL Concessionario",
                placeholder="https://www.autoscout24.it/concessionari/esempio"
            )
            
            if st.form_submit_button("Aggiungi", use_container_width=True):
                try:
                    dealer_id = url.split('/')[-1]
                    if not dealer_id:
                        st.error("❌ URL non valido")
                    else:
                        self.tracker.save_dealer(dealer_id, url)
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
                value=config.get('enabled', False),
                help="Attiva o disattiva l'aggiornamento automatico di tutti i concessionari"
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                hour = st.number_input(
                    "Ora esecuzione (0-23)",
                    min_value=0,
                    max_value=23,
                    value=config.get('hour', 1),
                    help="Ora del giorno in cui eseguire l'aggiornamento"
                )
                
            with col2:
                minute = st.number_input(
                    "Minuto esecuzione (0-59)",
                    min_value=0,
                    max_value=59,
                    value=config.get('minute', 0),
                    help="Minuto dell'ora in cui eseguire l'aggiornamento"
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
                    
                    # Mostra prossima esecuzione se abilitato
                    if enabled:
                        now = datetime.now()
                        next_run = now.replace(hour=hour, minute=minute)
                        if next_run < now:
                            next_run = next_run.replace(day=next_run.day + 1)
                        st.info(f"⏰ Prossima esecuzione: {next_run.strftime('%d/%m/%Y %H:%M')}")
                    
                except Exception as e:
                    st.error(f"❌ Errore nel salvataggio: {str(e)}")
                    
        # Mostra stato ultimo aggiornamento
        if config.get('last_update'):
            st.caption(f"Ultimo aggiornamento automatico: {config['last_update'].strftime('%d/%m/%Y %H:%M')}")
                
        # Lista dealers esistenti
        dealers = self.tracker.get_dealers()
        if dealers:
            st.header("📋 Concessionari Attivi")
            
            for dealer in dealers:
                with st.expander(dealer['url']):
                    st.write(f"ID: {dealer['id']}")
                    if dealer.get('last_update'):
                        st.caption(f"Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")
                        
                    col1, col2 = st.columns([3,1])
                    with col2:
                        if st.button("❌ Rimuovi", key=f"remove_{dealer['id']}", use_container_width=True):
                            confirm = st.checkbox("Conferma rimozione", key=f"confirm_{dealer['id']}")
                            if confirm:
                                self.tracker.remove_dealer(dealer['id'])
                                st.success("✅ Concessionario rimosso")
                                st.rerun()

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