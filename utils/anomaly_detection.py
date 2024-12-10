import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import cv2
import requests

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

def find_reappeared_vehicles(history_data: List[Dict]) -> List[Dict]:
    """Trova veicoli riapparsi con analisi immagini"""
    if not history_data:
        return []
    
    df = pd.DataFrame(history_data)
    reappearances = []
    
    for listing_id in df['listing_id'].unique():
        listing_data = df[df['listing_id'] == listing_id].sort_values('date')
        events = listing_data['event'].tolist()
        
        removed_date = None
        removed_details = None
        
        for idx, (event, row) in enumerate(zip(events, listing_data.iterrows())):
            if event == 'removed':
                removed_date = row[1]['date']
                removed_details = row[1].get('listing_details', {})
            elif event == 'update' and removed_date:
                days_gone = (row[1]['date'] - removed_date).days
                current_details = row[1].get('listing_details', {})
                
                # Confronta dettagli
                matches = {
                    'plate': removed_details.get('plate') == current_details.get('plate'),
                    'title': removed_details.get('title') == current_details.get('title'),
                    'image': False
                }
                
                # Confronta immagini se disponibili
                if (removed_details.get('image_urls') and 
                    current_details.get('image_urls')):
                    # Confronta solo la prima immagine
                    img_score = image_similarity_score(
                        removed_details['image_urls'][0],
                        current_details['image_urls'][0]
                    )
                    matches['image'] = img_score > 0.8
                
                # Calcola confidence score complessivo
                confidence = 0.0
                if matches['plate']:  # Targa uguale
                    confidence = 0.9
                elif matches['image']:  # Immagine simile
                    confidence = 0.8
                elif matches['title']:  # Solo titolo uguale
                    confidence = 0.3
                
                if confidence > 0.3:  # Soglia minima per segnalare
                    reappearances.append({
                        'listing_id': listing_id,
                        'removed_date': removed_date,
                        'reappeared_date': row[1]['date'],
                        'days_gone': days_gone,
                        'confidence': confidence,
                        'matches': matches,
                        'price_before': listing_data.iloc[idx-1]['price'] if idx > 0 else None,
                        'price_after': row[1]['price']
                    })
                
                removed_date = None
                removed_details = None
    
    return reappearances

def detect_duplicate_listings(listings: List[Dict], threshold: float = 0.8) -> List[Dict]:
    """Identifica annunci duplicati"""
    duplicates = []
    
    # Raggruppa per marca/modello per ridurre confronti
    by_model = {}
    for listing in listings:
        model = ' '.join(listing.get('title', '').split()[:2])
        if model:
            if model not in by_model:
                by_model[model] = []
            by_model[model].append(listing)
    
    # Cerca duplicati in ogni gruppo
    for model, model_listings in by_model.items():
        if len(model_listings) < 2:
            continue
            
        for i, listing1 in enumerate(model_listings):
            for listing2 in model_listings[i+1:]:
                matches = {
                    'plate': False,
                    'image': False,
                    'price_diff': 0
                }
                
                # Confronta targhe se disponibili
                if listing1.get('plate') and listing2.get('plate'):
                    matches['plate'] = listing1['plate'] == listing2['plate']
                
                # Confronta immagini
                if (listing1.get('image_urls') and listing2.get('image_urls')):
                    img_score = image_similarity_score(
                        listing1['image_urls'][0],
                        listing2['image_urls'][0]
                    )
                    matches['image'] = img_score > threshold
                
                # Calcola differenza prezzi
                if listing1.get('original_price') and listing2.get('original_price'):
                    price_diff = abs(listing1['original_price'] - listing2['original_price'])
                    matches['price_diff'] = price_diff
                
                # Determina se è un duplicato
                is_duplicate = False
                confidence = 0.0
                
                if matches['plate']:  # Stessa targa
                    is_duplicate = True
                    confidence = 0.9
                elif matches['image'] and matches['price_diff'] < 1000:  # Immagine simile e prezzo simile
                    is_duplicate = True
                    confidence = 0.8
                
                if is_duplicate:
                    duplicates.append({
                        'listing1_id': listing1['id'],
                        'listing2_id': listing2['id'],
                        'model': model,
                        'confidence': confidence,
                        'matches': matches,
                        'detected_at': datetime.now()
                    })
    
    return duplicates

def image_similarity_score(img1_url: str, img2_url: str) -> float:
    """
    Calcola un punteggio di similarità tra due immagini
    Returns: score tra 0 e 1 (1 = identiche)
    """
    try:
        # Scarica immagini
        def download_img(url):
            response = requests.get(url)
            img_array = np.asarray(bytearray(response.content), dtype=np.uint8)
            return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        img1 = download_img(img1_url)
        img2 = download_img(img2_url)
        
        if img1 is None or img2 is None:
            return 0.0
            
        # Ridimensiona alla stessa dimensione
        size = (400, 300)
        img1 = cv2.resize(img1, size)
        img2 = cv2.resize(img2, size)
        
        # Converti in scala di grigi
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        
        # Calcola score usando SSIM
        score = cv2.matchTemplate(gray1, gray2, cv2.TM_CCOEFF_NORMED)
        return float(score.max())
        
    except Exception:
        return 0.0

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