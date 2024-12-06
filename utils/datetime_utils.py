# utils/datetime_utils.py

import pandas as pd
from datetime import datetime
import pytz

def ensure_tz_aware(dt):
    """
    Assicura che un datetime sia timezone-aware, convertendolo in UTC se necessario
    """
    if dt is None:
        return None
    if pd.isna(dt):
        return None
        
    if isinstance(dt, pd.Timestamp):
        if dt.tz is None:
            return dt.tz_localize('UTC')
        return dt.tz_convert('UTC')
    
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return pytz.UTC.localize(dt)
        return dt.astimezone(pytz.UTC)
        
    return None

def normalize_df_dates(df, date_columns=['date', 'first_seen', 'last_seen']):
    """
    Normalizza le colonne data di un DataFrame assicurando che siano tutte timezone-aware
    """
    df = df.copy()
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
            # Gestisce sia date naive che aware
            df[col] = df[col].apply(ensure_tz_aware)
    return df

def get_current_time():
    """
    Restituisce il timestamp corrente in UTC
    """
    return datetime.now(pytz.UTC)

def calculate_date_diff(start_date, end_date=None):
    """
    Calcola la differenza in giorni tra due date, gestendo correttamente i timezone
    """
    if end_date is None:
        end_date = get_current_time()
        
    start = ensure_tz_aware(start_date)
    end = ensure_tz_aware(end_date)
    
    if start and end:
        return (end - start).days
    return None