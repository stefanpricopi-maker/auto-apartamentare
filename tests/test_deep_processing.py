import io
import ezdxf
import pytest
from shapely.geometry import Polygon
from modules.processor import ProcessorConfig, process_dxf_bytes

def _doc_to_bytes(doc) -> bytes:
    sio = io.StringIO()
    doc.write(sio)
    return sio.getvalue().encode("utf-8")

# 1. TEST: Verificăm dacă vede geometria din interiorul unui BLOC (INSERT)
def test_block_geometry_extraction():
    doc = ezdxf.new()
    # Creăm o definiție de bloc (ex: o ușă simbolică)
    door_blk = doc.blocks.new(name='USA_TIP_1')
    door_blk.add_line((0, 0), (1, 1), dxfattribs={"layer": "TAMPLARIE"})
    
    msp = doc.modelspace()
    # Contur apartament
    msp.add_lwpolyline([(0,0), (10,0), (10,10), (0,10)], close=True, dxfattribs={"layer": "CONTUR_APARTAMENT"})
    
    # Inserăm blocul în interiorul apartamentului
    msp.add_blockref('USA_TIP_1', (5, 5), dxfattribs={"layer": "TAMPLARIE"})

    results = process_dxf_bytes(_doc_to_bytes(doc), ProcessorConfig(reference_layer="CONTUR_APARTAMENT"))
    
    # Verificăm dacă geometria din interiorul blocului a fost extrasă
    # Ar trebui să avem o linie (segment de 2 puncte) în lista de geometrii
    assert len(results) == 1
    assert len(results[0].geometries) > 0

# 2. TEST: Verificăm procesarea ARCELOR (Geometrie curbă)
def test_arc_clipping():
    doc = ezdxf.new()
    msp = doc.modelspace()
    
    # Apartament
    msp.add_lwpolyline([(0,0), (10,0), (10,10), (0,10)], close=True, dxfattribs={"layer": "CONTUR_APARTAMENT"})
    
    # Adăugăm un arc (ex: deschiderea unei uși) parțial în interior
    # Centru (10,5), rază 2, de la 90 la 270 grade
    msp.add_arc(center=(10, 5), radius=2, start_angle=90, end_angle=270, dxfattribs={"layer": "TAMPLARIE"})

    results = process_dxf_bytes(_doc_to_bytes(doc), ProcessorConfig(reference_layer="CONTUR_APARTAMENT"))
    
    # Arcul trebuie să fie convertit în puncte și păstrat (cel puțin parțial)
    assert len(results[0].geometries) > 0
    # Verificăm dacă punctele rezultate sunt în interiorul sau pe marginea poligonului [0,10]
    for segment in results[0].geometries:
        for x, y in segment:
            assert 0 <= x <= 10
            assert 0 <= y <= 10

# 3. TEST: Verificăm dacă Tabelul (DataFrame) se populează corect
def test_areas_dataframe_content():
    doc = ezdxf.new()
    msp = doc.modelspace()
    
    # Contur
    msp.add_lwpolyline([(0,0), (10,0), (10,10), (0,10)], close=True, dxfattribs={"layer": "CONTUR_APARTAMENT"})
    
    # Adăugăm texte (Nume cameră și Suprafață)
    msp.add_text("LIVING", dxfattribs={"layer": "TEXTE"}).set_placement((2, 8))
    msp.add_text("S=15.50mp", dxfattribs={"layer": "TEXTE"}).set_placement((2, 7))
    
    msp.add_text("BAIE", dxfattribs={"layer": "TEXTE"}).set_placement((7, 2))
    msp.add_text("S=4.20mp", dxfattribs={"layer": "TEXTE"}).set_placement((7, 1))

    results = process_dxf_bytes(_doc_to_bytes(doc), ProcessorConfig(reference_layer="CONTUR_APARTAMENT"))
    
    df = results[0].areas_df
    assert len(df) == 2
    assert "LIVING" in df['Denumire'].values
    assert 15.50 in df['Suprafață (mp)'].values
    assert df['Suprafață (mp)'].sum() == 19.70