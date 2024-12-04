import streamlit as st
from tracker import AutoTracker
import pandas as pd
from datetime import datetime
from utils import format_price, create_timeline_chart, create_price_history_chart

st.set_page_config(
    page_title="AutoScout24 Tracker",
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
        .car-card {
            background-color: white;
            border-radius: 10px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .price-section {
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 10px 0;
        }
        .price-tag {
            font-size: 1.5em;
            font-weight: bold;
            color: #4CAF50;
        }
        .discount-price {
            font-size: 1.2em;
            color: #666;
            text-decoration: line-through;
        }
        .discount-badge {
            background-color: #f44336;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9em;
            font-weight: bold;
        }
        .car-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin: 10px 0;
        }
        .car-image {
            border-radius: 5px;
            width: 100%;
            height: auto;
        }
        .detail-item {
            display: flex;
            align-items: center;
            margin: 5px 0;
        }
        .detail-label {
            font-weight: bold;
            margin-right: 5px;
        }
    </style>
""", unsafe_allow_html=True)

def main():
    st.title("🚗 AutoScout24 Tracker")
    
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
                                    # Assicurati che ogni annuncio abbia il dealer_id
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
                    
                    # Formattazione prezzi
                    df['prezzo'] = df['original_price'].apply(format_price)
                    df['prezzo_scontato'] = df['discounted_price'].apply(format_price)
                    
                    # Aggiunta link cliccabile
                    df['link'] = df['url'].apply(lambda x: f'<a href="{x}" target="_blank">🔗 Vedi</a>' if pd.notna(x) else '')
                    
                    # Selezione e rinomina colonne
                    display_columns = {
                        'title': 'Modello',
                        'prezzo': 'Prezzo',
                        'prezzo_scontato': 'Prezzo Scontato',
                        'discount_percentage': 'Sconto %',
                        'mileage': 'Km',
                        'registration': 'Immatricolazione',
                        'fuel': 'Carburante',
                        'link': 'Link'
                    }
                    
                    # Filtra solo le colonne disponibili
                    available_columns = [col for col in display_columns.keys() if col in df.columns]
                    display_df = df[available_columns].copy()
                    display_df.columns = [display_columns[col] for col in available_columns]
                    
                    # Visualizzazione tabella con link cliccabili
                    st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Errore nella creazione del DataFrame: {str(e)}")
                    st.write("Debug - Struttura dati listing:", listings[0].keys() if listings else "No listings")
                
                # Visualizzazione dettagliata stile AutoScout24
                with st.expander("📸 Dettagli Annunci", expanded=False):
                    for listing in listings:
                        st.markdown("""
                            <div class="car-card">
                        """, unsafe_allow_html=True)
                        
                        cols = st.columns([2, 3])
                        
                        with cols[0]:
                            if listing.get('image_urls') and len(listing['image_urls']) > 0:
                                try:
                                    st.image(
                                        listing['image_urls'][0],
                                        use_column_width=True
                                    )
                                except Exception as e:
                                    st.error(f"Errore nel caricamento dell'immagine: {str(e)}")
                                    st.write(f"URL immagine problematico: {listing['image_urls'][0]}")
                            else:
                                st.write("Nessuna immagine disponibile")
                        
                        with cols[1]:
                            st.markdown(f"### {listing['title']}")
                            
                            # Visualizzazione prezzi migliorata
                            price_html = '<div class="price-section">'
                            
                            if listing.get('has_discount') and listing.get('discounted_price'):
                                # Se c'è uno sconto, mostra prima il prezzo scontato e poi quello originale barrato
                                price_html += f'''
                                    <span class="price-tag">{format_price(listing['discounted_price'])}</span>
                                    <span class="discount-price">{format_price(listing['original_price'])}</span>
                                '''
                                if listing.get('discount_percentage'):
                                    price_html += f'<span class="discount-badge">-{listing["discount_percentage"]}%</span>'
                            else:
                                # Se non c'è sconto, mostra solo il prezzo originale
                                price_html += f'<span class="price-tag">{format_price(listing["original_price"])}</span>'
                            
                            price_html += '</div>'
                            st.markdown(price_html, unsafe_allow_html=True)
                            
                            # Dettagli in due colonne
                            detail_cols = st.columns(2)
                            
                            with detail_cols[0]:
                                if listing.get('mileage'):
                                    st.markdown(f"**Chilometraggio**: {listing['mileage']:,d} km")
                                if listing.get('registration'):
                                    st.markdown(f"**Immatricolazione**: {listing['registration']}")
                                if listing.get('transmission'):
                                    st.markdown(f"**Cambio**: {listing['transmission']}")
                            
                            with detail_cols[1]:
                                if listing.get('fuel'):
                                    st.markdown(f"**Alimentazione**: {listing['fuel']}")
                                if listing.get('power'):
                                    st.markdown(f"**Potenza**: {listing['power']}")
                                if listing.get('consumption'):
                                    st.markdown(f"**Consumi**: {listing['consumption']}")
                            
                            # Link all'annuncio
                            if listing.get('url'):
                                st.markdown(f"""
                                    <a href="{listing['url']}" target="_blank" 
                                       style="display: inline-block; 
                                              padding: 8px 16px; 
                                              background-color: #4CAF50; 
                                              color: white; 
                                              text-decoration: none; 
                                              border-radius: 4px; 
                                              margin-top: 10px;">
                                        Vedi Annuncio Completo
                                    </a>
                                """, unsafe_allow_html=True)
                        
                        st.markdown("</div>", unsafe_allow_html=True)
                    
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