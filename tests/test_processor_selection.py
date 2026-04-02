import io

import ezdxf
import pytest

from modules.processor import ProcessorConfig, process_dxf_bytes


def _doc_to_bytes(doc: ezdxf.EzDxf) -> bytes:
    sio = io.StringIO()
    doc.write(sio)
    return sio.getvalue().encode("utf-8")


def test_raises_when_no_contours_on_reference_layer():
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "WALLS"})

    with pytest.raises(ValueError):
        process_dxf_bytes(_doc_to_bytes(doc), config=ProcessorConfig(reference_layer="CONTUR_APARTAMENT"))


def test_common_wall_on_shared_boundary_included_in_both_apartments():
    doc = ezdxf.new()
    msp = doc.modelspace()

    # Two adjacent apartments:
    # A: square [0,0]-[10,10]
    # B: square [10,0]-[20,10]
    msp.add_lwpolyline(
        [(0, 0), (10, 0), (10, 10), (0, 10)],
        format="xy",
        close=True,
        dxfattribs={"layer": "CONTUR_APARTAMENT"},
    )
    msp.add_lwpolyline(
        [(10, 0), (20, 0), (20, 10), (10, 10)],
        format="xy",
        close=True,
        dxfattribs={"layer": "CONTUR_APARTAMENT"},
    )

    # Common wall exactly on the boundary x=10 from y=0..10
    msp.add_line((10, 0), (10, 10), dxfattribs={"layer": "WALLS"})

    # One wall strictly inside apartment A only
    msp.add_line((1, 1), (1, 9), dxfattribs={"layer": "WALLS"})

    results = process_dxf_bytes(_doc_to_bytes(doc), config=ProcessorConfig(reference_layer="CONTUR_APARTAMENT", eps=0.0))
    assert len(results) == 2
    assert all(r.entity_count >= 1 for r in results)

    # Parse each resulting DXF and check entity counts by location.
    docs = [
        ezdxf.read(io.TextIOWrapper(io.BytesIO(r.dxf_bytes), encoding="utf-8", errors="replace"))
        for r in results
    ]
    msps = [d.modelspace() for d in docs]

    def _lines(msp_):
        return [e for e in msp_ if e.dxftype() == "LINE" and (e.dxf.layer or "") == "WALLS"]

    lines = [_lines(x) for x in msps]

    # Both apartments should include the common wall line.
    def _is_common(line):
        s = line.dxf.start
        e = line.dxf.end
        return float(s.x) == 10.0 and float(e.x) == 10.0 and {float(s.y), float(e.y)} == {0.0, 10.0}

    assert any(_is_common(l) for l in lines[0])
    assert any(_is_common(l) for l in lines[1])

    # The inside-A wall should appear in only one result.
    def _is_inside_a(line):
        s = line.dxf.start
        e = line.dxf.end
        return float(s.x) == 1.0 and float(e.x) == 1.0 and {float(s.y), float(e.y)} == {1.0, 9.0}

    inside_counts = sum(any(_is_inside_a(l) for l in ls) for ls in lines)
    assert inside_counts == 1


def test_excluded_layers_are_ignored():
    doc = ezdxf.new()
    msp = doc.modelspace()

    msp.add_lwpolyline(
        [(0, 0), (10, 0), (10, 10), (0, 10)],
        format="xy",
        close=True,
        dxfattribs={"layer": "CONTUR_APARTAMENT"},
    )
    msp.add_line((5, 1), (5, 9), dxfattribs={"layer": "MOBILIER"})
    msp.add_line((6, 1), (6, 9), dxfattribs={"layer": "WALLS"})

    results = process_dxf_bytes(
        _doc_to_bytes(doc),
        config=ProcessorConfig(reference_layer="CONTUR_APARTAMENT", excluded_layers=("MOBILIER",), eps=0.0),
    )
    assert len(results) == 1

    out_doc = ezdxf.read(
        io.TextIOWrapper(io.BytesIO(results[0].dxf_bytes), encoding="utf-8", errors="replace")
    )
    out_msp = out_doc.modelspace()

    layers = [(e.dxftype(), (getattr(e.dxf, "layer", "") or "")) for e in out_msp]
    assert ("LINE", "WALLS") in layers
    assert ("LINE", "MOBILIER") not in layers

