import streamlit as st
import pandas as pd

from utils.formatting import format_price

def show_plate_editor(tracker, listings):
    """Mostra editor targhe in formato accordion"""
    if not listings:
        return
        
    df = pd.DataFrame(listings)
    
    with st.expander("✏️ Modifica Targhe", expanded=False):
        # Filtro rapido
        show_missing = st.checkbox("Mostra solo auto senza targa", value=False)
        if show_missing:
            df = df[df['plate'].isna()]
            
        if len(df) == 0:
            st.info("Nessuna auto da modificare")
            return
            
        st.write(f"**{len(df)} auto da gestire**")
        
        # Editor
        for idx, row in df.iterrows():
            container = st.container()
            with container:
                cols = st.columns([3, 2, 1])
                
                # Info auto
                with cols[0]:
                    st.write(f"**{row['title']}**")
                    if 'original_price' in row:
                        st.caption(f"Prezzo: {format_price(row['original_price'])}")
                
                # Input targa
                with cols[1]:
                    current_plate = row.get('plate', '')
                    new_plate = st.text_input(
                        "Targa",
                        value=current_plate,
                        key=f"plate_{row['id']}",
                        placeholder="Inserisci targa",
                        max_chars=7
                    ).upper()
                
                # Pulsante salva
                with cols[2]:
                    if new_plate != current_plate:
                        if st.button("💾", key=f"save_{row['id']}", help="Salva targa"):
                            try:
                                if tracker.update_plate(row['id'], new_plate):
                                    st.success("✅")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"❌ {str(e)}")
                                
                st.divider()