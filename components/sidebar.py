import streamlit as st
from services.tracker import AutoTracker

def show_sidebar(tracker):
    """Gestisce la sidebar dell'applicazione"""
    st.sidebar.title("🚗 Auto Tracker")
    
    # Recupera concessionari
    dealers = tracker.get_dealers()
    selected_dealer = None
    
    # Lista concessionari
    if dealers:
        st.sidebar.subheader("🏢 Concessionari")
        for dealer in dealers:
            dealer_name = dealer['url'].split('/')[-1].upper()
            if st.sidebar.button(
                f"🏢 {dealer_name}",
                key=f"nav_{dealer['id']}",
                use_container_width=True
            ):
                selected_dealer = dealer
                
            # Mostra ultima data aggiornamento
            if dealer.get('last_update'):
                st.sidebar.caption(
                    f"Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}"
                )
    
    # Form aggiunta concessionario
    st.sidebar.divider()
    with st.sidebar.expander("➕ Nuovo Concessionario"):
        with st.form("add_dealer_form"):
            new_url = st.text_input(
                "URL Concessionario",
                placeholder="https://www.autoscout24.it/concessionari/esempio"
            )
            
            if st.form_submit_button("Aggiungi", use_container_width=True):
                try:
                    dealer_id = new_url.split('/')[-1]
                    if not dealer_id:
                        st.error("❌ URL non valido")
                    else:
                        tracker.save_dealer(dealer_id, new_url)
                        st.success("✅ Concessionario aggiunto")
                        st.rerun()
                        
                except Exception as e:
                    st.error(f"❌ Errore: {str(e)}")
                
    return selected_dealer