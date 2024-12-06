import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import streamlit as st
from utils.datetime_utils import get_current_time, calculate_date_diff, normalize_df_dates

class AnalyticsService:
    def __init__(self, tracker):
        self.tracker = tracker

    def analyze_dealer_patterns(self, dealer_id: str, days: int = 30) -> Dict:
        """Analizza pattern comportamentali del dealer"""
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
            'suspicious_activities': []
        }
        
        # Analizza cambi prezzo
        price_changes = df_history[df_history['event'] == 'price_changed']
        if not price_changes.empty:
            patterns['avg_price_changes'] = len(price_changes) / days
            
            # Analizza pattern riduzioni
            for listing_id in price_changes['listing_id'].unique():
                listing_changes = price_changes[price_changes['listing_id'] == listing_id]
                if len(listing_changes) >= 3:
                    patterns['price_reduction_patterns'].append({
                        'listing_id': listing_id,
                        'changes_count': len(listing_changes),
                        'avg_reduction': listing_changes['price'].pct_change().mean()
                    })
        
        # Analizza riapparizioni
        reappearances = df_history[df_history['event'] == 'reappeared']
        if not reappearances.empty:
            patterns['reappearance_rate'] = len(reappearances) / len(set(df_history['listing_id']))
            
            # Identifica attività sospette
            for listing_id in reappearances['listing_id'].unique():
                listing_data = df_history[df_history['listing_id'] == listing_id]
                reapp_count = len(listing_data[listing_data['event'] == 'reappeared'])
                
                if reapp_count >= 2:
                    patterns['suspicious_activities'].append({
                        'listing_id': listing_id,
                        'reappearance_count': reapp_count,
                        'last_seen': listing_data['date'].max()
                    })
        
        # Calcola durata media annunci
        for listing in listings:
            if listing.get('first_seen'):
                duration = calculate_date_diff(listing['first_seen'], get_current_time())
                if duration is not None:
                    patterns['listing_duration'] += duration
        
        if listings:
            patterns['listing_duration'] /= len(listings)
            
        return patterns

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
        
        # Statistiche prezzi
        if 'original_price' in df.columns:
            price_series = df['original_price'].dropna()
            stats['price_stats'] = {
                'mean': price_series.mean(),
                'median': price_series.median(),
                'std': price_series.std(),
                'q25': price_series.quantile(0.25),
                'q75': price_series.quantile(0.75)
            }
        
        # Statistiche inventario
        now = pd.Timestamp.now(tz='UTC')
        
        def safe_convert_to_utc(series):
            """Converte una serie di datetime a UTC in modo sicuro"""
            dt_series = pd.to_datetime(series)
            if dt_series.dt.tz is None:
                return dt_series.dt.tz_localize('UTC')
            return dt_series.dt.tz_convert('UTC')
        
        stats['inventory_stats'] = {
            'total_listings': len(df),
            'avg_age': (
                (now - safe_convert_to_utc(df['first_seen'])).mean().days
                if 'first_seen' in df.columns else None
            ),
            'plates_missing': len(df[df['plate'].isna()]) if 'plate' in df.columns else None
        }
        
        # Statistiche per segmento
        df['segment'] = df['title'].apply(lambda x: x.split()[0])
        segment_counts = df['segment'].value_counts()
        stats['segment_stats'] = {
            segment: count for segment, count in segment_counts.items()
        }
        
        # Statistiche temporali
        if 'first_seen' in df.columns:
            df['week'] = safe_convert_to_utc(df['first_seen']).dt.isocalendar().week
            weekly_counts = df.groupby('week').size()
            stats['temporal_stats'] = {
                'weekly_avg': weekly_counts.mean(),
                'weekly_std': weekly_counts.std()
            }
                
        return stats


    def detect_suspicious_patterns(self, dealer_id: str, threshold: float = 0.8) -> List[Dict]:
        """Rileva pattern sospetti negli annunci"""
        history = self.tracker.get_dealer_history(dealer_id)
        
        if not history:
            return []
            
        df = pd.DataFrame(history)
        patterns = []
        
        # Pattern 1: Rimozioni e riapparizioni frequenti
        for listing_id in df['listing_id'].unique():
            listing_data = df[df['listing_id'] == listing_id].sort_values('date')
            events = listing_data['event'].tolist()
            
            removals = events.count('removed')
            reappearances = events.count('reappeared')
            
            if removals >= 2 and reappearances >= 2:
                patterns.append({
                    'type': 'frequent_reappearance',
                    'listing_id': listing_id,
                    'removals': removals,
                    'reappearances': reappearances,
                    'confidence': min(1.0, (removals + reappearances) / 10)
                })
        
        # Pattern 2: Variazioni prezzo sospette
        price_changes = df[df['event'] == 'price_changed']
        for listing_id in price_changes['listing_id'].unique():
            listing_changes = price_changes[price_changes['listing_id'] == listing_id]
            
            if len(listing_changes) >= 3:
                price_series = listing_changes['price']
                variations = price_series.pct_change()
                
                if (variations.abs() > 0.2).any():  # Variazioni maggiori del 20%
                    patterns.append({
                        'type': 'suspicious_price_changes',
                        'listing_id': listing_id,
                        'changes_count': len(listing_changes),
                        'max_variation': variations.abs().max() * 100,
                        'confidence': min(1.0, variations.abs().max())
                    })
        
        # Pattern 3: Variazioni rapide e ripetute
        for listing_id in df['listing_id'].unique():
            listing_data = df[df['listing_id'] == listing_id].sort_values('date')
            if len(listing_data) >= 3:
                time_diffs = listing_data['date'].diff()
                rapid_changes = time_diffs <= timedelta(hours=24)
                
                if rapid_changes.sum() >= 3:
                    patterns.append({
                        'type': 'rapid_changes',
                        'listing_id': listing_id,
                        'changes_count': rapid_changes.sum(),
                        'avg_time_between_changes': time_diffs.mean().total_seconds() / 3600,
                        'confidence': min(1.0, rapid_changes.sum() / 5)
                    })
        
        return patterns

    def analyze_price_trends(self, history_data: List[Dict]) -> Dict:
        """Analizza trend prezzi nel tempo"""
        if not history_data:
            return {}
            
        df = pd.DataFrame(history_data)
        # Assicurati che tutte le date siano timezone-aware
        df['date'] = pd.to_datetime(df['date']).dt.tz_localize('UTC')
        df = df.sort_values('date')
        
        # Calcola variazioni settimanali
        df['week'] = df['date'].dt.isocalendar().week
        df['year'] = df['date'].dt.year
        
        # Raggruppa per settimana
        weekly_avg = df.groupby(['year', 'week'])['price'].agg(['mean', 'count']).reset_index()
        weekly_avg['pct_change'] = weekly_avg['mean'].pct_change() * 100
        
        trends = {
            'weekly': {
                'avg_prices': weekly_avg['mean'].tolist(),
                'volumes': weekly_avg['count'].tolist(),
                'changes': weekly_avg['pct_change'].dropna().tolist(),
                'weeks': [f"{row['year']}-W{row['week']}" for _, row in weekly_avg.iterrows()]
            }
        }
        
        # Calcola trend mensili
        df['month'] = df['date'].dt.month
        monthly_avg = df.groupby(['year', 'month'])['price'].agg(['mean', 'count']).reset_index()
        monthly_avg['pct_change'] = monthly_avg['mean'].pct_change() * 100
        
        trends['monthly'] = {
            'avg_prices': monthly_avg['mean'].tolist(),
            'volumes': monthly_avg['count'].tolist(),
            'changes': monthly_avg['pct_change'].dropna().tolist(),
            'months': [f"{row['year']}-{row['month']}" for _, row in monthly_avg.iterrows()]
        }
        
        return trends
    
    def get_market_insights(self, dealer_id: str) -> Dict:
        """Genera insights aggregati sul mercato"""
        listings = self.tracker.get_active_listings(dealer_id)
        history = self.tracker.get_dealer_history(dealer_id)
        
        insights = {
            'patterns': self.analyze_dealer_patterns(dealer_id),
            'statistics': self.calculate_market_statistics(dealer_id),
            'suspicious': self.detect_suspicious_patterns(dealer_id),
            'recommendations': []
        }
        
        # Genera raccomandazioni basate sui dati
        if insights['patterns'].get('reappearance_rate', 0) > 0.2:
            insights['recommendations'].append({
                'type': 'high_reappearance',
                'message': 'Alto tasso di riapparizione veicoli - possibile manipolazione prezzi',
                'priority': 'high'
            })
            
        if insights['patterns'].get('avg_price_changes', 0) > 2:
            insights['recommendations'].append({
                'type': 'frequent_changes',
                'message': 'Frequenti variazioni prezzi - monitorare pattern',
                'priority': 'medium'
            })
            
        price_stats = insights['statistics'].get('price_stats', {})
        if price_stats and price_stats.get('std', 0) > price_stats.get('mean', 0) * 0.3:
            insights['recommendations'].append({
                'type': 'price_volatility',
                'message': 'Alta volatilità prezzi - possibile instabilità mercato',
                'priority': 'medium'
            })
        
        return insights

    def analyze_competitor_behavior(self, dealer_id: str, days: int = 30) -> Dict:
        """Analizza comportamento del competitor nel periodo specificato"""
        history = self.tracker.get_dealer_history(dealer_id)
        if not history:
            return {}
            
        df = pd.DataFrame(history)
        cutoff_date = datetime.now() - timedelta(days=days)
        df = df[df['date'] >= cutoff_date]
        
        analysis = {
            'pricing_strategy': self._analyze_pricing_strategy(df),
            'inventory_management': self._analyze_inventory_management(df),
            'market_positioning': self._analyze_market_positioning(df),
            'overall_score': 0
        }
        
        # Calcola score complessivo
        scores = {
            'pricing': analysis['pricing_strategy'].get('strategy_score', 0),
            'inventory': analysis['inventory_management'].get('efficiency_score', 0),
            'positioning': analysis['market_positioning'].get('position_score', 0)
        }
        
        analysis['overall_score'] = sum(scores.values()) / len(scores)
        
        return analysis

    def _analyze_pricing_strategy(self, df: pd.DataFrame) -> Dict:
        """Analizza strategia di pricing"""
        strategy = {
            'avg_initial_price': 0,
            'avg_final_price': 0,
            'avg_discount': 0,
            'price_changes_frequency': 0,
            'strategy_score': 0
        }
        
        if df.empty:
            return strategy
            
        # Calcola prezzi iniziali e finali per ogni annuncio
        listings_prices = df.groupby('listing_id').agg({
            'price': ['first', 'last']
        })
        
        if not listings_prices.empty:
            strategy['avg_initial_price'] = listings_prices[('price', 'first')].mean()
            strategy['avg_final_price'] = listings_prices[('price', 'last')].mean()
            
            # Calcola sconto medio
            discounts = (listings_prices[('price', 'first')] - listings_prices[('price', 'last')]) / listings_prices[('price', 'first')] * 100
            strategy['avg_discount'] = discounts.mean()
            
        # Calcola frequenza cambi prezzo
        price_changes = df[df['event'] == 'price_changed']
        days_analyzed = (df['date'].max() - df['date'].min()).days or 1
        strategy['price_changes_frequency'] = len(price_changes) / days_analyzed
        
        # Calcola score strategia
        score = 0
        if strategy['avg_discount'] > 0 and strategy['avg_discount'] < 15:
            score += 0.4  # Sconti ragionevoli
        if 0.1 <= strategy['price_changes_frequency'] <= 0.5:
            score += 0.3  # Frequenza aggiornamenti normale
        if strategy['avg_final_price'] > 0:
            score += 0.3  # Prezzi finali positivi
            
        strategy['strategy_score'] = score
        
        return strategy

    def _analyze_inventory_management(self, df: pd.DataFrame) -> Dict:
        """Analizza gestione inventario"""
        inventory = {
            'avg_listing_duration': 0,
            'turnover_rate': 0,
            'stock_stability': 0,
            'efficiency_score': 0
        }
        
        if df.empty:
            return inventory
            
        # Calcola durata media annunci
        listings_duration = df.groupby('listing_id').agg({
            'date': lambda x: (x.max() - x.min()).days
        })
        inventory['avg_listing_duration'] = listings_duration['date'].mean()
        
        # Calcola tasso di turnover
        removed = df[df['event'] == 'removed']
        days_analyzed = (df['date'].max() - df['date'].min()).days or 1
        inventory['turnover_rate'] = len(removed) / days_analyzed
        
        # Calcola stabilità stock
        daily_count = df.groupby(df['date'].dt.date).size()
        inventory['stock_stability'] = 1 - (daily_count.std() / daily_count.mean() if daily_count.mean() > 0 else 0)
        
        # Calcola score efficienza
        score = 0
        if 15 <= inventory['avg_listing_duration'] <= 60:
            score += 0.4  # Durata ottimale
        if 0.05 <= inventory['turnover_rate'] <= 0.2:
            score += 0.3  # Turnover sano
        if inventory['stock_stability'] >= 0.7:
            score += 0.3  # Buona stabilità
            
        inventory['efficiency_score'] = score
        
        return inventory

    def _analyze_market_positioning(self, df: pd.DataFrame) -> Dict:
        """Analizza posizionamento di mercato"""
        positioning = {
            'price_segment': 'unknown',
            'market_share': 0,
            'competitive_advantage': [],
            'position_score': 0
        }
        
        if df.empty:
            return positioning
            
        # Determina segmento di prezzo
        avg_price = df['price'].mean()
        if avg_price > 0:
            if avg_price <= 15000:
                positioning['price_segment'] = 'economic'
            elif avg_price <= 30000:
                positioning['price_segment'] = 'medium'
            else:
                positioning['price_segment'] = 'premium'
        
        # Identifica vantaggi competitivi
        price_stability = 1 - (df['price'].std() / df['price'].mean() if df['price'].mean() > 0 else 0)
        if price_stability > 0.8:
            positioning['competitive_advantage'].append('stable_pricing')
            
        quick_sales = df.groupby('listing_id').agg({
            'date': lambda x: (x.max() - x.min()).days
        })
        if quick_sales['date'].mean() < 30:
            positioning['competitive_advantage'].append('quick_turnover')
            
        if len(df[df['event'] == 'reappeared']) < len(df[df['event'] == 'removed']) * 0.1:
            positioning['competitive_advantage'].append('honest_listings')
        
        # Calcola score posizionamento
        score = 0
        score += min(len(positioning['competitive_advantage']) * 0.3, 0.9)
        if price_stability > 0.7:
            score += 0.1
            
        positioning['position_score'] = score
        
        return positioning