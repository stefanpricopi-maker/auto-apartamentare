import pytest
from playwright.sync_api import Page, expect
import os
import re

BASE_URL = "http://localhost:8501"

def wait_for_streamlit(page: Page):
    # Așteptăm indicatorul de status (rotița) să dispară
    page.wait_for_selector("[data-testid='stStatusWidget']", state="hidden", timeout=10000)
    page.wait_for_timeout(1000) # Buffer mic pentru hidratare UI

def test_app_load(page: Page):
    page.goto(BASE_URL)
    wait_for_streamlit(page)
    
    # Verificăm titlul curat (fără emoji)
    expect(page.get_by_text("AutoApartamentare - Versiunea Profesionala")).to_be_visible()

def test_sidebar_config_visibility(page: Page):
    page.goto(BASE_URL)
    wait_for_streamlit(page)
    
    sidebar = page.locator("[data-testid='stSidebar']")
    # Verificăm headerele curățate
    expect(sidebar.get_by_text("Incarcare Fisier")).to_be_visible()
    expect(sidebar.get_by_text("Configurare")).to_be_visible()
    
    # Verificăm label-ul inputului
    expect(page.get_by_text("Nume Layer Contur:")).to_be_visible()

def test_full_workflow_processing(page: Page):
    page.goto(BASE_URL)
    wait_for_streamlit(page)
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, "data", "etaj_test.dxf")
    
    if not os.path.exists(file_path):
        pytest.skip("Lipseste fisierul de test DXF.")

    # Incarcare stabila
    page.set_input_files("input[type='file']", file_path)
    
    # Asteptam Plotly (Previzualizarea)
    expect(page.locator(".js-plotly-plot").first).to_be_visible(timeout=15000)

    # Click pe butonul curățat
    page.get_by_text("GENEREAZA RELEVEE COMPLET").click()

    # Verificăm rezultatele
    expect(page.get_by_text("Rezultat Final: Relevee Curatate")).to_be_visible(timeout=20000)
    expect(page.get_by_text("Centralizator Suprafete")).to_be_visible()