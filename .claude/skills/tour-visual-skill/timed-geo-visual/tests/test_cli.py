import sys
import types
import pytest
import tempfile
import os
import json
import googlemaps
import pyphoton
from timed_geo_visual.timed_geo_visual import main, _main_async
from timed_geo_visual import timed_geo_visual


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
        # ensure a known location from the sample appears in the embedded events
        assert "Nabana no Sato" in content or "Nabana" in content
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
def test_osm_with_pyphoton(monkeypatch):
    refs = os.path.join(os.path.dirname(__file__), "planned-KHH-NGO-CTS.json")
    refs = os.path.abspath(refs)
    assert os.path.exists(refs)

    class FakePhotonClient:
        async def query(self, q, limit=1):
            # return a single fake feature with coords and a name
            return {
                "features": [
                    {
                        "geometry": {"coordinates": [120.999, 23.999]},
                        "properties": {"name": "FAKEPLACE", "country": "TW"},
                    }
                ]
            }

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out-osm-success.html")
        # Patch pyphoton.client.Photon to return our fake client instance
        monkeypatch.setattr(pyphoton, "client", types.SimpleNamespace(Photon=FakePhotonClient))
        timed_geo_visual.main(["--input", refs, "--output", out, "--geocoder", "osm"])
        assert os.path.exists(out)
        content = open(out, "r", encoding="utf-8").read()
        # The fake name should appear in the embedded events JSON
        assert "FAKEPLACE" in content


@pytest.mark.timeout(10)
@pytest.mark.asyncio
async def test_osm_with_pyphoton_async(monkeypatch):
    """Exercise the async pyphoton client path."""
    refs = os.path.join(os.path.dirname(__file__), "planned-KHH-NGO-CTS.json")
    refs = os.path.abspath(refs)
    assert os.path.exists(refs)

    class FakeAsyncPhotonClient:
        async def query(self, q, limit=1):
            # mimic async HTTP client returning JSON structure
            return {
                "features": [
                    {
                        "geometry": {"coordinates": [120.999, 23.999]},
                        "properties": {"name": "ASYNCPLACE", "country": "TW"},
                    }
                ]
            }

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out-osm-async.html")
        # Patch pyphoton.client.Photon to return our fake async client
        monkeypatch.setattr(pyphoton, "client", types.SimpleNamespace(Photon=FakeAsyncPhotonClient))
        await _main_async(["--input", refs, "--output", out, "--geocoder", "osm"])
        assert os.path.exists(out)
        content = open(out, "r", encoding="utf-8").read()
        # The fake async name should appear in the embedded events JSON
        assert "ASYNCPLACE" in content


@pytest.mark.timeout(10)
def test_osm_with_pyphoton_full_props(monkeypatch):
    """Ensure rich pyphoton properties are attached to events and coordinates are set."""
    refs = os.path.join(os.path.dirname(__file__), "planned-KHH-NGO-CTS.json")
    refs = os.path.abspath(refs)
    assert os.path.exists(refs)

    class FakePhotonClient:
        async def query(self, q, limit=1):
            return {
                "features": [
                    {
                        "geometry": {"coordinates": [136.6966916, 35.0975101]},
                        "properties": {
                            "name": "Bus to Nabana No Sato Park",
                            "postcode": "511-1126",
                            "city": "Kuwana",
                            "street": "Route Nagashima Station",
                            "state": "Mie Prefecture",
                            "osm_type": "N",
                            "osm_id": 10596542106,
                            "osm_key": "highway",
                            "osm_value": "bus_stop",
                        },
                    }
                ]
            }

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out-osm-fullprops.html")
        monkeypatch.setattr(pyphoton, "client", types.SimpleNamespace(Photon=FakePhotonClient))
        timed_geo_visual.main(["--input", refs, "--output", out, "--geocoder", "osm"])
        assert os.path.exists(out)
        content = open(out, "r", encoding="utf-8").read()
        # The resolved name and some properties should appear in the embedded events JSON
        assert "Bus to Nabana No Sato Park" in content
        assert "511-1126" in content
        assert "Kuwana" in content
        # Ensure coordinates were added (lat appears)
        assert "35.0975101" in content


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
        assert "if (e.lat && e.lon)" in content
        # and unresolved locations should be noted in the sidebar
        assert "(no exact coordinates)" in content
