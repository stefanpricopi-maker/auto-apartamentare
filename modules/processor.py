import ezdxf
import pandas as pd
import re
from typing import List
from dataclasses import dataclass
from shapely.geometry import Polygon, Point

@dataclass
class ApartmentResult:
    index: int
    name: str
    polygon: Polygon
    area_calc: float
    net_area: float      # Suprafața utilă (fără balcoane)
    balcony_area: float  # Doar balcoanele/logiile
    total_area: float    # Totul adunat
    areas_df: pd.DataFrame

class ProcessorConfig:
    def __init__(self, reference_layer: str, units: str = "m", eps: float = 1e-6):
        self.reference_layer = reference_layer
        self.units = units
        self.scale = 1000.0 if units == "mm" else 1.0

def _entity_text_value(e) -> str:
    raw = ""
    if e.dxftype() == "TEXT": raw = e.dxf.text
    elif e.dxftype() == "MTEXT": raw = e.text
    elif e.dxftype() == "ATTRIB": raw = e.dxf.text
    if not raw: return ""
    clean = re.sub(r"\\P|\\{.*?\\}|\\{.*|\\}|\\f.*?|\\A.*|\\H.*|\\S.*|\\Q.*|\\W.*|\\T.*|\\C.*|;", " ", raw)
    replacements = {"\\U+0102": "Ă", "\\U+0103": "ă", "\\U+00CE": "Î", "\\U+00EE": "î",
                    "\\U+0218": "Ș", "\\U+0219": "ș", "\\U+021A": "Ț", "\\U+021B": "ț",
                    "\\U+00C2": "Â", "\\U+00E2": "â"}
    for code, char in replacements.items():
        clean = clean.replace(code, char)
    return clean.strip()

def process_dxf_bytes(dxf_data: bytes, config: ProcessorConfig) -> List[ApartmentResult]:
    import io
    stream = io.TextIOWrapper(io.BytesIO(dxf_data), encoding="utf-8", errors="replace")
    doc = ezdxf.read(stream)
    msp = doc.modelspace()
    
    apartments_data = []
    for p in msp.query(f'LWPOLYLINE[layer=="{config.reference_layer}"]'):
        if p.is_closed and len(p) >= 3:
            pts = [(v[0], v[1]) for v in p.get_points()]
            poly = Polygon(pts)
            if poly.is_valid and poly.area > 0.1:
                apartments_data.append({"poly": poly, "temp_name": f"Unitate_{len(apartments_data)+1}"})
    
    if not apartments_data: return []

    blacklist = {"GRESIE", "PARCHET", "ANTID", "LAMINAT", "BETON", "VOPSEA", "CIMENT", "CERAMIC"}
    balcony_keywords = {"BALCON", "LOGIE", "TERASA", "BALC", "LOG"}

    all_labels = []
    for e in msp:
        entities = [e]
        if e.dxftype() == "INSERT":
            entities = list(e.attribs)
            try: entities.extend(e.virtual_entities())
            except: pass
        for sub_e in entities:
            if sub_e.dxftype() in {"TEXT", "MTEXT", "ATTRIB"}:
                val = _entity_text_value(sub_e)
                if len(val) < 2 or any(w in val.upper() for w in blacklist): continue
                try:
                    p = sub_e.dxf.insert
                    all_labels.append({"val": val, "pt": Point(p.x, p.y)})
                except: continue

    area_pat = re.compile(r"(\d+[.,]\d+)")
    final_results = []
    search_buffer = 1.5 * config.scale

    for apt in apartments_data:
        rows = []
        real_name = apt["temp_name"]
        current_room = "Încăpere"
        
        # Pas 1: Redenumire apartament
        for lbl in all_labels:
            if apt["poly"].contains(lbl["pt"]) or apt["poly"].distance(lbl["pt"]) < search_buffer:
                if "AP." in lbl["val"].upper() or "APT." in lbl["val"].upper():
                    real_name = lbl["val"]

        # Pas 2: Colectare date camere
        sum_net = 0.0
        sum_balcony = 0.0

        for lbl in all_labels:
            if apt["poly"].contains(lbl["pt"]) or apt["poly"].distance(lbl["pt"]) < search_buffer:
                txt = lbl["val"]
                if "AP." in txt.upper() or "APT." in txt.upper(): continue

                match = area_pat.search(txt)
                if match:
                    try:
                        val = round(float(match.group(1).replace(",", ".")), 2)
                        if 1.0 <= val <= 250.0:
                            is_balcony = any(k in current_room.upper() for k in balcony_keywords)
                            
                            rows.append({
                                "Nr. Apartament": real_name, 
                                "Denumire": current_room, 
                                "Suprafață (mp)": val,
                                "Tip": "Balcon" if is_balcony else "Utilă"
                            })
                            
                            if is_balcony: sum_balcony += val
                            else: sum_net += val
                            
                            current_room = "Încăpere"
                    except: continue
                else:
                    if len(txt) > 3 and not any(c.isdigit() for c in txt):
                        current_room = txt

        df = pd.DataFrame(rows).drop_duplicates()
        area_calc = apt["poly"].area / (1000000.0 if config.units == "mm" else 1.0)
        
        final_results.append(ApartmentResult(
            index=0, 
            name=real_name, 
            polygon=apt["poly"], 
            area_calc=area_calc,
            net_area=round(sum_net, 2),
            balcony_area=round(sum_balcony, 2),
            total_area=round(sum_net + sum_balcony, 2),
            areas_df=df
        ))
        
    return final_results