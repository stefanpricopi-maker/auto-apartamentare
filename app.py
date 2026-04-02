import streamlit as st
import pandas as pd
import ezdxf
import io
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from modules.processor import ProcessorConfig, process_dxf_bytes, draw_all_layers_interactive

st.set_page_config(page_title="AutoApartamentare Pro", layout="centered")

# CSS custom pentru un aspect profesional
st.markdown("""
    <style>
    .block-container {
        max-width: 900px;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #f63366;
        color: white;
        font-weight: bold;
    }
    .stMarkdown { line-height: 1.2; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ AutoApartamentare - FAZA 5.1")
st.caption("Detecție Balcoane + Raport de Cadastru. Organizare Split Layout.")

uploaded = st.file_uploader("Încarcă fișierul DXF", type=["dxf"])

if uploaded:
    # --- SPLIT LAYOUT ZONA CFG/PREVIEW ---
    col_input, col_preview = st.columns([1, 1.5]) # Zona de control mai strânsă
    
    raw_bytes = uploaded.getvalue()

    with col_input:
        st.subheader("⚙️ Configurare")
        try:
            text_stream = io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8", errors="replace")
            doc = ezdxf.read(text_stream)
            layers = sorted([layer.dxf.name for layer in doc.layers])
            idx = layers.index("CONTUR_APARTAMENT") if "CONTUR_APARTAMENT" in layers else 0
            selected_layer = st.selectbox("Alege Layer Contur", options=layers, index=idx)
            
        except Exception as e:
            st.error(f"Eroare citire layere: {e}")
            selected_layer = "CONTUR_APARTAMENT"

        unit_type = st.radio("Unități desen AutoCAD", ["Metri (m)", "Milimetri (mm)"], horizontal=False)
        unit_key = "m" if "Metri" in unit_type else "mm"

        st.write("")
        do_process = st.button("🚀 PROCESEAZĂ")

    # DREAPTA: Previzualizarea completă și interactivă (Plotly)
    with col_preview:
        st.write("🛠️ Previzualizare Straturi Complete (Interactivă)")
        fig_interact = draw_all_layers_interactive(raw_bytes)
        st.plotly_chart(fig_interact, use_container_width=True)

    if do_process:
        cfg = ProcessorConfig(reference_layer=selected_layer, units=unit_key)
        results = process_dxf_bytes(raw_bytes, cfg)
        
        if results:
            st.divider()

            # ZONA REZULTATE (Tabel lung, urmat de previzualizare geometrie/centralizator jos)
            all_dfs = [r.areas_df for r in results if not r.areas_df.empty]
            if all_dfs:
                final_df = pd.concat(all_dfs, ignore_index=True)
                st.subheader("📋 Detaliu pe Încăperi (PENTRU EXCEL)")
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 DESCARCĂ EXCEL DETALIAT", csv, "Raport_Detaliat.csv", "text/csv")
            
            st.divider()

            col_res1, col_res2 = st.columns([6, 4])
            
            with col_res1:
                st.subheader("🏠 Centralizator (RAPORT CADASTRU)")
                summary_data = []
                for r in results:
                    summary_data.append({"Nr. Unitate": r.name, "S. Utilă": r.net_area, 
                                          "S. Balcoane": r.balcony_area, "S. Totală": r.total_area,
                                          "S. Geometrie": f"{r.area_calc:.2f}"})
                st.table(summary_data)
                
            with col_res2:
                st.subheader("🖼️ Geometrie Apartamente (Shapely)")
                fig_geo, ax = plt.subplots(figsize=(6, 6))
                for r in results:
                    x, y = r.polygon.exterior.xy
                    ax.plot(x, y, linewidth=2)
                    ax.text(r.polygon.centroid.x, r.polygon.centroid.y, r.name, ha='center', fontsize=8, fontweight='bold', bbox=dict(facecolor='white', alpha=0.5))
                ax.set_aspect('equal')
                ax.set_axis_off()
                st.pyplot(fig_geo)