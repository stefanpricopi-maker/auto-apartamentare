import streamlit as st
import pandas as pd
import ezdxf
import io
import matplotlib.pyplot as plt
from modules.processor import ProcessorConfig, process_dxf_bytes, draw_all_layers_interactive

# 1. CONFIGURARE PAGINĂ ȘI DESIGN
st.set_page_config(
    page_title="AutoApartamentare Pro", 
    layout="centered", 
    page_icon="🏙️"
)

# Stilizare CSS pentru butoane și containere
st.markdown("""
    <style>
    .block-container { max-width: 1050px; padding-top: 1.5rem; }
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

st.title("🏙️ AutoApartamentare - Versiunea Profesională")
st.caption("Extracție automată de suprafețe și generare planuri curățate pentru cadastru.")

# 2. ÎNCĂRCARE FIȘIER DXF
uploaded = st.file_uploader("Încarcă fișierul DXF (Plan etaj)", type=["dxf"])

if uploaded:
    raw_bytes = uploaded.getvalue()
    
    # Layout: Stânga (Configurare) | Dreapta (Previzualizare Interactivă)
    col_input, col_preview = st.columns([1, 2])
    
    with col_input:
        st.subheader("⚙️ Configurare")
        
        # Filtre pentru curățarea listei de layere
        show_all = st.checkbox("Arată absolut toate layerele", value=False)
        custom_ignore = st.text_input("Ignoră layere (ex: AXE, MOBILA):", value="AXE, MOBILA, COTE, TEXT")
        
        ignore_list = [x.strip().upper() for x in custom_ignore.split(",") if x.strip()]
        base_ignore = ["HIDDEN", "PEN_NO", "EVACUARE", "GOLURI", "PLANSEE", "INTERACSI"]
        final_ignore = base_ignore + ignore_list

        try:
            # Citire temporară pentru popularea dropdown-ului de layere
            text_stream = io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8", errors="replace")
            doc = ezdxf.read(text_stream)
            msp = doc.modelspace()
            all_layers = [l.dxf.name for l in doc.layers]
            
            # Marcăm layerele care conțin poligoane (posibile contururi)
            useful_layers = {lname for lname in all_layers if msp.query(f'LWPOLYLINE[layer=="{lname}"]')}

            processed_options = []
            for n in all_layers:
                is_useful = n in useful_layers
                if show_all:
                    processed_options.append((n, f"🏠 {n}" if is_useful else n))
                else:
                    # Ascundem layerele de sistem sau cele din ignore_list, dacă nu sunt "utile"
                    should_hide = any(k in n.upper() for k in final_ignore) or n.startswith(("*", "$"))
                    if is_useful or not should_hide:
                        processed_options.append((n, f"🏠 {n}" if is_useful else n))
            
            processed_options.sort(key=lambda x: x[0].upper())
            opt_map = {label: name for name, label in processed_options}
            
            # Selectare automată layer probabil (ex: "ZONE" sau "CONTUR")
            default_idx = 0
            for i, (name, label) in enumerate(processed_options):
                if "ZONE" in name.upper() or "CONTUR" in name.upper():
                    default_idx = i
                    break

            selected_label = st.selectbox("Alege Layer Contur", options=list(opt_map.keys()), index=default_idx)
            selected_layer = opt_map[selected_label]
            
        except Exception as e:
            st.error(f"Eroare la citirea layerelor: {e}")
            selected_layer = "0"

        # Alegere unități
        unit_type = st.radio("Unități desen AutoCAD", ["Metri (m)", "Milimetri (mm)"], horizontal=True)
        unit_key = "m" if "Metri" in unit_type else "mm"
        
        st.write("---")
        do_process = st.button("🚀 PROCESEAZĂ ȘI CURĂȚĂ")

    with col_preview:
        # Previzualizarea Plotly (Harta interactivă din dreapta)
        fig_interact = draw_all_layers_interactive(raw_bytes)
        st.plotly_chart(fig_interact, use_container_width=True)

    # 3. LOGICA DE PROCESARE DUPĂ APĂSAREA BUTONULUI
    if do_process:
        cfg = ProcessorConfig(reference_layer=selected_layer, units=unit_key)
        results = process_dxf_bytes(raw_bytes, cfg)
        
        if results:
            st.divider()
            
            # AFIȘARE TABEL REZULTATE
            all_dfs = [r.areas_df for r in results if not r.areas_df.empty]
            if all_dfs:
                st.subheader("📋 Detaliu pe Încăperi")
                final_df = pd.concat(all_dfs, ignore_index=True)
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
                # Download Excel/CSV
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 DESCARCĂ RAPORT EXCEL", csv, "Raport_Suprafete.csv", "text/csv")
            
            st.divider()
            
            # AFIȘARE CENTRALIZATOR ȘI SCHIȚĂ FINALĂ CURĂȚATĂ
            col_res1, col_res2 = st.columns([1, 1.3])
            
            with col_res1:
                st.subheader("🏠 Centralizator")
                summary = [{"Unitate": r.name, "Total": r.total_area, "Utilă": r.net_area} for r in results]
                st.table(summary)
                
            with col_res2:
                st.subheader("🖼️ Schiță Finală (Rezultat Curățat)")
                # Desenăm schița fără culori stridente, doar linii gri și text negru
                fig_final, ax = plt.subplots(figsize=(10, 10))
                
                for r in results:
                    # Desenăm conturul (linii gri subțiri)
                    x, y = r.polygon.exterior.xy
                    ax.plot(x, y, linewidth=0.8, color="#555555")
                    
                    # Desenăm textele camerelor (Negru clar)
                    for lbl in r.all_room_labels:
                        ax.text(
                            lbl.point.x, lbl.point.y, lbl.text, 
                            ha='center', va='center', 
                            fontsize=8, 
                            color="black", 
                            fontweight='bold' if not lbl.is_area else 'normal',
                            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=0.1)
                        )
                
                ax.set_aspect('equal')
                ax.set_axis_off()
                st.pyplot(fig_final)
        else:
            st.warning(f"Nu s-au găsit date pe layer-ul '{selected_layer}'. Încearcă alt layer.")
else:
    st.info("Încarcă un fișier DXF pentru a începe.")import streamlit as st
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

# Design CSS pentru un aspect profesional
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
    
    # Creăm două coloane pentru interfață
    col_input, col_preview = st.columns([1, 2])
    
    with col_input:
        st.subheader("⚙️ Configurare")
        
        # Opțiuni de filtrare layere
        show_all = st.checkbox("Arată toate layerele", value=False)
        custom_ignore = st.text_input("Ignoră layere care conțin:", value="AXE, MOBILA, COTE, TEXT")
        
        ignore_list = [x.strip().upper() for x in custom_ignore.split(",") if x.strip()]
        base_ignore = ["HIDDEN", "PEN_NO", "EVACUARE", "GOLURI", "PLANSEE", "INTERACSI"]
        final_ignore = base_ignore + ignore_list

        try:
            # Citim fișierul pentru a extrage lista de layere
            text_stream = io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8", errors="replace")
            doc = ezdxf.read(text_stream)
            msp = doc.modelspace()
            all_layers = [l.dxf.name for l in doc.layers]
            
            # Identificăm layerele care conțin polilinii (potențiale contururi)
            useful_layers = {lname for lname in all_layers if msp.query(f'LWPOLYLINE[layer=="{lname}"]')}

            processed_options = []
            for n in all_layers:
                is_useful = n in useful_layers
                if show_all:
                    processed_options.append((n, f"🏠 {n}" if is_useful else n))
                else:
                    # Filtrare: nu ascundem dacă are poligoane, altfel aplicăm ignorarea
                    should_hide = any(k in n.upper() for k in final_ignore) or n.startswith(("*", "$"))
                    if is_useful or not should_hide:
                        processed_options.append((n, f"🏠 {n}" if is_useful else n))
            
            processed_options.sort(key=lambda x: x[0].upper())
            opt_map = {label: name for name, label in processed_options}
            
            # Selectare automată layer probabil (ex: "ZONE" sau "CONTUR")
            default_idx = 0
            for i, (name, label) in enumerate(processed_options):
                if "ZONE" in name.upper() or "CONTUR" in name.upper():
                    default_idx = i
                    break

            selected_label = st.selectbox("Alege Layer Contur", options=list(opt_map.keys()), index=default_idx)
            selected_layer = opt_map[selected_label]
            
        except:
            selected_layer = "0"

        # Alegere unități
        unit_type = st.radio("Unități desen AutoCAD", ["Metri (m)", "Milimetri (mm)"], horizontal=True)
        unit_key = "m" if "Metri" in unit_type else "mm"
        
        st.write("---")
        do_process = st.button("🚀 GENEREAZĂ PLAN CURĂȚAT")

    with col_preview:
        # Previzualizare Plotly interactivă
        fig_interact = draw_all_layers_interactive(raw_bytes)
        st.plotly_chart(fig_interact, use_container_width=True)

    # 3. PROCESARE ȘI REZULTATE
    if do_process:
        cfg = ProcessorConfig(reference_layer=selected_layer, units=unit_key)
        results = process_dxf_bytes(raw_bytes, cfg)
        
        if results:
            st.divider()
            
            # AFIȘARE TABEL REZULTATE
            all_dfs = [r.areas_df for r in results if not r.areas_df.empty]
            if all_dfs:
                st.subheader("📋 Detaliu pe Încăperi")
                final_df = pd.concat(all_dfs, ignore_index=True)
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
                # Buton download CSV
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 DESCARCĂ RAPORT", csv, "Raport_Suprafete.csv", "text/csv")
            
            st.divider()
            
            # AFIȘARE CENTRALIZATOR ȘI SCHIȚĂ FINALĂ
            col_res1, col_res2 = st.columns([1, 1.3])
            
            with col_res1:
                st.subheader("🏠 Centralizator")
                summary_data = [{"Unitate": r.name, "S. Totală": r.total_area, "S. Utilă": r.net_area} for r in results]
                st.table(summary_data)
                
            with col_res2:
                st.subheader("🖼️ Schiță Finală (Rezultat Curățat)")
                # Generăm schița cu Matplotlib: Linii gri subțiri și text negru
                fig_final, ax = plt.subplots(figsize=(10, 10))
                
                for r in results:
                    # 1. Desenăm poligonul (Contur gri subțire)
                    x, y = r.polygon.exterior.xy
                    ax.plot(x, y, linewidth=0.8, color="#555555", zorder=1)
                    
                    # 2. Desenăm etichetele interioare (Nume cameră și suprafață)
                    for lbl in r.all_room_labels:
                        ax.text(
                            lbl.point.x, lbl.point.y, lbl.text, 
                            ha='center', va='center', 
                            fontsize=8, 
                            color="black", 
                            fontweight='bold' if not lbl.is_area else 'normal',
                            bbox=dict(facecolor='white', alpha=0.8, edgecolor='none', pad=0.1),
                            zorder=2
                        )
                
                ax.set_aspect('equal')
                ax.set_axis_off()
                st.pyplot(fig_final)
        else:
            st.warning(f"Nu s-au găsit date pe layer-ul '{selected_layer}'. Încearcă să alegi altul.")
else:
    st.info("Încarcă un fișier DXF pentru a începe.")