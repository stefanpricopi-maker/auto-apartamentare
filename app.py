import streamlit as st

st.set_page_config(page_title="AutoApartamentare", layout="centered")

st.title("AutoApartamentare - Cadastru Helper")

uploaded = st.file_uploader("Încarcă fișierul .dxf", type=["dxf"])

reference_layer = st.text_input("Layer contur (default)", value="CONTUR_APARTAMENT")

run = st.button("Procesează", type="primary")

if run:
    if uploaded is None:
        st.warning("Te rog încarcă un fișier .dxf.")
    else:
        st.info(
            f"Fișier încărcat: **{uploaded.name}**. "
            f"Layer contur: **{reference_layer or 'CONTUR_APARTAMENT'}**."
        )

