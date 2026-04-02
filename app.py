import streamlit as st
import pandas as pd
import io
import matplotlib.pyplot as plt
from modules.processor import ProcessorConfig, process_dxf_bytes, draw_all_layers_interactive

st.set_page_config(page_title="AutoApartamentare Pro", layout="centered")

st.title("🏙️ Relevee Apartamente - Decupare Automată")

uploaded = st.file_uploader("Încarcă DXF", type=["dxf"])

if uploaded:
    raw_bytes = uploaded.getvalue()
    
    col_config, col_prev = st.columns([1, 2])
    
    with col_config:
        st.subheader("⚙️ Setări")
        # Identificare Layere (Simplificată pentru viteză)
        selected_layer = st.text_input("Nume Layer Contur (ex: Contur apartament)", value="Contur apartament")
        unit_key = "m" if st.checkbox("Unități în Metri", value=True) else "mm"
        process_btn = st.button("🚀 GENEREAZĂ RELEVEE")

    with col_prev:
        st.plotly_chart(draw_all_layers_interactive(raw_bytes), use_container_width=True)

    if process_btn:
        results = process_dxf_bytes(raw_bytes, ProcessorConfig(selected_layer, unit_key))
        
        if results:
            for res in results:
                st.divider()
                st.subheader(f"🏠 Releveu: {res.name}")
                
                col_data, col_img = st.columns([1, 2])
                
                with col_data:
                    st.write("**Suprafețe identificate:**")
                    st.dataframe(res.areas_df, hide_index=True)
                
                with col_img:
                    # Desenăm RELEVEUL DECAPAT
                    fig, ax = plt.subplots(figsize=(8, 8))
                    
                    # 1. Desenăm toate liniile interioare (pereții din interiorul apartamentului)
                    for line_coords in res.internal_geometries:
                        x, y = zip(*line_coords)
                        ax.plot(x, y, color="#444444", linewidth=0.7)
                    
                    # 2. Desenăm conturul principal (mai gros)
                    cx, cy = res.polygon.exterior.xy
                    ax.plot(cx, cy, color="black", linewidth=1.5)
                    
                    # 3. Punem textele (camere, suprafețe)
                    for lbl in res.all_room_labels:
                        ax.text(lbl.point.x, lbl.point.y, lbl.text, 
                                fontsize=7, ha='center', va='center',
                                bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=0.1))
                    
                    ax.set_aspect('equal')
                    ax.axis('off')
                    st.pyplot(fig)
        else:
            st.error("Nu am găsit poligoane pe layer-ul specificat!")