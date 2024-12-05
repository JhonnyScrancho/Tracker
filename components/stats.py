import streamlit as st
from utils.stats import calculate_dealer_stats, create_price_history_chart
from utils.formatting import format_price, format_duration

def show_dealer_overview(tracker, dealer_id: str):
    """Mostra overview statistiche del concessionario"""
    listings = tracker.get_active_listings(dealer_id)
    stats = calculate_dealer_stats(listings)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🚗 Auto Totali", stats['total_cars'])
    with col2:
        st.metric("💰 Valore Totale", format_price(stats['total_value']))
    with col3:
        st.metric("🏷️ Prezzo Medio", format_price(stats['avg_price']))
    with col4:
        st.metric("🔍 Targhe Mancanti", stats['missing_plates'])
        
    if stats['discounted_cars'] > 0:
        st.caption(f"Auto in sconto: {stats['discounted_cars']} (sconto medio: {stats['avg_discount']:.1f}%)")

def show_dealer_insights(tracker, dealer_id: str):
    """Mostra insights e analisi del concessionario"""
    history = tracker.get_dealer_history(dealer_id)
    
    col1, col2 = st.columns(2)
    with col1:
        timeline = create_timeline_chart(history)
        if timeline:
            st.plotly_chart(timeline, use_container_width=True)
            
    with col2:
        price_history = create_price_history_chart(history)
        if price_history:
            st.plotly_chart(price_history, use_container_width=True)