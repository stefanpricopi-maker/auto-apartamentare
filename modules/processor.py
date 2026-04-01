from __future__ import annotations

import io
import math
import re
import zipfile
from dataclasses import dataclass
from typing import Iterable, Optional

import ezdxf
import pandas as pd
from ezdxf.entities import DXFEntity
from shapely.geometry import LineString, Point, Polygon


DEFAULT_REFERENCE_LAYER = "CONTUR_APARTAMENT"


@dataclass(frozen=True)
class ProcessorConfig:
    reference_layer: str = DEFAULT_REFERENCE_LAYER
    excluded_layers: tuple[str, ...] = ()
    eps: float = 1e-6


@dataclass(frozen=True)
class ApartmentResult:
    index: int
    name: str
    dxf_bytes: bytes
    areas_df: pd.DataFrame


def process_dxf_bytes(
    dxf_bytes: bytes,
    *,
    config: ProcessorConfig = ProcessorConfig(),
) -> list[ApartmentResult]:
    # ezdxf expects a text stream for ASCII DXF (most common case).
    # We accept bytes from upload and decode via a TextIO wrapper.
    text_stream = io.TextIOWrapper(io.BytesIO(dxf_bytes), encoding="utf-8", errors="replace")
    doc = ezdxf.read(text_stream)
    msp = doc.modelspace()

    contours = _collect_apartment_contours(msp, config.reference_layer)
    if not contours:
        raise ValueError(
            f"No closed contours found on layer '{config.reference_layer}'. "
            "Draw closed polylines for each apartment."
        )

    results: list[ApartmentResult] = []
    for idx, contour_entity in enumerate(contours, start=1):
        polygon = _entity_to_polygon(contour_entity, eps=config.eps)
        if polygon is None or polygon.is_empty:
            continue

        apt_name = _guess_apartment_name(msp, polygon, fallback=f"Ap_{idx}")
        included = _select_entities_for_apartment(
            msp,
            polygon,
            reference_layer=config.reference_layer,
            excluded_layers=set(config.excluded_layers),
            eps=config.eps,
        )

        apt_doc = _build_apartment_doc(doc, included)
        out_text = io.StringIO()
        apt_doc.write(out_text)
        out_bytes = out_text.getvalue().encode("utf-8")

        areas_df = _extract_areas_table(msp, polygon, apartment_name=apt_name)

        results.append(
            ApartmentResult(
                index=idx,
                name=apt_name,
                dxf_bytes=out_bytes,
                areas_df=areas_df,
            )
        )

    return results


def build_export_zip(results: list[ApartmentResult]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        all_rows: list[pd.DataFrame] = []

        for r in results:
            safe_name = _safe_filename(r.name)
            zf.writestr(f"{safe_name}.dxf", r.dxf_bytes)

            if not r.areas_df.empty:
                all_rows.append(r.areas_df)

        if all_rows:
            full = pd.concat(all_rows, ignore_index=True)
            xlsx_bytes = _df_to_xlsx_bytes(full)
            zf.writestr("tabel_suprafete.xlsx", xlsx_bytes)

    return buf.getvalue()


def _collect_apartment_contours(msp, reference_layer: str) -> list[DXFEntity]:
    contours: list[DXFEntity] = []
    for e in msp:
        if e.dxftype() in {"LWPOLYLINE", "POLYLINE"} and (e.dxf.layer or "") == reference_layer:
            if _is_closed_polyline(e):
                contours.append(e)
    return contours


def _is_closed_polyline(e: DXFEntity) -> bool:
    if e.dxftype() == "LWPOLYLINE":
        return bool(getattr(e, "closed", False))
    if e.dxftype() == "POLYLINE":
        return bool(getattr(e, "is_closed", False))
    return False


def _entity_to_polygon(e: DXFEntity, *, eps: float) -> Optional[Polygon]:
    pts = _polyline_points(e)
    if not pts or len(pts) < 3:
        return None
    if pts[0] != pts[-1]:
        pts = [*pts, pts[0]]
    poly = Polygon(pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    if eps > 0:
        poly = poly.buffer(eps)
    return poly


def _polyline_points(e: DXFEntity) -> list[tuple[float, float]]:
    if e.dxftype() == "LWPOLYLINE":
        return [(float(x), float(y)) for x, y, *_ in e.get_points("xy")]
    if e.dxftype() == "POLYLINE":
        return [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices()]
    return []


def _select_entities_for_apartment(
    msp,
    polygon: Polygon,
    *,
    reference_layer: str,
    excluded_layers: set[str],
    eps: float,
) -> list[DXFEntity]:
    """
    Implements spec 3.1:
    - Include if fully inside contour
    - OR on boundary / intersects / touches contour (common walls, entrance doors, etc.)
    Result: common walls appear in both adjacent apartments.
    """
    boundary = polygon.boundary
    selected: list[DXFEntity] = []

    for e in msp:
        layer = (getattr(e.dxf, "layer", "") or "").strip()
        if not layer:
            layer = "0"

        if layer == reference_layer:
            continue
        if layer in excluded_layers:
            continue

        geom = _entity_to_shapely(e, eps=eps)
        if geom is None or geom.is_empty:
            continue

        # Fast reject by bounding box
        if not _bbox_overlaps(polygon.bounds, geom.bounds, pad=eps):
            continue

        # 3.1: inside OR at boundary and intersects/touches
        if polygon.covers(geom) or geom.intersects(boundary):
            selected.append(e)

    return selected


def _bbox_overlaps(a, b, *, pad: float = 0.0) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (
        (ax2 + pad) < (bx1 - pad)
        or (bx2 + pad) < (ax1 - pad)
        or (ay2 + pad) < (by1 - pad)
        or (by2 + pad) < (ay1 - pad)
    )


def _entity_to_shapely(e: DXFEntity, *, eps: float):
    t = e.dxftype()
    try:
        if t == "LINE":
            s = e.dxf.start
            f = e.dxf.end
            return LineString([(float(s.x), float(s.y)), (float(f.x), float(f.y))])

        if t == "LWPOLYLINE":
            pts = [(float(x), float(y)) for x, y, *_ in e.get_points("xy")]
            if not pts:
                return None
            if getattr(e, "closed", False) and len(pts) >= 3:
                if pts[0] != pts[-1]:
                    pts = [*pts, pts[0]]
                return LineString(pts)
            return LineString(pts)

        if t == "POLYLINE":
            pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices()]
            if not pts:
                return None
            if getattr(e, "is_closed", False) and len(pts) >= 3:
                if pts[0] != pts[-1]:
                    pts = [*pts, pts[0]]
            return LineString(pts)

        if t in {"TEXT", "MTEXT"}:
            ins = e.dxf.insert
            return Point(float(ins.x), float(ins.y)).buffer(max(eps, 0.0))

        if t == "CIRCLE":
            c = e.dxf.center
            r = float(e.dxf.radius)
            return Point(float(c.x), float(c.y)).buffer(max(r, eps))

        if t == "ARC":
            c = e.dxf.center
            r = float(e.dxf.radius)
            a0 = math.radians(float(e.dxf.start_angle))
            a1 = math.radians(float(e.dxf.end_angle))
            pts = _sample_arc(float(c.x), float(c.y), r, a0, a1)
            return LineString(pts)

        if t == "INSERT":
            ins = e.dxf.insert
            return Point(float(ins.x), float(ins.y)).buffer(max(eps, 0.0))
    except Exception:
        return None

    # Unknown entity types: skip (or they will require deep-copy of dependent tables/blocks)
    return None


def _sample_arc(cx: float, cy: float, r: float, a0: float, a1: float) -> list[tuple[float, float]]:
    # normalize to a forward sweep
    if a1 < a0:
        a1 += 2 * math.pi
    sweep = max(a1 - a0, 0.0)
    steps = max(12, int(24 * sweep / (2 * math.pi)))
    pts: list[tuple[float, float]] = []
    for i in range(steps + 1):
        a = a0 + sweep * (i / steps)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _build_apartment_doc(source_doc: ezdxf.EzDxf, entities: Iterable[DXFEntity]) -> ezdxf.EzDxf:
    new_doc = ezdxf.new(dxfversion=source_doc.dxfversion)

    # Copy layers so entities keep styling. Skip built-in layer "0" (exists by default).
    for layer in source_doc.layers:
        name = layer.dxf.name
        if name == "0":
            continue
        if name in new_doc.layers:
            continue
        new_doc.layers.add(
            name=name,
            dxfattribs={
                "color": layer.color,
                "linetype": layer.dxf.linetype,
                "lineweight": layer.dxf.lineweight,
            },
        )

    msp = new_doc.modelspace()
    for e in entities:
        try:
            msp.add_entity(e.copy())
        except Exception:
            # Some entities (dimensions, leaders, block inserts with missing defs) may fail.
            continue

    return new_doc


def _guess_apartment_name(msp, polygon: Polygon, *, fallback: str) -> str:
    # Prefer any text fully inside contour; common conventions: "Ap 1", "AP1", "Apartament 1"
    texts: list[str] = []
    for e in msp:
        if e.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        pt = _entity_to_shapely(e, eps=0.0)
        if pt is None:
            continue
        if polygon.covers(pt):
            s = _entity_text_value(e)
            if s:
                texts.append(s)

    for s in texts:
        m = re.search(r"\b(ap|apt|apartament)\s*\.?\s*([0-9]+)\b", s, flags=re.IGNORECASE)
        if m:
            return f"Ap {m.group(2)}"

    return fallback


def _entity_text_value(e: DXFEntity) -> str:
    if e.dxftype() == "TEXT":
        return (e.dxf.text or "").strip()
    if e.dxftype() == "MTEXT":
        return (e.text or "").strip()
    return ""


def _extract_areas_table(msp, polygon: Polygon, *, apartment_name: str) -> pd.DataFrame:
    """
    Best-effort implementation of spec 4.2:
    scan text inside contour and look for patterns: [Room Name] + [value mp].
    """
    rows: list[dict] = []
    texts: list[str] = []

    for e in msp:
        if e.dxftype() not in {"TEXT", "MTEXT"}:
            continue
        pt = _entity_to_shapely(e, eps=0.0)
        if pt is None:
            continue
        if polygon.covers(pt):
            s = _entity_text_value(e)
            if s:
                texts.append(s)

    # Allow "Living 18.50", "Living: 18.50 mp", "18.50 mp Living"
    pat1 = re.compile(r"^\s*(?P<name>.+?)\s*[:\-]?\s*(?P<area>\d+(?:[.,]\d+)?)\s*(?:m2|mp)?\s*$", re.I)
    pat2 = re.compile(r"^\s*(?P<area>\d+(?:[.,]\d+)?)\s*(?:m2|mp)\s*(?P<name>.+?)\s*$", re.I)

    for t in texts:
        m = pat1.match(t) or pat2.match(t)
        if not m:
            continue
        name = (m.group("name") or "").strip()
        area_s = (m.group("area") or "").strip().replace(",", ".")
        try:
            area = float(area_s)
        except ValueError:
            continue
        if not name:
            continue
        rows.append(
            {
                "Nr. Apartament": apartment_name,
                "Denumire Încăpere": name,
                "Suprafață (mp)": area,
            }
        )

    df = pd.DataFrame(rows, columns=["Nr. Apartament", "Denumire Încăpere", "Suprafață (mp)"])
    if df.empty:
        return df

    total = float(df["Suprafață (mp)"].sum())
    df_total = pd.DataFrame(
        [
            {
                "Nr. Apartament": f"Total {apartment_name}",
                "Denumire Încăpere": "",
                "Suprafață (mp)": total,
            }
        ]
    )
    return pd.concat([df, df_total], ignore_index=True)


def _df_to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Suprafete")
    return bio.getvalue()


def _safe_filename(name: str) -> str:
    name = name.strip() or "apartament"
    name = re.sub(r"[^\w\-. ]+", "_", name, flags=re.UNICODE)
    name = re.sub(r"\s+", "_", name)
    return name[:120]

