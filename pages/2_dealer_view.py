import streamlit as st
from services.tracker import AutoTracker
from datetime import datetime
from utils.formatting import format_price
from components import stats, plate_editor, filters, tables

class DealerView:
    def __init__(self):
        self.tracker = AutoTracker()
        if 'update_status' not in st.session_state:
            st.session_state.update_status = {}
            
    def show(self):
        # Recupera dealer_id dalla query string
        dealer_id = st.query_params.get("dealer_id")
        if not dealer_id:
            st.error("❌ ID concessionario mancante")
            return
            
        # Recupera dati dealer
        dealers = self.tracker.get_dealers()
        dealer = next((d for d in dealers if d['id'] == dealer_id), None)
        
        if not dealer:
            st.error("❌ Concessionario non trovato")
            return
            
        self._show_header(dealer)
        self._show_content(dealer)
        
    def _show_header(self, dealer):
        st.title(f"🏢 {dealer['url'].split('/')[-1].upper()}")
        st.caption(dealer['url'])
        
        if dealer.get('last_update'):
            st.info(f"📅 Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")
            
    def _show_content(self, dealer):
        # Bottone aggiorna
        if st.button("🔄 Aggiorna Annunci", use_container_width=True):
            self._update_listings(dealer)
            
        # Mostra stats del dealer
        stats.show_dealer_overview(self.tracker, dealer['id'])
        
        # Mostra filtri
        active_filters = filters.show_filters()
        
        # Recupera e mostra annunci
        listings = self.tracker.get_active_listings(dealer['id'])
        if listings:
            # Applica filtri se presenti
            if active_filters:
                listings = self._apply_filters(listings, active_filters)
                
            # Mostra tabella annunci
            tables.show_listings_table(listings)
            
            # Editor targhe
            plate_editor.show_plate_editor(self.tracker, listings)
            
            # Grafici e insights
            stats.show_dealer_insights(self.tracker, dealer['id'])
        else:
            st.warning("⚠️ Nessun annuncio attivo")
            
    def _update_listings(self, dealer):
        with st.status("⏳ Aggiornamento in corso...", expanded=True) as status:
            try:
                listings = self.tracker.scrape_dealer(dealer['url'])
                if listings:
                    for listing in listings:
                        listing['dealer_id'] = dealer['id']
                    self.tracker.save_listings(listings)
                    self.tracker.mark_inactive_listings(dealer['id'], [l['id'] for l in listings])
                    
                    # Aggiorna session state invece di usare rerun
                    st.session_state.update_status[dealer['id']] = {
                        'success': True,
                        'message': "✅ Aggiornamento completato!",
                        'timestamp': datetime.now()
                    }
                    status.update(label="✅ Aggiornamento completato!", state="complete")
                    st.rerun()  # Qui è sicuro usare rerun perché abbiamo il dealer_id nella query string
                else:
                    status.update(label="⚠️ Nessun annuncio trovato", state="error")
                    st.session_state.update_status[dealer['id']] = {
                        'success': False,
                        'message': "⚠️ Nessun annuncio trovato",
                        'timestamp': datetime.now()
                    }
            except Exception as e:
                error_message = f"❌ Errore: {str(e)}"
                status.update(label=error_message, state="error")
                st.session_state.update_status[dealer['id']] = {
                    'success': False,
                    'message': error_message,
                    'timestamp': datetime.now()
                }
                
    def _apply_filters(self, listings, filters):
        filtered = listings.copy()
        
        if filters.get('min_price'):
            filtered = [l for l in filtered if l.get('original_price', 0) >= filters['min_price']]
            
        if filters.get('max_price'):
            filtered = [l for l in filtered if l.get('original_price', 0) <= filters['max_price']]
            
        if filters.get('missing_plates_only'):
            filtered = [l for l in filtered if not l.get('plate')]
            
        if filters.get('only_discounted'):
            filtered = [l for l in filtered if l.get('has_discount')]
            
        return filtered

if __name__ == "__main__":
    dealer_view = DealerView()
    dealer_view.show()