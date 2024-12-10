import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import cv2
import requests
from sklearn.ensemble import IsolationForest

def detect_price_anomalies(history_data: List[Dict], threshold: float = 0.2) -> List[Dict]:
    """Rileva anomalie nei prezzi usando algoritmi statistici avanzati"""
    if not history_data:
        return []
    
    df = pd.DataFrame(history_data)
    anomalies = []
    
    # Per ogni annuncio
    for listing_id in df['listing_id'].unique():
        listing_data = df[df['listing_id'] == listing_id].sort_values('date')
        
        if len(listing_data) < 2:
            continue
        
        # Analisi serie temporale prezzi
        prices = listing_data['price'].values.reshape(-1, 1)
        clf = IsolationForest(contamination=0.1, random_state=42)
        yhat = clf.fit_predict(prices)
        
        # Identifica anomalie statistiche
        mask = yhat == -1
        if mask.any():
            anomalous_indices = np.where(mask)[0]
            
            for idx in anomalous_indices:
                if idx > 0:  # Abbiamo un prezzo precedente
                    prev_price = prices[idx-1][0]
                    curr_price = prices[idx][0]
                    variation = (curr_price - prev_price) / prev_price
                    
                    anomalies.append({
                        'listing_id': listing_id,
                        'date': listing_data.iloc[idx]['date'],
                        'old_price': prev_price,
                        'new_price': curr_price,
                        'variation': variation * 100,
                        'confidence': float(abs(variation) / threshold),
                        'type': 'statistical',
                        'details': {
                            'zscore': float((curr_price - prices.mean()) / prices.std()),
                            'is_outlier': bool(abs(variation) > threshold)
                        }
                    })
        
        # Analisi variazioni rapide
        price_changes = listing_data['price'].pct_change()
        rapid_changes = abs(price_changes) > threshold
        
        if rapid_changes.any():
            rapid_indices = rapid_changes[rapid_changes].index
            for idx in rapid_indices:
                row = listing_data.loc[idx]
                prev_row = listing_data.iloc[listing_data.index.get_loc(idx)-1]
                
                anomalies.append({
                    'listing_id': listing_id,
                    'date': row['date'],
                    'old_price': prev_row['price'],
                    'new_price': row['price'],
                    'variation': price_changes[idx] * 100,
                    'confidence': min(abs(price_changes[idx]) / threshold, 1.0),
                    'type': 'rapid_change',
                    'details': {
                        'time_delta': (row['date'] - prev_row['date']).total_seconds() / 3600,
                        'price_pattern': 'increase' if price_changes[idx] > 0 else 'decrease'
                    }
                })
    
    return sorted(anomalies, key=lambda x: abs(x['variation']), reverse=True)

def find_reappeared_vehicles(history_data: List[Dict], min_confidence: float = 0.7) -> List[Dict]:
    """Trova veicoli riapparsi con analisi avanzata"""
    if not history_data:
        return []
    
    df = pd.DataFrame(history_data)
    reappearances = []
    
    for listing_id in df['listing_id'].unique():
        listing_data = df[df['listing_id'] == listing_id].sort_values('date')
        events = listing_data['event'].tolist()
        
        removed_data = None
        
        for idx, (event, row) in enumerate(zip(events, listing_data.iterrows())):
            if event == 'removed':
                removed_data = {
                    'date': row[1]['date'],
                    'details': row[1].get('listing_details', {}),
                    'price': row[1].get('price')
                }
            elif event == 'update' and removed_data:
                days_gone = (row[1]['date'] - removed_data['date']).days
                
                # Confronto caratteristiche
                current_details = row[1].get('listing_details', {})
                similarity_score = calculate_listing_similarity(
                    removed_data['details'],
                    current_details
                )
                
                if similarity_score >= min_confidence:
                    reappearances.append({
                        'listing_id': listing_id,
                        'removed_date': removed_data['date'],
                        'reappeared_date': row[1]['date'],
                        'days_gone': days_gone,
                        'similarity_score': similarity_score,
                        'price_before': removed_data['price'],
                        'price_after': row[1].get('price'),
                        'details': {
                            'matching_features': get_matching_features(
                                removed_data['details'],
                                current_details
                            ),
                            'images_similarity': compare_images(
                                removed_data['details'].get('image_urls', []),
                                current_details.get('image_urls', [])
                            ) if 'image_urls' in current_details else None
                        }
                    })
                
                removed_data = None
    
    return sorted(reappearances, key=lambda x: x['similarity_score'], reverse=True)

def calculate_listing_similarity(details1: Dict, details2: Dict) -> float:
    """Calcola similarità tra due annunci"""
    if not details1 or not details2:
        return 0.0
    
    scores = []
    
    # Confronto targa
    if details1.get('plate') and details2.get('plate'):
        scores.append(1.0 if details1['plate'] == details2['plate'] else 0.0)
    
    # Confronto titolo
    if details1.get('title') and details2.get('title'):
        title_similarity = compare_strings(details1['title'], details2['title'])
        scores.append(title_similarity)
    
    # Confronto prezzo
    if details1.get('price') and details2.get('price'):
        price_diff = abs(details1['price'] - details2['price'])
        price_similarity = max(0, 1 - price_diff / max(details1['price'], details2['price']))
        scores.append(price_similarity)
    
    # Confronto chilometri
    if details1.get('mileage') and details2.get('mileage'):
        km_diff = abs(details1['mileage'] - details2['mileage'])
        km_similarity = max(0, 1 - km_diff / max(details1['mileage'], details2['mileage']))
        scores.append(km_similarity)
    
    return np.mean(scores) if scores else 0.0

def get_matching_features(details1: Dict, details2: Dict) -> Dict:
    """Identifica caratteristiche corrispondenti tra due annunci"""
    matches = {}
    
    for key in ['plate', 'title', 'fuel', 'transmission', 'registration']:
        if details1.get(key) and details2.get(key):
            matches[key] = details1[key] == details2[key]
    
    # Confronto numerico con tolleranza
    for key in ['price', 'mileage']:
        if details1.get(key) and details2.get(key):
            diff = abs(details1[key] - details2[key])
            tolerance = 0.1 * max(details1[key], details2[key])
            matches[key] = diff <= tolerance
    
    return matches

def compare_images(images1: List[str], images2: List[str], max_images: int = 3) -> float:
    """Confronta immagini tra due annunci"""
    if not images1 or not images2:
        return 0.0
    
    similarities = []
    
    for img1_url in images1[:max_images]:
        for img2_url in images2[:max_images]:
            try:
                similarity = image_similarity_score(img1_url, img2_url)
                similarities.append(similarity)
            except Exception:
                continue
    
    return max(similarities) if similarities else 0.0

def image_similarity_score(img1_url: str, img2_url: str) -> float:
    """Calcola similarità tra due immagini"""
    try:
        # Download immagini
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

def compare_strings(s1: str, s2: str) -> float:
    """Calcola similarità tra stringhe"""
    if not s1 or not s2:
        return 0.0
        
    s1 = s1.lower()
    s2 = s2.lower()
    
    # Rimuovi spazi e caratteri speciali
    s1 = ''.join(c for c in s1 if c.isalnum())
    s2 = ''.join(c for c in s2 if c.isalnum())
    
    if not s1 or not s2:
        return 0.0
        
    # Levenshtein distance
    m = len(s1)
    n = len(s2)
    
    d = np.zeros((m+1, n+1))
    
    for i in range(m+1):
        d[i, 0] = i
    for j in range(n+1):
        d[0, j] = j
        
    for j in range(1, n+1):
        for i in range(1, m+1):
            if s1[i-1] == s2[j-1]:
                d[i, j] = d[i-1, j-1]
            else:
                d[i, j] = min(d[i-1, j], d[i, j-1], d[i-1, j-1]) + 1
                
    max_len = max(m, n)
    return 1 - (d[m, n] / max_len) if max_len > 0 else 0.0

def analyze_listing_patterns(history_data: List[Dict]) -> List[Dict]:
    """Analizza pattern comportamentali degli annunci"""
    if not history_data:
        return []
    
    df = pd.DataFrame(history_data)
    patterns = []
    
    # Pattern riapparizioni multiple
    reappearances = df[df['event'] == 'reappeared']
    if not reappearances.empty:
        for listing_id in reappearances['listing_id'].unique():
            reapp_data = reappearances[reappearances['listing_id'] == listing_id]
            if len(reapp_data) >= 2:
                time_diffs = reapp_data['date'].diff()
                patterns.append({
                    'type': 'multiple_reappearance',
                    'listing_id': listing_id,
                    'count': len(reapp_data),
                    'dates': reapp_data['date'].tolist(),
                    'avg_time_between': time_diffs.mean().total_seconds() / 86400,
                    'confidence': min(len(reapp_data) / 5, 1.0)
                })
    
    # Pattern riduzioni prezzo sistematiche
    price_changes = df[df['event'] == 'price_changed']
    if not price_changes.empty:
        for listing_id in price_changes['listing_id'].unique():
            changes_data = price_changes[price_changes['listing_id'] == listing_id]
            if len(changes_data) >= 3:
                variations = changes_data['price'].pct_change()
                negative_changes = variations[variations < 0]
                if len(negative_changes) >= 3:
                    patterns.append({
                        'type': 'systematic_reduction',
                        'listing_id': listing_id,
                        'reduction_count': len(negative_changes),
                        'avg_reduction': negative_changes.mean() * 100,
                        'total_reduction': (
                            changes_data['price'].iloc[-1] - changes_data['price'].iloc[0]
                        ) / changes_data['price'].iloc[0] * 100,
                        'confidence': min(len(negative_changes) / 5, 1.0)
                    })
    
    # Pattern durata anomala
    if 'first_seen' in df.columns:
        for listing_id in df['listing_id'].unique():
            listing_data = df[df['listing_id'] == listing_id]
            duration = (listing_data['date'].max() - listing_data['first_seen']).days
            if duration > 90:  # Annunci attivi da più di 90 giorni
                patterns.append({
                    'type': 'extended_duration',
                    'listing_id': listing_id,
                    'duration_days': duration,
                    'price_stability': calculate_price_stability(listing_data),
                    'confidence': min(duration / 180, 1.0)
                })
    
    return patterns

def calculate_price_stability(listing_data: pd.DataFrame) -> float:
    """Calcola stabilità prezzo di un annuncio"""
    if 'price' not in listing_data.columns or len(listing_data) < 2:
        return 1.0
        
    prices = listing_data['price'].dropna()
    if len(prices) < 2:
        return 1.0
        
    # Coefficiente di variazione
    cv = prices.std() / prices.mean()
    return max(0, 1 - cv)

def detect_market_manipulation(history_data: List[Dict], min_occurrences: int = 3) -> List[Dict]:
    """Rileva possibili manipolazioni di mercato"""
    if not history_data:
        return []
        
    df = pd.DataFrame(history_data)
    manipulations = []
    
    # Pattern 1: Rimozioni e riapparizioni con prezzo maggiorato
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
                    'confidence': min(price_increase * 5, 1.0),
                    'details': reapp['details']
                })
    
    # Pattern 2: Modifiche frequenti dello stesso annuncio
    for listing_id in df['listing_id'].unique():
        listing_data = df[df['listing_id'] == listing_id]
        changes = listing_data[listing_data['event'].isin(['update', 'price_changed'])]
        
        if len(changes) >= min_occurrences:
            time_diffs = changes['date'].diff()
            rapid_changes = time_diffs <= timedelta(days=1)
            
            if rapid_changes.sum() >= min_occurrences:
                manipulations.append({
                    'type': 'frequent_updates',
                    'listing_id': listing_id,
                    'update_count': len(changes),
                    'avg_time_between_updates': time_diffs.mean().total_seconds() / 3600,
                    'confidence': min(len(changes) / 10, 1.0),
                    'details': {
                        'rapid_changes': rapid_changes.sum(),
                        'price_variations': changes['price'].pct_change().describe().to_dict()
                    }
                })
    
    # Pattern 3: Oscillazioni prezzo coordinate
    if len(df['listing_id'].unique()) >= 2:
        price_changes = df[df['event'] == 'price_changed']
        if not price_changes.empty:
            for date in price_changes['date'].dt.date.unique():
                daily_changes = price_changes[price_changes['date'].dt.date == date]
                if len(daily_changes) >= min_occurrences:
                    variations = daily_changes['price'].pct_change()
                    if (abs(variations) > 0.05).all():  # Variazioni >5%
                        manipulations.append({
                            'type': 'coordinated_changes',
                            'date': date,
                            'listings_involved': daily_changes['listing_id'].tolist(),
                            'avg_variation': variations.mean() * 100,
                            'confidence': min(len(daily_changes) / 5, 1.0),
                            'details': {
                                'total_changes': len(daily_changes),
                                'variation_stats': variations.describe().to_dict()
                            }
                        })
    
    return sorted(manipulations, key=lambda x: x['confidence'], reverse=True)

def detect_seasonal_anomalies(history_data: List[Dict], window_size: int = 7) -> List[Dict]:
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
                'value': float(row[('price', 'mean')]),
                'expected': float(row['price_ma']),
                'zscore': float(price_zscore),
                'confidence': min(price_zscore / 4, 1.0)
            })
        
        # Anomalie volume
        volume_zscore = abs(row[('listing_id', 'nunique')] - row['volume_ma']) / (row['volume_std'] + 1e-6)
        if volume_zscore > 2:
            anomalies.append({
                'type': 'seasonal_volume',
                'date': row['date'],
                'value': int(row[('listing_id', 'nunique')]),
                'expected': float(row['volume_ma']),
                'zscore': float(volume_zscore),
                'confidence': min(volume_zscore / 4, 1.0)
            })
    
    return anomalies