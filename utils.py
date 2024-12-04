from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

def format_price(price):
    """Formatta un prezzo in formato leggibile"""
    if pd.isna(price) or price is None:
        return "N/D"
    return f"€{price:,.0f}".replace(",", ".")

def format_date(date):
    """Formatta una data in formato leggibile"""
    if not date:
        return "N/D"
    return date.strftime("%d/%m/%Y")

def create_timeline_chart(history_data):
    """Crea grafico timeline delle attività"""
    if not history_data:
        return None
        
    df = pd.DataFrame(history_data)
    
    fig = go.Figure()
    for listing_id in df['listing_id'].unique():
        mask = df['listing_id'] == listing_id
        listing_data = df[mask]
        
        fig.add_trace(go.Scatter(
            x=listing_data['date'],
            y=[listing_id] * len(listing_data),
            mode='markers+lines',
            name=f'Annuncio {listing_id}',
            hovertemplate='%{text}<br>Data: %{x}',
            text=[f"Evento: {e}" for e in listing_data['event']]
        ))
    
    fig.update_layout(
        title="Timeline Attività Annunci",
        xaxis_title="Data",
        yaxis_title="ID Annuncio",
        height=400,
        showlegend=True
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

def calculate_duration_stats(listings):
    """Calcola statistiche sulla durata degli annunci"""
    if not listings:
        return {
            'avg_duration': 0,
            'min_duration': 0,
            'max_duration': 0
        }
    
    now = datetime.now()
    durations = []
    
    for listing in listings:
        if listing.get('created_at'):
            duration = (now - listing['created_at']).days
            durations.append(duration)
    
    if not durations:
        return {
            'avg_duration': 0,
            'min_duration': 0,
            'max_duration': 0
        }
        
    return {
        'avg_duration': sum(durations) / len(durations),
        'min_duration': min(durations),
        'max_duration': max(durations)
    }

def calculate_price_stats(listings):
    """Calcola statistiche sui prezzi"""
    if not listings:
        return {
            'avg_price': 0,
            'min_price': 0,
            'max_price': 0,
            'discount_count': 0,
            'avg_discount': 0
        }
    
    prices = []
    discounts = []
    discount_count = 0
    
    for listing in listings:
        if listing.get('original_price'):
            prices.append(listing['original_price'])
            
            if listing.get('discounted_price'):
                discount = ((listing['original_price'] - listing['discounted_price']) / 
                          listing['original_price'] * 100)
                discounts.append(discount)
                discount_count += 1
    
    if not prices:
        return {
            'avg_price': 0,
            'min_price': 0,
            'max_price': 0,
            'discount_count': 0,
            'avg_discount': 0
        }
        
    return {
        'avg_price': sum(prices) / len(prices),
        'min_price': min(prices),
        'max_price': max(prices),
        'discount_count': discount_count,
        'avg_discount': sum(discounts) / len(discounts) if discounts else 0
    }

def format_duration(days):
    """Formatta una durata in giorni in formato leggibile"""
    if days < 1:
        return "< 1 giorno"
    elif days == 1:
        return "1 giorno"
    return f"{int(days)} giorni"