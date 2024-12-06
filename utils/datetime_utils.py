# utils/datetime_utils.py

from datetime import datetime
import pytz
import pandas as pd
from typing import Optional, Union

def get_current_time() -> datetime:
    """Restituisce il timestamp corrente in UTC"""
    return datetime.now(pytz.UTC)

def normalize_datetime(dt: Optional[Union[datetime, str]]) -> Optional[datetime]:
    """
    Normalizza un datetime assicurandosi che sia timezone-aware in UTC
    
    Args:
        dt: datetime object o stringa ISO
        
    Returns:
        datetime normalizzato in UTC o None se input invalido
    """
    if dt is None:
        return None
        
    try:
        # Se è una stringa, prova a parsarla
        if isinstance(dt, str):
            dt = pd.to_datetime(dt)
            
        # Se è naive, assumiamo sia UTC
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)
        # Altrimenti convertiamo in UTC
        else:
            dt = dt.astimezone(pytz.UTC)
            
        return dt
        
    except Exception:
        return None

def normalize_df_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalizza tutte le colonne datetime in un DataFrame
    
    Args:
        df: DataFrame da normalizzare
        
    Returns:
        DataFrame con date normalizzate
    """
    df = df.copy()
    
    date_columns = [
        'date', 'first_seen', 'last_seen', 'created_at', 
        'updated_at', 'removed_at', 'reappeared_at'
    ]
    
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True)
            
    return df

def calculate_date_diff(start: Union[datetime, str], 
                       end: Union[datetime, str]) -> Optional[int]:
    """
    Calcola la differenza in giorni tra due date gestendo i timezone
    
    Args:
        start: Data iniziale
        end: Data finale
        
    Returns:
        Differenza in giorni o None se input invalido
    """
    start_dt = normalize_datetime(start)
    end_dt = normalize_datetime(end)
    
    if start_dt is None or end_dt is None:
        return None
        
    return (end_dt - start_dt).days