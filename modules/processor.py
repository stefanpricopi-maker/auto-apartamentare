import ezdxf
import pandas as pd
import re
import io
from typing import List, Any
from dataclasses import dataclass
from shapely.geometry import Polygon, Point, LineString
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
    internal_geometries: List[Any] # Stocăm liniile interioare (pereți, uși etc.)

class ProcessorConfig:
    def __init__(self, reference_layer: str, units: str = "m"):
        self.reference_layer = reference_layer
        self.units = units
        self.scale = 1000.0 if units == "mm" else 1.0

# --- FUNCȚII AUXILIARE ---

def _entity_text_value(e) -> str:
    if e.dxftype() == "MTEXT":
        raw = e.plain_text()
    else:
        raw = getattr(e.dxf, "text", "")
    if not raw: return ""
    clean = re.sub(r"\\P|\\{.*?\\}|\\{.*|\\}|\\f.*?|\\A.*|\\H.*|\\S.*|\\Q.*|\\W.*|\\T.*|\\C.*|;", " ", raw)
    replacements = {"\\U+0102": "Ă", "\\U+0103": "ă", "\\U+00CE": "Î", "\\U+00EE": "î",
                    "\\U+0218": "Ș", "\\U+0219": "ș", "\\U+021A": "Ț", "\\U+021B": "ț",
                    "\\U+00C2": "Â", "\\U+00E2": "â"}
    for code, char in replacements.items():
        clean = clean.replace(code, char)
    return clean.strip()

def draw_all_layers_interactive(dxf_data: bytes):
    stream = io.TextIOWrapper(io.BytesIO(dxf_data), encoding="utf-8", errors="replace")
    doc = ezdxf.read(stream)
    msp = doc.modelspace()
    fig = go.Figure()
    
    for p in msp.query('LWPOLYLINE'):
        try:
            pts = [(v[0], v[1]) for v in p.get_points()]
            if pts:
                x, y = zip(*pts); 
                if p.is_closed: x, y = x + (x[0],), y + (y[0],)
                fig.add_trace(go.Scatter(x=x, y=y, mode='lines', line=dict(color='#A0A0A0', width=0.8), hoverinfo='none', showlegend=False))
        except: continue
    return fig

# --- PROCESARE GEOMETRIE ȘI RELEVEE ---

def process_dxf_bytes(dxf_data: bytes, config: ProcessorConfig) -> List[ApartmentResult]:
    stream = io.TextIOWrapper(io.BytesIO(dxf_data), encoding="utf-8", errors="replace")
    doc = ezdxf.read(stream)
    msp = doc.modelspace()
    
    # 1. Identificăm Contururile Apartamentelor
    apts_raw = []
    for p in msp.query(f'LWPOLYLINE[layer=="{config.reference_layer}"]'):
        if p.is_closed and len(p) >= 3:
            pts = [(v[0], v[1]) for v in p.get_points()]
            poly = Polygon(pts)
            if poly.is_valid and poly.area > 0.1:
                apts_raw.append({"poly": poly, "temp_name": f"Unitate_{len(apts_raw)+1}"})
    
    if not apts_raw: return []

    # 2. Colectăm Geometria și Textele din tot planul (explodând blocurile)
    all_geoms = []
    all_labels = []
    
    for e in msp:
        items = [e]
        if e.dxftype() == "INSERT":
            try: items.extend(list(e.virtual_entities()))
            except: pass
            
        for it in items:
            # Colectăm linii/polilinii pentru pereți
            if it.dxftype() in ("LWPOLYLINE", "LINE"):
                try:
                    if it.dxftype() == "LWPOLYLINE":
                        pts = [(v[0], v[1]) for v in it.get_points()]
                    else:
                        pts = [(it.dxf.start.x, it.dxf.start.y), (it.dxf.end.x, it.dxf.end.y)]
                    if len(pts) >= 2:
                        all_geoms.append({"type": "line", "coords": pts, "layer": it.dxf.layer})
                except: continue
            
            # Colectăm texte
            if it.dxftype() in ("TEXT", "MTEXT", "ATTRIB"):
                val = _entity_text_value(it)
                if len(val) > 1:
                    all_labels.append({"val": val, "pt": Point(it.dxf.insert.x, it.dxf.insert.y)})

    # 3. Alocăm geometria și textele fiecărui contur (Spatially)
    final_results = []
    blacklist = {"GRESIE", "PARCHET", "ANTID", "LIMITA", "GOL", "PLACA"}
    area_pat = re.compile(r"(\d+[.,]\d+)")

    for apt in apts_raw:
        internal_lines = []
        labels_to_draw = []
        rows, real_name, current_room = [], apt["temp_name"], "Încăpere"

        # Tăiem/Filtrăm liniile care sunt în interiorul apartamentului
        for g in all_geoms:
            ls = LineString(g["coords"])
            if apt["poly"].intersects(ls):
                # Putem chiar tăia linia exact pe contur pentru curățenie perfectă
                intersection = ls.intersection(apt["poly"])
                if not intersection.is_empty:
                    if intersection.geom_type == 'LineString':
                        internal_lines.append(list(intersection.coords))
                    elif intersection.geom_type == 'MultiLineString':
                        for line in intersection.geoms:
                            internal_lines.append(list(line.coords))

        # Filtrăm textele
        for lbl in all_labels:
            if apt["poly"].contains(lbl["pt"]):
                txt = lbl["val"]
                if any(w in txt.upper() for w in blacklist): continue
                
                # Identificare Nume Apartament
                if "AP." in txt.upper():
                    real_name = txt.split("S=")[0].strip()
                    labels_to_draw.append(RoomLabel(txt, lbl["pt"], False))
                else:
                    match = area_pat.search(txt)
                    if match:
                        val = float(match.group(1).replace(",", "."))
                        rows.append({"Nr. Apartament": real_name, "Denumire": current_room, "Suprafață (mp)": val})
                        labels_to_draw.append(RoomLabel(txt, lbl["pt"], True))
                        current_room = "Încăpere"
                    else:
                        if not any(c.isdigit() for c in txt):
                            current_room = txt
                            labels_to_draw.append(RoomLabel(txt, lbl["pt"], False))

        final_results.append(ApartmentResult(
            index=0, name=real_name, polygon=apt["poly"], 
            area_calc=apt["poly"].area / (config.scale**2),
            net_area=0.0, balcony_area=0.0, total_area=0.0,
            areas_df=pd.DataFrame(rows).drop_duplicates(), 
            all_room_labels=labels_to_draw,
            internal_geometries=internal_lines
        ))
    return final_results