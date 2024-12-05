import streamlit as st
from services.tracker import AutoTracker
from pages.home import HomePage
from pages.dealer_view import DealerView
from pages.settings import SettingsPage
from components import sidebar

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
            background-color: #f3f4f6;
            border-radius: 4px;
            font-size: 0.8em;
            color: #374151;
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

    def run(self):
        """Esegue l'applicazione"""
        # Inizializza il tracker
        dealers = self.tracker.get_dealers()

        # Mostra la sidebar
        selected_dealer = sidebar.show_sidebar(self.tracker)

        # Main content
        if not dealers:
            # Prima esecuzione - mostra welcome page
            st.title("👋 Benvenuto in Auto Tracker")
            st.info("Aggiungi un concessionario nella sezione impostazioni per iniziare")
            settings = SettingsPage()
            settings.show()
        else:
            # Controlla la query string per determinare la pagina da mostrare
            page = st.query_params.get("page", "home")
            dealer_id = st.query_params.get("dealer_id")

            if dealer_id:
                # Mostra la pagina del dealer specifico
                dealer_view = DealerView()
                dealer_view.show()
            elif page == "settings":
                # Mostra la pagina impostazioni
                settings = SettingsPage()
                settings.show()
            else:
                # Mostra la home page di default
                home = HomePage()
                home.show()

            # Gestione notifiche in session state
            self._handle_notifications()

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