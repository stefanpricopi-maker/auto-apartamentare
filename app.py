import streamlit as st
import pandas as pd
import ezdxf
import io
import matplotlib.pyplot as plt
from modules.processor import ProcessorConfig, process_dxf_bytes, draw_all_layers_interactive

# --- CONFIGURARE PAGINĂ ---
st.set_page_config(
    page_title="AutoApartamentare Pro - Cadastru", 
    layout="centered", 
    page_icon="🏙️"
)

# --- STILIZARE CSS ---
st.markdown("""
    <style>
    .block-container { max-width: 1100px; padding-top: 1.5rem; }
    .stButton>button { 
        width: 100%; 
        border-radius: 10px; 
        height: 3.5em; 
        background-color: #e63946; 
        color: white; 
        font-weight: bold;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #ff4d5a;
        transform: scale(1.02);
    }
    /* Stil pentru tabele și date */
    div[data-testid="stTable"] { border-radius: 10px; overflow: hidden; }
    </style>
    """, unsafe_allow_html=True)

st.title("🏙️ AutoApartamentare - Versiunea Finală")
st.caption("Instrument profesional pentru curățare DXF și generare rapoarte de suprafețe.")

# --- ÎNCĂRCARE FIȘIER ---
uploaded = st.file_uploader("Încarcă fișierul DXF (Plan etaj)", type=["dxf"])

if uploaded:
    raw_bytes = uploaded.getvalue()
    
    # Împărțim ecranul: Configurare (stânga) | Previzualizare (dreapta)
    col_input, col_preview = st.columns([1, 1.8])
    
    with col_input:
        st.subheader("⚙️ Configurare")
        
        # Filtre pentru curățarea listei de layere
        with st.expander("Filtre avansate", expanded=False):
            show_all = st.checkbox("Arată absolut tot", value=False)
            custom_ignore = st.text_input("Ignoră cuvinte (ex: AXE, COTE):", value="AXE, MOBILA, COTE, TEXT")
        
        ignore_list = [x.strip().upper() for x in custom_ignore.split(",") if x.strip()]
        base_ignore = ["HIDDEN", "PEN_NO", "EVACUARE", "GOLURI", "PLANSEE", "INTERACSI"]
        final_ignore = base_ignore + ignore_list

        try:
            # Citim fișierul pentru a extrage layerele
            text_stream = io.TextIOWrapper(io.BytesIO(raw_bytes), encoding="utf-8", errors="replace")
            doc = ezdxf.read(text_stream)
            msp = doc.modelspace()
            all_layers = [l.dxf.name for l in doc.layers]
            
            # Identificăm layerele care conțin geometrie utilă (Poligoane)
            useful_layers = set()
            for lname in all_layers:
                if msp.query(f'LWPOLYLINE[layer=="{lname}"]'):
                    useful_layers.add(lname)

            # Construim lista pentru dropdown
            processed_options = []
            for n in all_layers:
                is_useful = n in useful_layers
                
                if show_all:
                    label = f"🏠 {n}" if is_useful else n
                    processed_options.append((n, label))
                else:
                    # Regula: NU ascundem dacă are poligoane, altfel aplicăm filtrele
                    should_hide = any(k in n.upper() for k in final_ignore) or n.startswith(("*", "$"))
                    if is_useful or not should_hide:
                        label = f"🏠 {n}" if is_useful else n
                        processed_options.append((n, label))
            
            # Sortare alfabetică
            processed_options.sort(key=lambda x: x[0].upper())
            opt_map = {label: name for name, label in processed_options}
            
            # Selectarea automată a unui layer probabil de contur
            default_candidates = ["CONTUR", "Model Unit", "ZONE", "APARTAMENT"]
            found_idx = 0
            for i, (real_name, label) in enumerate(processed_options):
                if any(cand.upper() in real_name.upper() for cand in default_candidates):
                    found_idx = i
                    break

            selected_label = st.selectbox("Alege Layer Contur", options=list(opt_map.keys()), index=found_idx)
            selected_layer = opt_map[selected_label]
            
        except Exception as e:
            st.error(f"Eroare la citirea DXF: {e}")
            selected_layer = "0"

        # Unități și Procesare
        unit_type = st.radio("Unități desen AutoCAD", ["Metri (m)", "Milimetri (mm)"], horizontal=True)
        unit_key = "m" if "Metri" in unit_type else "mm"
        
        st.write("---")
        do_process = st.button("🚀 GENEREAZĂ REZULTAT FINAL")

    with col_preview:
        # Previzualizare interactivă a tot ce e în fișier (Plotly)
        fig_interact = draw_all_layers_interactive(raw_bytes)
        st.plotly_chart(fig_interact, use_container_width=True, config={'displayModeBar': True})

    # --- LOGICA DE PROCESARE ȘI AFIȘARE REZULTATE ---
    if do_process:
        cfg = ProcessorConfig(reference_layer=selected_layer, units=unit_key)
        results = process_dxf_bytes(raw_bytes, cfg)
        
        if results:
            st.divider()
            
            # 1. TABELUL DETALIAT (PENTRU EXCEL)
            all_dfs = [r.areas_df for r in results if not r.areas_df.empty]
            if all_dfs:
                st.subheader("📋 Detaliu pe Încăperi")
                final_df = pd.concat(all_dfs, ignore_index=True)
                st.dataframe(final_df, use_container_width=True, hide_index=True)
                
                csv = final_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 DESCARCĂ EXCEL (.csv)", csv, "Raport_Cadastru.csv", "text/csv")
            
            st.divider()

            # 2. REZULTATUL VIZUAL ȘI CENTRALIZATORUL
            col_res1, col_res2 = st.columns([1, 1.2])
            
            with col_res1:
                st.subheader("🏠 Centralizator")
                summary_data = []
                for r in results:
                    summary_data.append({
                        "Unitate": r.name,
                        "S. Totală": r.total_area,
                        "S. Utilă": r.net_area,
                        "S. Balcon": r.balcony_area
                    })
                st.table(summary_data)
                
            with col_res2:
                st.subheader("🖼️ Schiță Finală Curățată")
                # Generăm schița cu linii roșii groase și textele interioare
                fig_final, ax = plt.subplots(figsize=(10, 10))
                
                for r in results:
                    # Contur Roșu Gros
                    x, y = r.polygon.exterior.xy
                    ax.plot(x, y, linewidth=3, color="#e63946", solid_capstyle='round', zorder=1)
                    
                    # Desenăm textele camerelor (nume și suprafețe)
                    for lbl in r.all_room_labels:
                        f_size = 7 if lbl.is_area else 8
                        f_weight = 'normal' if lbl.is_area else 'bold'
                        
                        ax.text(
                            lbl.point.x, lbl.point.y, lbl.text, 
                            ha='center', va='center', 
                            fontsize=f_size, fontweight=f_weight,
                            color="#1d3557",
                            bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=0.1),
                            zorder=2
                        )
                
                ax.set_aspect('equal')
                ax.set_axis_off()
                st.pyplot(fig_final)
                
        else:
            st.warning(f"Nu s-au găsit poligoane închise pe layer-ul '{selected_layer}'. Verifică dacă layer-ul ales este cel corect.")
else:
    st.info("👋 Salut! Încarcă un fișier DXF în zona de sus pentru a începe procesarea.")