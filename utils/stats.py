from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from typing import List, Dict

def calculate_dealer_stats(listings: List[Dict]) -> Dict:
    """Calcola statistiche aggregate per un concessionario"""
    stats = {
        'total_cars': len(listings),
        'total_value': 0,
        'avg_price': 0,
        'missing_plates': 0,
        'discounted_cars': 0,
        'avg_discount': 0
    }
    
    if not listings:
        return stats
        
    # Calcolo valori
    prices = []
    discounts = []
    
    for listing in listings:
        price = listing.get('original_price')
        if price:
            stats['total_value'] += price
            prices.append(price)
            
        if not listing.get('plate'):
            stats['missing_plates'] += 1
            
        if listing.get('has_discount') and listing.get('discount_percentage'):
            stats['discounted_cars'] += 1
            discounts.append(listing['discount_percentage'])
            
    if prices:
        stats['avg_price'] = sum(prices) / len(prices)
        
    if discounts:
        stats['avg_discount'] = sum(discounts) / len(discounts)
        
    return stats

def create_timeline_chart(history_data):
    """
    Crea grafico timeline delle attività del dealer
    
    Args:
        history_data: Lista di eventi storici dal database
        
    Returns:
        Figura Plotly con il grafico timeline
    """
    if not history_data:
        return None
        
    # Converti dati in DataFrame
    df = pd.DataFrame(history_data)
    
    # Crea la figura
    fig = go.Figure()
    
    # Aggiungi una traccia per ogni annuncio
    for listing_id in df['listing_id'].unique():
        mask = df['listing_id'] == listing_id
        listing_data = df[mask]
        
        # Aggiungi traccia al grafico
        fig.add_trace(go.Scatter(
            x=listing_data['date'],
            y=[listing_id] * len(listing_data),
            mode='markers+lines',
            name=f'Annuncio {listing_id[:8]}...',  # Tronca ID lunghi
            hovertemplate='%{text}<br>Data: %{x}',
            text=[f"Evento: {e}" for e in listing_data['event']]
        ))
    
    # Configura layout
    fig.update_layout(
        title="Timeline Attività Annunci",
        xaxis_title="Data",
        yaxis_title="ID Annuncio",
        height=400,
        showlegend=True,
        xaxis=dict(
            type='date',
            tickformat='%d/%m/%Y'
        ),
        yaxis=dict(
            type='category'
        ),
        hovermode='closest'
    )
    
    return fig

def create_price_history_chart(history_data):
    """Crea grafico storico prezzi"""
    if not history_data:
        return None
        
    df = pd.DataFrame(history_data)
    df = df.sort_values('date')
    
    fig = go.Figure()
    
    # Prezzo originale
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['price'],
        mode='lines+markers',
        name='Prezzo Originale',
        line=dict(color='blue')
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
                line=dict(color='red')
            ))
    
    fig.update_layout(
        title="Storico Prezzi",
        xaxis_title="Data",
        yaxis_title="Prezzo (€)",
        height=400,
        showlegend=True,
        yaxis_tickformat='€,.0f'
    )
    
    return fig