import streamlit as st
from datetime import datetime

def show_plate_editor(tracker, listings):
    """Mostra editor targhe in formato accordion"""
    if not listings:
        return
        
    with st.expander("✏️ Modifica Targhe", expanded=False):
        # Filtro
        show_missing = st.checkbox("Mostra solo auto senza targa")
        
        # Lista auto da modificare
        for listing in listings:
            if show_missing and listing.get('plate'):
                continue
                
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                # Info auto
                st.write(f"**{listing.get('title', 'N/D')}**")
                if listing.get('original_price'):
                    st.caption(f"€{listing['original_price']:,.0f}".replace(",", "."))
            
            with col2:
                # Input targa con gestione null
                current_plate = listing.get('plate', '')
                new_plate = st.text_input(
                    "Targa",
                    value=current_plate if current_plate is not None else '',
                    key=f"plate_{listing['id']}",
                    placeholder="Inserisci targa",
                    max_chars=7
                )
                # Applica upper() solo se c'è un valore
                new_plate = new_plate.upper() if new_plate else ''
            
            with col3:
                # Pulsante salva
                if new_plate != current_plate:
                    if st.button("💾", key=f"save_{listing['id']}"):
                        if tracker.update_plate(listing['id'], new_plate):
                            st.success("✅")
                            st.rerun()
            
            st.divider()