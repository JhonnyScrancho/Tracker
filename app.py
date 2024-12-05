import streamlit as st
from services.tracker import AutoTracker
from components import stats, plate_editor, filters, tables, sidebar
from utils.data import prepare_listings_dataframe, filter_listings
from utils.formatting import format_price

st.set_page_config(
    page_title="Tracker",
    page_icon="🚗",
    layout="wide"
)

# CSS esistente
st.markdown("""
    <style>
        .stExpander { width: 100% !important; }
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
        .element-container { width: 100% !important; }
        .stMarkdown { width: 100% !important; }
        
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
        
        .col-foto { width: 300px !important; padding: 5px !important; }
        .col-id { width: auto !important; font-family: monospace; font-size: 0.5em; }
        .col-targa { width: auto !important; text-align: center !important; }
        .col-modello { min-width: auto !important; }
        .col-prezzo { width: auto !important; text-align: right !important; }
        .col-km { width: auto !important; text-align: right !important; }
        .col-data { width: auto !important; text-align: center !important; }
        .col-carburante { width: auto !important; }
        .col-link { width: auto !important; text-align: center !important; }
        
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
    </style>
""", unsafe_allow_html=True)

# Inizializzazione
tracker = AutoTracker()

# Sidebar e selezione concessionario
selected_dealer = sidebar.show_sidebar(tracker)

# Main content
dealers = tracker.get_dealers()

if not dealers:
    st.title("👋 Benvenuto in Auto Tracker")
    st.info("Aggiungi un concessionario per iniziare")
    
elif selected_dealer:
    # Vista concessionario
    st.title(f"🏢 {selected_dealer['url'].split('/')[-1].upper()}")
    st.caption(selected_dealer['url'])
    
    # Header con stats
    stats.show_dealer_overview(tracker, selected_dealer['id'])
    
    # Aggiorna annunci
    if st.button("🔄 Aggiorna Annunci"):
        with st.status("⏳ Aggiornamento...", expanded=True) as status:
            try:
                listings = tracker.scrape_dealer(selected_dealer['url'])
                if listings:
                    for listing in listings:
                        listing['dealer_id'] = selected_dealer['id']
                    tracker.save_listings(listings)
                    tracker.mark_inactive_listings(selected_dealer['id'], [l['id'] for l in listings])
                    status.update(label="✅ Completato!", state="complete")
                    st.rerun()
                else:
                    status.update(label="⚠️ Nessun annuncio trovato", state="error")
            except Exception as e:
                status.update(label=f"❌ Errore: {str(e)}", state="error")
    
    # Filtri
    active_filters = filters.show_filters()
    
    # Lista annunci
    listings = tracker.get_active_listings(selected_dealer['id'])
    if listings:
        if active_filters:
            # Applica filtri
            filtered_listings = []
            for listing in listings:
                if active_filters.get('min_price') and listing.get('original_price', 0) < active_filters['min_price']:
                    continue
                if active_filters.get('max_price') and listing.get('original_price', 0) > active_filters['max_price']:
                    continue
                if active_filters.get('missing_plates_only') and listing.get('plate'):
                    continue
                if active_filters.get('only_discounted') and not listing.get('has_discount'):
                    continue
                filtered_listings.append(listing)
            listings = filtered_listings
        
        # Mostra tabella
        tables.show_listings_table(listings)
        
        # Editor targhe
        plate_editor.show_plate_editor(tracker, listings)
        
        # Grafici
        stats.show_dealer_insights(tracker, selected_dealer['id'])
    else:
        st.info("ℹ️ Nessun annuncio attivo")
        
else:
    # Dashboard
    st.title("📊 Dashboard")
    
    # Stats globali
    total_cars = 0
    total_value = 0
    missing_plates = 0
    
    for dealer in dealers:
        listings = tracker.get_active_listings(dealer['id'])
        total_cars += len(listings)
        total_value += sum(l.get('original_price', 0) for l in listings if l.get('original_price'))
        missing_plates += len([l for l in listings if not l.get('plate')])
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🏢 Concessionari", len(dealers))
    with col2:
        st.metric("🚗 Auto Totali", total_cars)
    with col3:
        st.metric("💰 Valore Totale", format_price(total_value))
    with col4:
        st.metric("🔍 Targhe Mancanti", missing_plates)
        
    # Lista concessionari nella dashboard
    st.subheader("🏢 Concessionari Monitorati")
    for dealer in dealers:
        with st.expander(f"**{dealer['url'].split('/')[-1].upper()}** - {dealer['url']}", expanded=False):
            if dealer.get('last_update'):
                st.caption(f"Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")
            
            dealer_listings = tracker.get_active_listings(dealer['id'])
            if dealer_listings:
                stats.show_dealer_overview(tracker, dealer['id'])
            else:
                st.info("ℹ️ Nessun annuncio attivo")

if __name__ == "__main__":
    # Modern way to clear Streamlit cache
    st.cache_data.clear()
    st.cache_resource.clear()