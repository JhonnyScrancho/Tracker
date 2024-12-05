import streamlit as st
from services.tracker import AutoTracker
from datetime import datetime
from utils.formatting import format_price

class HomePage:
    def __init__(self):
        self.tracker = AutoTracker()
        if 'update_status' not in st.session_state:
            st.session_state.update_status = {}

    def show(self):
        st.title("🏠 Dashboard")
        
        dealers = self.tracker.get_dealers()
        
        if not dealers:
            st.info("👋 Aggiungi un concessionario per iniziare")
            return
            
        self._show_global_stats(dealers)
        self._show_dealers_list(dealers)
        
    def _show_global_stats(self, dealers):
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
            st.metric("💰 Valore Totale", format_price(total_value))
            
    def _show_dealers_list(self, dealers):
        st.subheader("🏢 Concessionari Monitorati")
        
        for dealer in dealers:
            with st.expander(f"**{dealer['url'].split('/')[-1].upper()}** - {dealer['url']}", expanded=False):
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
                        st.metric("💰 Valore Totale", format_price(dealer_value))
                    with cols[1]:
                        st.metric("🔍 Targhe Mancanti", missing_plates)
                        
                    # Bottone navigazione
                    if st.button("🔍 Vedi Dettagli", key=f"view_{dealer['id']}", use_container_width=True):
                        st.query_params["dealer_id"] = dealer['id']
                        st.rerun()
                else:
                    st.info("ℹ️ Nessun annuncio attivo")

if __name__ == "__main__":
    home = HomePage()
    home.show()