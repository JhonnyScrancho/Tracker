from datetime import datetime
import pytz
import pandas as pd
import plotly.graph_objects as go
from typing import List, Dict
import streamlit as st
from utils.datetime_utils import normalize_df_dates, calculate_date_diff, get_current_time


@st.cache_data(ttl=3600)
def calculate_dealer_stats(listings: List[Dict]) -> Dict:
    """
    Calcola statistiche aggregate per un concessionario
    
    Args:
        listings: Lista di dizionari contenenti i dati degli annunci
        
    Returns:
        Dict con le statistiche calcolate
    """
    stats = {
        'total_cars': len(listings),
        'total_value': 0,
        'avg_price': 0,
        'missing_plates': 0,
        'discounted_cars': 0,
        'avg_discount': 0,
        'avg_days_listed': 0,
        'reappeared_vehicles': 0,
        'price_stats': {
            'min': None,
            'max': None,
            'median': None,
            'std': None
        }
    }
    
    if not listings:
        return stats
        
    # Converti lista in DataFrame per calcoli più efficienti
    df = pd.DataFrame(listings)
    df = normalize_df_dates(df)
    
    # Statistiche prezzi
    prices = []
    total_value = 0
    
    for listing in listings:
        price = listing.get('original_price')
        if price and isinstance(price, (int, float)) and price > 0:
            prices.append(price)
            total_value += price
    
    if prices:
        stats['total_value'] = total_value
        stats['avg_price'] = sum(prices) / len(prices)
        
        # Statistiche prezzi dettagliate
        price_series = pd.Series(prices)
        stats['price_stats'].update({
            'min': price_series.min(),
            'max': price_series.max(),
            'median': price_series.median(),
            'std': price_series.std()
        })
    
    # Conteggio targhe mancanti
    stats['missing_plates'] = sum(1 for listing in listings 
                                if not listing.get('plate'))
    
    # Analisi sconti
    discounts = []
    for listing in listings:
        if (listing.get('has_discount') and 
            listing.get('original_price') and 
            listing.get('discounted_price')):
            
            original = listing['original_price']
            discounted = listing['discounted_price']
            
            if original > 0:  # Previene divisione per zero
                discount_pct = ((original - discounted) / original) * 100
                if 0 <= discount_pct <= 100:  # Validazione sconto
                    discounts.append(discount_pct)
                    stats['discounted_cars'] += 1
    
    if discounts:
        stats['avg_discount'] = sum(discounts) / len(discounts)
    
    # Calcolo durata media annunci
    now = get_current_time()
    listing_days = []
    
    for listing in listings:
        first_seen = listing.get('first_seen')
        if first_seen:
            try:
                days = calculate_date_diff(first_seen, now)
                if days is not None and days >= 0:
                    listing_days.append(days)
            except Exception as e:
                st.error(f"❌ Errore calcolo durata listing {listing.get('id')}: {str(e)}")
                continue
    
    if listing_days:
        stats['avg_days_listed'] = sum(listing_days) / len(listing_days)
    
    # Conteggio riapparizioni
    stats['reappeared_vehicles'] = sum(1 for listing in listings 
                                     if listing.get('reappeared'))
    
    # Statistiche aggiuntive
    stats.update({
        'active_listings': len([l for l in listings if l.get('active', True)]),
        'inactive_listings': len([l for l in listings if not l.get('active', True)]),
        'avg_mileage': None,
        'fuel_distribution': {},
        'brand_distribution': {}
    })
    
    # Calcolo chilometraggio medio
    mileages = [l.get('mileage') for l in listings 
                if l.get('mileage') and isinstance(l['mileage'], (int, float))]
    if mileages:
        stats['avg_mileage'] = sum(mileages) / len(mileages)
    
    # Distribuzione carburanti
    if 'fuel' in df.columns:
        fuel_counts = df['fuel'].value_counts().to_dict()
        stats['fuel_distribution'] = {
            str(k): int(v) for k, v in fuel_counts.items() if pd.notna(k)
        }
    
    # Distribuzione marche
    if 'title' in df.columns:
        df['brand'] = df['title'].apply(lambda x: str(x).split()[0] if pd.notna(x) else None)
        brand_counts = df['brand'].value_counts().to_dict()
        stats['brand_distribution'] = {
            str(k): int(v) for k, v in brand_counts.items() if pd.notna(k)
        }
    
    # Aggiungi timestamp calcolo
    stats['calculated_at'] = now.isoformat()
    
    return stats

@st.cache_data(ttl=3600)
def create_timeline_chart(history_data: List[Dict]) -> go.Figure:
    """Crea grafico timeline delle attività con migliore leggibilità"""
    if not history_data:
        return None
        
    df = pd.DataFrame(history_data)
    
    # Ottimizza dati veicoli per visualizzazione
    vehicle_details = {}
    for listing_id in df['listing_id'].unique():
        latest = df[df['listing_id'] == listing_id].iloc[-1]
        details = latest.get('listing_details', {})
        
        # Crea etichetta informativa
        plate = details.get('plate', 'NO TARGA')
        title = details.get('title', '')
        if title:
            # Estrai marca e modello
            parts = title.split(' ', 2)
            label = f"{plate} - {' '.join(parts[:2])}"
        else:
            label = f"{plate} - {listing_id[:8]}"
            
        vehicle_details[listing_id] = label
    
    fig = go.Figure()
    
    # Definisci colori per eventi con significato intuitivo
    colors = {
        'update': '#2E86C1',       # Blu - aggiornamento normale 
        'removed': '#E74C3C',      # Rosso - rimozione
        'reappeared': '#F39C12',   # Arancione - ricomparsa
        'price_changed': '#27AE60'  # Verde - cambio prezzo
    }
    
    # Crea tracce per ogni veicolo con tooltip migliorati
    for listing_id in df['listing_id'].unique():
        vehicle_data = df[df['listing_id'] == listing_id]
        
        # Aggiungi traccia principale con più informazioni nel tooltip
        fig.add_trace(go.Scatter(
            x=vehicle_data['date'],
            y=[vehicle_details[listing_id]] * len(vehicle_data),
            mode='lines+markers',
            name=vehicle_details[listing_id],
            line=dict(color=colors.get('update'), width=2),
            hovertemplate='<b>%{text}</b><br>' +
                         'Data: %{x|%d/%m/%Y %H:%M}<br>' +
                         'Prezzo: €%{customdata:,.0f}<br>' +
                         'Stato: %{text}',
            text=[f"Evento: {e.title()}" for e in vehicle_data['event']],
            customdata=vehicle_data['price'].fillna(0)
        ))
        
        # Evidenzia eventi speciali con marker più visibili
        for event in ['removed', 'reappeared', 'price_changed']:
            event_data = vehicle_data[vehicle_data['event'] == event]
            if not event_data.empty:
                fig.add_trace(go.Scatter(
                    x=event_data['date'],
                    y=[vehicle_details[listing_id]] * len(event_data),
                    mode='markers',
                    marker=dict(
                        symbol='star',
                        size=12,
                        color=colors.get(event),
                        line=dict(width=2, color='white')
                    ),
                    name=event.title(),
                    showlegend=False,
                    hovertemplate='<b>%{text}</b><br>' +
                                'Data: %{x|%d/%m/%Y %H:%M}<br>' +
                                'Prezzo: €%{customdata:,.0f}',
                    text=[f"{e.title()}" for e in event_data['event']],
                    customdata=event_data['price'].fillna(0)
                ))
    
    # Configura layout ottimizzato
    fig.update_layout(
        title=dict(
            text="Timeline Attività Annunci",
            x=0.5,
            xanchor='center',
            font=dict(size=20)
        ),
        xaxis_title="Data",
        yaxis_title="Veicolo",
        height=max(400, len(vehicle_details) * 40),
        showlegend=True,
        hovermode='closest',
        xaxis=dict(
            type='date',
            tickformat='%d/%m/%Y',
            rangeslider=dict(visible=True),
            tickfont=dict(size=12)
        ),
        yaxis=dict(
            type='category',
            tickfont=dict(size=12)
        ),
        plot_bgcolor='white',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Aggiungi griglia per migliore leggibilità
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    
    return fig

@st.cache_data(ttl=3600)
def create_price_history_chart(history_data: List[Dict]) -> go.Figure:
    """Crea grafico storico prezzi con evidenziazione anomalie e bande di confidenza"""
    if not history_data:
        return None
        
    df = pd.DataFrame(history_data)
    df = df.sort_values('date')
    
    # Calcola statistiche prezzi per bande di confidenza
    mean_price = df['price'].mean()
    std_price = df['price'].std()
    
    fig = go.Figure()
    
    # Aggiungi banda di confidenza con area colorata
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=[mean_price + 2*std_price] * len(df),
        fill=None,
        mode='lines',
        line=dict(color='rgba(200,200,200,0)'),
        name='Banda superiore (+2σ)',
        showlegend=False
    ))
    
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=[mean_price - 2*std_price] * len(df),
        fill='tonexty',
        mode='lines',
        line=dict(color='rgba(200,200,200,0)'),
        name='Intervallo di confidenza',
        fillcolor='rgba(200,200,200,0.2)'
    ))
    
    # Aggiungi linea prezzo medio
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=[mean_price] * len(df),
        mode='lines',
        line=dict(color='rgba(100,100,100,0.5)', dash='dash'),
        name='Prezzo medio'
    ))
    
    # Prezzo originale con tooltip migliorati
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['price'],
        mode='lines+markers',
        name='Prezzo Originale',
        line=dict(color='#2E86C1', width=2),
        hovertemplate='<b>Prezzo Originale</b><br>' +
                     'Data: %{x|%d/%m/%Y %H:%M}<br>' +
                     'Prezzo: €%{y:,.0f}<br>' +
                     'Evento: %{text}',
        text=df['event'].apply(lambda x: x.title())
    ))
    
    # Prezzo scontato se presente
    if 'discounted_price' in df.columns:
        mask = df['discounted_price'].notna()
        if mask.any():
            fig.add_trace(go.Scatter(
                x=df[mask]['date'],
                y=df[mask]['discounted_price'],
                mode='lines+markers',
                name='Prezzo Scontato',
                line=dict(color='#27AE60', width=2),
                hovertemplate='<b>Prezzo Scontato</b><br>' +
                            'Data: %{x|%d/%m/%Y %H:%M}<br>' +
                            'Prezzo: €%{y:,.0f}'
            ))
    
    # Evidenzia variazioni significative
    price_changes = df['price'].pct_change().abs()
    significant_changes = df[price_changes > 0.1]  # Variazioni > 10%
    
    if not significant_changes.empty:
        fig.add_trace(go.Scatter(
            x=significant_changes['date'],
            y=significant_changes['price'],
            mode='markers',
            marker=dict(
                symbol='star',
                size=12,
                color='#F39C12',  # Arancione per evidenziare
                line=dict(color='#E67E22', width=2)
            ),
            name='Variazioni >10%',
            hovertemplate='<b>Variazione Significativa</b><br>' +
                         'Data: %{x|%d/%m/%Y %H:%M}<br>' +
                         'Nuovo Prezzo: €%{y:,.0f}<br>' +
                         'Variazione: %{text}',
            text=[f"{(change*100):.1f}%" for change in price_changes[significant_changes.index]]
        ))
    
    # Configura layout ottimizzato
    fig.update_layout(
        title=dict(
            text="Storico Prezzi",
            x=0.5,
            xanchor='center',
            font=dict(size=20)
        ),
        xaxis_title="Data",
        yaxis_title="Prezzo (€)",
        height=500,
        showlegend=True,
        hovermode='x unified',
        yaxis=dict(
            tickformat='€,.0f',
            tickfont=dict(size=12)
        ),
        xaxis=dict(
            rangeslider=dict(visible=True),
            type='date',
            tickformat='%d/%m/%Y',
            tickfont=dict(size=12)
        ),
        plot_bgcolor='white',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    # Aggiungi griglia per migliore leggibilità
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
    
    return fig