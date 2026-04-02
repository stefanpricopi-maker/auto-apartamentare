import streamlit as st
import pandas as pd
import ezdxf
import io
import matplotlib.pyplot as plt
from modules.processor import ProcessorConfig, process_dxf_bytes

# Forțăm layout-ul pe centru pentru un aspect profesional
st.set_page_config(page_title="AutoApartamentare Pro", layout="centered")

# --- CSS PENTRU DESIGN ȘI CURĂȚENIE ---
st.markdown("""
    <style>
    .block-container {
        max-width: 900px;
        padding-top: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #f63366;
        color: white;
        font-weight: bold;
        border: none;
    }
    .stButton>button:hover {
        background-color: #ff4b7d;
        border: none;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ AutoApartamentare - FAZA 5.1")
st.write("Instrument de extras suprafețe. Design compact și filtrare layere.")

uploaded = st.file_uploader("Încarcă fișierul DXF", type=["dxf"])

if uploaded:
    try:
        raw_bytes = uploaded.getvalue()
        text_stream = io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8", errors="replace")
        doc = ezdxf.read(text_stream)
        
        # --- FILTRARE ȘI ORDONARE LAYERE ---
        # Luăm toate layerele, dar le filtrăm pe cele de sistem/ascunse
        all_layers = [l.dxf.name for l in doc.layers]
        
        clean_layers = [
            name for name in all_layers 
            if "HIDDEN" not in name.upper() 
            and not name.startswith(("-", "*", "$"))
            and len(name.strip()) > 0
        ]
        
        # Sortare alfabetică (A-Z)
        layers = sorted(clean_layers)
        
        # Dacă lista e goală după filtrare (puțin probabil), punem totuși lista completă
        if not layers:
            layers = sorted(all_layers)

        default_layer = "CONTUR_APARTAMENT"
        idx = layers.index(default_layer) if default_layer in layers else 0
    except Exception as e:
        st.error(f"Eroare la citirea layerelor: {e}")
        layers = ["CONTUR_APARTAMENT"]
        idx = 0

    # --- INTERFAȚA COMPACTĂ ---
    col_sel1, col_sel2 = st.columns([2, 1])
    
    with col_sel1:
        selected_layer = st.selectbox("Layer Contur (Polilinii)", options=layers, index=idx)
    
    with col_sel2:
        unit_type = st.radio("Unități desen", ["Metri (m)", "Milimetri (mm)"], horizontal=True)
        unit_key = "m" if "Metri" in unit_type else "mm"

    st.write("") 
    
    if st.button("🚀 PROCESEAZĂ ȘI CALCULEAZĂ"):
        cfg = ProcessorConfig(reference_layer=selected_layer, units=unit_key)
        try:
            results = process_dxf_bytes(raw_bytes, cfg)
            
            if results:
                st.divider()
                
                # 1. TABEL DETALIAT
                all_dfs = [r.areas_df for r in results if not r.areas_df.empty]
                if all_dfs:
                    final_df = pd.concat(all_dfs, ignore_index=True)
                    st.subheader("📋 Detaliu pe Încăperi")
                    st.dataframe(final_df, use_container_width=True, hide_index=True)
                    
                    csv = final_df.to_csv(index=False).encode('utf-8-sig')
                    st.download_button("📥 DESCARCĂ EXCEL", csv, "Raport_Detaliat.csv", "text/csv")
                
                st.write("")
                
                # 2. CENTRALIZATOR + FIGURĂ (Pe două coloane)
                st.subheader("🏠 Rezumat Unități")
                col_res1, col_res2 = st.columns([1, 1])
                
                with col_res1:
                    summary_data = []
                    for r in results:
                        summary_data.append({
                            "Nr. Unitate": r.name,
                            "S. Utilă (mp)": r.net_area,
                            "S. Balcoane (mp)": r.balcony_area,
                            "Total (mp)": r.total_area
                        })
                    st.table(summary_data)
                    
                with col_res2:
                    fig, ax = plt.subplots(figsize=(6, 6))
                    # Folosim o culoare mai plăcută pentru contururi
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
                st.warning(f"Nu am găsit poligoane pe layer-ul '{selected_layer}'.")
                
        except Exception as e:
            st.error(f"Eroare critică: {e}")
else:
    st.info("Încarcă un fișier DXF pentru a începe.")