import streamlit as st
from services.tracker import AutoTracker
import pandas as pd
from datetime import datetime
from utils.formatting import format_price

def show():
    # Recupera ID dealer dalla query string
    dealer_id = st.query_params.get("id")
    if not dealer_id:
        st.error("❌ ID concessionario mancante")
        return
        
    tracker = AutoTracker()
    dealers = tracker.get_dealers()
    dealer = next((d for d in dealers if d['id'] == dealer_id), None)
    
    if not dealer:
        st.error("❌ Concessionario non trovato")
        return
        
    # Header
    st.title(f"🏢 {dealer['url'].split('/')[-1].upper()}")
    st.caption(dealer['url'])
    
    if dealer.get('last_update'):
        st.info(f"📅 Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")
        
    # Bottone aggiorna
    if st.button("🔄 Aggiorna Annunci"):
        with st.status("⏳ Aggiornamento in corso...", expanded=True) as status:
            try:
                listings = tracker.scrape_dealer(dealer['url'])
                if listings:
                    for listing in listings:
                        listing['dealer_id'] = dealer['id']
                    tracker.save_listings(listings)
                    tracker.mark_inactive_listings(dealer['id'], [l['id'] for l in listings])
                    status.update(label="✅ Aggiornamento completato!", state="complete")
                else:
                    status.update(label="⚠️ Nessun annuncio trovato", state="error")
            except Exception as e:
                status.update(label=f"❌ Errore: {str(e)}", state="error")
                
    # Recupera annunci
    listings = tracker.get_active_listings(dealer['id'])
    if not listings:
        st.warning("⚠️ Nessun annuncio attivo")
        return
        
    # Tabella annunci
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
        df['prezzo_scontato'] = df['discounted_price'].apply(lambda x: f'<div class="col-prezzo">{format_price(x)}</div>')
        df['km'] = df['mileage'].apply(
            lambda x: f'{x:,.0f} km'.replace(",", ".") if pd.notna(x) else "N/D"
        )
        df['registration'] = df['registration'].apply(lambda x: x if pd.notna(x) else "N/D")
        df['fuel'] = df['fuel'].apply(lambda x: x if pd.notna(x) else "N/D")
        df['link'] = df['url'].apply(
            lambda x: f'<a href="{x}" target="_blank">🔗</a>' if pd.notna(x) else ''
        )

        # Selezione colonne
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
        
        # Visualizza tabella
        st.write(df.to_html(escape=False, index=False), unsafe_allow_html=True)
        
        # Accordion per modifica targhe
        with st.expander("✏️ Modifica Targhe", expanded=False):
            st.write("Seleziona l'auto e modifica la targa:")
            
            for idx, row in df.iterrows():
                cols = st.columns([3, 1, 1])
                with cols[0]:
                    st.write(f"**{row['Modello']}**")
                with cols[1]:
                    new_plate = st.text_input(
                        "Targa",
                        value=row.get('Targa', ''),
                        key=f"plate_{row['ID Annuncio']}",
                        label_visibility="collapsed"
                    )
                with cols[2]:
                    if new_plate != row.get('Targa', ''):
                        if st.button("💾", key=f"save_{row['ID Annuncio']}"):
                            if tracker.update_plate(row['ID Annuncio'], new_plate):
                                st.success("✅ Targa aggiornata")
                                st.rerun()
                                
    except Exception as e:
        st.error(f"❌ Errore nella visualizzazione: {str(e)}")