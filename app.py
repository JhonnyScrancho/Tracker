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

# CSS migliorato con tema moderno e responsive
st.markdown("""
    <style>
        /* Layout e container generali */
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
            width: 100% !important;
            border-collapse: separate !important;
            border-spacing: 0 !important;
            border: none !important;
            margin: 1rem 0 !important;
            background: white !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
            border-radius: 8px !important;
            overflow: hidden !important;
        }
        
        .dataframe th {
            background-color: #f8f9fa !important;
            padding: 12px 15px !important;
            border: none !important;
            font-weight: 600 !important;
            color: #1f2937 !important;
            font-size: 0.9rem !important;
            text-align: left !important;
            white-space: nowrap !important;
        }
        
        .dataframe td {
            padding: 12px 15px !important;
            border: none !important;
            border-top: 1px solid #f0f0f0 !important;
            color: #4b5563 !important;
            font-size: 0.9rem !important;
            vertical-align: middle !important;
        }
        
        .dataframe tr:hover {
            background-color: #f9fafb !important;
        }
        
        /* Stili immagini e thumbnails */
        .thumbnail-container {
            position: relative;
            display: inline-block;
        }
        
        .thumbnail {
            width: 80px;
            height: 60px;
            object-fit: cover;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s ease-in-out;
            border: 2px solid transparent;
        }
        
        .thumbnail:hover {
            transform: scale(1.05);
            border-color: #3b82f6;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .image-count-badge {
            position: absolute;
            top: -6px;
            right: -6px;
            background-color: #3b82f6;
            color: white;
            border-radius: 9999px;
            padding: 2px 6px;
            font-size: 0.7rem;
            font-weight: 600;
        }
        
        .expanded-image-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.8);
            z-index: 1000;
            justify-content: center;
            align-items: center;
            cursor: pointer;
        }
        
        .expanded-image {
            max-width: 90%;
            max-height: 90vh;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        /* Stili ID annuncio */
        .listing-id {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            color: #6b7280;
            font-size: 0.85rem;
            padding: 4px 8px;
            background-color: #f3f4f6;
            border-radius: 4px;
            cursor: help;
            transition: background-color 0.2s ease;
        }
        
        .listing-id:hover {
            background-color: #e5e7eb;
            color: #4b5563;
        }
        
        /* Badge e indicatori */
        .price-badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.85rem;
        }
        
        .original-price {
            color: #059669;
            background-color: #ecfdf5;
        }
        
        .discounted-price {
            color: #dc2626;
            background-color: #fef2f2;
            text-decoration: line-through;
            margin-left: 8px;
        }
        
        .discount-percent {
            color: white;
            background-color: #dc2626;
            padding: 2px 6px;
            border-radius: 9999px;
            font-size: 0.75rem;
            margin-left: 6px;
        }
        
        /* Link e bottoni */
        .action-link {
            display: inline-flex;
            align-items: center;
            padding: 6px 12px;
            background-color: #3b82f6;
            color: white !important;
            text-decoration: none !important;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        
        .action-link:hover {
            background-color: #2563eb;
            transform: translateY(-1px);
        }
        
        .action-link svg {
            margin-right: 4px;
        }
        
        /* Stili car card */
        .car-card {
            background-color: white;
            border-radius: 10px;
            padding: 20px;
            margin: 10px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .car-details {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin: 10px 0;
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
        
        /* Stili responsive */
        @media (max-width: 768px) {
            .dataframe {
                display: block;
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
            }
            
            .thumbnail {
                width: 60px;
                height: 45px;
            }
            
            .car-details {
                grid-template-columns: 1fr;
            }
        }
    </style>
    
    <script>
        // Funzione per espandere l'immagine
        function expandImage(imgUrl) {
            const modal = document.createElement('div');
            modal.className = 'expanded-image-modal';
            modal.style.display = 'flex';
            
            const img = document.createElement('img');
            img.src = imgUrl;
            img.className = 'expanded-image';
            
            modal.onclick = () => document.body.removeChild(modal);
            modal.appendChild(img);
            document.body.appendChild(modal);
        }
        
        // Inizializzazione tooltips
        document.addEventListener('DOMContentLoaded', function() {
            const tooltips = document.querySelectorAll('[data-tooltip]');
            tooltips.forEach(element => {
                element.addEventListener('mouseover', e => {
                    const tooltip = document.createElement('div');
                    tooltip.className = 'tooltip';
                    tooltip.textContent = element.dataset.tooltip;
                    document.body.appendChild(tooltip);
                    
                    const rect = element.getBoundingClientRect();
                    tooltip.style.top = rect.bottom + 'px';
                    tooltip.style.left = rect.left + 'px';
                });
                
                element.addEventListener('mouseout', () => {
                    const tooltip = document.querySelector('.tooltip');
                    if (tooltip) tooltip.remove();
                });
            });
        });
    </script>
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
                    
                    # Formattazione prezzi con badge di stile
                    def format_price_with_style(row):
                        original = format_price(row['original_price'])
                        if pd.notna(row.get('discounted_price')):
                            discounted = format_price(row['discounted_price'])
                            discount = f"<span class='discount-percent'>-{row.get('discount_percentage', 0):.1f}%</span>"
                            return f"""
                                <span class='price-badge original-price'>{discounted}</span>
                                <span class='price-badge discounted-price'>{original}</span>
                                {discount}
                            """
                        return f"<span class='price-badge original-price'>{original}</span>"
                    
                    # Formattazione thumbnail con contatore immagini
                    def format_thumbnail(row):
                        if not row.get('image_urls'):
                            return "No image"
                        
                        img_count = len(row['image_urls'])
                        return f"""
                            <div class='thumbnail-container'>
                                <img src='{row['image_urls'][0]}' 
                                     class='thumbnail' 
                                     onclick='expandImage("{row['image_urls'][0]}")' 
                                     alt='Miniatura'>
                                <span class='image-count-badge'>{img_count}</span>
                            </div>
                        """
                    
                    # Formattazione ID con tooltip
                    def format_id(id_value):
                        return f"""
                            <span class='listing-id' 
                                  data-tooltip='ID Univoco Annuncio'>{id_value}</span>
                        """
                    
                    # Formattazione link con stile
                    def format_link(url):
                        return f"""
                            <a href='{url}' target='_blank' class='action-link'>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" 
                                     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                                    <polyline points="15 3 21 3 21 9"></polyline>
                                    <line x1="10" y1="14" x2="21" y2="3"></line>
                                </svg>
                                Vedi
                            </a>
                        """
                    
                    # Applicazione formattazioni
                    df['prezzo'] = df.apply(format_price_with_style, axis=1)
                    df['thumbnail'] = df.apply(format_thumbnail, axis=1)
                    df['listing_id'] = df['id'].apply(format_id)
                    df['link'] = df['url'].apply(format_link)
                    
                    # Formattazione chilometri
                    df['mileage'] = df['mileage'].apply(
                        lambda x: f"{x:,d} km".replace(",", ".") if pd.notna(x) else "N/D"
                    )
                    
                    # Selezione e rinomina colonne con nuovo ordine
                    display_columns = {
                        'thumbnail': 'Foto',
                        'listing_id': 'ID Annuncio',
                        'title': 'Modello',
                        'prezzo': 'Prezzo',
                        'mileage': 'Km',
                        'registration': 'Immatricolazione',
                        'fuel': 'Carburante',
                        'transmission': 'Cambio',
                        'link': 'Link'
                    }
                    
                    # Filtra solo le colonne disponibili
                    available_columns = [col for col in display_columns.keys() if col in df.columns]
                    display_df = df[available_columns].copy()
                    display_df.columns = [display_columns[col] for col in available_columns]
                    
                    # Visualizzazione tabella con elementi interattivi
                    st.write(
                        display_df.to_html(
                            escape=False, 
                            index=False,
                            classes=['display-table'],
                            table_id='listings-table'
                        ), 
                        unsafe_allow_html=True
                    )
                    
                    # Visualizzazione dettagliata stile cards
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
                                else:
                                    st.write("Nessuna immagine disponibile")
                            
                            with cols[1]:
                                st.markdown(f"### {listing['title']}")
                                st.markdown(f"**ID Annuncio:** `{listing['id']}`")
                                
                                # Visualizzazione prezzi migliorata
                                price_html = '<div class="price-section">'
                                if listing.get('has_discount') and listing.get('discounted_price'):
                                    price_html += f"""
                                        <span class="price-badge original-price">{format_price(listing['discounted_price'])}</span>
                                        <span class="price-badge discounted-price">{format_price(listing['original_price'])}</span>
                                        <span class="discount-percent">-{listing.get('discount_percentage', 0):.1f}%</span>
                                    """
                                else:
                                    price_html += f"""
                                        <span class="price-badge original-price">{format_price(listing['original_price'])}</span>
                                    """
                                price_html += '</div>'
                                st.markdown(price_html, unsafe_allow_html=True)
                                
                                # Dettagli in due colonne
                                detail_cols = st.columns(2)
                                
                                with detail_cols[0]:
                                    if listing.get('mileage'):
                                        st.markdown(f"**Chilometraggio**: {listing['mileage']:,d} km".replace(",", "."))
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
                                
                                # Link all'annuncio con stile migliorato
                                if listing.get('url'):
                                    st.markdown(f"""
                                        <a href="{listing['url']}" target="_blank" class="action-link">
                                            Vedi Annuncio Completo
                                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" 
                                                 stroke="currentColor" stroke-width="2" stroke-linecap="round" 
                                                 stroke-linejoin="round" style="margin-left: 4px;">
                                                <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                                                <polyline points="15 3 21 3 21 9"></polyline>
                                                <line x1="10" y1="14" x2="21" y2="3"></line>
                                            </svg>
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
                
                # Metriche principali con stile migliorato
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