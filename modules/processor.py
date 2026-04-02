import ezdxf
import pandas as pd
import re
import io
from typing import List
from dataclasses import dataclass
from shapely.geometry import Polygon, Point
import plotly.graph_objects as go

# --- STRUCTURI DE DATE ---

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
    all_room_labels: List[RoomLabel]

class ProcessorConfig:
    def __init__(self, reference_layer: str, units: str = "m", eps: float = 1e-6):
        self.reference_layer = reference_layer
        self.units = units
        self.scale = 1000.0 if units == "mm" else 1.0

# --- FUNCȚII DE UTILITATE ---

def _entity_text_value(e) -> str:
    """Extrage și curăță textul din entități DXF, reparând caracterele românești."""
    if e.dxftype() == "MTEXT":
        raw = e.plain_text()
    else:
        raw = getattr(e.dxf, "text", "")
    
    if not raw: return ""
    
    # Eliminăm codurile de formatare specifice AutoCAD/ArchiCAD
    clean = re.sub(r"\\P|\\{.*?\\}|\\{.*|\\}|\\f.*?|\\A.*|\\H.*|\\S.*|\\Q.*|\\W.*|\\T.*|\\C.*|;", " ", raw)
    
    # Mapare caractere românești codate
    replacements = {
        "\\U+0102": "Ă", "\\U+0103": "ă", "\\U+00CE": "Î", "\\U+00EE": "î",
        "\\U+0218": "Ș", "\\U+0219": "ș", "\\U+021A": "Ț", "\\U+021B": "ț",
        "\\U+00C2": "Â", "\\U+00E2": "â"
    }
    for code, char in replacements.items():
        clean = clean.replace(code, char)
    return clean.strip()

def draw_all_layers_interactive(dxf_data: bytes):
    """Generează previzualizarea Plotly interactivă cu scanare în blocuri."""
    stream = io.TextIOWrapper(io.BytesIO(dxf_data), encoding="utf-8", errors="replace")
    doc = ezdxf.read(stream)
    msp = doc.modelspace()
    fig = go.Figure()
    
    # 1. Desenăm poliliniile (gri mediu)
    for p in msp.query('LWPOLYLINE'):
        try:
            pts = [(v[0], v[1]) for v in p.get_points()]
            if pts:
                x, y = zip(*pts)
                if p.is_closed:
                    x = x + (x[0],)
                    y = y + (y[0],)
                fig.add_trace(go.Scatter(x=x, y=y, mode='lines', 
                                         line=dict(color='#A0A0A0', width=0.8), 
                                         hoverinfo='none', showlegend=False))
        except: continue
        
    # 2. Scanăm textele (inclusiv cele din Block-uri/Inserts)
    for e in msp:
        check_list = [e]
        if e.dxftype() == "INSERT":
            try:
                check_list.extend(list(e.virtual_entities()))
            except: pass

        for item in check_list:
            if item.dxftype() in ("TEXT", "MTEXT", "ATTRIB"):
                try:
                    txt = _entity_text_value(item)
                    if txt and len(txt) > 1 and "Arial" not in txt:
                        pos = item.dxf.insert
                        fig.add_trace(go.Scatter(
                            x=[pos.x], y=[pos.y], mode='text', 
                            text=[txt], textfont=dict(size=11, color="#000000"),
                            hoverinfo='text', showlegend=False
                        ))
                except: continue
        
    fig.update_layout(
        plot_bgcolor="white",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1),
        margin=dict(l=0, r=0, t=0, b=0),
        hovermode='closest', dragmode='pan'
    )
    return fig

# --- PROCESARE DATE ---

def process_dxf_bytes(dxf_data: bytes, config: ProcessorConfig) -> List[ApartmentResult]:
    stream = io.TextIOWrapper(io.BytesIO(dxf_data), encoding="utf-8", errors="replace")
    doc = ezdxf.read(stream)
    msp = doc.modelspace()
    
    # Găsim contururile
    apts_raw = []
    for p in msp.query(f'LWPOLYLINE[layer=="{config.reference_layer}"]'):
        if p.is_closed and len(p) >= 3:
            pts = [(v[0], v[1]) for v in p.get_points()]
            poly = Polygon(pts)
            if poly.is_valid and poly.area > 0.1:
                apts_raw.append({"poly": poly, "temp_name": f"Unitate_{len(apts_raw)+1}"})
    
    if not apts_raw: return []

    blacklist = {"GRESIE", "PARCHET", "ANTID", "LAMINAT", "BETON", "VOPSEA", "CIMENT", "CERAMIC", "LIMITA", "GOL", "PLACA", "H=", "HB="}
    balcony_keywords = {"BALCON", "LOGIE", "TERASA", "BALC", "LOG"}
    area_pat = re.compile(r"(\d+[.,]\d+)")
    search_buffer = 0.2 * config.scale # Buffer mic pentru precizie

    # Colectăm textele global (scanând și blocurile)
    all_labels_raw = []
    for e in msp:
        items = [e]
        if e.dxftype() == "INSERT":
            try: items.extend(list(e.virtual_entities()))
            except: pass
        for it in items:
            if it.dxftype() in ("TEXT", "MTEXT", "ATTRIB"):
                val = _entity_text_value(it)
                if len(val) < 2 or any(w in val.upper() for w in blacklist): continue
                all_labels_raw.append({"val": val, "pt": Point(it.dxf.insert.x, it.dxf.insert.y)})

    final_results = []
    for apt in apts_raw:
        rows, labels_to_draw, real_name, current_room = [], [], apt["temp_name"], "Încăpere"
        
        # 1. Identificăm Numele (AP. X)
        for lbl in all_labels_raw:
            if apt["poly"].contains(lbl["pt"]) or apt["poly"].distance(lbl["pt"]) < search_buffer:
                if "AP." in lbl["val"].upper() or "APT." in lbl["val"].upper():
                    real_name = lbl["val"].split("S=")[0].split("s=")[0].strip()
                    labels_to_draw.append(RoomLabel(lbl["val"], lbl["pt"], False))

        # 2. Extragem Camerele
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
            index=0, name=real_name, polygon=apt["poly"], 
            area_calc=apt["poly"].area / (config.scale**2),
            net_area=round(sum_net, 2), balcony_area=round(sum_balcony, 2), total_area=round(sum_net + sum_balcony, 2),
            areas_df=pd.DataFrame(rows).drop_duplicates(), all_room_labels=labels_to_draw
        ))
    return final_results