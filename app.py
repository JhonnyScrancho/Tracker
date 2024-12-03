import streamlit as st
from tracker import AutoTracker
import time
from datetime import datetime, timedelta

st.set_page_config(
    page_title="AutoScout24 Tracker",
    page_icon="🚗",
    layout="wide"
)

def main():
    st.title("🚗 AutoScout24 Dealer Tracker")
    
    # Inizializza il tracker
    tracker = AutoTracker()
    
    # Input URL concessionario
    dealer_url = st.text_input(
        "URL Concessionario AutoScout24",
        placeholder="https://www.autoscout24.it/concessionari/esempio"
    )
    
    if dealer_url:
        # Tabs per diverse funzionalità
        tab1, tab2 = st.tabs(["Monitoraggio", "Statistiche"])
        
        with tab1:
            if st.button("Analizza Annunci"):
                with st.spinner("Analisi in corso..."):
                    # Scraping annunci
                    listings = tracker.scrape_dealer(dealer_url)
                    
                    if listings:
                        # Salva annunci
                        tracker.save_listings(listings)
                        
                        # Marca inattivi quelli non più presenti
                        active_plates = [l['plate'] for l in listings]
                        dealer_id = dealer_url.split('/')[-1]
                        tracker.mark_inactive_listings(dealer_id, active_plates)
                        
                        # Mostra risultati
                        st.success(f"Trovati {len(listings)} annunci")
                        
                        # Mostra tabella annunci
                        df = pd.DataFrame(listings)
                        st.dataframe(df)
                    else:
                        st.warning("Nessun annuncio trovato")
        
        with tab2:
            dealer_id = dealer_url.split('/')[-1]
            stats = tracker.get_dealer_stats(dealer_id)
            
            # Metriche principali
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Annunci Attivi", stats['total_active'])
            with col2:
                st.metric("Targhe Riapparse", stats['reappeared_plates'])
            with col3:
                st.metric("Durata Media Annunci", f"{stats['avg_listing_duration']:.1f} giorni")

if __name__ == "__main__":
    main()