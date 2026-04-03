import ezdxf
import pandas as pd
import re
import io
import plotly.graph_objects as go
import numpy as np
from typing import List, Any
from dataclasses import dataclass
from shapely.geometry import Polygon, Point, LineString

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
    geometries: List[Any]

class ProcessorConfig:
    def __init__(self, reference_layer: str, units: str = "m"):
        self.reference_layer = reference_layer
        self.units = units
        self.scale = 1000.0 if units == "mm" else 1.0

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

def draw_all_layers_interactive(dxf_data: bytes, highlight_layer: str = None):
    stream = io.TextIOWrapper(io.BytesIO(dxf_data), encoding="utf-8", errors="replace")
    doc = ezdxf.read(stream)
    msp = doc.modelspace()
    fig = go.Figure()
    
    all_x, all_y = [], []
    
    for e in msp:
        items = [e]
        if e.dxftype() == "INSERT":
            try: items.extend(list(e.virtual_entities()))
            except: pass
            
        for item in items:
            pts = []
            lname = item.dxf.layer
            # Stabilim culoarea: Rosu daca e layerul selectat, altfel gri
            is_highlight = (highlight_layer and lname == highlight_layer)
            color = "#FF0000" if is_highlight else "#D3D3D3"
            width = 1.5 if is_highlight else 0.6
            opacity = 1.0 if is_highlight else 0.4

            if item.dxftype() == "LWPOLYLINE":
                pts = [(v[0], v[1]) for v in item.get_points()]
                if item.is_closed and pts: pts.append(pts[0])
            elif item.dxftype() == "LINE":
                pts = [(item.dxf.start.x, item.dxf.start.y), (item.dxf.end.x, item.dxf.end.y)]
            elif item.dxftype() in ("ARC", "CIRCLE"):
                center, radius = item.dxf.center, item.dxf.radius
                angles = np.linspace(np.radians(item.dxf.start_angle), np.radians(item.dxf.end_angle), 30) if item.dxftype() == "ARC" else np.linspace(0, 2*np.pi, 50)
                pts = [(center.x + radius * np.cos(a), center.y + radius * np.sin(a)) for a in angles]

            if pts:
                x, y = zip(*pts)
                all_x.extend(x); all_y.extend(y)
                fig.add_trace(go.Scatter(x=x, y=y, mode='lines', 
                                         line=dict(color=color, width=width), 
                                         opacity=opacity, hoverinfo='text', text=f"Layer: {lname}", showlegend=False))

    if all_x and all_y:
        x_min, x_max, y_min, y_max = min(all_x), max(all_x), min(all_y), max(all_y)
        dx, dy = (x_max - x_min)*0.05, (y_max - y_min)*0.05
        fig.update_xaxes(range=[x_min-dx, x_max+dx], visible=False)
        fig.update_yaxes(range=[y_min-dy, y_max+dy], visible=False, scaleanchor="x", scaleratio=1)
    
    fig.update_layout(plot_bgcolor="white", margin=dict(l=0, r=0, t=0, b=0), dragmode='pan')
    return fig

def process_dxf_bytes(dxf_data: bytes, config: ProcessorConfig) -> List[ApartmentResult]:
    stream = io.TextIOWrapper(io.BytesIO(dxf_data), encoding="utf-8", errors="replace")
    doc = ezdxf.read(stream)
    msp = doc.modelspace()
    
    apts_raw = []
    for p in msp.query(f'LWPOLYLINE[layer=="{config.reference_layer}"]'):
        if p.is_closed and len(p) >= 3:
            poly = Polygon([(v[0], v[1]) for v in p.get_points()])
            if poly.is_valid and poly.area > 0.1:
                apts_raw.append({"poly": poly, "temp_name": f"Unitate_{len(apts_raw)+1}"})
    
    if not apts_raw: return []

    raw_geoms, raw_labels = [], []
    for e in msp:
        items = [e]
        if e.dxftype() == "INSERT":
            try: items.extend(list(e.virtual_entities()))
            except: pass
        for it in items:
            if it.dxftype() in ("LWPOLYLINE", "LINE", "ARC", "CIRCLE"):
                try:
                    if it.dxftype() == "LWPOLYLINE": pts = [(v[0], v[1]) for v in it.get_points()]
                    elif it.dxftype() == "LINE": pts = [(it.dxf.start.x, it.dxf.start.y), (it.dxf.end.x, it.dxf.end.y)]
                    else: continue
                    raw_geoms.append(LineString(pts))
                except: continue
            if it.dxftype() in ("TEXT", "MTEXT", "ATTRIB", "DIMENSION"):
                val = _entity_text_value(it)
                if len(val) > 1:
                    pos = it.dxf.defpoint if it.dxftype() == "DIMENSION" else it.dxf.insert
                    raw_labels.append({"val": val, "pt": Point(pos.x, pos.y)})

    final_results = []
    area_pat = re.compile(r"(\d+[.,]\d+)")
    for apt in apts_raw:
        apt_poly = apt["poly"]; internal_lines = []; labels_to_draw = []
        rows, real_name, current_room = [], apt["temp_name"], "Încăpere"
        
        for g in raw_geoms:
            if apt_poly.intersects(g):
                inter = g.intersection(apt_poly)
                if not inter.is_empty:
                    if inter.geom_type == 'LineString': internal_lines.append(list(inter.coords))
                    elif inter.geom_type == 'MultiLineString':
                        for seg in inter.geoms: internal_lines.append(list(seg.coords))

        for lbl in raw_labels:
            if apt_poly.buffer(0.1).contains(lbl["pt"]):
                txt = lbl["val"]
                if "AP." in txt.upper():
                    real_name = txt.split("S=")[0].strip()
                    labels_to_draw.append(RoomLabel(txt, lbl["pt"], False))
                else:
                    match = area_pat.search(txt)
                    if match:
                        rows.append({"Nr.": real_name, "D": current_room, "S": float(match.group(1).replace(",", "."))})
                        labels_to_draw.append(RoomLabel(txt, lbl["pt"], True))
                        current_room = "Încăpere"
                    elif not any(c.isdigit() for c in txt):
                        current_room = txt
                        labels_to_draw.append(RoomLabel(txt, lbl["pt"], False))

        final_results.append(ApartmentResult(
            index=0, name=real_name, polygon=apt_poly, area_calc=apt_poly.area / (config.scale**2),
            net_area=0, balcony_area=0, total_area=0,
            areas_df=pd.DataFrame(rows).drop_duplicates(), all_room_labels=labels_to_draw,
            geometries=internal_lines
        ))
    return final_results