import streamlit as st
import pandas as pd
import ezdxf
import io
import matplotlib.pyplot as plt
from modules.processor import ProcessorConfig, process_dxf_bytes, draw_all_layers_interactive

st.set_page_config(page_title="AutoApartamentare Pro", layout="centered")

st.markdown("""
    <style>
    .block-container { max-width: 1000px; padding-top: 2rem; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; background-color: #f63366; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ AutoApartamentare - FAZA 5.2")

uploaded = st.file_uploader("Încarcă fișierul DXF", type=["dxf"])

if uploaded:
    raw_bytes = uploaded.getvalue()
    col_input, col_preview = st.columns([1, 1.8])
    
    with col_input:
        st.subheader("⚙️ Configurare")
        try:
            text_stream = io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8", errors="replace")
            doc = ezdxf.read(text_stream)
            
            # FILTRARE STRICTĂ ȘI SORTARE ALFABETICĂ
            all_layers = [l.dxf.name for l in doc.layers]
            clean_layers = sorted([
                n for n in all_layers 
                if "HIDDEN" not in n.upper() and not n.startswith(("-", "*", "$"))
            ])
            
            if not clean_layers: clean_layers = sorted(all_layers)
            
            default_layer = "CONTUR_APARTAMENT"
            idx = clean_layers.index(default_layer) if default_layer in clean_layers else 0
            selected_layer = st.selectbox("Alege Layer Contur", options=clean_layers, index=idx)
            
        except:
            selected_layer = "CONTUR_APARTAMENT"

        unit_type = st.radio("Unități desen AutoCAD", ["Metri (m)", "Milimetri (mm)"], horizontal=True)
        unit_key = "m" if "Metri" in unit_type else "mm"
        do_process = st.button("🚀 PROCESEAZĂ")

    with col_preview:
        # Am scos titlul redundant de aici, rămâne doar cel din grafic
        fig_interact = draw_all_layers_interactive(raw_bytes)
        st.plotly_chart(fig_interact, use_container_width=True, config={'displayModeBar': True})

    if do_process:
        cfg = ProcessorConfig(reference_layer=selected_layer, units=unit_key)
        results = process_dxf_bytes(raw_bytes, cfg)
        
        if results:
            st.divider()
            all_dfs = [r.areas_df for r in results if not r.areas_df.empty]
            if all_dfs:
                final_df = pd.concat(all_dfs, ignore_index=True)
                st.subheader("📋 Detaliu pe Încăperi")
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 DESCARCĂ EXCEL", csv, "Raport.csv", "text/csv")
            
            st.divider()
            col_res1, col_res2 = st.columns([1, 1])
            with col_res1:
                st.subheader("🏠 Centralizator")
                summary = [{"Unitate": r.name, "S. Utilă": r.net_area, "S. Balc.": r.balcony_area, "Total": r.total_area} for r in results]
                st.table(summary)
            with col_res2:
                st.subheader("🖼️ Schiță")
                fig, ax = plt.subplots()
                for r in results:
                    x, y = r.polygon.exterior.xy
                    ax.plot(x, y, linewidth=2, color="#f63366")
                    ax.text(r.polygon.centroid.x, r.polygon.centroid.y, r.name, ha='center', fontsize=8, fontweight='bold')
                ax.set_aspect('equal'); ax.set_axis_off()
                st.pyplot(fig)