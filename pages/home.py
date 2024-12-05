import streamlit as st
from services.tracker import AutoTracker
import pandas as pd
from datetime import datetime

def show():
    st.title("🏠 Dashboard")
    
    tracker = AutoTracker()
    dealers = tracker.get_dealers()
    
    if not dealers:
        st.info("👋 Aggiungi un concessionario per iniziare")
        return
        
    # Stats generali
    total_cars = 0
    total_value = 0
    
    cols = st.columns(3)
    for dealer in dealers:
        listings = tracker.get_active_listings(dealer['id'])
        total_cars += len(listings)
        total_value += sum(l.get('original_price', 0) for l in listings if l.get('original_price'))
    
    with cols[0]:
        st.metric("🏢 Concessionari", len(dealers))
    with cols[1]:    
        st.metric("🚗 Auto Totali", total_cars)
    with cols[2]:
        st.metric("💰 Valore Totale", f"€{total_value:,.0f}".replace(",", "."))
        
    # Lista concessionari
    st.subheader("🏢 Concessionari Monitorati")
    
    for dealer in dealers:
        with st.expander(f"**{dealer['url'].split('/')[-1].upper()}** - {dealer['url']}", expanded=False):
            if dealer.get('last_update'):
                st.caption(f"Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")
                
            listings = tracker.get_active_listings(dealer['id'])
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
                    
                # Link alla pagina del concessionario    
                st.page_link(f"pages/dealer_view?id={dealer['id']}", label="Vedi Dettagli")
            else:
                st.info("ℹ️ Nessun annuncio attivo")