import streamlit as st
import pandas as pd
import ezdxf
import io
import matplotlib.pyplot as plt
from modules.processor import ProcessorConfig, process_dxf_bytes

st.set_page_config(page_title="AutoApartamentare Pro", layout="wide")

st.title("🏙️ AutoApartamentare - FAZA 5")
st.caption("Detecție Balcoane + Raport de Cadastru")

uploaded = st.file_uploader("Încarcă fișierul DXF", type=["dxf"])

if uploaded:
    col_cfg1, col_cfg2 = st.columns(2)
    
    with col_cfg1:
        try:
            raw_bytes = uploaded.getvalue()
            doc = ezdxf.read(io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8", errors="replace"))
            layers = sorted([l.dxf.name for l in doc.layers])
            sel_layer = st.selectbox("Layer Contur", layers, index=layers.index("CONTUR_APARTAMENT") if "CONTUR_APARTAMENT" in layers else 0)
        except:
            sel_layer = "CONTUR_APARTAMENT"
            
    with col_cfg2:
        unit_type = st.radio("Unități desen", ["Metri (m)", "Milimetri (mm)"], horizontal=True)
        unit_key = "m" if "Metri" in unit_type else "mm"

    if st.button("🚀 PROCESEAZĂ ȘI CALCULEAZĂ"):
        cfg = ProcessorConfig(reference_layer=sel_layer, units=unit_key)
        results = process_dxf_bytes(raw_bytes, cfg)
        
        if results:
            # 1. TABELUL DETALIAT (PENTRU EXCEL)
            all_dfs = [r.areas_df for r in results if not r.areas_df.empty]
            if all_dfs:
                final_df = pd.concat(all_dfs, ignore_index=True)
                st.subheader("📋 Detaliu pe Încăperi")
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 DESCARCĂ EXCEL DETALIAT", csv, "Raport_Detaliat.csv", "text/csv")
            
            st.divider()

            # 2. CENTRALIZATOR (RAPORTUL DE CADASTRU)
            col1, col2 = st.columns([6, 4])
            
            with col1:
                st.subheader("🏠 Centralizator Apartamente")
                summary_data = []
                for r in results:
                    summary_data.append({
                        "Nr. Unitate": r.name,
                        "S. Utilă (mp)": r.net_area,
                        "S. Balcoane (mp)": r.balcony_area,
                        "S. Totală (mp)": r.total_area,
                        "S. Geometrie (mp)": f"{r.area_calc:.2f}"
                    })
                st.table(summary_data)
                
            with col2:
                st.subheader("🖼️ Identificare Plan")
                fig, ax = plt.subplots(figsize=(8, 8))
                for r in results:
                    x, y = r.polygon.exterior.xy
                    ax.plot(x, y, linewidth=2)
                    ax.text(r.polygon.centroid.x, r.polygon.centroid.y, r.name, ha='center', fontsize=8, fontweight='bold', bbox=dict(facecolor='white', alpha=0.5))
                ax.set_aspect('equal')
                ax.set_axis_off()
                st.pyplot(fig)