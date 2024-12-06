import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import List, Dict
from datetime import datetime
import pytz
from utils.datetime_utils import normalize_datetime, get_current_time

def show_comparison_view(tracker, listings: List[Dict]):
    """Mostra vista comparativa tra veicoli"""
    st.subheader("🔍 Confronto Veicoli")
    
    if not listings:
        st.info("Nessun veicolo disponibile per il confronto")
        return
        
    # Raggruppa per marca/modello
    df = pd.DataFrame(listings)
    df['brand_model'] = df['title'].apply(lambda x: ' '.join(str(x).split()[:2]))
    
    # Selezione veicoli da confrontare
    selected_model = st.selectbox(
        "Seleziona Marca/Modello",
        options=sorted(df['brand_model'].unique())
    )
    
    model_vehicles = df[df['brand_model'] == selected_model]
    
    if len(model_vehicles) < 2:
        st.warning("Non ci sono abbastanza veicoli simili per un confronto")
        return
        
    col1, col2 = st.columns(2)
    
    with col1:
        vehicle1 = st.selectbox(
            "Veicolo 1",
            options=model_vehicles['id'].tolist(),
            format_func=lambda x: model_vehicles[model_vehicles['id'] == x]['title'].iloc[0]
        )
        
    with col2:
        vehicle2 = st.selectbox(
            "Veicolo 2",
            options=[x for x in model_vehicles['id'].tolist() if x != vehicle1],
            format_func=lambda x: model_vehicles[model_vehicles['id'] == x]['title'].iloc[0]
        )
    
    if vehicle1 and vehicle2:
        show_vehicle_comparison(
            model_vehicles[model_vehicles['id'] == vehicle1].iloc[0],
            model_vehicles[model_vehicles['id'] == vehicle2].iloc[0]
        )

def show_vehicle_comparison(vehicle1: Dict, vehicle2: Dict):
    """Mostra confronto dettagliato tra due veicoli"""
    # Metriche principali
    cols = st.columns(3)
    
    # Prezzo
    with cols[0]:
        price_diff = vehicle1['original_price'] - vehicle2['original_price']
        st.metric(
            "Differenza Prezzo",
            f"€{abs(price_diff):,.0f}",
            f"{'+' if price_diff > 0 else ''}{price_diff/vehicle2['original_price']*100:.1f}%"
        )
    
    # Chilometri
    with cols[1]:
        if 'mileage' in vehicle1 and 'mileage' in vehicle2:
            km_diff = vehicle1['mileage'] - vehicle2['mileage']
            st.metric(
                "Differenza KM",
                f"{abs(km_diff):,.0f} km",
                f"{'+' if km_diff > 0 else ''}{km_diff:,.0f}"
            )
            
    # Età annuncio con gestione timezone corretta
    with cols[2]:
        if 'first_seen' in vehicle1 and 'first_seen' in vehicle2:
            try:
                # Usa get_current_time() per timestamp UTC corrente
                now = get_current_time()
                
                # Normalizza i timestamp first_seen
                first_seen1 = normalize_datetime(vehicle1['first_seen'])
                first_seen2 = normalize_datetime(vehicle2['first_seen'])
                
                if first_seen1 and first_seen2:
                    days1 = (now - first_seen1).days
                    days2 = (now - first_seen2).days
                    days_diff = days1 - days2
                    
                    st.metric(
                        "Differenza Giorni in Lista",
                        f"{abs(days_diff)} giorni",
                        f"{'+' if days_diff > 0 else ''}{days_diff}"
                    )
                else:
                    st.metric("Differenza Giorni in Lista", "N/D", "")
            except Exception as e:
                st.error(f"Errore nel calcolo differenza giorni: {str(e)}")
                st.metric("Differenza Giorni in Lista", "Errore", "")
    
    # Confronto dettagli
    st.write("📊 Confronto Dettagli")
    
    comparison_data = []
    fields_to_compare = [
        ('title', 'Modello'),
        ('original_price', 'Prezzo'),
        ('mileage', 'Chilometri'),
        ('registration', 'Immatricolazione'),
        ('fuel', 'Carburante'),
        ('plate', 'Targa')
    ]
    
    for field, label in fields_to_compare:
        if field in vehicle1 and field in vehicle2:
            comparison_data.append({
                'Caratteristica': label,
                'Veicolo 1': vehicle1[field],
                'Veicolo 2': vehicle2[field],
                'Differenza': '=' if vehicle1[field] == vehicle2[field] else '≠'
            })
            
    df_comparison = pd.DataFrame(comparison_data)
    st.table(df_comparison)
    
    # Storico prezzi se disponibile
    st.write("📈 Storico Prezzi")
    show_price_history_comparison(vehicle1['id'], vehicle2['id'])

def show_price_history_comparison(vehicle1_id: str, vehicle2_id: str):
    """Mostra confronto storico prezzi tra due veicoli"""
    fig = go.Figure()
    
    for vehicle_id in [vehicle1_id, vehicle2_id]:
        # Query storico prezzi
        history = []  # Qui andrà la query al DB
        
        if history:
            df = pd.DataFrame(history)
            fig.add_trace(go.Scatter(
                x=df['date'],
                y=df['price'],
                name=f"Veicolo {vehicle_id}",
                mode='lines+markers'
            ))
    
    fig.update_layout(
        title="Confronto Andamento Prezzi",
        xaxis_title="Data",
        yaxis_title="Prezzo (€)",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)

def find_similar_vehicles(listings: List[Dict], reference_vehicle: Dict, threshold: float = 0.8) -> List[Dict]:
    """Trova veicoli simili a quello di riferimento"""
    if not listings or not reference_vehicle:
        return []
    
    similar = []
    for vehicle in listings:
        if vehicle['id'] == reference_vehicle['id']:
            continue
            
        # Calcola score similarità
        score = calculate_similarity_score(reference_vehicle, vehicle)
        
        if score >= threshold:
            similar.append({
                'vehicle': vehicle,
                'similarity_score': score
            })
    
    return sorted(similar, key=lambda x: x['similarity_score'], reverse=True)

def calculate_similarity_score(vehicle1: Dict, vehicle2: Dict) -> float:
    """Calcola uno score di similarità tra due veicoli"""
    score = 0.0
    weights = {
        'brand_model': 0.4,
        'price': 0.3,
        'mileage': 0.2,
        'year': 0.1
    }
    
    # Confronta marca/modello
    if ('title' in vehicle1 and 'title' in vehicle2 and
        vehicle1['title'].split()[:2] == vehicle2['title'].split()[:2]):
        score += weights['brand_model']
    
    # Confronta prezzo
    if 'original_price' in vehicle1 and 'original_price' in vehicle2:
        price_diff = abs(vehicle1['original_price'] - vehicle2['original_price'])
        price_avg = (vehicle1['original_price'] + vehicle2['original_price']) / 2
        if price_diff / price_avg < 0.2:  # Differenza max 20%
            score += weights['price']
    
    # Confronta chilometri
    if 'mileage' in vehicle1 and 'mileage' in vehicle2:
        km_diff = abs(vehicle1['mileage'] - vehicle2['mileage'])
        km_avg = (vehicle1['mileage'] + vehicle2['mileage']) / 2
        if km_diff / km_avg < 0.3:  # Differenza max 30%
            score += weights['mileage']
    
    # Confronta anno
    if 'registration' in vehicle1 and 'registration' in vehicle2:
        if vehicle1['registration'][:4] == vehicle2['registration'][:4]:
            score += weights['year']
    
    return score