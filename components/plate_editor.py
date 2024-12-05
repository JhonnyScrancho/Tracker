# components/plate_editor.py

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
                # Input targa
                new_plate = st.text_input(
                    "Targa",
                    value=listing.get('plate', ''),
                    key=f"plate_{listing['id']}",
                    placeholder="Inserisci targa",
                    max_chars=7
                ).upper()
            
            with col3:
                # Pulsante salva
                if new_plate != listing.get('plate', ''):
                    if st.button("💾", key=f"save_{listing['id']}"):
                        if tracker.update_plate(listing['id'], new_plate):
                            st.success("✅")
                            st.rerun()
            
            st.divider()