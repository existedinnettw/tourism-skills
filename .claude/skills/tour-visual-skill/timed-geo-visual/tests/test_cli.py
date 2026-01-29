import types
import pytest
import tempfile
import os
import json
import pyphoton
from pydantic import TypeAdapter
from timed_geo_visual.timed_geo_visual import main, _main_async
from timed_geo_visual import timed_geo_visual
from timed_geo_visual.model import _PendingItem, _Event
from timed_geo_visual.geocode_osm import _build_pending


@pytest.mark.timeout(10)
def test_cli_writes_html():
    refs = os.path.join(os.path.dirname(__file__), "planned-KHH-NGO-CTS.json")
    refs = os.path.abspath(refs)
    assert os.path.exists(refs)

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out.html")
        # Use explicit 'none' geocoder to avoid network calls in the default test run
        main(["--input", refs, "--output", out, "--geocoder", "none"])
        assert os.path.exists(out)
        content = open(out, "r", encoding="utf-8").read()
        assert '<div id="map">' in content
        # ensure the tile URL uses proper Leaflet placeholders
        assert "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" in content
        # no client-side Nominatim geocoder anymore (we pre-resolve locations or use defaults)
        assert "nominatim.openstreetmap.org" not in content
        # new UI controls: show all and cycle
        assert (
            'id="fit-btn"' in content
            and 'id="scan-btn"' in content
            and 'id="scan-interval"' in content
        )


@pytest.mark.timeout(10)
def test_cli_with_no_geocoder():
    refs = os.path.join(os.path.dirname(__file__), "planned-KHH-NGO-CTS.json")
    refs = os.path.abspath(refs)
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out2.html")
        # explicit 'none' geocoder should run without attempting server-side google scraping
        main(["--input", refs, "--output", out, "--geocoder", "none"])
        assert os.path.exists(out)
        content = open(out, "r", encoding="utf-8").read()
        # the client script should only create markers when coords are known
        assert "if (pLat && pLon)" in content
        # and unresolved locations should be noted in the sidebar
        assert "(no exact coordinates)" in content


def test_build_pending_returns_pydantic_items():
    # verify the new helper returns typed objects for events needing geocoding
    refs = os.path.join(os.path.dirname(__file__), "planned-KHH-NGO-CTS.json")
    refs = os.path.abspath(refs)
    with open(refs, "r", encoding="utf-8") as f:
        events = json.load(f)

    models = TypeAdapter(list[_Event]).validate_python(events)
    pending = _build_pending(models)
    assert isinstance(pending, list)
    assert pending, "expected at least one pending item from sample events"
    assert all(isinstance(p, _PendingItem) for p in pending)
    # check that required attributes exist and are of expected types
    for p in pending:
        assert isinstance(p.query, str)
        assert isinstance(p.src_field, str)
        assert isinstance(p.lat_field, str)
        assert isinstance(p.lon_field, str)
