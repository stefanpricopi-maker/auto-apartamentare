import streamlit as st
import pandas as pd
import ezdxf
import io
import matplotlib.pyplot as plt
from modules.processor import ProcessorConfig, process_dxf_bytes, draw_all_layers_interactive

# 1. CONFIGURARE PAGINĂ
st.set_page_config(
    page_title="AutoApartamentare Pro", 
    layout="centered", 
    page_icon="🏙️"
)

# Design CSS
st.markdown("""
    <style>
    .block-container { max-width: 1100px; padding-top: 1.5rem; }
    .stButton>button { 
        width: 100%; 
        border-radius: 8px; 
        height: 3.5em; 
        background-color: #2b2b2b; 
        color: white; 
        font-weight: bold; 
        border: none; 
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ AutoApartamentare - Versiunea Profesională")
st.caption("Planuri curățate pentru cadastru: Linii gri subțiri și text negru clar.")

# 2. ÎNCĂRCARE FIȘIER
uploaded = st.file_uploader("Încarcă fișierul DXF", type=["dxf"])

if uploaded:
    raw_bytes = uploaded.getvalue()
    col_input, col_preview = st.columns([1, 2])
    
    with col_input:
        st.subheader("⚙️ Configurare")
        show_all = st.checkbox("Arată toate layerele", value=False)
        custom_ignore = st.text_input("Ignoră layere (ex: AXE, MOBILA):", value="AXE, MOBILA, COTE, TEXT")
        
        ignore_list = [x.strip().upper() for x in custom_ignore.split(",") if x.strip()]
        base_ignore = ["HIDDEN", "PEN_NO", "EVACUARE", "GOLURI", "PLANSEE", "INTERACSI"]
        final_ignore = base_ignore + ignore_list

        try:
            text_stream = io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8", errors="replace")
            doc = ezdxf.read(text_stream)
            msp = doc.modelspace()
            all_layers = [l.dxf.name for l in doc.layers]
            
            # Identificăm layerele cu polilinii (🏠)
            useful_layers = {lname for lname in all_layers if msp.query(f'LWPOLYLINE[layer=="{lname}"]')}

            processed_options = []
            for n in all_layers:
                is_useful = n in useful_layers
                if show_all:
                    processed_options.append((n, f"🏠 {n}" if is_useful else n))
                else:
                    should_hide = any(k in n.upper() for k in final_ignore) or n.startswith(("*", "$"))
                    if is_useful or not should_hide:
                        processed_options.append((n, f"🏠 {n}" if is_useful else n))
            
            processed_options.sort(key=lambda x: x[0].upper())
            opt_map = {label: name for name, label in processed_options}
            
            # Selectare automată layer probabil ("Contur apartament" sau similar)
            default_idx = 0
            for i, (name, label) in enumerate(processed_options):
                if "CONTUR" in name.upper() or "ZONE" in name.upper():
                    default_idx = i
                    break

            selected_label = st.selectbox("Alege Layer Contur", options=list(opt_map.keys()), index=default_idx)
            selected_layer = opt_map[selected_label]
            
        except:
            selected_layer = "0"

        unit_type = st.radio("Unități desen AutoCAD", ["Metri (m)", "Milimetri (mm)"], horizontal=True)
        unit_key = "m" if "Metri" in unit_type else "mm"
        
        st.write("---")
        do_process = st.button("🚀 GENEREAZĂ PLAN CURĂȚAT")

    with col_preview:
        fig_interact = draw_all_layers_interactive(raw_bytes)
        st.plotly_chart(fig_interact, use_container_width=True)

    # 3. PROCESARE
    if do_process:
        cfg = ProcessorConfig(reference_layer=selected_layer, units=unit_key)
        results = process_dxf_bytes(raw_bytes, cfg)
        
        if results:
            st.divider()
            
            # TABEL REZULTATE
            all_dfs = [r.areas_df for r in results if not r.areas_df.empty]
            if all_dfs:
                st.subheader("📋 Tabel Rezultate")
                final_df = pd.concat(all_dfs, ignore_index=True)
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 DESCARCĂ RAPORT", csv, "Raport.csv", "text/csv")
            
            st.divider()
            
            col_res1, col_res2 = st.columns([1, 1.3])
            
            with col_res1:
                st.subheader("🏠 Centralizator")
                summary = [{"Unitate": r.name, "Total": r.total_area, "Utilă": r.net_area} for r in results]
                st.table(summary)
                
            with col_res2:
                st.subheader("🖼️ Schiță Finală (Curățată)")
                fig_final, ax = plt.subplots(figsize=(10, 10))
                
                for r in results:
                    # Linii gri subțiri (Originale)
                    x, y = r.polygon.exterior.xy
                    ax.plot(x, y, linewidth=0.8, color="#555555", zorder=1)
                    
                    # Textele interioare găsite în acest contur
                    for lbl in r.all_room_labels:
                        ax.text(
                            lbl.point.x, lbl.point.y, lbl.text, 
                            ha='center', va='center', 
                            fontsize=8, color="black", 
                            fontweight='bold' if not lbl.is_area else 'normal',
                            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=0.1),
                            zorder=2
                        )
                
                ax.set_aspect('equal')
                ax.set_axis_off()
                st.pyplot(fig_final)
        else:
            st.warning(f"Nu s-au găsit date pe layer-ul '{selected_layer}'.")
else:
    st.info("Încarcă un fișier DXF pentru a începe.")