import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import pytz
from typing import List, Dict
from utils.datetime_utils import normalize_datetime, get_current_time
from utils.anomaly_detection import image_similarity_score

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

    # Mostra possibili duplicati
    show_potential_duplicates(model_vehicles)
        
    # Selezione manuale per confronto
    st.subheader("🔄 Confronto Manuale")
    col1, col2 = st.columns(2)
    
    with col1:
        vehicle1 = st.selectbox(
            "Veicolo 1",
            options=model_vehicles['id'].tolist(),
            format_func=lambda x: format_vehicle_label(model_vehicles[model_vehicles['id'] == x].iloc[0])
        )
        
    with col2:
        vehicle2 = st.selectbox(
            "Veicolo 2",
            options=[x for x in model_vehicles['id'].tolist() if x != vehicle1],
            format_func=lambda x: format_vehicle_label(model_vehicles[model_vehicles['id'] == x].iloc[0])
        )
    
    if vehicle1 and vehicle2:
        show_vehicle_comparison(
            model_vehicles[model_vehicles['id'] == vehicle1].iloc[0],
            model_vehicles[model_vehicles['id'] == vehicle2].iloc[0]
        )

def format_vehicle_label(vehicle: Dict) -> str:
    """Formatta etichetta veicolo per select box"""
    parts = []
    if vehicle.get('title'):
        parts.append(vehicle['title'])
    if vehicle.get('plate'):
        parts.append(f"[{vehicle['plate']}]")
    if vehicle.get('original_price'):
        parts.append(f"€{vehicle['original_price']:,.0f}")
    return " - ".join(parts)

def show_potential_duplicates(vehicles_df: pd.DataFrame):
    """Mostra potenziali duplicati nel gruppo di veicoli"""
    st.subheader("🔍 Potenziali Duplicati")
    
    duplicates_found = False
    processed = set()
    
    for i, v1 in vehicles_df.iterrows():
        for j, v2 in vehicles_df.iterrows():
            if i >= j or f"{v1['id']}-{v2['id']}" in processed:
                continue
                
            similarity = calculate_similarity(v1, v2)
            if similarity['score'] > 0.7:  # Alta similarità
                duplicates_found = True
                processed.add(f"{v1['id']}-{v2['id']}")
                
                with st.expander(f"Similarità: {similarity['score']:.0%} - {v1['title']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        show_vehicle_summary(v1, "Veicolo 1")
                        if v1.get('image_urls'):
                            st.image(v1['image_urls'][0], use_column_width=True)
                            
                    with col2:
                        show_vehicle_summary(v2, "Veicolo 2")
                        if v2.get('image_urls'):
                            st.image(v2['image_urls'][0], use_column_width=True)
                            
                    st.write("Elementi Corrispondenti:")
                    for key, value in similarity['matches'].items():
                        if value:
                            st.write(f"✅ {key.title()}")
    
    if not duplicates_found:
        st.info("Nessun duplicato rilevato")

def show_vehicle_summary(vehicle: Dict, title: str = ""):
    """Mostra riepilogo veicolo"""
    st.write(f"**{title}**")
    st.write(f"ID: {vehicle['id']}")
    if vehicle.get('plate'):
        st.write(f"Targa: {vehicle['plate']}")
    st.write(f"Prezzo: €{vehicle.get('original_price', 0):,.0f}")
    if vehicle.get('mileage'):
        st.write(f"KM: {vehicle['mileage']:,.0f}")

def calculate_similarity(v1: Dict, v2: Dict) -> Dict:
    """Calcola similarità tra due veicoli"""
    matches = {
        'targa': False,
        'prezzo': False,
        'chilometri': False,
        'immagini': False
    }
    
    # Confronto targa
    if v1.get('plate') and v2.get('plate'):
        matches['targa'] = v1['plate'] == v2['plate']
    
    # Confronto prezzo (tolleranza 5%)
    if v1.get('original_price') and v2.get('original_price'):
        price_diff = abs(v1['original_price'] - v2['original_price'])
        matches['prezzo'] = price_diff / max(v1['original_price'], v2['original_price']) < 0.05
    
    # Confronto chilometri (tolleranza 10%)
    if v1.get('mileage') and v2.get('mileage'):
        km_diff = abs(v1['mileage'] - v2['mileage'])
        matches['chilometri'] = km_diff / max(v1['mileage'], v2['mileage']) < 0.10
    
    # Confronto immagini
    if v1.get('image_urls') and v2.get('image_urls'):
        img_score = image_similarity_score(v1['image_urls'][0], v2['image_urls'][0])
        matches['immagini'] = img_score > 0.8
    
    # Calcola score complessivo
    weights = {'targa': 0.4, 'prezzo': 0.2, 'chilometri': 0.2, 'immagini': 0.2}
    score = sum(weights[k] for k, v in matches.items() if v)
    
    return {
        'score': score,
        'matches': matches
    }
        

def show_vehicle_comparison(vehicle1: Dict, vehicle2: Dict):
    """Mostra confronto dettagliato tra due veicoli"""
    st.subheader("📊 Confronto Dettagliato")
    
    # Calcola similarità
    similarity = calculate_similarity(vehicle1, vehicle2)
    
    # Metriche principali
    cols = st.columns(3)
    
    # Similarità
    with cols[0]:
        st.metric("Indice di Similarità", f"{similarity['score']:.0%}")
    
    # Prezzo
    with cols[1]:
        price_diff = vehicle1['original_price'] - vehicle2['original_price']
        price_pct = (price_diff / vehicle2['original_price'] * 100) if vehicle2['original_price'] else 0
        st.metric(
            "Differenza Prezzo",
            f"€{abs(price_diff):,.0f}",
            f"{'+' if price_diff > 0 else ''}{price_pct:.1f}%"
        )
    
    # Chilometri
    with cols[2]:
        if vehicle1.get('mileage') and vehicle2.get('mileage'):
            km_diff = vehicle1['mileage'] - vehicle2['mileage']
            st.metric(
                "Differenza KM",
                f"{abs(km_diff):,.0f} km",
                f"{'+' if km_diff > 0 else ''}{km_diff:,.0f}"
            )
    
    # Confronto immagini
    if vehicle1.get('image_urls') and vehicle2.get('image_urls'):
        st.write("🖼️ Confronto Immagini")
        col1, col2 = st.columns(2)
        with col1:
            st.image(vehicle1['image_urls'][0], caption="Veicolo 1", use_column_width=True)
        with col2:
            st.image(vehicle2['image_urls'][0], caption="Veicolo 2", use_column_width=True)
        
        if len(vehicle1['image_urls']) > 1 or len(vehicle2['image_urls']) > 1:
            with st.expander("Mostra altre immagini"):
                for i in range(1, max(len(vehicle1['image_urls']), len(vehicle2['image_urls']))):
                    col1, col2 = st.columns(2)
                    with col1:
                        if i < len(vehicle1['image_urls']):
                            st.image(vehicle1['image_urls'][i], use_column_width=True)
                    with col2:
                        if i < len(vehicle2['image_urls']):
                            st.image(vehicle2['image_urls'][i], use_column_width=True)
    
    # Confronto dettagli
    st.write("📋 Dettagli Veicoli")
    
    comparison_data = []
    fields_to_compare = [
        ('title', 'Modello'),
        ('plate', 'Targa'),
        ('original_price', 'Prezzo'),
        ('discounted_price', 'Prezzo Scontato'),
        ('mileage', 'Chilometri'),
        ('registration', 'Immatricolazione'),
        ('fuel', 'Carburante'),
        ('transmission', 'Cambio'),
        ('power', 'Potenza'),
        ('first_seen', 'Prima Vista'),
        ('last_seen', 'Ultima Vista')
    ]
    
    for field, label in fields_to_compare:
        val1 = vehicle1.get(field)
        val2 = vehicle2.get(field)
        
        # Formatta valori speciali
        if field in ['first_seen', 'last_seen'] and val1:
            val1 = val1.strftime('%d/%m/%Y %H:%M')
        if field in ['first_seen', 'last_seen'] and val2:
            val2 = val2.strftime('%d/%m/%Y %H:%M')
        if field in ['original_price', 'discounted_price']:
            if val1:
                val1 = f"€{val1:,.0f}"
            if val2:
                val2 = f"€{val2:,.0f}"
        if field == 'mileage':
            if val1:
                val1 = f"{val1:,.0f} km"
            if val2:
                val2 = f"{val2:,.0f} km"
        
        comparison_data.append({
            'Caratteristica': label,
            'Veicolo 1': val1 if val1 is not None else "N/D",
            'Veicolo 2': val2 if val2 is not None else "N/D",
            'Match': '=' if val1 == val2 else '≠'
        })
    
    df_comparison = pd.DataFrame(comparison_data)
    st.table(df_comparison.style.apply(
        lambda x: ['background: #e6ffe6' if x['Match'] == '=' else '' for i in x], 
        axis=1
    ))
    
    # Link agli annunci
    st.write("🔗 Link Annunci")
    col1, col2 = st.columns(2)
    with col1:
        if vehicle1.get('url'):
            st.markdown(f"[Vai all'annuncio 1]({vehicle1['url']})")
    with col2:
        if vehicle2.get('url'):
            st.markdown(f"[Vai all'annuncio 2]({vehicle2['url']})")

    # Note e warning
    if similarity['score'] > 0.8:
        st.warning("⚠️ Questi annunci hanno un'alta probabilità di essere duplicati")
        
    # Se le targhe sono diverse ma le immagini molto simili
    if (vehicle1.get('plate') and vehicle2.get('plate') and 
        vehicle1['plate'] != vehicle2['plate'] and 
        similarity['matches']['immagini']):
        st.warning("⚠️ Le targhe sono diverse ma le immagini sono molto simili")

    # Se i prezzi hanno una differenza significativa
    if abs(price_pct) > 20:
        st.warning(f"⚠️ Differenza prezzo significativa: {abs(price_pct):.1f}%")

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