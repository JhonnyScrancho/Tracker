from datetime import datetime
import plotly.graph_objects as go
import pandas as pd

def format_price(price):
    """Formatta un prezzo in formato leggibile"""
    if pd.isna(price) or price is None:
        return "N/D"
    return f"€{price:,.0f}".replace(",", ".")

def format_date(date):
    """Formatta una data in formato leggibile"""
    if not date:
        return "N/D"
    return date.strftime("%d/%m/%Y")

def format_duration(days):
    """Formatta una durata in giorni in formato leggibile"""
    if days < 1:
        return "< 1 giorno"
    elif days == 1:
        return "1 giorno"
    return f"{int(days)} giorni"