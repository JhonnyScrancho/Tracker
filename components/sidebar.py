import streamlit as st
from services.tracker import AutoTracker
from datetime import datetime

class Sidebar:
    def __init__(self, tracker: AutoTracker):
        self.tracker = tracker
        if 'sidebar_state' not in st.session_state:
            st.session_state.sidebar_state = {
                'active_dealer': None,
                'last_update': {}
            }

    def show(self):
        """Gestisce e mostra la sidebar dell'applicazione"""
        st.sidebar.title("🚗 Auto Tracker")
        
        # Bottone Home
        if st.sidebar.button("🏠 Dashboard", use_container_width=True):
            st.query_params.clear()
            st.rerun()
        
        # Recupera concessionari
        dealers = self.tracker.get_dealers()
        
        if dealers:
            self._show_dealers_list(dealers)
            
        st.sidebar.divider()
        
        # Bottone Impostazioni
        if st.sidebar.button("⚙️ Impostazioni", use_container_width=True):
            st.query_params["page"] = "settings"
            st.rerun()
        
        # Form aggiunta concessionario
        self._show_add_dealer_form()

    def _show_dealers_list(self, dealers):
        """Mostra la lista dei concessionari"""
        st.sidebar.subheader("🏢 Concessionari")
        
        for dealer in dealers:
            dealer_name = dealer['url'].split('/')[-1].upper()
            
            # Container per il dealer con info aggiornamento
            with st.sidebar.container():
                if st.sidebar.button(
                    f"🏢 {dealer_name}",
                    key=f"nav_{dealer['id']}",
                    use_container_width=True
                ):
                    # Imposta il dealer_id nei query params e forza il refresh
                    st.query_params["dealer_id"] = dealer['id']
                    st.rerun()
                
                # Mostra stato ultimo aggiornamento
                if dealer.get('last_update'):
                    st.sidebar.caption(
                        f"Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}"
                    )
                
                # Mostra stato operazione se presente
                if 'update_status' in st.session_state and dealer['id'] in st.session_state.update_status:
                    status = st.session_state.update_status[dealer['id']]
                    if datetime.now().timestamp() - status['timestamp'].timestamp() < 5:  # Mostra per 5 secondi
                        if status['success']:
                            st.sidebar.success(status['message'], icon="✅")
                        else:
                            st.sidebar.error(status['message'], icon="❌")

    def _show_add_dealer_form(self):
        """Mostra il form per l'aggiunta di un nuovo concessionario"""
        with st.sidebar.expander("➕ Nuovo Concessionario"):
            with st.form("add_dealer_form", clear_on_submit=True):
                new_url = st.text_input(
                    "URL Concessionario",
                    placeholder="https://www.autoscout24.it/concessionari/esempio"
                )
                
                if st.form_submit_button("Aggiungi", use_container_width=True):
                    try:
                        dealer_id = new_url.split('/')[-1]
                        if not dealer_id:
                            st.error("❌ URL non valido")
                        else:
                            self.tracker.save_dealer(dealer_id, new_url)
                            # Aggiorna stato e mostra conferma
                            st.session_state.sidebar_state['last_update'][dealer_id] = {
                                'success': True,
                                'message': "✅ Concessionario aggiunto",
                                'timestamp': datetime.now()
                            }
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Errore: {str(e)}")

def show_sidebar(tracker: AutoTracker):
    """Funzione di utility per mostrare la sidebar"""
    sidebar = Sidebar(tracker)
    return sidebar.show()