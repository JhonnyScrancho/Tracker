import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import streamlit as st
from utils.datetime_utils import get_current_time, calculate_date_diff, normalize_df_dates

class AnalyticsService:
    def __init__(self, tracker):
        self.tracker = tracker
        self.cache_timeout = 3600  # 1 ora

    def analyze_dealer_patterns(self, dealer_id: str, days: int = 30) -> Dict:
        """Analizza pattern comportamentali del dealer con cache"""
        cache_key = f"dealer_patterns_{dealer_id}_{days}"
        
        # Check cache
        if cache_key in st.session_state and \
           (datetime.now() - st.session_state[cache_key]['timestamp']).seconds < self.cache_timeout:
            return st.session_state[cache_key]['data']
            
        listings = self.tracker.get_active_listings(dealer_id)
        history = self.tracker.get_dealer_history(dealer_id)
        
        if not listings or not history:
            return {}
            
        df_history = pd.DataFrame(history)
        df_history = normalize_df_dates(df_history)
        
        cutoff_date = get_current_time() - timedelta(days=days)
        df_history = df_history[df_history['date'] >= cutoff_date]
        
        patterns = {
            'avg_price_changes': 0,
            'reappearance_rate': 0,
            'listing_duration': 0,
            'price_reduction_patterns': [],
            'suspicious_activities': [],
            'market_trends': {}
        }
        
        # Analizza cambi prezzo
        price_changes = df_history[df_history['event'] == 'price_changed']
        if not price_changes.empty:
            patterns['avg_price_changes'] = len(price_changes) / days
            
            # Analizza pattern riduzioni prezzo
            for listing_id in price_changes['listing_id'].unique():
                listing_changes = price_changes[price_changes['listing_id'] == listing_id]
                if len(listing_changes) >= 3:
                    variations = listing_changes['price'].pct_change()
                    patterns['price_reduction_patterns'].append({
                        'listing_id': listing_id,
                        'changes_count': len(listing_changes),
                        'avg_reduction': variations[variations < 0].mean() * 100,
                        'max_reduction': variations.min() * 100,
                        'frequency': len(listing_changes) / days
                    })
        
        # Analizza riapparizioni con dettagli
        reappearances = df_history[df_history['event'] == 'reappeared']
        if not reappearances.empty:
            total_listings = len(set(df_history['listing_id']))
            patterns['reappearance_rate'] = len(reappearances) / total_listings
            
            # Analizza pattern riapparizioni
            for listing_id in reappearances['listing_id'].unique():
                listing_data = df_history[df_history['listing_id'] == listing_id]
                reapp_events = listing_data[listing_data['event'] == 'reappeared']
                
                if len(reapp_events) >= 2:
                    time_diffs = reapp_events['date'].diff()
                    price_diffs = reapp_events['price'].pct_change()
                    
                    patterns['suspicious_activities'].append({
                        'listing_id': listing_id,
                        'reappearance_count': len(reapp_events),
                        'avg_time_between': time_diffs.mean().total_seconds() / 86400,  # in giorni
                        'avg_price_change': price_diffs.mean() * 100,
                        'confidence': min(len(reapp_events) / 5, 1.0)
                    })
        
        # Calcola durata media annunci con ottimizzazione
        listing_durations = []
        now = get_current_time()
        for listing in listings:
            if listing.get('first_seen'):
                duration = calculate_date_diff(listing['first_seen'], now)
                if duration is not None:
                    listing_durations.append(duration)
                    
        if listing_durations:
            patterns['listing_duration'] = np.mean(listing_durations)
            patterns['duration_std'] = np.std(listing_durations)
        
        # Analisi trend di mercato
        if not price_changes.empty:
            df_grouped = price_changes.groupby(price_changes['date'].dt.date).agg({
                'price': ['mean', 'std', 'count']
            }).reset_index()
            
            patterns['market_trends'] = {
                'daily_avg_prices': df_grouped['price']['mean'].tolist(),
                'price_volatility': df_grouped['price']['std'].mean(),
                'volume_trend': self._calculate_volume_trend(df_grouped['price']['count'].tolist())
            }
        
        # Cache results
        st.session_state[cache_key] = {
            'data': patterns,
            'timestamp': datetime.now()
        }
            
        return patterns

    def _calculate_volume_trend(self, volumes: List[float]) -> str:
        """Calcola il trend del volume basato sugli ultimi valori"""
        if len(volumes) < 2:
            return "stable"
            
        recent_avg = np.mean(volumes[-3:])
        previous_avg = np.mean(volumes[-6:-3])
        
        change = (recent_avg - previous_avg) / previous_avg
        
        if change > 0.1:
            return "increasing"
        elif change < -0.1:
            return "decreasing"
        return "stable"

    def get_market_insights(self, dealer_id: str) -> Dict:
        """Genera insights aggregati sul mercato con performance ottimizzate"""
        listings = self.tracker.get_active_listings(dealer_id)
        history = self.tracker.get_dealer_history(dealer_id)
        
        insights = {
            'patterns': self.analyze_dealer_patterns(dealer_id),
            'statistics': self.calculate_market_statistics(dealer_id),
            'suspicious': self.detect_suspicious_patterns(dealer_id),
            'recommendations': [],
            'performance_metrics': {}
        }
        
        # Performance metrics
        if listings:
            avg_time = sum(1 for l in listings if l.get('plate')) / len(listings) * 100
            insights['performance_metrics'] = {
                'plate_detection_rate': avg_time,
                'listing_quality_score': self._calculate_listing_quality(listings)
            }
        
        # Genera raccomandazioni intelligenti
        self._generate_smart_recommendations(insights)
        
        return insights

    def _calculate_listing_quality(self, listings: List[Dict]) -> float:
        """Calcola uno score di qualità per gli annunci"""
        if not listings:
            return 0.0
            
        scores = []
        for listing in listings:
            score = 0.0
            # Presenza immagini
            if listing.get('image_urls'):
                score += len(listing['image_urls']) * 0.1  # max 1.0
            # Completezza dati
            for field in ['plate', 'mileage', 'registration', 'fuel']:
                if listing.get(field):
                    score += 0.25
            # Presenza prezzo
            if listing.get('original_price'):
                score += 0.5
            scores.append(min(score, 2.0))  # max 2.0
            
        return sum(scores) / len(scores) / 2 * 100  # percentuale

    def _generate_smart_recommendations(self, insights: Dict):
        """Genera raccomandazioni intelligenti basate sui pattern"""
        if insights['patterns'].get('reappearance_rate', 0) > 0.2:
            insights['recommendations'].append({
                'type': 'high_reappearance',
                'message': 'Alto tasso di riapparizione veicoli - possibile manipolazione prezzi',
                'priority': 'high',
                'action_items': [
                    'Monitorare pattern riapparizioni',
                    'Verificare variazioni prezzo post-riapparizione',
                    'Controllare durata media offline'
                ]
            })
            
        if insights['patterns'].get('avg_price_changes', 0) > 2:
            insights['recommendations'].append({
                'type': 'frequent_changes',
                'message': 'Frequenti variazioni prezzi - monitorare pattern',
                'priority': 'medium',
                'action_items': [
                    'Analizzare direzione variazioni',
                    'Verificare timing cambi prezzo',
                    'Confrontare con media mercato'
                ]
            })

        # Analisi qualità annunci
        if insights['performance_metrics'].get('listing_quality_score', 100) < 70:
            insights['recommendations'].append({
                'type': 'listing_quality',
                'message': 'Qualità annunci sotto la media - miglioramenti necessari',
                'priority': 'medium',
                'action_items': [
                    'Aumentare numero immagini',
                    'Completare informazioni mancanti',
                    'Verificare accuratezza dati'
                ]
            })

        # Market positioning
        price_stats = insights['statistics'].get('price_stats', {})
        if price_stats and price_stats.get('std', 0) > price_stats.get('mean', 0) * 0.3:
            insights['recommendations'].append({
                'type': 'price_volatility',
                'message': 'Alta volatilità prezzi - possibile instabilità mercato',
                'priority': 'medium',
                'action_items': [
                    'Analizzare causa variazioni',
                    'Confrontare con trend mercato',
                    'Valutare strategia pricing'
                ]
            })

    def calculate_market_statistics(self, dealer_id: str) -> Dict:
        """Calcola statistiche di mercato dettagliate"""
        listings = self.tracker.get_active_listings(dealer_id)
        
        if not listings:
            return {}
            
        df = pd.DataFrame(listings)
        stats = {
            'price_stats': {},
            'inventory_stats': {},
            'segment_stats': {},
            'temporal_stats': {}
        }
        
        # Statistiche prezzi ottimizzate
        if 'original_price' in df.columns:
            price_series = df['original_price'].dropna()
            if not price_series.empty:
                q25, q75 = np.percentile(price_series, [25, 75])
                stats['price_stats'] = {
                    'mean': price_series.mean(),
                    'median': price_series.median(),
                    'std': price_series.std(),
                    'q25': q25,
                    'q75': q75,
                    'iqr': q75 - q25,
                    'outliers': len(price_series[
                        (price_series < q25 - 1.5*(q75-q25)) | 
                        (price_series > q75 + 1.5*(q75-q25))
                    ])
                }
        
        # Statistiche inventario
        now = pd.Timestamp.now(tz='UTC')
        stats['inventory_stats'] = {
            'total_listings': len(df),
            'avg_age': (
                (now - pd.to_datetime(df['first_seen'])).mean().days
                if 'first_seen' in df.columns else None
            ),
            'plates_missing': len(df[df['plate'].isna()]) if 'plate' in df.columns else None,
            'turnover_rate': self._calculate_turnover_rate(dealer_id)
        }
        
        # Statistiche per segmento
        if 'title' in df.columns:
            df['segment'] = df['title'].apply(lambda x: str(x).split()[0])
            segment_counts = df['segment'].value_counts()
            stats['segment_stats'] = {
                segment: {
                    'count': count,
                    'share': count/len(df)*100,
                    'avg_price': df[df['segment'] == segment]['original_price'].mean()
                }
                for segment, count in segment_counts.items()
            }
        
        return stats

    def _calculate_turnover_rate(self, dealer_id: str) -> float:
        """Calcola il tasso di turnover dell'inventario"""
        history = self.tracker.get_dealer_history(dealer_id)
        if not history:
            return 0.0
            
        df = pd.DataFrame(history)
        if df.empty:
            return 0.0
            
        removed = len(df[df['event'] == 'removed'])
        total_days = (df['date'].max() - df['date'].min()).days or 1
        
        return removed / total_days * 30  # mensile