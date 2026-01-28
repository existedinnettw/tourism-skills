import tempfile
import os
import json
from timed_geo_visual import main


def test_cli_writes_html():
    refs = os.path.join(os.path.dirname(__file__), '..', 'references', 'planned-KHH-NGO-CTS.json')
    refs = os.path.abspath(refs)
    assert os.path.exists(refs)

    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'out.html')
        main(['--input', refs, '--output', out])
        assert os.path.exists(out)
        content = open(out, 'r', encoding='utf-8').read()
        assert '<div id="map">' in content
        # ensure a known location from the sample appears in the embedded events
        assert 'Nabana no Sato' in content or 'Nabana' in content
        # ensure the tile URL uses proper Leaflet placeholders
        assert 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png' in content
        # new UI controls: show all and cycle
        assert 'id="fit-btn"' in content and 'id="scan-btn"' in content and 'id="scan-interval"' in content
