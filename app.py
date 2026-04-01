import streamlit as st
import ezdxf
import io

st.set_page_config(page_title="AutoApartamentare", layout="centered")

st.markdown(
    """
<style>
div[data-testid="stVerticalBlock"] h2 {
  margin-bottom: 0.5rem;
}
.aa-center {
  display: flex;
  justify-content: center;
  margin-top: 0.75rem;
}
.aa-center div[data-testid="stButton"] > button {
  background: #e53935 !important;
  border: 1px solid #e53935 !important;
  color: white !important;
  padding: 0.6rem 1.2rem !important;
  border-radius: 0.6rem !important;
}
.aa-center div[data-testid="stButton"] > button:hover {
  background: #d32f2f !important;
  border-color: #d32f2f !important;
}
.aa-center div[data-testid="stButton"] > button:focus {
  box-shadow: 0 0 0 0.2rem rgba(229, 57, 53, 0.25) !important;
}
</style>
<h2>AutoApartamentare - Cadastru Helper</h2>
""",
    unsafe_allow_html=True,
)

uploaded = st.file_uploader("Încarcă fișierul .dxf", type=["dxf"])

reference_layer = "CONTUR_APARTAMENT"
layers: list[str] = []
layer_read_error = False
doc = None

if uploaded is not None:
    try:
        # ezdxf expects a text stream for common ASCII DXF files
        text_stream = io.TextIOWrapper(io.BytesIO(uploaded.getvalue()), encoding="utf-8", errors="replace")
        doc = ezdxf.read(text_stream)
        layers = sorted({layer.dxf.name for layer in doc.layers if getattr(layer.dxf, "name", None)})
    except Exception as e:
        layer_read_error = True
        st.error("Hopa! Fișierul pare să aibă probleme. Sigur este un DXF valid?")
        st.caption(f"Detalii tehnice: {e}")

if doc is not None and not layer_read_error:
    try:
        # DXF version: translate "AC10xx" to human-friendly AutoCAD release when possible
        from ezdxf.lldxf.const import acad_release

        dxf_ver = getattr(doc, "dxfversion", "") or ""
        release = acad_release.get(dxf_ver, dxf_ver or "necunoscut")
        version_label = release if release.lower().startswith("autocad") else f"AutoCAD {release}"

        total_entities = sum(len(layout) for layout in doc.layouts)
        st.caption(f"**Versiune DXF**: {version_label} · **Entități totale**: {total_entities}")
    except Exception:
        # Don't block the UI if stats fail
        pass

if layers:
    default_idx = layers.index("CONTUR_APARTAMENT") if "CONTUR_APARTAMENT" in layers else 0
    reference_layer = st.selectbox("Layer contur (alege din fișier)", options=layers, index=default_idx)
else:
    reference_layer = st.text_input("Layer contur (default)", value="CONTUR_APARTAMENT")

st.markdown('<div class="aa-center">', unsafe_allow_html=True)
run = st.button("Procesează")
st.markdown("</div>", unsafe_allow_html=True)

if run:
    if uploaded is None:
        st.warning("Te rog încarcă un fișier .dxf.")
    elif layer_read_error:
        st.warning("Nu pot procesa acest fișier până nu este un DXF valid.")
    else:
        st.info(
            f"Fișier încărcat: **{uploaded.name}**. "
            f"Layer contur: **{reference_layer or 'CONTUR_APARTAMENT'}**."
        )

