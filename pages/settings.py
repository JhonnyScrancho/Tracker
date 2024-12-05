import streamlit as st
from services.tracker import AutoTracker

def show():
    st.title("⚙️ Impostazioni")
    
    tracker = AutoTracker()
    dealers = tracker.get_dealers()
    
    # Aggiungi concessionario
    st.header("➕ Aggiungi Concessionario")
    with st.form("add_dealer"):
        url = st.text_input(
            "URL Concessionario",
            placeholder="https://www.autoscout24.it/concessionari/esempio"
        )
        
        if st.form_submit_button("Aggiungi"):
            try:
                dealer_id = url.split('/')[-1]
                tracker.save_dealer(dealer_id, url)
                st.success("✅ Concessionario aggiunto")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Errore: {str(e)}")
                
    # Gestione concessionari esistenti
    if dealers:
        st.header("📋 Concessionari Attivi")
        for dealer in dealers:
            with st.expander(dealer['url']):
                st.write(f"ID: {dealer['id']}")
                if dealer.get('last_update'):
                    st.caption(f"Ultimo aggiornamento: {dealer['last_update'].strftime('%d/%m/%Y %H:%M')}")
                    
                col1, col2 = st.columns([3,1])
                with col2:
                    if st.button("❌ Rimuovi", key=f"remove_{dealer['id']}"):
                        confirm = st.checkbox("Conferma rimozione", key=f"confirm_{dealer['id']}")
                        if confirm:
                            tracker.remove_dealer(dealer['id'])
                            st.success("✅ Concessionario rimosso")
                            st.rerun()