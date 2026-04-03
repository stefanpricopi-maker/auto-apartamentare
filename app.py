import streamlit as st
import pandas as pd
import io
import matplotlib.pyplot as plt
from modules.processor import ProcessorConfig, process_dxf_bytes, draw_all_layers_interactive

# 1. CONFIGURARE PAGINA
st.set_page_config(
    page_title="AutoApartamentare Pro", 
    layout="wide"
)

# Design CSS simplificat
st.markdown("""
    <style>
    .stButton>button { 
        width: 100%; 
        border-radius: 8px; 
        height: 3.5em; 
        background-color: #f63366; 
        color: white; 
        font-weight: bold; 
        border: none; 
    }
    </style>
    """, unsafe_allow_html=True)

st.title("AutoApartamentare - Versiunea Profesionala")
st.caption("Planuri Relevee Curatate Automat pentru Cadastru.")

# 2. BARA LATERALA
with st.sidebar:
    st.header("Incarcare Fisier")
    uploaded = st.file_uploader("Incarca DXF", type=["dxf"])
    
    st.divider()
    st.header("Configurare")
    reference_layer = st.text_input("Nume Layer Contur:", value="Contur apartament")
    
    unit_type = st.radio("Unitati desen AutoCAD", ["Metri", "Milimetri"], horizontal=True, index=1)
    unit_key = "m" if "Metri" in unit_type else "mm"
    
    st.write("---")
    do_process = st.button("GENEREAZA RELEVEE COMPLET")

# 3. ZONA PRINCIPALA
if uploaded:
    raw_bytes = uploaded.getvalue()
    st.subheader("Previzualizare Plan General")
    
    fig_interact = draw_all_layers_interactive(raw_bytes)
    st.plotly_chart(fig_interact, use_container_width=True)

    # 4. PROCESARE
    if do_process:
        with st.spinner("Procesare..."):
            cfg = ProcessorConfig(reference_layer=reference_layer, units=unit_key)
            results = process_dxf_bytes(raw_bytes, cfg)
        
        if results:
            st.divider()
            st.subheader("Centralizator Suprafete")
            all_dfs = [r.areas_df for r in results if not r.areas_df.empty]
            if all_dfs:
                final_df = pd.concat(all_dfs, ignore_index=True)
                st.dataframe(final_df, use_container_width=True, hide_index=True)
            
            st.divider()
            st.subheader("Rezultat Final: Relevee Curatate")
            
            fig_final, ax = plt.subplots(figsize=(12, 12))
            for r in results:
                for line_coords in r.geometries:
                    x, y = zip(*line_coords)
                    ax.plot(x, y, linewidth=0.7, color="#555555", alpha=0.9)
                cx, cy = r.polygon.exterior.xy
                ax.plot(cx, cy, linewidth=1.5, color="black")
                for lbl in r.all_room_labels:
                    ax.text(lbl.point.x, lbl.point.y, lbl.text, 
                            ha='center', va='center', fontsize=8, color="black", 
                            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=0.1))
            
            ax.set_aspect('equal')
            ax.axis('off')
            st.pyplot(fig_final)
else:
    st.info("Incarca un fisier DXF pentru a incepe.")