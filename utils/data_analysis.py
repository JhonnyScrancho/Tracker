import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import streamlit as st

def calculate_market_statistics(listings: List[Dict]) -> Dict:
    """Calcola statistiche di mercato per i veicoli"""
    if not listings:
        return {}
        
    df = pd.DataFrame(listings)
    stats = {}
    
    # Raggruppa per marca/modello
    df['brand_model'] = df['title'].apply(lambda x: ' '.join(str(x).split()[:2]))
    
    for brand_model in df['brand_model'].unique():
        model_data = df[df['brand_model'] == brand_model]
        
        # Calcola statistiche prezzi
        prices = model_data['original_price'].dropna()
        if len(prices) > 0:
            stats[brand_model] = {
                'count': len(model_data),
                'avg_price': prices.mean(),
                'min_price': prices.min(),
                'max_price': prices.max(),
                'std_price': prices.std()
            }
            
            # Calcola fasce prezzo
            q25, q75 = np.percentile(prices, [25, 75])
            stats[brand_model].update({
                'price_q25': q25,
                'price_q75': q75,
                'price_iqr': q75 - q25
            })
            
            # Identifica outlier prezzi
            iqr = q75 - q25
            price_outliers = prices[(prices < (q25 - 1.5 * iqr)) | (prices > (q75 + 1.5 * iqr))]
            stats[brand_model]['price_outliers'] = len(price_outliers)
            
            # Calcola statistiche km
            if 'mileage' in model_data.columns:
                mileage = model_data['mileage'].dropna()
                if len(mileage) > 0:
                    stats[brand_model].update({
                        'avg_mileage': mileage.mean(),
                        'min_mileage': mileage.min(),
                        'max_mileage': mileage.max()
                    })
    
    return stats

def analyze_price_trends(history_data: List[Dict]) -> Dict:
    """Analizza trend prezzi nel tempo"""
    if not history_data:
        return {}
        
    df = pd.DataFrame(history_data)
    trends = {}
    
    # Calcola variazioni settimanali
    df['week'] = pd.to_datetime(df['date']).dt.isocalendar().week
    df['year'] = pd.to_datetime(df['date']).dt.year
    
    # Raggruppa per settimana
    weekly_avg = df.groupby(['year', 'week'])['price'].agg(['mean', 'count']).reset_index()
    weekly_avg['pct_change'] = weekly_avg['mean'].pct_change() * 100
    
    trends['weekly'] = {
        'avg_prices': weekly_avg['mean'].tolist(),
        'volumes': weekly_avg['count'].tolist(),
        'changes': weekly_avg['pct_change'].dropna().tolist(),
        'weeks': [f"{row['year']}-W{row['week']}" for _, row in weekly_avg.iterrows()]
    }
    
    # Calcola trend mensili
    df['month'] = pd.to_datetime(df['date']).dt.month
    monthly_avg = df.groupby(['year', 'month'])['price'].agg(['mean', 'count']).reset_index()
    monthly_avg['pct_change'] = monthly_avg['mean'].pct_change() * 100
    
    trends['monthly'] = {
        'avg_prices': monthly_avg['mean'].tolist(),
        'volumes': monthly_avg['count'].tolist(),
        'changes': monthly_avg['pct_change'].dropna().tolist(),
        'months': [f"{row['year']}-{row['month']}" for _, row in monthly_avg.iterrows()]
    }
    
    return trends

def analyze_vehicle_lifecycle(listings: List[Dict], history: List[Dict]) -> Dict:
    """Analizza ciclo vita dei veicoli"""
    lifecycle = {
        'avg_time_to_sale': 0,
        'removal_rate': 0,
        'reappearance_rate': 0,
        'price_reduction_rate': 0
    }
    
    if not listings or not history:
        return lifecycle
        
    df_history = pd.DataFrame(history)
    
    # Tempo medio alla vendita
    active_times = []
    for listing in listings:
        if listing.get('first_seen') and listing.get('last_seen'):
            active_time = (listing['last_seen'] - listing['first_seen']).days
            active_times.append(active_time)
    
    if active_times:
        lifecycle['avg_time_to_sale'] = sum(active_times) / len(active_times)
    
    # Calcola tassi
    total_listings = len(set(df_history['listing_id']))
    if total_listings > 0:
        # Tasso rimozioni
        removals = len(df_history[df_history['event'] == 'removed'])
        lifecycle['removal_rate'] = (removals / total_listings) * 100
        
        # Tasso riapparizioni
        reappearances = len(df_history[df_history['event'] == 'reappeared'])
        if removals > 0:
            lifecycle['reappearance_rate'] = (reappearances / removals) * 100
            
        # Tasso riduzioni prezzo
        price_reductions = len(df_history[
            (df_history['event'] == 'update') & 
            (df_history['price'].diff() < 0)
        ])
        lifecycle['price_reduction_rate'] = (price_reductions / total_listings) * 100
    
    return lifecycle

def detect_similar_vehicles(listings: List[Dict], threshold: float = 0.8) -> List[Dict]:
    """Identifica veicoli simili/duplicati"""
    if not listings:
        return []
        
    similar_groups = []
    df = pd.DataFrame(listings)
    
    # Raggruppa per marca/modello
    df['brand_model'] = df['title'].apply(lambda x: ' '.join(str(x).split()[:2]))
    
    for brand_model in df['brand_model'].unique():
        model_group = df[df['brand_model'] == brand_model]
        
        if len(model_group) < 2:
            continue
            
        # Confronta caratteristiche
        for i, row1 in model_group.iterrows():
            similar = []
            for j, row2 in model_group.iterrows():
                if i >= j:
                    continue
                    
                # Calcola similarità
                price_diff = abs(row1['original_price'] - row2['original_price']) / max(row1['original_price'], row2['original_price'])
                
                mileage_similar = True
                if 'mileage' in row1 and 'mileage' in row2:
                    mileage_diff = abs(row1['mileage'] - row2['mileage']) / max(row1['mileage'], row2['mileage'])
                    mileage_similar = mileage_diff < 0.2
                
                registration_similar = True
                if 'registration' in row1 and 'registration' in row2:
                    registration_similar = row1['registration'] == row2['registration']
                
                # Se abbastanza simili, aggiungi al gruppo
                if price_diff < 0.2 and mileage_similar and registration_similar:
                    if not similar:
                        similar.append({
                            'id': row1['id'],
                            'title': row1['title'],
                            'price': row1['original_price'],
                            'mileage': row1.get('mileage'),
                            'plate': row1.get('plate')
                        })
                    
                    similar.append({
                        'id': row2['id'],
                        'title': row2['title'],
                        'price': row2['original_price'],
                        'mileage': row2.get('mileage'),
                        'plate': row2.get('plate')
                    })
            
            if len(similar) > 1:
                similar_groups.append(similar)
    
    return similar_groups

def get_market_insights(listings: List[Dict], history: List[Dict]) -> Dict:
    """Genera insights di mercato aggregati"""
    insights = {
        'market_stats': calculate_market_statistics(listings),
        'price_trends': analyze_price_trends(history),
        'lifecycle_analysis': analyze_vehicle_lifecycle(listings, history),
        'similar_vehicles': detect_similar_vehicles(listings)
    }
    
    # Aggiungi metriche derivate
    if insights['market_stats'] and insights['price_trends']:
        # Calcola trend generale prezzi
        monthly_changes = insights['price_trends']['monthly']['changes']
        if monthly_changes:
            insights['price_trend'] = sum(monthly_changes) / len(monthly_changes)
            
        # Identifica segmenti di mercato più attivi
        segment_activity = sorted(
            insights['market_stats'].items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        insights['active_segments'] = [
            {'segment': k, 'count': v['count']} 
            for k, v in segment_activity[:5]
        ]
    
    return insights