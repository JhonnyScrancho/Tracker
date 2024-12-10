import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
from typing import List, Dict, Optional
from utils.datetime_utils import normalize_df_dates, get_current_time, calculate_date_diff

def show_anomaly_dashboard(tracker, dealer_id: str):
    """Mostra dashboard completa delle anomalie per un dealer"""
    st.subheader("📊 Analisi Anomalie")
    
    # Recupera dati
    listings = tracker.get_active_listings(dealer_id)
    history = tracker.get_dealer_history(dealer_id)
    
    if not listings or not history:
        st.info("Nessun dato disponibile per l'analisi")
        return
        
    # Converti in DataFrame
    df_history = pd.DataFrame(history)
    df_listings = pd.DataFrame(listings)
    
    # Layout principale con tabs
    tabs = st.tabs([
        "🔄 Variazioni Prezzi", 
        "⚠️ Rimozioni", 
        "📈 Trend",
        "🔍 Pattern Sospetti"
    ])
    
    with tabs[0]:
        show_price_anomalies(df_history, df_listings)
        
    with tabs[1]:
        show_removed_listings(df_history, tracker)
        
    with tabs[2]:
        show_temporal_analysis(df_history, df_listings)
        
    with tabs[3]:
        show_suspicious_patterns(df_history, df_listings)

def show_price_anomalies(df_history: pd.DataFrame, df_listings: pd.DataFrame):
    """Analizza e mostra anomalie nei prezzi"""
    if df_history.empty or 'price' not in df_history.columns:
        st.info("Dati insufficienti per l'analisi prezzi")
        return
    
    # Calcola variazioni significative
    price_changes = []
    for listing_id in df_history['listing_id'].unique():
        listing_data = df_history[df_history['listing_id'] == listing_id].sort_values('date')
        if len(listing_data) > 1:
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
                    'title': details.get('title', 'N/D'),
                    'image_url': details.get('image_urls', [''])[0] if details.get('image_urls') else None
                })
    
    if price_changes:
        df_changes = pd.DataFrame(price_changes)
        df_changes = df_changes.sort_values('date', ascending=False)
        
        # Metriche principali
        cols = st.columns(3)
        with cols[0]:
            st.metric("Variazioni Totali", len(df_changes))
        with cols[1]:
            st.metric("Variazione Media", f"{df_changes['variation'].mean():.1f}%")
        with cols[2]:
            st.metric("Max Variazione", f"{df_changes['variation'].max():.1f}%")
        
        # Mostra variazioni significative
        st.write("### Variazioni Significative (>10%)")
        for _, row in df_changes.iterrows():
            with st.expander(f"{row['title']} - {row['plate']}"):
                cols = st.columns([1, 2])
                with cols[0]:
                    if row['image_url']:
                        st.image(row['image_url'], width=200)
                with cols[1]:
                    st.metric("Variazione", f"{row['variation']:.1f}%",
                             delta=f"€{row['new_price'] - row['old_price']:,.0f}")
                    st.write(f"Prezzo precedente: €{row['old_price']:,.0f}")
                    st.write(f"Nuovo prezzo: €{row['new_price']:,.0f}")
                    st.caption(f"Data variazione: {row['date'].strftime('%d/%m/%Y %H:%M')}")
    else:
        st.info("Nessuna variazione significativa rilevata")

def show_removed_listings(df_history: pd.DataFrame, tracker):
    """Mostra dettagli annunci rimossi"""
    removed = df_history[df_history['event'] == 'removed'].copy()
    if removed.empty:
        st.info("Nessun annuncio rimosso")
        return
    
    # Raggruppa per data rimozione
    removed['date_str'] = removed['date'].dt.strftime('%d/%m/%Y')
    groups = removed.groupby('date_str')
    
    # Metriche
    total_removed = len(removed)
    avg_per_day = total_removed / len(groups)
    
    cols = st.columns(3)
    with cols[0]:
        st.metric("Totale Rimozioni", total_removed)
    with cols[1]:
        st.metric("Media Giornaliera", f"{avg_per_day:.1f}")
    with cols[2]:
        st.metric("Giorni con Rimozioni", len(groups))
    
    # Timeline rimozioni
    st.write("### Timeline Rimozioni")
    for date, group in groups:
        with st.expander(f"📅 {date} - {len(group)} rimozioni"):
            for _, row in group.iterrows():
                details = row.get('listing_details', {})
                
                cols = st.columns([1, 2])
                with cols[0]:
                    if details.get('image_urls'):
                        st.image(details['image_urls'][0], width=200)
                with cols[1]:
                    if details.get('title'):
                        st.write(f"**{details['title']}**")
                    if details.get('plate'):
                        st.write(f"🚗 Targa: {details['plate']}")
                    if details.get('price'):
                        st.write(f"💰 Ultimo prezzo: €{details['price']:,.0f}")
                    st.caption(f"Rimosso il: {row['date'].strftime('%d/%m/%Y %H:%M')}")
                st.divider()

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

def show_suspicious_patterns(df_history: pd.DataFrame, df_listings: pd.DataFrame):
    """Analizza e mostra pattern sospetti"""
    st.write("### 🔍 Pattern Sospetti")
    
    # Pattern 1: Riapparizioni multiple
    reappearances = df_history[df_history['event'] == 'reappeared']
    if not reappearances.empty:
        reapp_counts = reappearances.groupby('listing_id').size()
        multiple_reapp = reapp_counts[reapp_counts > 1]
        
        if not multiple_reapp.empty:
            st.write("#### 🔄 Riapparizioni Multiple")
            for listing_id, count in multiple_reapp.items():
                listing_data = df_history[df_history['listing_id'] == listing_id].sort_values('date')
                details = listing_data.iloc[-1].get('listing_details', {})
                
                with st.expander(f"{details.get('title', 'N/D')} - {count} riapparizioni"):
                    cols = st.columns([1, 2])
                    with cols[0]:
                        if details.get('image_urls'):
                            st.image(details['image_urls'][0], width=200)
                    with cols[1]:
                        st.write(f"🚗 Targa: {details.get('plate', 'N/D')}")
                        st.write(f"💰 Ultimo prezzo: €{listing_data.iloc[-1]['price']:,.0f}")
                        st.write(f"📅 Prima vista: {listing_data['date'].min().strftime('%d/%m/%Y')}")
                        st.write(f"📅 Ultima vista: {listing_data['date'].max().strftime('%d/%m/%Y')}")
    
    # Pattern 2: Variazioni prezzo anomale
    st.write("#### 💰 Variazioni Prezzo Anomale")
    price_changes = []
    for listing_id in df_history['listing_id'].unique():
        listing_data = df_history[df_history['listing_id'] == listing_id].sort_values('date')
        if len(listing_data) > 1:
            price_series = listing_data['price']
            total_variation = (price_series.max() - price_series.min()) / price_series.min() * 100
            if total_variation > 20:  # Variazione >20%
                details = listing_data.iloc[-1].get('listing_details', {})
                price_changes.append({
                    'listing_id': listing_id,
                    'title': details.get('title', 'N/D'),
                    'plate': details.get('plate', 'N/D'),
                    'variation': total_variation,
                    'image_url': details.get('image_urls', [''])[0],
                    'min_price': price_series.min(),
                    'max_price': price_series.max()
                })
    
    if price_changes:
        for change in sorted(price_changes, key=lambda x: x['variation'], reverse=True):
            with st.expander(f"{change['title']} - Variazione {change['variation']:.1f}%"):
                cols = st.columns([1, 2])
                with cols[0]:
                    if change['image_url']:
                        st.image(change['image_url'], width=200)
                with cols[1]:
                    st.write(f"🚗 Targa: {change['plate']}")
                    st.write(f"💰 Prezzo minimo: €{change['min_price']:,.0f}")
                    st.write(f"💰 Prezzo massimo: €{change['max_price']:,.0f}")
                    st.write(f"📊 Variazione: {change['variation']:.1f}%")

def show_temporal_analysis(df_history: pd.DataFrame, df_listings: pd.DataFrame):
    """Mostra analisi temporale delle attività con tutti i dettagli"""
    from utils.datetime_utils import get_current_time, normalize_df_dates, normalize_datetime
    
    st.write("### 📈 Trend Attività")
    
    # Normalizza DataFrame usando l'utility esistente
    df_history = normalize_df_dates(df_history)
    df_history['date_str'] = df_history['date'].dt.strftime('%d/%m/%Y')
    df_grouped = df_history.groupby(['date_str', 'event']).size().reset_index(name='count')
    
    # Crea grafico eventi
    events = {
        'update': 'Aggiornamenti',
        'removed': 'Rimozioni',
        'price_changed': 'Cambi Prezzo',
        'reappeared': 'Riapparizioni'
    }
    colors = {
        'update': '#3498db',
        'removed': '#e74c3c',
        'price_changed': '#2ecc71',
        'reappeared': '#f39c12'
    }
    
    fig = go.Figure()
    for event in events:
        event_data = df_grouped[df_grouped['event'] == event]
        if not event_data.empty:
            fig.add_trace(go.Scatter(
                x=event_data['date_str'],
                y=event_data['count'],
                name=events[event],
                line=dict(color=colors[event]),
                mode='lines+markers'
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
    
    # Grafico trend prezzi
    st.write("### 💰 Trend Prezzi")
    price_data = df_history[df_history['price'].notna()].copy()
    if not price_data.empty:
        price_fig = go.Figure()
        
        # Prezzo medio per giorno
        daily_avg = price_data.groupby('date_str')['price'].mean().reset_index()
        price_fig.add_trace(go.Scatter(
            x=daily_avg['date_str'],
            y=daily_avg['price'],
            name='Prezzo Medio',
            line=dict(color='#2ecc71')
        ))
        
        price_fig.update_layout(
            title="Andamento Prezzi nel Tempo",
            xaxis_title="Data",
            yaxis_title="Prezzo (€)",
            height=400
        )
        
        st.plotly_chart(price_fig, use_container_width=True)
    
    # Statistiche temporali dettagliate
    st.write("### 📊 Statistiche Temporali")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Permanenza media annunci
        active_days = []
        now = get_current_time()  # Usa l'utility per il timestamp corrente
        
        if 'first_seen' in df_listings.columns:
            for _, listing in df_listings.iterrows():
                if pd.notna(listing.get('first_seen')):
                    # Usa l'utility per normalizzare la data
                    first_seen = normalize_datetime(listing['first_seen'])
                    if first_seen is not None:
                        days = (now - first_seen).days
                        if days >= 0:
                            active_days.append(days)
                        
            if active_days:
                avg_days = sum(active_days) / len(active_days)
                st.metric("Permanenza Media", f"{avg_days:.1f} giorni")
            
    with col2:
        # Tasso di rimozione
        if not df_history.empty:
            date_range = (df_history['date'].max() - df_history['date'].min()).days or 1
            removed_count = len(df_history[df_history['event'] == 'removed'])
            removal_rate = removed_count / date_range * 7
            st.metric("Rimozioni/Settimana", f"{removal_rate:.1f}")
            
    with col3:
        # Tasso di riapparizione
        reappeared = len(df_history[df_history['event'] == 'reappeared'])
        if removed_count > 0:
            reapp_rate = reappeared / removed_count * 100
            st.metric("Tasso Riapparizione", f"{reapp_rate:.1f}%")
            
    with col4:
        # Variazioni prezzo medie
        price_changes = df_history[df_history['event'] == 'price_changed']
        if not price_changes.empty:
            avg_changes = len(price_changes) / date_range
            st.metric("Cambi Prezzo/Giorno", f"{avg_changes:.1f}")
    
    # Segmentazione temporale
    st.write("### 🕒 Segmentazione Temporale")
    df_history['hour'] = df_history['date'].dt.hour
    hourly_dist = df_history.groupby('hour')['event'].count()
    
    hour_fig = go.Figure(data=[go.Bar(
        x=hourly_dist.index,
        y=hourly_dist.values,
        marker_color='#3498db'
    )])
    
    hour_fig.update_layout(
        title="Distribuzione Oraria Eventi",
        xaxis_title="Ora del Giorno",
        yaxis_title="Numero Eventi",
        height=300
    )
    
    st.plotly_chart(hour_fig, use_container_width=True)