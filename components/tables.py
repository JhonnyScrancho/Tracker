# components/tables.py

import streamlit as st
import pandas as pd
from utils.formatting import format_price

def show_listings_table(listings):
    """Visualizza la tabella degli annunci"""
    if not listings:
        st.info("Nessun annuncio disponibile")
        return
        
    try:
        df = pd.DataFrame(listings)
        
        # Formattazione colonne
        df['thumbnail'] = df['image_urls'].apply(
            lambda x: f'<img src="{x[0]}" class="table-img" alt="Auto">' if x and len(x) > 0 else '❌'
        )
        
        df['listing_id'] = df['id'].apply(
            lambda x: f'<span class="listing-id">{x}</span>'
        )
        
        df['title'] = df['title'].apply(lambda x: f'<div class="col-modello">{x}</div>')
        df['prezzo'] = df['original_price'].apply(lambda x: f'<div class="col-prezzo">{format_price(x)}</div>')
        df['prezzo_scontato'] = df['discounted_price'].apply(
            lambda x: f'<div class="col-prezzo">{format_price(x)}</div>'
        )
        df['km'] = df['mileage'].apply(
            lambda x: f'<div class="col-km">{x:,.0f} km</div>'.replace(",", ".") if pd.notna(x) else "N/D"
        )
        df['registration'] = df['registration'].apply(lambda x: f'<div class="col-data">{x}</div>' if pd.notna(x) else "N/D")
        df['fuel'] = df['fuel'].apply(lambda x: f'<div class="col-carburante">{x}</div>' if pd.notna(x) else "N/D")
        df['link'] = df['url'].apply(
            lambda x: f'<a href="{x}" target="_blank">🔗</a>' if pd.notna(x) else ''
        )

        # Selezione colonne per display
        display_columns = {
            'thumbnail': 'Foto',
            'listing_id': 'ID Annuncio',
            'plate': 'Targa',
            'title': 'Modello',
            'prezzo': 'Prezzo',
            'prezzo_scontato': 'Prezzo Scontato',
            'km': 'Chilometri',
            'registration': 'Immatricolazione',
            'fuel': 'Carburante',
            'link': 'Link'
        }

        df = df[display_columns.keys()]
        df.columns = display_columns.values()
        
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"❌ Errore nella visualizzazione: {str(e)}")