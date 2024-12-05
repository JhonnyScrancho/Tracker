import streamlit as st
from typing import Dict

def show_filters() -> Dict:
    """Mostra e gestisce filtri di ricerca"""
    filters = {}
    
    with st.expander("🔍 Filtri", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            filters['min_price'] = st.number_input(
                "Prezzo Minimo",
                min_value=0,
                step=1000,
                value=0
            )
            
        with col2:
            filters['max_price'] = st.number_input(
                "Prezzo Massimo",
                min_value=0,
                step=1000,
                value=0
            )
            
        filters['missing_plates_only'] = st.checkbox(
            "Solo auto senza targa",
            value=False
        )
        
        filters['only_discounted'] = st.checkbox(
            "Solo auto in sconto",
            value=False
        )
        
    return filters