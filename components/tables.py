import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
from utils.formatting import format_price

def show_listings_table(listings, highlight_anomalies=True):
    """Visualizza la tabella degli annunci con evidenziazione anomalie"""
    if not listings:
        st.info("Nessun annuncio disponibile")
        return
        
    try:
        df = pd.DataFrame(listings)
        
        # Helper function per date
        def safe_convert_to_utc(dt):
            if pd.isna(dt):
                return None
            if isinstance(dt, str):
                dt = pd.to_datetime(dt)
            if dt.tzinfo is None:
                return dt.tz_localize('UTC')
            return dt.tz_convert('UTC')
        
        # Converti le date in UTC
        date_columns = ['first_seen', 'last_seen', 'created_at', 'updated_at']
        for col in date_columns:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: safe_convert_to_utc(pd.to_datetime(x)) if pd.notna(x) else None)
        
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
            lambda x: f'<img src="{x[0]}" class="table-img" alt="Auto" title="{len(x)} immagini disponibili">' 
            if x and len(x) > 0 else '❌'
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
        
        # Formattazione prezzo con evidenziazione anomalie e variazioni
        def format_price_cell(row):
            price = row['original_price']
            cell_class = 'col-prezzo'
            
            if highlight_anomalies and price:
                if abs(price - avg_price) > price_threshold:
                    cell_class += ' price-anomaly'
                    
            # Aggiungi indicatore variazione se presente
            price_html = format_price(price)
            if row.get('price_variation'):
                variation = row['price_variation']
                variation_class = 'variation-positive' if variation > 0 else 'variation-negative'
                price_html += f' <span class="{variation_class}">({variation:+.1f}%)</span>'
                
            return f'<div class="{cell_class}">{price_html}</div>'
            
        df['prezzo'] = df.apply(format_price_cell, axis=1)
        
        # Formattazione prezzo scontato
        df['prezzo_scontato'] = df.apply(
            lambda row: f'<div class="col-prezzo discount">{format_price(row["discounted_price"])}</div>'
            if pd.notna(row.get('discounted_price')) else "", 
            axis=1
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
        
        # Formattazione link e icone stato
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

            # Aggiungi confidenza OCR se disponibile
            confidence_html = ''
            if row.get('plate_confidence'):
                confidence = row['plate_confidence']
                confidence_html = f' <small>({confidence:.0%})</small>'
                
            return f'<div class="{cell_class}">{plate or "N/D"}{confidence_html}</div>'
            
        df['targa'] = df.apply(format_plate_cell, axis=1)
        
        # Aggiungi età annuncio se disponibile
        now = pd.Timestamp.now(tz='UTC')
        if 'first_seen' in df.columns:
            df['eta'] = df['first_seen'].apply(
                lambda x: f'<div class="col-eta">'
                         f'{(now - x).days} giorni</div>'
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
        
        # Formattazione valori
        df['price'] = df['price'].apply(lambda x: format_price(x))
        df['mileage'] = df['mileage'].apply(
            lambda x: f"{x:,.0f} km".replace(",", ".") if pd.notna(x) else "N/D"
        )
        
        # Evidenzia similitudini
        def highlight_similarities(s):
            if s.name in ['price', 'mileage']:
                # Calcola range accettabile
                values = pd.to_numeric(s.str.replace('[^0-9.]', '', regex=True))
                mean = values.mean()
                threshold = mean * 0.1  # 10% di variazione
                
                return ['background-color: #d1fae5' 
                       if abs(float(str(v).replace(',', '')) - mean) <= threshold 
                       else '' for v in values]
            return ['' for _ in range(len(s))]
        
        # Applica stili
        styled_df = df.style.apply(highlight_similarities)
        
        st.write(styled_df.to_html(escape=False, index=False), unsafe_allow_html=True)
        st.markdown("---")

def show_timeline_table(history_data):
    """Mostra tabella cronologica eventi con dettagli migliorati"""
    if not history_data:
        return
        
    df = pd.DataFrame(history_data)
    
    # Converti date
    df['date'] = pd.to_datetime(df['date']).dt.strftime('%d/%m/%Y %H:%M')
    
    # Formatta prezzi e variazioni
    df['price'] = df['price'].apply(lambda x: format_price(x) if pd.notna(x) else "N/D")
    
    # Formatta eventi con icone
    event_icons = {
        'update': '🔄',
        'removed': '❌',
        'reappeared': '↩️',
        'price_changed': '💰'
    }
    
    def format_event(row):
        event = row['event']
        details = ''
        
        if event == 'price_changed' and row.get('price_variation'):
            variation = row['price_variation']
            details = f" ({variation:+.1f}%)"
            
        return f"{event_icons.get(event, '❓')} {event.title()}{details}"
    
    df['event'] = df.apply(format_event, axis=1)
    
    # Rinomina colonne
    df.columns = [col.title() for col in df.columns]
    
    # Mostra tabella
    st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)