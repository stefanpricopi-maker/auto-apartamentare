import streamlit as st
import pandas as pd
import ezdxf
import io
import matplotlib.pyplot as plt
from modules.processor import ProcessorConfig, process_dxf_bytes, draw_all_layers_interactive

st.set_page_config(page_title="AutoApartamentare Pro", layout="centered")

st.markdown("""
    <style>
    .block-container { max-width: 1050px; padding-top: 1.5rem; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3.5em; background-color: #f63366; color: white; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ AutoApartamentare - FAZA 5.3")

uploaded = st.file_uploader("Încarcă fișierul DXF", type=["dxf"])

if uploaded:
    raw_bytes = uploaded.getvalue()
    col_input, col_preview = st.columns([1, 2])
    
    with col_input:
        st.subheader("⚙️ Configurare")
        
        # Opțiune de a vedea totul în caz că filtrul e prea agresiv
        show_all = st.checkbox("Arată absolut toate layerele (fără filtru)", value=False)
        
        custom_ignore = st.text_input("Ignoră layere care conțin:", value="AXE, MOBILA, TEXT")
        ignore_list = [x.strip().upper() for x in custom_ignore.split(",") if x.strip()]
        base_ignore = ["HIDDEN", "PEN_NO", "EVACUARE", "GOLURI", "PLANSEE", "INTERACSI"]
        final_ignore = base_ignore + ignore_list

        try:
            text_stream = io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8", errors="replace")
            doc = ezdxf.read(text_stream)
            msp = doc.modelspace()
            
            all_layers = [l.dxf.name for l in doc.layers]
            
            # Identificăm layerele cu poligoane (🏠)
            useful_layers = set()
            for lname in all_layers:
                if msp.query(f'LWPOLYLINE[layer=="{lname}"]'):
                    useful_layers.add(lname)

            processed_options = []
            for n in all_layers:
                # LOGICĂ NOUĂ: Dacă are poligoane (🏠), îl arătăm MEREU. 
                # Altfel, aplicăm filtrele de nume.
                is_useful = n in useful_layers
                
                if show_all:
                    # Dacă bifăm "Arată tot", nu mai filtrăm nimic
                    label = f"🏠 {n}" if is_useful else n
                    processed_options.append((n, label))
                else:
                    # Filtrare inteligentă:
                    # NU ascundem dacă e "useful" (are poligoane)
                    should_hide = any(k in n.upper() for k in final_ignore) or n.startswith(("*", "$"))
                    
                    if is_useful or not should_hide:
                        label = f"🏠 {n}" if is_useful else n
                        processed_options.append((n, label))
            
            # Sortare alfabetică a etichetelor finale
            processed_options.sort(key=lambda x: x[0].upper())
            
            opt_map = {label: name for name, label in processed_options}
            
            # Căutăm layer-ul de contur standard pentru a-l pune ca default
            default_candidates = ["CONTUR_APARTAMENT", "Model Unit - Zone"]
            found_default = 0
            for i, (real_name, label) in enumerate(processed_options):
                if any(cand.upper() in real_name.upper() for cand in default_candidates):
                    found_default = i
                    break

            selected_label = st.selectbox("Alege Layer Contur", options=list(opt_map.keys()), index=found_default)
            selected_layer = opt_map[selected_label]
            
        except Exception as e:
            st.error(f"Eroare: {e}")
            selected_layer = "0"

        unit_type = st.radio("Unități desen", ["Metri (m)", "Milimetri (mm)"], horizontal=True)
        unit_key = "m" if "Metri" in unit_type else "mm"
        do_process = st.button("🚀 PROCESEAZĂ")

    with col_preview:
        fig_interact = draw_all_layers_interactive(raw_bytes)
        st.plotly_chart(fig_interact, use_container_width=True)

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
            col_res1, col_res2 = st.columns([1, 1.2])
            with col_res1:
                st.subheader("🏠 Centralizator")
                summary = [{"Unitate": r.name, "Total": r.total_area, "Utilă": r.net_area, "Balcon": r.balcony_area} for r in results]
                st.table(summary)
            with col_res2:
                st.subheader("🖼️ Schiță Geometrie")
                fig, ax = plt.subplots()
                for r in results:
                    x, y = r.polygon.exterior.xy
                    ax.plot(x, y, linewidth=2, color="#f63366")
                    ax.text(r.polygon.centroid.x, r.polygon.centroid.y, r.name, ha='center', fontsize=8, fontweight='bold')
                ax.set_aspect('equal'); ax.set_axis_off()
                st.pyplot(fig)
else:
    st.info("Încarcă un fișier DXF pentru a începe.")