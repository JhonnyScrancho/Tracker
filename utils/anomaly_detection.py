import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

def detect_price_anomalies(history_data: List[Dict], 
                          threshold: float = 0.2) -> List[Dict]:
    """Rileva anomalie nei prezzi"""
    if not history_data:
        return []
    
    df = pd.DataFrame(history_data)
    anomalies = []
    
    # Per ogni annuncio
    for listing_id in df['listing_id'].unique():
        listing_data = df[df['listing_id'] == listing_id].sort_values('date')
        
        if len(listing_data) < 2:
            continue
            
        # Calcola variazioni prezzo
        price_changes = listing_data['price'].pct_change()
        
        # Trova variazioni significative
        significant_changes = listing_data[abs(price_changes) > threshold]
        
        for idx, row in significant_changes.iterrows():
            prev_price = listing_data['price'].shift(1).loc[idx]
            variation = (row['price'] - prev_price) / prev_price
            
            anomalies.append({
                'listing_id': listing_id,
                'date': row['date'],
                'old_price': prev_price,
                'new_price': row['price'],
                'variation': variation * 100,
                'confidence': min(abs(variation) / threshold, 1.0)
            })
    
    return anomalies

def find_reappeared_vehicles(history_data: List[Dict], 
                           min_days: int = 7) -> List[Dict]:
    """Trova veicoli riapparsi dopo rimozione"""
    if not history_data:
        return []
    
    df = pd.DataFrame(history_data)
    reappearances = []
    
    for listing_id in df['listing_id'].unique():
        listing_data = df[df['listing_id'] == listing_id].sort_values('date')
        events = listing_data['event'].tolist()
        
        removed_date = None
        for idx, (event, row) in enumerate(zip(events, listing_data.iterrows())):
            if event == 'removed':
                removed_date = row[1]['date']
            elif event == 'update' and removed_date:
                days_gone = (row[1]['date'] - removed_date).days
                if days_gone >= min_days:
                    reappearances.append({
                        'listing_id': listing_id,
                        'removed_date': removed_date,
                        'reappeared_date': row[1]['date'],
                        'days_gone': days_gone,
                        'price_before': listing_data.iloc[idx-1]['price'] if idx > 0 else None,
                        'price_after': row[1]['price']
                    })
                removed_date = None
    
    return reappearances

def analyze_listing_patterns(history_data: List[Dict]) -> List[Dict]:
    """Analizza pattern comportamentali degli annunci"""
    if not history_data:
        return []
    
    df = pd.DataFrame(history_data)
    patterns = []
    
    for listing_id in df['listing_id'].unique():
        listing_data = df[df['listing_id'] == listing_id].sort_values('date')
        
        # Pattern riapparizioni multiple
        reappearances = listing_data[listing_data['event'] == 'reappeared']
        if len(reappearances) >= 2:
            patterns.append({
                'type': 'multiple_reappearance',
                'listing_id': listing_id,
                'count': len(reappearances),
                'dates': reappearances['date'].tolist(),
                'confidence': min(len(reappearances) / 5, 1.0)
            })
        
        # Pattern riduzioni prezzo sistematiche
        price_changes = listing_data[listing_data['event'] == 'price_changed']
        if len(price_changes) >= 3:
            variations = price_changes['price'].pct_change()
            negative_changes = variations[variations < 0]
            if len(negative_changes) >= 3:
                patterns.append({
                    'type': 'systematic_reduction',
                    'listing_id': listing_id,
                    'reduction_count': len(negative_changes),
                    'avg_reduction': negative_changes.mean() * 100,
                    'confidence': min(len(negative_changes) / 5, 1.0)
                })
        
        # Pattern durata anomala
        if 'first_seen' in listing_data.columns:
            duration = (listing_data['date'].max() - listing_data['first_seen']).days
            if duration > 90:  # Annunci attivi da più di 90 giorni
                patterns.append({
                    'type': 'extended_duration',
                    'listing_id': listing_id,
                    'duration_days': duration,
                    'confidence': min(duration / 180, 1.0)
                })
    
    return patterns

def calculate_confidence_intervals(data: List[float], 
                                confidence: float = 0.95) -> Tuple[float, float]:
    """Calcola intervalli di confidenza per un set di dati"""
    if not data:
        return (0, 0)
        
    data = np.array(data)
    mean = np.mean(data)
    std = np.std(data)
    
    z_score = stats.norm.ppf((1 + confidence) / 2)
    margin = z_score * (std / np.sqrt(len(data)))
    
    return (mean - margin, mean + margin)

def detect_seasonal_anomalies(history_data: List[Dict], 
                            window_size: int = 7) -> List[Dict]:
    """Rileva anomalie stagionali nei dati"""
    if not history_data:
        return []
        
    df = pd.DataFrame(history_data)
    anomalies = []
    
    # Aggrega dati per giorno
    df['date'] = pd.to_datetime(df['date'])
    daily_stats = df.groupby(df['date'].dt.date).agg({
        'price': ['mean', 'count'],
        'listing_id': 'nunique'
    }).reset_index()
    
    # Calcola medie mobili
    daily_stats['price_ma'] = daily_stats[('price', 'mean')].rolling(window=window_size).mean()
    daily_stats['volume_ma'] = daily_stats[('listing_id', 'nunique')].rolling(window=window_size).mean()
    
    # Calcola deviazioni standard
    daily_stats['price_std'] = daily_stats[('price', 'mean')].rolling(window=window_size).std()
    daily_stats['volume_std'] = daily_stats[('listing_id', 'nunique')].rolling(window=window_size).std()
    
    # Identifica anomalie
    for idx, row in daily_stats.iterrows():
        if idx < window_size:
            continue
            
        # Anomalie prezzo
        price_zscore = abs(row[('price', 'mean')] - row['price_ma']) / (row['price_std'] + 1e-6)
        if price_zscore > 2:
            anomalies.append({
                'type': 'seasonal_price',
                'date': row['date'],
                'value': row[('price', 'mean')],
                'expected': row['price_ma'],
                'zscore': price_zscore,
                'confidence': min(price_zscore / 4, 1.0)
            })
        
        # Anomalie volume
        volume_zscore = abs(row[('listing_id', 'nunique')] - row['volume_ma']) / (row['volume_std'] + 1e-6)
        if volume_zscore > 2:
            anomalies.append({
                'type': 'seasonal_volume',
                'date': row['date'],
                'value': row[('listing_id', 'nunique')],
                'expected': row['volume_ma'],
                'zscore': volume_zscore,
                'confidence': min(volume_zscore / 4, 1.0)
            })
    
    return anomalies

def detect_market_manipulation(history_data: List[Dict], 
                             min_occurrences: int = 3) -> List[Dict]:
    """Rileva possibili manipolazioni di mercato"""
    if not history_data:
        return []
        
    df = pd.DataFrame(history_data)
    manipulations = []
    
    # Pattern 1: Rimozione e riapparizione con prezzo maggiorato
    reappearances = find_reappeared_vehicles(history_data)
    for reapp in reappearances:
        if reapp['price_before'] and reapp['price_after']:
            price_increase = (reapp['price_after'] - reapp['price_before']) / reapp['price_before']
            if price_increase > 0.1:  # Aumento >10%
                manipulations.append({
                    'type': 'price_manipulation',
                    'listing_id': reapp['listing_id'],
                    'price_increase': price_increase * 100,
                    'removed_date': reapp['removed_date'],
                    'reappeared_date': reapp['reappeared_date'],
                    'confidence': min(price_increase * 5, 1.0)
                })
    
    # Pattern 2: Modifiche frequenti dello stesso annuncio
    for listing_id in df['listing_id'].unique():
        listing_data = df[df['listing_id'] == listing_id]
        changes = listing_data[listing_data['event'].isin(['update', 'price_changed'])]
        
        if len(changes) >= min_occurrences:
            time_diffs = changes['date'].diff()
            if (time_diffs <= timedelta(days=1)).sum() >= min_occurrences:
                manipulations.append({
                    'type': 'frequent_updates',
                    'listing_id': listing_id,
                    'update_count': len(changes),
                    'avg_time_between_updates': time_diffs.mean().total_seconds() / 3600,
                    'confidence': min(len(changes) / 10, 1.0)
                })
    
    return manipulations