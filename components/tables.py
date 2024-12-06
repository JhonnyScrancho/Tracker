import streamlit as st
import pandas as pd
from utils.formatting import format_price
from datetime import datetime

def show_listings_table(listings, highlight_anomalies=True):
    """Visualizza la tabella degli annunci con evidenziazione anomalie"""
    if not listings:
        st.info("Nessun annuncio disponibile")
        return
        
    try:
        df = pd.DataFrame(listings)
        
        # Calcola valori di riferimento per anomalie
        if highlight_anomalies and len(df) > 0:
            avg_price = df['original_price'].mean()
            std_price = df['original_price'].std()
            price_threshold = std_price * 2
            
            if 'mileage' in df.columns:
                avg_mileage = df['mileage'].mean()
                std_mileage = df['mileage'].std()
                mileage_threshold = std_mileage * 2
        
        # Formattazione colonne base
        df['thumbnail'] = df['image_urls'].apply(
            lambda x: f'<img src="{x[0]}" class="table-img" alt="Auto">' if x and len(x) > 0 else '❌'
        )
        
        df['listing_id'] = df['id'].apply(
            lambda x: f'<span class="listing-id">{x}</span>'
        )
        
        # Formattazione titolo con evidenziazione riapparizioni
        df['title'] = df.apply(lambda row: 
            f'<div class="col-modello {" reappeared" if row.get("reappeared") else ""}">'
            f'{row["title"]}'
            f'{"🔄" if row.get("reappeared") else ""}</div>', 
            axis=1
        )
        
        # Formattazione prezzo con evidenziazione anomalie
        def format_price_cell(row):
            price = row['original_price']
            cell_class = 'col-prezzo'
            
            if highlight_anomalies and price:
                if abs(price - avg_price) > price_threshold:
                    cell_class += ' price-anomaly'
                    
            formatted_price = format_price(price)
            return f'<div class="{cell_class}">{formatted_price}</div>'
            
        df['prezzo'] = df.apply(format_price_cell, axis=1)
        
        # Formattazione prezzo scontato
        df['prezzo_scontato'] = df['discounted_price'].apply(
            lambda x: f'<div class="col-prezzo discount">{format_price(x)}</div>'
            if pd.notna(x) else ""
        )
        
        # Formattazione chilometri con evidenziazione anomalie
        def format_mileage_cell(row):
            mileage = row.get('mileage')
            cell_class = 'col-km'
            
            if highlight_anomalies and mileage and 'mileage_threshold' in locals():
                if abs(mileage - avg_mileage) > mileage_threshold:
                    cell_class += ' mileage-anomaly'
                    
            formatted_mileage = f'{mileage:,.0f} km'.replace(",", ".") if pd.notna(mileage) else "N/D"
            return f'<div class="{cell_class}">{formatted_mileage}</div>'
            
        df['km'] = df.apply(format_mileage_cell, axis=1)
        
        # Formattazione data
        df['registration'] = df['registration'].apply(
            lambda x: f'<div class="col-data">{x}</div>' if pd.notna(x) else "N/D"
        )
        
        # Formattazione carburante
        df['fuel'] = df['fuel'].apply(
            lambda x: f'<div class="col-carburante">{x}</div>' if pd.notna(x) else "N/D"
        )
        
        # Formattazione link con icone stato
        def format_link_cell(row):
            icons = []
            
            if row.get('reappeared'):
                icons.append("🔄")
            if row.get('has_discount'):
                icons.append("💰")
            if row.get('plate_edited'):
                icons.append("✏️")
                
            url = row.get('url', '')
            icons_html = ' '.join(icons)
            
            return f'<div class="col-link">{icons_html} <a href="{url}" target="_blank">🔗</a></div>'
            
        df['link'] = df.apply(format_link_cell, axis=1)
        
        # Formattazione targa con evidenziazione modifiche
        def format_plate_cell(row):
            plate = row.get('plate', '')
            cell_class = 'col-targa'
            
            if row.get('plate_edited'):
                cell_class += ' plate-edited'
                
            return f'<div class="{cell_class}">{plate or "N/D"}</div>'
            
        df['targa'] = df.apply(format_plate_cell, axis=1)
        
        # Aggiungi età annuncio se disponibile
        if 'first_seen' in df.columns:
            df['eta'] = df['first_seen'].apply(
                lambda x: f'<div class="col-eta">'
                         f'{(datetime.now() - x).days} giorni</div>'
                if pd.notna(x) else "N/D"
            )
        
        # Selezione e ordinamento colonne
        display_columns = {
            'thumbnail': 'Foto',
            'listing_id': 'ID Annuncio',
            'targa': 'Targa',
            'title': 'Modello',
            'prezzo': 'Prezzo',
            'prezzo_scontato': 'P. Scontato',
            'km': 'Chilometri',
            'registration': 'Immatricolazione',
            'fuel': 'Carburante',
            'eta': 'In Lista Da',
            'link': 'Azioni'
        }
        
        # Seleziona solo colonne disponibili
        available_columns = [col for col in display_columns.keys() if col in df.columns]
        df = df[available_columns]
        df.columns = [display_columns[col] for col in available_columns]
        
        # Aggiungi CSS per evidenziare anomalie
        st.markdown("""
            <style>
                .price-anomaly { color: #ff4b4b !important; font-weight: bold; }
                .mileage-anomaly { color: #ff4b4b !important; font-weight: bold; }
                .plate-edited { background-color: #fffae6; }
                .reappeared { background-color: #e6f3ff; }
                .discount { color: #28a745 !important; }
            </style>
        """, unsafe_allow_html=True)
        
        # Mostra tabella
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"❌ Errore nella visualizzazione: {str(e)}")

def show_comparison_table(similar_vehicles):
    """Mostra tabella comparativa per veicoli simili"""
    if not similar_vehicles:
        return
        
    st.subheader("🔄 Veicoli Simili")
    
    for group in similar_vehicles:
        df = pd.DataFrame(group)
        
        df['price'] = df['price'].apply(lambda x: format_price(x))
        df['mileage'] = df['mileage'].apply(
            lambda x: f"{x:,.0f} km".replace(",", ".") if pd.notna(x) else "N/D"
        )
        
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        st.markdown("---")

def show_timeline_table(history_data):
    """Mostra tabella cronologica eventi"""
    if not history_data:
        return
        
    df = pd.DataFrame(history_data)
    
    # Formatta colonne
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%d/%m/%Y %H:%M')
    df['price'] = df['price'].apply(lambda x: format_price(x) if pd.notna(x) else "N/D")
    
    # Formatta evento
    event_icons = {
        'update': '🔄',
        'removed': '❌',
        'reappeared': '↩️',
        'price_changed': '💰'
    }
    df['event'] = df['event'].apply(lambda x: f"{event_icons.get(x, '❓')} {x.title()}")
    
    # Rinomina colonne
    df.columns = [col.title() for col in df.columns]
    
    st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)