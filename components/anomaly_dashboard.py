import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from typing import List, Dict, Optional
from utils.datetime_utils import normalize_df_dates, calculate_date_diff

def show_anomaly_dashboard(tracker, dealer_id: str):
    """Mostra dashboard delle anomalie per un dealer"""
    st.subheader("📊 Analisi Anomalie")
    
    # Recupera dati
    listings = tracker.get_active_listings(dealer_id)
    history = tracker.get_dealer_history(dealer_id)
    
    if not listings or not history:
        st.info("Nessun dato disponibile per l'analisi")
        return
        
    # Converte in DataFrame
    df_history = pd.DataFrame(history)
    df_listings = pd.DataFrame(listings)
    
    # Layout a colonne
    col1, col2 = st.columns(2)
    
    with col1:
        show_price_anomalies(df_history, df_listings)
        
    with col2:
        show_reappearance_analysis(df_history)
        
    # Analisi temporale
    st.subheader("⏱️ Analisi Temporale")
    show_temporal_analysis(df_history, df_listings)

def show_price_anomalies(df_history: pd.DataFrame, df_listings: pd.DataFrame):
    """Analizza e mostra anomalie nei prezzi"""
    st.write("💰 Anomalie Prezzi")
    
    if df_history.empty or 'price' not in df_history.columns:
        st.info("Dati insufficienti per l'analisi prezzi")
        return
    
    # Calcola variazioni prezzi significative
    price_changes = []
    for listing_id in df_history['listing_id'].unique():
        listing_data = df_history[df_history['listing_id'] == listing_id].sort_values('date')
        if len(listing_data) > 1:
            # Calcola variazione percentuale
            price_change = listing_data['price'].pct_change()
            significant_changes = listing_data[abs(price_change) > 0.1]
            
            for _, row in significant_changes.iterrows():
                details = row.get('listing_details', {})
                price_changes.append({
                    'listing_id': listing_id,
                    'date': row['date'],
                    'variation': price_change.loc[row.name] * 100,
                    'old_price': listing_data['price'].shift(1).loc[row.name],
                    'new_price': row['price'],
                    'plate': details.get('plate', 'N/D'),
                    'title': details.get('title', 'N/D')
                })
    
    if price_changes:
        df_changes = pd.DataFrame(price_changes)
        df_changes = df_changes.sort_values('date', ascending=False)
        
        # Mostra tabella variazioni
        st.write("Variazioni Prezzi Significative (>10%)")
        for _, row in df_changes.iterrows():
            with st.expander(f"{row['title']} - {row['plate']}"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Variazione", f"{row['variation']:.1f}%")
                with col2:
                    st.metric("Prezzo Precedente", f"€{row['old_price']:,.0f}")
                with col3:
                    st.metric("Nuovo Prezzo", f"€{row['new_price']:,.0f}")
                st.caption(f"Data variazione: {row['date'].strftime('%d/%m/%Y')}")
    else:
        st.info("Nessuna variazione significativa rilevata")

def show_reappearance_analysis(df_history: pd.DataFrame):
    """Analizza e mostra veicoli riapparsi"""
    st.write("🔄 Analisi Riapparizioni")
    
    if df_history.empty:
        st.info("Dati insufficienti per l'analisi riapparizioni")
        return
        
    # Identifica riapparizioni
    reappearances = []
    for listing_id in df_history['listing_id'].unique():
        listing_data = df_history[df_history['listing_id'] == listing_id].sort_values('date')
        events = listing_data['event'].tolist()
        
        removed_date = None
        for idx, (event, row) in enumerate(zip(events, listing_data.iterrows())):
            if event == 'removed':
                removed_date = row[1]['date']
            elif event == 'update' and removed_date:
                details = row[1].get('listing_details', {})
                reappearances.append({
                    'listing_id': listing_id,
                    'removed_date': removed_date,
                    'reappeared_date': row[1]['date'],
                    'days_gone': (row[1]['date'] - removed_date).days,
                    'plate': details.get('plate', 'N/D'),
                    'title': details.get('title', 'N/D'),
                    'price_before': listing_data.iloc[idx-1]['price'] if idx > 0 else None,
                    'price_after': row[1]['price']
                })
                removed_date = None
    
    if reappearances:
        df_reapp = pd.DataFrame(reappearances)
        df_reapp = df_reapp.sort_values('reappeared_date', ascending=False)
        
        # Mostra riapparizioni
        for _, row in df_reapp.iterrows():
            with st.expander(f"{row['title']} - {row['plate']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Giorni Assente", row['days_gone'])
                with col2:
                    if row['price_before'] and row['price_after']:
                        price_diff = ((row['price_after'] - row['price_before']) / row['price_before'] * 100)
                        st.metric("Variazione Prezzo", f"{price_diff:.1f}%")
                st.caption(f"Rimosso: {row['removed_date'].strftime('%d/%m/%Y')}")
                st.caption(f"Riapparso: {row['reappeared_date'].strftime('%d/%m/%Y')}")
    else:
        st.info("Nessuna riapparizione rilevata")

def show_temporal_analysis(df_history: pd.DataFrame, df_listings: pd.DataFrame):
    df_history = normalize_df_dates(df_history)
    df_listings = normalize_df_dates(df_listings)
    if df_history.empty:
        st.info("Dati insufficienti per l'analisi temporale")
        return
        
    # Crea grafico eventi nel tempo
    fig = go.Figure()
    
    # Aggrega eventi per data
    events_by_date = df_history.groupby(['date', 'event']).size().reset_index(name='count')
    
    # Colori per tipo evento
    colors = {
        'update': 'blue',
        'removed': 'red',
        'price_changed': 'green'
    }
    
    # Crea una traccia per ogni tipo di evento
    for event in events_by_date['event'].unique():
        event_data = events_by_date[events_by_date['event'] == event]
        fig.add_trace(go.Scatter(
            x=event_data['date'],
            y=event_data['count'],
            mode='lines+markers',
            name=event.title(),
            line=dict(color=colors.get(event, 'gray')),
            hovertemplate='Data: %{x}<br>' +
                         'Eventi: %{y}'
        ))
    
    fig.update_layout(
        title="Distribuzione Eventi nel Tempo",
        xaxis_title="Data",
        yaxis_title="Numero Eventi",
        height=400,
        showlegend=True,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # Statistiche temporali
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Tempo medio di permanenza
        active_days = []
        for _, listing in df_listings.iterrows():
            if listing.get('first_seen'):
                days = (datetime.now() - listing['first_seen']).days
                active_days.append(days)
        if active_days:
            avg_days = sum(active_days) / len(active_days)
            st.metric("Permanenza Media", f"{avg_days:.1f} giorni")
            
    with col2:
        # Frequenza rimozioni
        total_removed = len(df_history[df_history['event'] == 'removed'])
        total_days = (df_history['date'].max() - df_history['date'].min()).days
        if total_days > 0:
            removal_rate = total_removed / total_days * 7  # settimanale
            st.metric("Rimozioni/Settimana", f"{removal_rate:.1f}")
            
    with col3:
        # Tasso di riapparizione
        reappearances = len(df_history[df_history['event'] == 'reappeared'])
        if total_removed > 0:
            reapp_rate = reappearances / total_removed * 100
            st.metric("Tasso Riapparizione", f"{reapp_rate:.1f}%")