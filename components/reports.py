from datetime import datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import pytz
from typing import List, Dict, Optional
from utils.datetime_utils import normalize_df_dates, get_current_time

def generate_weekly_report(tracker, dealer_id: str) -> Dict:
    """Genera report settimanale delle attività"""
    # Usa UTC per tutto
    end_date = datetime.now(pytz.UTC)
    start_date = end_date - timedelta(days=7)
    
    # Recupera dati periodo
    history = tracker.get_dealer_history(dealer_id)
    current_listings = tracker.get_active_listings(dealer_id)
    
    if not history:
        return {}
        
    df_history = pd.DataFrame(history)
    # Converti date in UTC se non lo sono già
    df_history['date'] = pd.to_datetime(df_history['date']).dt.tz_convert('UTC')
    
    # Filtra per periodo
    df_history = df_history[(df_history['date'] >= start_date) & 
                           (df_history['date'] <= end_date)]
    
    report = {
        'period': {
            'start': start_date,
            'end': end_date
        },
        'summary': {
            'total_active': len(current_listings),
            'new_listings': len(df_history[df_history['event'] == 'update']),
            'removed_listings': len(df_history[df_history['event'] == 'removed']),
            'price_changes': len(df_history[df_history['event'] == 'price_changed']),
            'reappeared': len(df_history[df_history['event'] == 'reappeared'])
        },
        'price_analysis': analyze_price_changes(df_history),
        'inventory_changes': analyze_inventory_changes(df_history),
        'anomalies': detect_weekly_anomalies(df_history)
    }
    
    return report

def create_anomaly_report(tracker, dealer_id: str, days: int = 30) -> Dict:
    """Genera report dettagliato delle anomalie"""
    history = tracker.get_dealer_history(dealer_id)
    if not history:
        return {}
        
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    df = pd.DataFrame(history)
    df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
    
    report = {
        'period': {
            'start': start_date,
            'end': end_date
        },
        'price_anomalies': [],
        'reappearance_anomalies': [],
        'duration_anomalies': []
    }
    
    # Analisi anomalie prezzo
    price_changes = df[df['event'] == 'price_changed']
    for listing_id in price_changes['listing_id'].unique():
        listing_changes = price_changes[price_changes['listing_id'] == listing_id]
        if len(listing_changes) >= 3:
            variations = listing_changes['price'].pct_change()
            if (abs(variations) > 0.2).any():
                report['price_anomalies'].append({
                    'listing_id': listing_id,
                    'changes_count': len(listing_changes),
                    'max_variation': variations.abs().max() * 100,
                    'last_change': listing_changes['date'].max()
                })
    
    # Analisi riapparizioni anomale
    reappearances = df[df['event'] == 'reappeared']
    for listing_id in reappearances['listing_id'].unique():
        reapp_count = len(reappearances[reappearances['listing_id'] == listing_id])
        if reapp_count >= 2:
            report['reappearance_anomalies'].append({
                'listing_id': listing_id,
                'reappearance_count': reapp_count,
                'last_seen': reappearances[reappearances['listing_id'] == listing_id]['date'].max()
            })
    
    # Analisi durata anomala
    listings = tracker.get_active_listings(dealer_id)
    if listings:
        df_listings = pd.DataFrame(listings)
        if 'first_seen' in df_listings.columns:
            df_listings['duration'] = (datetime.now() - df_listings['first_seen']).dt.days
            avg_duration = df_listings['duration'].mean()
            std_duration = df_listings['duration'].std()
            
            anomalous_duration = df_listings[
                abs(df_listings['duration'] - avg_duration) > 2 * std_duration
            ]
            
            for _, row in anomalous_duration.iterrows():
                report['duration_anomalies'].append({
                    'listing_id': row['id'],
                    'duration_days': row['duration'],
                    'deviation': abs(row['duration'] - avg_duration) / std_duration
                })
    
    return report

def show_trend_analysis(history_data: List[Dict]):
    """Visualizza analisi dei trend"""
    if not history_data:
        st.info("Dati insufficienti per l'analisi")
        return
        
    df = pd.DataFrame(history_data)
    
    # Trend prezzi
    st.subheader("📈 Trend Prezzi")
    price_fig = go.Figure()
    
    df['week'] = pd.to_datetime(df['date']).dt.isocalendar().week
    weekly_prices = df.groupby('week')['price'].mean()
    
    price_fig.add_trace(go.Scatter(
        x=weekly_prices.index,
        y=weekly_prices.values,
        mode='lines+markers',
        name='Prezzo Medio'
    ))
    
    price_fig.update_layout(
        title="Andamento Prezzi Settimanale",
        xaxis_title="Settimana",
        yaxis_title="Prezzo Medio (€)",
        height=400
    )
    
    st.plotly_chart(price_fig, use_container_width=True)
    
    # Trend volumi
    st.subheader("📊 Trend Volumi")
    volume_fig = go.Figure()
    
    weekly_volumes = df.groupby('week').size()
    
    volume_fig.add_trace(go.Bar(
        x=weekly_volumes.index,
        y=weekly_volumes.values,
        name='Numero Annunci'
    ))
    
    volume_fig.update_layout(
        title="Volume Annunci Settimanale",
        xaxis_title="Settimana",
        yaxis_title="Numero Annunci",
        height=400
    )
    
    st.plotly_chart(volume_fig, use_container_width=True)

def export_statistics(tracker, dealer_id: str) -> pd.DataFrame:
    """Esporta statistiche complete in formato DataFrame"""
    listings = tracker.get_active_listings(dealer_id)
    history = tracker.get_dealer_history(dealer_id)
    
    if not listings or not history:
        return pd.DataFrame()
        
    # Prepara dati base
    df_listings = pd.DataFrame(listings)
    df_history = pd.DataFrame(history)
    
    # Calcola metriche
    stats = []
    
    # Statistiche prezzi
    price_stats = df_listings['original_price'].describe()
    stats.append({
        'metric': 'Prezzo Medio',
        'value': price_stats['mean']
    })
    stats.append({
        'metric': 'Prezzo Mediano',
        'value': price_stats['50%']
    })
    
    # Statistiche inventory
    stats.append({
        'metric': 'Totale Annunci',
        'value': len(df_listings)
    })
    
    if 'first_seen' in df_listings.columns:
        avg_age = (datetime.now() - df_listings['first_seen']).mean().days
        stats.append({
            'metric': 'Età Media Annunci',
            'value': avg_age
        })
    
    # Statistiche eventi
    for event in df_history['event'].unique():
        count = len(df_history[df_history['event'] == event])
        stats.append({
            'metric': f'Totale {event.title()}',
            'value': count
        })
    
    return pd.DataFrame(stats)

def analyze_price_changes(df_history: pd.DataFrame) -> Dict:
    """Analizza variazioni prezzi nel periodo"""
    if df_history.empty:
        return {}
        
    price_changes = df_history[df_history['event'] == 'price_changed']
    
    analysis = {
        'total_changes': len(price_changes),
        'avg_change': 0,
        'significant_changes': 0
    }
    
    if not price_changes.empty:
        price_variations = price_changes.groupby('listing_id')['price'].pct_change()
        analysis['avg_change'] = price_variations.mean() * 100
        analysis['significant_changes'] = len(price_variations[abs(price_variations) > 0.1])
    
    return analysis

def analyze_inventory_changes(df_history: pd.DataFrame) -> Dict:
    """Analizza variazioni inventory nel periodo"""
    if df_history.empty:
        return {}
        
    analysis = {
        'new_listings': len(df_history[df_history['event'] == 'update']),
        'removed_listings': len(df_history[df_history['event'] == 'removed']),
        'net_change': 0
    }
    
    analysis['net_change'] = analysis['new_listings'] - analysis['removed_listings']
    
    return analysis

def detect_weekly_anomalies(df_history: pd.DataFrame) -> List[Dict]:
    """Rileva anomalie nel periodo"""
    if df_history.empty:
        return []
        
    anomalies = []
    
    # Rileva riapparizioni multiple
    reappearances = df_history[df_history['event'] == 'reappeared']
    for listing_id in reappearances['listing_id'].unique():
        count = len(reappearances[reappearances['listing_id'] == listing_id])
        if count >= 2:
            anomalies.append({
                'type': 'multiple_reappearance',
                'listing_id': listing_id,
                'count': count
            })
    
    # Rileva variazioni prezzo significative
    price_changes = df_history[df_history['event'] == 'price_changed']
    for listing_id in price_changes['listing_id'].unique():
        listing_prices = price_changes[price_changes['listing_id'] == listing_id]['price']
        if len(listing_prices) >= 2:
            variation = (listing_prices.max() - listing_prices.min()) / listing_prices.min()
            if variation > 0.2:
                anomalies.append({
                    'type': 'significant_price_variation',
                    'listing_id': listing_id,
                    'variation_pct': variation * 100
                })
    
    return anomalies