import streamlit as st
from tracker import AutoTracker
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

st.set_page_config(
    page_title="AutoScout24 Tracker",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded"
)

def format_price(price):
    if pd.isna(price) or price is None:
        return "N/D"
    return f"€{price:,.0f}".replace(",", ".")

def main():
    st.title("🚗 AutoScout24 Dealer Tracker")
    
    # Inizializza il tracker
    tracker = AutoTracker()
    
    # Input URL concessionario
    dealer_url = st.text_input(
        "URL Concessionario AutoScout24",
        placeholder="https://www.autoscout24.it/concessionari/esempio"
    )
    
    if dealer_url:
        # Tabs per diverse funzionalità
        tab1, tab2 = st.tabs(["📊 Monitoraggio", "📈 Statistiche"])
        
        with tab1:
            if st.button("🔄 Analizza Annunci", type="primary"):
                with st.spinner("⏳ Analisi in corso..."):
                    # Scraping annunci
                    listings = tracker.scrape_dealer(dealer_url)
                    
                    if listings:
                        # Salva annunci
                        tracker.save_listings(listings)
                        
                        # Marca inattivi quelli non più presenti
                        active_ids = [l['id'] for l in listings]
                        dealer_id = dealer_url.split('/')[-1]
                        tracker.mark_inactive_listings(dealer_id, active_ids)
                        
                        # Mostra risultati
                        st.success(f"✅ Trovati {len(listings)} annunci")
                        
                        # Crea DataFrame
                        df = pd.DataFrame(listings)
                        
                        # Formatta prezzi
                        df['prezzo_originale'] = df['original_price'].apply(format_price)
                        df['prezzo_scontato'] = df['discounted_price'].apply(format_price)
                        
                        # Seleziona e rinomina colonne per visualizzazione
                        display_df = df[[
                            'title', 'version', 'prezzo_originale', 'prezzo_scontato',
                            'has_discount', 'mileage', 'registration', 'fuel', 'power'
                        ]].copy()
                        
                        display_df.columns = [
                            'Modello', 'Versione', 'Prezzo Originale', 'Prezzo Scontato',
                            'In Offerta', 'Km', 'Immatricolazione', 'Carburante', 'Potenza'
                        ]
                        
                        # Mostra tabella con stile
                        st.dataframe(
                            display_df,
                            use_container_width=True,
                            column_config={
                                "In Offerta": st.column_config.BooleanColumn(
                                    "🏷️ In Offerta",
                                    help="Indica se l'auto è in offerta"
                                ),
                                "Km": st.column_config.NumberColumn(
                                    "📏 Km",
                                    help="Chilometraggio",
                                    format="%d"
                                )
                            }
                        )
                        
                        # Dettagli annunci con immagini
                        st.subheader("🖼️ Dettaglio Annunci")
                        cols = st.columns(3)
                        for idx, listing in enumerate(listings):
                            col = cols[idx % 3]
                            with col:
                                st.image(
                                    listing['image_urls'][0] if listing['image_urls'] else "https://via.placeholder.com/300x200",
                                    caption=listing['title'],
                                    use_column_width=True
                                )
                                st.markdown(f"**Prezzo**: {format_price(listing['original_price'])}")
                                if listing['has_discount']:
                                    st.markdown(f"**Prezzo Scontato**: {format_price(listing['discounted_price'])}")
                                st.markdown(f"**Km**: {listing['mileage']:,d}" if listing['mileage'] else "**Km**: N/D")
                                if listing['url']:
                                    st.markdown(f"[Vedi Annuncio]({listing['url']})")
                                st.divider()
                    else:
                        st.warning("⚠️ Nessun annuncio trovato")
        
        with tab2:
            dealer_id = dealer_url.split('/')[-1]
            stats = tracker.get_dealer_stats(dealer_id)
            
            # Metriche principali
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🚗 Annunci Attivi", stats['total_active'])
            with col2:
                st.metric("🔄 Targhe Riapparse", stats['reappeared_plates'])
            with col3:
                st.metric("⏱️ Durata Media Annunci", f"{stats['avg_listing_duration']:.1f} giorni")
            with col4:
                if stats['total_discount_count'] > 0:
                    st.metric("💰 Sconto Medio", f"{stats['avg_discount_percentage']:.1f}%")
                else:
                    st.metric("💰 Sconto Medio", "N/D")

            # Statistiche sugli sconti
            if stats['total_discount_count'] > 0:
                st.subheader("📊 Analisi Sconti")
                st.write(f"- Auto in offerta: {stats['total_discount_count']}")
                st.write(f"- Percentuale auto scontate: {(stats['total_discount_count']/stats['total_active']*100):.1f}%")
                st.write(f"- Sconto medio: {stats['avg_discount_percentage']:.1f}%")

if __name__ == "__main__":
    main()