import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
from typing import List, Dict, Optional
from utils.datetime_utils import normalize_df_dates, get_current_time, calculate_date_diff
from utils.formatting import format_price, format_duration, format_date
from utils.anomaly_detection import detect_price_anomalies, find_reappeared_vehicles
import pytz

from utils.stats import calculate_dealer_stats


def show_dealer_overview(tracker, dealer_id: str):
    """Mostra overview statistiche del concessionario con variazioni"""
    current_listings = tracker.get_active_listings(dealer_id)
    stats = calculate_dealer_stats(current_listings)
    
    # Recupera statistiche precedenti per confronto
    previous_stats = tracker.get_previous_stats(dealer_id)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        delta = None
        if previous_stats and 'total_cars' in previous_stats:
            delta = stats['total_cars'] - previous_stats['total_cars']
        st.metric("🚗 Auto Totali", 
                 stats['total_cars'], 
                 f"{delta:+d}" if delta is not None else None,
                 help="Numero totale di auto attualmente in vendita")
    
    with col2:
        delta_value = None
        if previous_stats and 'total_value' in previous_stats:
            delta_value = stats['total_value'] - previous_stats['total_value']
        st.metric("💰 Valore Totale", 
                 format_price(stats['total_value']),
                 f"{format_price(delta_value)}" if delta_value is not None else None,
                 help="Valore totale del parco auto")
    
    with col3:
        delta_price = None
        if previous_stats and 'avg_price' in previous_stats:
            delta_price = stats['avg_price'] - previous_stats['avg_price']
        st.metric("🏷️ Prezzo Medio", 
                 format_price(stats['avg_price']),
                 f"{format_price(delta_price)}" if delta_price is not None else None,
                 help="Prezzo medio delle auto in vendita")
    
    with col4:
        delta_missing = None
        if previous_stats and 'missing_plates' in previous_stats:
            delta_missing = stats['missing_plates'] - previous_stats['missing_plates']
        st.metric("🔍 Targhe Mancanti", 
                 stats['missing_plates'],
                 f"{delta_missing:+d}" if delta_missing is not None else None,
                 help="Numero di auto senza targa")
        
    # Statistiche aggiuntive in expander
    with st.expander("📊 Statistiche Dettagliate", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            if stats['discounted_cars'] > 0:
                st.metric("🏷️ Auto in Sconto", 
                         stats['discounted_cars'],
                         f"Sconto medio: {stats['avg_discount']:.1f}%")
            
            if 'avg_days_listed' in stats:
                st.metric("⏱️ Permanenza Media", 
                         f"{stats['avg_days_listed']:.1f} giorni")
                
        with col2:
            if 'brand_distribution' in stats and stats['brand_distribution']:
                st.write("🏭 Distribuzione Marche")
                brands_df = pd.DataFrame(
                    list(stats['brand_distribution'].items()),
                    columns=['Marca', 'Conteggio']
                ).sort_values('Conteggio', ascending=False)
                
                st.bar_chart(brands_df.set_index('Marca'))

def show_dealer_insights(tracker, dealer_id: str):
    """Mostra insights e analisi del concessionario con visualizzazioni migliorate"""
    history = tracker.get_dealer_history(dealer_id)
    
    if not history:
        st.info("Dati insufficienti per l'analisi")
        return
        
    col1, col2 = st.columns(2)
    
    with col1:
        # Timeline eventi
        timeline = create_timeline_chart(history)
        if timeline:
            st.plotly_chart(timeline, use_container_width=True)
            
            # Metriche eventi
            events_df = pd.DataFrame(history)
            event_counts = events_df['event'].value_counts()
            
            st.write("📊 Distribuzione Eventi")
            metrics_cols = st.columns(len(event_counts))
            for i, (event, count) in enumerate(event_counts.items()):
                with metrics_cols[i]:
                    icon = {
                        'update': '🔄',
                        'removed': '❌',
                        'price_changed': '💰',
                        'reappeared': '↩️'
                    }.get(event, '❓')
                    
                    st.metric(f"{icon} {event.title()}", count)
            
    with col2:
        # Storico prezzi con analisi trend
        price_history = create_price_history_chart(history)
        if price_history:
            st.plotly_chart(price_history, use_container_width=True)
            
            # Analisi variazioni prezzo
            price_changes = analyze_price_changes(history)
            if price_changes:
                st.write("💰 Analisi Variazioni Prezzo")
                
                changes_cols = st.columns(3)
                with changes_cols[0]:
                    st.metric("Variazioni Totali", 
                             price_changes['total_changes'])
                with changes_cols[1]:
                    st.metric("Variazione Media", 
                             f"{price_changes['avg_variation']:.1f}%")
                with changes_cols[2]:
                    st.metric("Variazioni Significative",
                             price_changes['significant_changes'])

def analyze_price_changes(history_data: List[Dict]) -> Dict:
    """Analizza le variazioni di prezzo nel tempo"""
    if not history_data:
        return {}
        
    df = pd.DataFrame(history_data)
    price_changes = df[df['event'] == 'price_changed']
    
    analysis = {
        'total_changes': len(price_changes),
        'avg_variation': 0,
        'significant_changes': 0,
        'largest_increase': 0,
        'largest_decrease': 0
    }
    
    if not price_changes.empty:
        variations = []
        for listing_id in price_changes['listing_id'].unique():
            listing_prices = price_changes[price_changes['listing_id'] == listing_id]['price']
            if len(listing_prices) > 1:
                pct_changes = listing_prices.pct_change() * 100
                variations.extend(pct_changes.dropna().tolist())
        
        if variations:
            analysis['avg_variation'] = np.mean(variations)
            analysis['significant_changes'] = len([v for v in variations if abs(v) > 10])
            analysis['largest_increase'] = max(variations)
            analysis['largest_decrease'] = min(variations)
    
    return analysis

def create_timeline_chart(history_data: List[Dict]) -> go.Figure:
    """Crea grafico timeline degli eventi con tooltips migliorati e dettagli"""
    if not history_data:
        return None
    
    df = pd.DataFrame(history_data)
    df['date'] = pd.to_datetime(df['date'])
    
    # Aggrega eventi per data
    events_by_date = df.groupby(['date', 'event']).size().reset_index(name='count')
    
    # Colori per tipo evento
    colors = {
        'update': 'rgb(46, 134, 193)',
        'removed': 'rgb(231, 76, 60)',
        'price_changed': 'rgb(39, 174, 96)',
        'reappeared': 'rgb(243, 156, 18)'
    }
    
    fig = go.Figure()
    
    # Crea una traccia per ogni tipo di evento
    for event in df['event'].unique():
        event_data = events_by_date[events_by_date['event'] == event]
        
        hover_text = []
        for _, row in event_data.iterrows():
            daily_events = df[
                (df['date'].dt.date == row['date'].date()) & 
                (df['event'] == event)
            ]
            details = "<br>".join([
                f"• {get_event_details(event_row)}"
                for _, event_row in daily_events.iterrows()
            ])
            hover_text.append(f"Data: {row['date'].strftime('%d/%m/%Y')}<br>"
                            f"Eventi: {row['count']}<br>"
                            f"Dettagli:<br>{details}")
        
        fig.add_trace(go.Scatter(
            x=event_data['date'],
            y=event_data['count'],
            name=event.title(),
            mode='lines+markers',
            line=dict(color=colors.get(event, 'gray'), width=2),
            hovertemplate="%{text}",
            text=hover_text
        ))
    
    fig.update_layout(
        title="Timeline Eventi",
        xaxis_title="Data",
        yaxis_title="Numero Eventi",
        height=400,
        hovermode='closest',
        showlegend=True
    )
    
    return fig

def get_event_details(event_row: pd.Series) -> str:
    """Genera dettagli formattatati per un evento"""
    details = []
    
    if 'listing_details' in event_row and event_row['listing_details']:
        listing = event_row['listing_details']
        if listing.get('title'):
            details.append(listing['title'])
        if listing.get('plate'):
            details.append(f"Targa: {listing['plate']}")
    
    if event_row['event'] == 'price_changed':
        if 'price' in event_row:
            details.append(f"Nuovo prezzo: {format_price(event_row['price'])}")
    
    return " - ".join(details) if details else "N/D"

def create_price_history_chart(history_data: List[Dict]) -> go.Figure:
    """Crea grafico storico prezzi con bande di confidenza e trend"""
    if not history_data:
        return None
    
    df = pd.DataFrame(history_data)
    df['date'] = pd.to_datetime(df['date'])
    
    # Calcola statistiche prezzi per bande di confidenza
    price_data = df[df['price'].notna()]
    mean_price = price_data['price'].mean()
    std_price = price_data['price'].std()
    
    fig = go.Figure()
    
    # Aggiungi bande di confidenza
    fig.add_trace(go.Scatter(
        name='Upper Bound',
        x=df['date'],
        y=[mean_price + 2*std_price] * len(df),
        mode='lines',
        line=dict(width=0),
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        name='Lower Bound',
        x=df['date'],
        y=[mean_price - 2*std_price] * len(df),
        mode='lines',
        line=dict(width=0),
        fillcolor='rgba(68, 68, 68, 0.1)',
        fill='tonexty',
        showlegend=False
    ))
    
    # Linea prezzo medio mobile
    window = 7  # 7 giorni
    if len(price_data) > window:
        rolling_mean = price_data.set_index('date')['price'].rolling(window).mean()
        fig.add_trace(go.Scatter(
            x=rolling_mean.index,
            y=rolling_mean.values,
            name='Media Mobile (7g)',
            line=dict(color='rgb(46, 134, 193)', dash='dash')
        ))
    
    # Prezzi effettivi
    fig.add_trace(go.Scatter(
        x=price_data['date'],
        y=price_data['price'],
        name='Prezzo',
        mode='lines+markers',
        line=dict(color='rgb(39, 174, 96)'),
        hovertemplate="Data: %{x|%d/%m/%Y}<br>" +
                     "Prezzo: €%{y:,.0f}<br>"
    ))
    
    fig.update_layout(
        title="Andamento Prezzi",
        xaxis_title="Data",
        yaxis_title="Prezzo (€)",
        height=400,
        hovermode='x unified',
        yaxis=dict(tickformat="€,.0f"),
        showlegend=True
    )
    
    return fig