import streamlit as st
from services.tracker import AutoTracker
from datetime import datetime

class SettingsPage:
    def __init__(self):
        self.tracker = AutoTracker()
        if 'settings_status' not in st.session_state:
            st.session_state.settings_status = {}
            
    def show(self):
        st.title("⚙️ Impostazioni")
        
        self._show_add_dealer()
        self._show_manage_dealers()
        
    def _show_add_dealer(self):
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
                        st.session_state.settings_status['add_dealer'] = {
                            'success': True,
                            'message': "✅ Concessionario aggiunto",
                            'timestamp': datetime.now()
                        }
                        st.rerun()
                except Exception as e:
                    st.session_state.settings_status['add_dealer'] = {
                        'success': False,
                        'message': f"❌ Errore: {str(e)}",
                        'timestamp': datetime.now()
                    }
                    st.error(f"❌ Errore: {str(e)}")
                    
    def _show_manage_dealers(self):
        dealers = self.tracker.get_dealers()
        if not dealers:
            return
            
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
                            st.session_state.settings_status['remove_dealer'] = {
                                'success': True,
                                'message': "✅ Concessionario rimosso",
                                'timestamp': datetime.now()
                            }
                            st.rerun()

if __name__ == "__main__":
    settings = SettingsPage()
    settings.show()