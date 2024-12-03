from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

def create_heatmap(data):
    """Crea heatmap per visualizzare pattern di riapparizione"""
    df = pd.DataFrame(data)
    fig = px.density_heatmap(
        df,
        x='appearance_date',
        y='dealer_id',
        title='Pattern di Riapparizione Annunci'
    )
    return fig

def calculate_reappearance_metrics(listings):
    """Calcola metriche sulle riapparizioni"""
    plates = {}
    for listing in listings:
        if listing['plate'] not in plates:
            plates[listing['plate']] = {
                'appearances': 1,
                'first_seen': listing['first_seen'],
                'last_seen': listing['last_seen']
            }
        else:
            plates[listing['plate']]['appearances'] += 1
            plates[listing['plate']]['last_seen'] = listing['last_seen']
    
    return plates

def format_time_difference(start_time, end_time):
    """Formatta la differenza di tempo in modo leggibile"""
    diff = end_time - start_time
    days = diff.days
    hours = diff.seconds // 3600
    
    if days > 0:
        return f"{days}g {hours}h"
    return f"{hours}h"

def create_timeline_chart(history_data):
    """Crea un grafico timeline delle attività"""
    fig = go.Figure()
    
    for plate, events in history_data.items():
        fig.add_trace(go.Scatter(
            x=[e['date'] for e in events],
            y=[plate for _ in events],
            mode='markers+lines',
            name=plate,
            hovertext=[e['status'] for e in events]
        ))
    
    fig.update_layout(
        title="Timeline Attività Annunci",
        xaxis_title="Data",
        yaxis_title="Targa",
        height=400
    )
    
    return fig