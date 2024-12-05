from typing import Dict, List
import pandas as pd
from datetime import datetime

def prepare_listings_dataframe(listings: List[Dict]) -> pd.DataFrame:
    """Prepara DataFrame per visualizzazione"""
    if not listings:
        return pd.DataFrame()
        
    df = pd.DataFrame(listings)
    
    # Formattazione colonne base
    if 'image_urls' in df.columns:
        df['thumbnail'] = df['image_urls'].apply(
            lambda x: f'<img src="{x[0]}" class="table-img" alt="Auto">' if x and len(x) > 0 else '❌'
        )
    
    if 'id' in df.columns:    
        df['listing_id'] = df['id'].apply(
            lambda x: f'<span class="listing-id">{x}</span>'
        )
    
    # Mapping colonne per display
    display_columns = {
        'thumbnail': 'Foto',
        'listing_id': 'ID Annuncio',
        'plate': 'Targa',
        'title': 'Modello',
        'original_price': 'Prezzo',
        'discounted_price': 'Prezzo Scontato',
        'mileage': 'Chilometri',
        'registration': 'Immatricolazione',
        'fuel': 'Carburante',
        'url': 'Link'
    }
    
    # Seleziona e rinomina colonne disponibili
    available_columns = [col for col in display_columns.keys() if col in df.columns]
    result_df = df[available_columns].copy()
    result_df.columns = [display_columns[col] for col in available_columns]
    
    return result_df

def filter_listings(df: pd.DataFrame, filters: Dict) -> pd.DataFrame:
    """Applica filtri al DataFrame"""
    filtered_df = df.copy()
    
    if filters.get('min_price'):
        filtered_df = filtered_df[filtered_df['Prezzo'] >= filters['min_price']]
        
    if filters.get('max_price'):
        filtered_df = filtered_df[filtered_df['Prezzo'] <= filters['max_price']]
        
    if filters.get('missing_plates_only'):
        filtered_df = filtered_df[filtered_df['Targa'].isna()]
        
    return filtered_df