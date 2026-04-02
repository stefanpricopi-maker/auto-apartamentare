import ezdxf
import pandas as pd
import re
from typing import List
from dataclasses import dataclass
from shapely.geometry import Polygon, Point

@dataclass
class RoomLabel:
    text: str
    point: Point
    is_area: bool

@dataclass
class ApartmentResult:
    index: int
    name: str
    polygon: Polygon
    area_calc: float
    net_area: float      
    balcony_area: float  
    total_area: float    
    areas_df: pd.DataFrame
    all_room_labels: List[RoomLabel] # Păstrăm textele pentru desen

# ... (funcțiile _entity_text_value și draw_all_layers_interactive rămân la fel ca anterior) ...

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

    blacklist = {"GRESIE", "PARCHET", "ANTID", "LAMINAT", "BETON", "VOPSEA", "CIMENT", "CERAMIC", "LIMITA", "GOL", "PLACA", "H=", "HB="}
    balcony_keywords = {"BALCON", "LOGIE", "TERASA", "BALC", "LOG"}
    area_pat = re.compile(r"(\d+[.,]\d+)")
    search_buffer = 0.2 * config.scale 

    all_labels_raw = []
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
                all_labels_raw.append({"val": val, "pt": Point(sub_e.dxf.insert.x, sub_e.dxf.insert.y)})

    final_results = []
    for apt in apartments_data:
        rows, labels_to_draw, real_name, current_room = [], [], apt["temp_name"], "Încăpere"
        
        # Pas 1: Nume Apartament
        for lbl in all_labels_raw:
            if apt["poly"].contains(lbl["pt"]) or apt["poly"].distance(lbl["pt"]) < search_buffer:
                if "AP." in lbl["val"].upper() or "APT." in lbl["val"].upper():
                    real_name = lbl["val"].split("S=")[0].split("s=")[0].strip()
                    labels_to_draw.append(RoomLabel(lbl["val"], lbl["pt"], False))

        # Pas 2: Camere și Suprafețe
        sum_net, sum_balcony = 0.0, 0.0
        for lbl in all_labels_raw:
            if apt["poly"].contains(lbl["pt"]) or apt["poly"].distance(lbl["pt"]) < search_buffer:
                txt = lbl["val"]
                if "AP." in txt.upper() or "APT." in txt.upper(): continue

                match = area_pat.search(txt)
                if match:
                    try:
                        val = round(float(match.group(1).replace(",", ".")), 2)
                        if 1.0 <= val <= 250.0:
                            is_balcony = any(k in current_room.upper() for k in balcony_keywords)
                            rows.append({"Nr. Apartament": real_name, "Denumire": current_room, "Suprafață (mp)": val, "Tip": "Balcon" if is_balcony else "Utilă"})
                            if is_balcony: sum_balcony += val
                            else: sum_net += val
                            labels_to_draw.append(RoomLabel(txt, lbl["pt"], True))
                            current_room = "Încăpere"
                    except: continue
                else:
                    if len(txt) > 3 and not any(c.isdigit() for c in txt):
                        current_room = txt
                        labels_to_draw.append(RoomLabel(txt, lbl["pt"], False))

        final_results.append(ApartmentResult(
            index=0, name=real_name, polygon=apt["poly"], area_calc=apt["poly"].area / (1000000.0 if config.units == "mm" else 1.0),
            net_area=round(sum_net, 2), balcony_area=round(sum_balcony, 2), total_area=round(sum_net + sum_balcony, 2),
            areas_df=pd.DataFrame(rows).drop_duplicates(), all_room_labels=labels_to_draw
        ))
    return final_results