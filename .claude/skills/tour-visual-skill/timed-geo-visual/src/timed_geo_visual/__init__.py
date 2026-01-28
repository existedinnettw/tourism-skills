import argparse
import json
import os
import textwrap
from datetime import datetime
from typing import Any, Dict, List


def _render_html(events: List[Dict[str, Any]], title: str = "Timed Geo Visual") -> str:
    events_json = json.dumps(events, ensure_ascii=False)
    html_template = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>__TITLE__</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    body { margin: 0; font-family: system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial; }
    #wrap { display: flex; height: 100vh; }
    #sidebar { width: 360px; overflow: auto; border-right: 1px solid #ddd; padding: 12px; box-sizing: border-box; }
    #map { flex: 1; }
    .event { padding: 8px; border-bottom: 1px solid #eee; cursor: pointer; }
    .event:hover { background: #fafafa; }
    .time { font-weight: 600; color: #333; }
    .loc { color: #555; }
  </style>
</head>
<body>
  <div id="wrap">
    <div id="sidebar">
      <h2>Itinerary</h2>
      <div style="margin-bottom:8px">
        <button id="fit-btn">Show all</button>
        <button id="scan-btn">Cycle markers</button>
        <label style="margin-left:6px;font-size:90%">interval(ms): <input id="scan-interval" type="number" value="0" style="width:72px" /></label>
      </div>
      <div id="events"></div>
    </div>
    <div id="map"></div>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    if (location && location.protocol === 'file:') {
      console.warn('Note: running this file via file:// may block network requests (CORS). Serve over http to allow geocoding and map tiles. Example: python -m http.server 8000');
    }
    const events = __EVENTS_JSON__;

    const map = L.map('map').setView([35.0, 136.5], 5);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap contributors'
    }).addTo(map);

    const markers = [];

    function addEventToSidebar(e, idx) {
      const container = document.getElementById('events');
      const div = document.createElement('div');
      div.className = 'event';
      div.innerHTML = `<div class="time">${e.start_time} → ${e.end_time}</div><div class="loc">${e.location}</div><div class="details">${(e.details || '')}</div>`;
      div.onclick = () => { if (markers[idx]) { map.setView(markers[idx].getLatLng(), 14); markers[idx].openPopup(); } };
      container.appendChild(div);
    }

    async function geocode(query) {
      const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}`;
      try {
        const resp = await fetch(url, {headers:{'Accept-Language':'en'}});
        const data = await resp.json();
        if (data && data.length) {
          const res = {lat: parseFloat(data[0].lat), lon: parseFloat(data[0].lon), display_name: data[0].display_name};
          console.debug('Geocode result', query, res.display_name, res.lat, res.lon);
          return res;
        }
      } catch (err) {
        console.warn('Geocode failed', query, err);
      }
      return null;
    }

    (async function() {
      for (let i = 0; i < events.length; i++) {
        const e = events[i];
        addEventToSidebar(e, i);
        // no throttle: fire geocode requests immediately
        let result = await geocode(e.location);
        if (!result && e.details) result = await geocode(e.details);
        const markerLatLng = result ? [result.lat, result.lon] : [35.0, 136.5];
        const marker = L.marker(markerLatLng).addTo(map);
        marker.bindPopup(`<div><b>${e.location}</b><div>${e.start_time} → ${e.end_time}</div><div>${e.details || ''}</div></div>`);
        markers.push(marker);
      }

      // wire up controls
      document.getElementById('fit-btn').onclick = () => {
        if (markers.length > 0) {
          const group = L.featureGroup(markers);
          map.fitBounds(group.getBounds().pad(0.2));
        }
      };

      document.getElementById('scan-btn').onclick = () => {
        const iv = parseInt(document.getElementById('scan-interval').value || '0', 10);
        for (let j = 0; j < markers.length; j++) {
          const run = () => {
            try {
              map.setView(markers[j].getLatLng(), 14);
              markers[j].openPopup();
            } catch (e) { console.warn('scan fail', e); }
          };
          if (iv > 0) setTimeout(run, j * iv); else setTimeout(run, 0);
        }
      };

      // if we placed markers, fit map bounds to them by default
      if (markers.length > 0) {
        const group = L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.2));
      }
    })();
  </script>
</body>
</html>
"""
    html = html_template.replace("__EVENTS_JSON__", events_json).replace("__TITLE__", title)
    return html


def main(argv: List[str] = None) -> None:
    parser = argparse.ArgumentParser(description="Render a timed geo visual map from a JSON itinerary")
    parser.add_argument("--input", "-i", required=True, help="Path to JSON itinerary file")
    parser.add_argument("--output", "-o", required=True, help="Path to output HTML file")
    args = parser.parse_args(argv)

    input_path = args.input
    output_path = args.output

    if not os.path.exists(input_path):
        raise SystemExit(f"Input file not found: {input_path}")

    with open(input_path, 'r', encoding='utf-8') as f:
        events = json.load(f)

    # Normalize times to readable format if present
    for e in events:
        if 'start_time' in e:
            try:
                e['start_time'] = datetime.fromisoformat(e['start_time']).isoformat()
            except Exception:
                pass
        if 'end_time' in e:
            try:
                e['end_time'] = datetime.fromisoformat(e['end_time']).isoformat()
            except Exception:
                pass

    html = _render_html(events, title=f"Timed Geo Visual — {os.path.basename(input_path)}")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Wrote map to {output_path}")
