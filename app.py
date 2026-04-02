import streamlit as st
import pandas as pd
import ezdxf
import io
import matplotlib.pyplot as plt
from modules.processor import ProcessorConfig, process_dxf_bytes

# Setări pagină - dezactivăm Wide Mode implicit pentru a strânge design-ul
st.set_page_config(page_title="AutoApartamentare Pro", layout="centered")

# --- CSS CUSTOM PENTRU DESIGN STRÂNS ---
st.markdown("""
    <style>
    /* Limităm lățimea conținutului */
    .block-container {
        max-width: 900px;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    /* Stil pentru butoane */
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #f63366;
        color: white;
        font-weight: bold;
    }
    /* Fundal pentru secțiuni */
    div[data-testid="stVerticalBlock"] > div:has(div.stTable) {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ AutoApartamentare - FAZA 5")
st.write("Instrument profesional pentru extras suprafețe cadastrale.")

# --- ZONA DE ÎNCĂRCARE ---
uploaded = st.file_uploader("Încarcă fișierul DXF", type=["dxf"])

if uploaded:
    # Încercăm să citim layerele pentru a popula selectorul
    try:
        raw_bytes = uploaded.getvalue()
        doc = ezdxf.read(io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8", errors="replace"))
        layers = sorted([l.dxf.name for l in doc.layers])
        default_layer = "CONTUR_APARTAMENT"
        idx = layers.index(default_layer) if default_layer in layers else 0
    except:
        layers = ["CONTUR_APARTAMENT"]
        idx = 0

    # --- INPUTURI COMPACTE (Pe același rând) ---
    col_sel1, col_sel2 = st.columns([2, 1]) # Proporție 2:1
    
    with col_sel1:
        sel_layer = st.selectbox("Layer Contur (Polilinii)", options=layers, index=idx)
    
    with col_sel2:
        unit_type = st.radio("Unități desen", ["Metri (m)", "Milimetri (mm)"], horizontal=True)
        unit_key = "m" if "Metri" in unit_type else "mm"

    st.write("") # Mic spațiu
    
    # Butonul de procesare într-o coloană mică centrală sau pe tot rândul (acum e mai strâns oricum)
    if st.button("🚀 PROCESEAZĂ ȘI CALCULEAZĂ"):
        cfg = ProcessorConfig(reference_layer=sel_layer, units=unit_key)
        results = process_dxf_bytes(raw_bytes, cfg)
        
        if results:
            st.divider()
            
            # --- REZULTATE TABEL ---
            all_dfs = [r.areas_df for r in results if not r.areas_df.empty]
            if all_dfs:
                final_df = pd.concat(all_dfs, ignore_index=True)
                st.subheader("📋 Detaliu pe Încăperi")
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 DESCARCĂ EXCEL", csv, "Raport_Detaliat.csv", "text/csv")
            
            st.write("")
            
            # --- REZUMAT ȘI PREVIZUALIZARE ---
            st.subheader("🏠 Centralizator Apartamente")
            col_res1, col_res2 = st.columns([1, 1])
            
            with col_res1:
                summary_data = []
                for r in results:
                    summary_data.append({
                        "Nr. Unitate": r.name,
                        "Utilă (mp)": r.net_area,
                        "Balcoane (mp)": r.balcony_area,
                        "Total (mp)": r.total_area
                    })
                st.table(summary_data)
                
            with col_res2:
                fig, ax = plt.subplots(figsize=(6, 6))
                for r in results:
                    x, y = r.polygon.exterior.xy
                    ax.plot(x, y, linewidth=2, color='#f63366')
                    ax.text(r.polygon.centroid.x, r.polygon.centroid.y, r.name, 
                            ha='center', fontsize=9, fontweight='bold', 
                            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=1))
                ax.set_aspect('equal')
                ax.set_axis_off()
                st.pyplot(fig)
else:
    st.info("Te rugăm să încarci un fișier DXF pentru a începe.")