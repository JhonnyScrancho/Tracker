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

        # Custom CSS per il container del log
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
            </style>
        """, unsafe_allow_html=True)

        for dealer in dealers:
            st.subheader(dealer['url'])
            if dealer.get('last_update'):
                st.caption(f"Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")

            col1, col2, col3 = st.columns([5,1,1])
            with col1:
                if st.button("🔄 Aggiorna", key=f"update_{dealer['id']}"):
                    with st.expander("📝 Log Aggiornamento", expanded=False):
                        progress_placeholder = st.empty()
                        try:
                            with st.spinner("⏳ Aggiornamento in corso..."):
                                listings = tracker.scrape_dealer(dealer['url'])
                                if listings:
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
                df = pd.DataFrame(listings)
                df['prezzo'] = df['original_price'].apply(format_price)
                df['prezzo_scontato'] = df['discounted_price'].apply(format_price)
                
                display_df = df[[
                    'title', 'prezzo', 'prezzo_scontato', 'mileage', 
                    'registration', 'fuel'
                ]].copy()
                
                display_df.columns = [
                    'Modello', 'Prezzo', 'Prezzo Scontato', 'Km',
                    'Immatricolazione', 'Carburante'
                ]
                
                st.dataframe(display_df, use_container_width=True)
                
                # Visualizzazione dettagliata annunci con immagini
                with st.expander("📸 Mostra Dettagli e Immagini", expanded=False):
                    cols = st.columns(3)
                    for idx, listing in enumerate(listings):
                        col = cols[idx % 3]
                        with col:
                            if listing.get('image_urls'):
                                st.image(
                                    listing['image_urls'][0],
                                    caption=listing['title'],
                                    use_column_width=True
                                )
                            
                            st.markdown(f"**Prezzo**: {format_price(listing['original_price'])}")
                            if listing.get('has_discount') and listing.get('discounted_price'):
                                st.markdown(f"**Prezzo Scontato**: {format_price(listing['discounted_price'])}")
                                discount = ((listing['original_price'] - listing['discounted_price']) / 
                                         listing['original_price'] * 100)
                                st.markdown(f"**Sconto**: {discount:.1f}%")
                            
                            if listing.get('mileage'):
                                st.markdown(f"**Km**: {listing['mileage']:,d}")
                            if listing.get('registration'):
                                st.markdown(f"**Immatricolazione**: {listing['registration']}")
                            if listing.get('fuel'):
                                st.markdown(f"**Alimentazione**: {listing['fuel']}")
                            if listing.get('power'):
                                st.markdown(f"**Potenza**: {listing['power']}")
                            
                            if listing.get('url'):
                                st.markdown(f"[Vedi Annuncio]({listing['url']})")
                            st.divider()
                    
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