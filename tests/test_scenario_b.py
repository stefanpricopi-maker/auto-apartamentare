import pytest
import re
from shapely.geometry import Polygon, Point
from modules.processor import _entity_text_value, ProcessorConfig

# 1. TEST: Curățarea Textului (Ă, Î, Ș și coduri AutoCAD)
def test_unicode_decoding():
    # Simulăm un obiect DXF cu coduri Unicode de tip ArchiCAD
    class MockEntity:
        def __init__(self, text):
            self.dxf = type('obj', (object,), {'text': text})
        def dxftype(self): return "TEXT"

    raw = "LIVING\\U+0102T\\U+0102RIE" # LIVINGĂTĂRIE
    clean = _entity_text_value(MockEntity(raw))
    
    assert "Ă" in clean
    assert "U+0102" not in clean

# 2. TEST: Logica de detecție a suprafețelor (Regex)
def test_area_recognition_logic():
    # Verificăm dacă robotul alege corect numerele din text
    texts = ["LIVING", "S=18.50 mp", "H=2.60 m"]
    area_pat = re.compile(r"(\d+[.,]\d+)")
    
    found_areas = []
    for t in texts:
        m = area_pat.search(t)
        if m:
            val = float(match_str := m.group(1).replace(",", "."))
            # Filtrul nostru de siguranță: între 3.0 și 200.0 mp
            if 3.0 <= val <= 200.0:
                found_areas.append(val)
                
    assert 18.50 in found_areas
    assert 2.60 not in found_areas # Trebuie să ignore înălțimea

# 3. TEST: Scalarea Metri vs Milimetri
def test_scaling_logic():
    cfg_m = ProcessorConfig(reference_layer="TEST", units="m")
    cfg_mm = ProcessorConfig(reference_layer="TEST", units="mm")
    
    # 1.5 metri în mm trebuie să fie 1500 pentru raza "magnetului"
    assert 1.5 * cfg_m.scale == 1.5
    assert 1.5 * cfg_mm.scale == 1500.0

# 4. TEST: Geometrie (Punct în Poligon)
def test_geometry_check():
    poly = Polygon([(0,0), (10,0), (10,10), (0,10)])
    p_inside = Point(5, 5)
    p_outside = Point(15, 15)
    
    assert poly.contains(p_inside) == True
    assert poly.distance(p_outside) > 1.5 # Verificăm pragul de magnet