import streamlit as st
from tracker import AutoTracker
import pandas as pd
from datetime import datetime
import time
from utils import format_price, create_timeline_chart, create_price_history_chart

st.set_page_config(
    page_title="Tracker",
    page_icon="🚗",
    layout="wide"
)

# Custom CSS migliorato
st.markdown("""
    <style>
        .stExpander {
            width: 100% !important;
        }
        .log-container {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 0.25rem;
            padding: 1rem;
            margin: 1rem 0;
            max-height: 400px;
            overflow-y: auto;
            width: 100% !important;
        }
        .element-container {
            width: 100% !important;
        }
        .stMarkdown {
            width: 100% !important;
        }
        
        /* Stili tabella migliorati */
        .dataframe {
            width: 100%;
            margin: 1rem 0;
            border-collapse: collapse;
            font-size: 14px;
        }
        .dataframe th {
            background-color: #f8f9fa;
            padding: 12px 8px;
            font-weight: 600;
            text-align: left;
            border-bottom: 2px solid #dee2e6;
            white-space: nowrap;
        }
        .dataframe td {
            padding: 8px;
            vertical-align: middle;
            border-bottom: 1px solid #eee;
        }
        .dataframe tr:hover {
            background-color: #f5f5f5;
        }
        
        /* Stili colonne specifiche */
        .col-foto { 
            width: 100px !important;
            padding: 5px !important;
        }
        .col-id { 
            width: 220px !important;
            font-family: monospace;
        }
        .col-targa { 
            width: 120px !important;
            text-align: center !important;
        }
        .col-modello { 
            min-width: 300px !important;
        }
        .col-prezzo { 
            width: 120px !important;
            text-align: right !important;
        }
        .col-km { 
            width: 120px !important;
            text-align: right !important;
        }
        .col-data { 
            width: 100px !important;
            text-align: center !important;
        }
        .col-carburante { 
            width: 100px !important;
        }
        .col-cambio { 
            width: 100px !important;
        }
        .col-link { 
            width: 80px !important;
            text-align: center !important;
        }
        
        .table-img {
            width: 80px;
            height: 60px;
            object-fit: cover;
            border-radius: 4px;
        }
        .listing-id {
            font-family: monospace;
            background-color: #f3f4f6;
            padding: 4px 6px;
            border-radius: 4px;
            font-size: 0.9em;
            color: #374151;
        }
        
        /* Stili per targhe modificate */
        .plate-edited {
            background-color: #e8f5e9;
            padding: 2px 6px;
            border-radius: 4px;
            border: 1px solid #81c784;
        }
        
        /* Input targa in tabella */
        .targa-input {
            width: 100px;
            text-align: center;
            padding: 4px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .targa-input:focus {
            border-color: #80bdff;
            outline: 0;
            box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25);
        }
        
        /* Bottone salva */
        .save-button {
            padding: 2px 8px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        .save-button:hover {
            background: #45a049;
        }
    </style>
""", unsafe_allow_html=True)

def main():
    st.title("🚗 Tracker")
    
    tracker = AutoTracker()
    
    # Sidebar per gestione concessionari
    with st.sidebar:
        st.header("📋 Gestione Concessionari")
        new_dealer_url = st.text_input(
            "Aggiungi Concessionario",
            placeholder="https://www.autoscout24.it/concessionari/esempio"
        )
        if new_dealer_url and st.button("➕ Aggiungi"):
            try:
                dealer_id = new_dealer_url.split('/')[-1]
                tracker.save_dealer(dealer_id, new_dealer_url)
                st.success("✅ Concessionario aggiunto")
            except Exception as e:
                st.error(f"❌ Errore: {str(e)}")
    
    # Tab principale
    tab1, tab2 = st.tabs(["📊 Dashboard", "📈 Statistiche"])
    
    with tab1:
        # Lista concessionari
        dealers = tracker.get_dealers()
        if not dealers:
            st.info("👋 Aggiungi un concessionario per iniziare")
            return
            
        st.header("🏢 Concessionari Monitorati")

        for dealer in dealers:
            st.subheader(dealer['url'])
            if dealer.get('last_update'):
                st.caption(f"Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")

            col1, col2, col3 = st.columns([5,1,1])
            with col1:
                if st.button("🔄 Aggiorna", key=f"update_{dealer['id']}"):
                    with st.expander("📝 Log Aggiornamento", expanded=True):
                        progress_placeholder = st.empty()
                        try:
                            with st.spinner("⏳ Aggiornamento in corso..."):
                                listings = tracker.scrape_dealer(dealer['url'])
                                if listings:
                                    for listing in listings:
                                        listing['dealer_id'] = dealer['id']
                                    
                                    tracker.save_listings(listings)
                                    tracker.mark_inactive_listings(dealer['id'], [l['id'] for l in listings])
                                    progress_placeholder.success("✅ Aggiornamento completato!")
                                else:
                                    progress_placeholder.warning("⚠️ Nessun annuncio trovato")
                        except Exception as e:
                            progress_placeholder.error(f"❌ Errore: {str(e)}")
            
            with col2:
                remove_button = st.button("❌ Rimuovi", key=f"remove_{dealer['id']}")
            
            with col3:
                if remove_button:
                    confirm = st.checkbox("Conferma rimozione", key=f"confirm_{dealer['id']}")
                    hard_delete = st.checkbox("Elimina permanentemente", key=f"hard_delete_{dealer['id']}")
                    
                    if confirm:
                        tracker.remove_dealer(dealer['id'], hard_delete=hard_delete)
                        st.rerun()
            
            # Mostra annunci attivi
            listings = tracker.get_active_listings(dealer['id'])
            
            if listings:
                try:
                    df = pd.DataFrame(listings)
                    
                    # Formattazione immagine
                    df['thumbnail'] = df['image_urls'].apply(
                        lambda x: f'<div class="col-foto"><img src="{x[0]}" class="table-img" alt="Auto"></div>' if x and len(x) > 0 else '❌'
                    )
                    
                    # Formattazione ID annuncio
                    df['listing_id'] = df['id'].apply(
                        lambda x: f'<div class="col-id"><span class="listing-id">{x}</span></div>'
                    )
                    
                    # Input targa con pulsante salva
                    df['targa'] = df.apply(
                        lambda row: st.text_input(
                            "Targa",
                            value=row.get('plate', ''),
                            key=f"plate_{row['id']}",
                            label_visibility="collapsed"
                        ) + (
                            st.button(
                                "💾",
                                key=f"save_{row['id']}",
                                help="Salva targa",
                                on_click=lambda: tracker.update_plate(
                                    row['id'],
                                    st.session_state[f"plate_{row['id']}"]
                                ) and time.sleep(0.5) and st.rerun()
                            ) if st.session_state.get(f"plate_{row['id']}") != row.get('plate', '') else ""
                        ),
                        axis=1
                    )
                    
                    # Altre formattazioni
                    df['title'] = df['title'].apply(lambda x: f'<div class="col-modello">{x}</div>')
                    df['prezzo'] = df['original_price'].apply(lambda x: f'<div class="col-prezzo">{format_price(x)}</div>')
                    df['prezzo_scontato'] = df['discounted_price'].apply(lambda x: f'<div class="col-prezzo">{format_price(x)}</div>')
                    df['km'] = df['mileage'].apply(
                        lambda x: f'<div class="col-km">{x:,.0f} km</div>'.replace(",", ".") if pd.notna(x) else "N/D"
                    )
                    df['registration'] = df['registration'].apply(lambda x: f'<div class="col-data">{x}</div>' if pd.notna(x) else "N/D")
                    df['fuel'] = df['fuel'].apply(lambda x: f'<div class="col-carburante">{x}</div>' if pd.notna(x) else "N/D")
                    df['transmission'] = df['transmission'].apply(lambda x: f'<div class="col-cambio">{x}</div>' if pd.notna(x) else "N/D")
                    df['link'] = df['url'].apply(
                        lambda x: f'<div class="col-link"><a href="{x}" target="_blank">🔗 Vedi</a></div>' if pd.notna(x) else ''
                    )
                    
                    # Selezione e rinomina colonne
                    display_columns = {
                        'thumbnail': 'Foto',
                        'listing_id': 'ID Annuncio',
                        'targa': 'Targa',
                        'title': 'Modello',
                        'prezzo': 'Prezzo',
                        'prezzo_scontato': 'Prezzo Scontato',
                        'discount_percentage': 'Sconto %',
                        'km': 'Chilometri',
                        'registration': 'Immatricolazione',
                        'fuel': 'Carburante',
                        'transmission': 'Cambio',
                        'link': 'Link'
                    }
                    
                    available_columns = [col for col in display_columns.keys() if col in df.columns]
                    display_df = df[available_columns].copy()
                    display_df.columns = [display_columns[col] for col in available_columns]
                    
                    # Visualizzazione tabella
                    st.write(
                        display_df.to_html(
                            escape=False,
                            index=False,
                            classes=['dataframe']
                        ),
                        unsafe_allow_html=True
                    )
                    
                    # Aggiungi JavaScript per la gestione del salvataggio
                    st.markdown("""
                        <script>
                        function savePlate(listingId) {
                            const input = document.getElementById('plate_' + listingId);
                            const newPlate = input.value;
                            
                            // Usa l'API di Streamlit per comunicare con il backend
                            window.parent.postMessage({
                                type: 'streamlit:setComponentValue',
                                value: {
                                    listingId: listingId,
                                    newPlate: newPlate
                                }
                            }, '*');
                            
                            // Nascondi il pulsante di salvataggio
                            input.nextElementSibling.style.display = 'none';
                        }
                        </script>
                    """, unsafe_allow_html=True)
                    
                    # Gestione del salvataggio
                    if 'plate_edit_data' in st.session_state:
                        listing_id = st.session_state.plate_edit_data['listingId']
                        new_plate = st.session_state.plate_edit_data['newPlate']
                        
                        if tracker.update_plate(listing_id, new_plate):
                            st.success(f"✅ Targa aggiornata con successo: {new_plate}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Errore nell'aggiornamento della targa")
                        
                        del st.session_state.plate_edit_data
                    
                    # Grafici storici
                    history = tracker.get_listing_history(dealer['id'])
                    if history:
                        st.subheader("📊 Analisi Storica")
                        col1, col2 = st.columns(2)
                        with col1:
                            timeline = create_timeline_chart(history)
                            if timeline:
                                st.plotly_chart(timeline, use_container_width=True)
                        with col2:
                            price_history = create_price_history_chart(history)
                            if price_history:
                                st.plotly_chart(price_history, use_container_width=True)
                except Exception as e:
                    st.error(f"Errore nella creazione del DataFrame: {str(e)}")
                    st.write("Debug - Struttura dati listing:", listings[0].keys() if listings else "No listings")
            else:
                st.info("ℹ️ Nessun annuncio attivo")
            st.divider()
    
    with tab2:
        if dealers:
            for dealer in dealers:
                st.subheader(dealer['url'])
                stats = tracker.get_dealer_stats(dealer['id'])
                
                # Metriche principali
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("🚗 Annunci Attivi", stats['total_active'])
                with col2:
                    st.metric("⏱️ Durata Media", f"{stats['avg_listing_duration']:.1f} giorni")
                with col3:
                    st.metric("💰 Annunci Scontati", stats['total_discount_count'])
                with col4:
                    if stats['total_discount_count'] > 0:
                        st.metric("📊 Sconto Medio", f"{stats['avg_discount_percentage']:.1f}%")
                    else:
                        st.metric("📊 Sconto Medio", "N/D")
                
                # Dettagli statistiche
                if stats['total_active'] > 0:
                    with st.expander("🔍 Dettagli Statistiche"):
                        st.write(f"""
                        - Totale annunci attivi: {stats['total_active']}
                        - Durata media annunci: {stats['avg_listing_duration']:.1f} giorni
                        - Numero annunci scontati: {stats['total_discount_count']}
                        - Sconto medio: {stats['avg_discount_percentage']:.1f}%
                        """)
                st.divider()

if __name__ == "__main__":
    main()