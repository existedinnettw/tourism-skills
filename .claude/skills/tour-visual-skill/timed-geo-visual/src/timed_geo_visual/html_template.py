
import json
from typing import Any, Dict, List

async def _render_html(
    events: List[Dict[str, Any]], title: str = "Timed Geo Visual"
) -> str:
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
    // Helpful debug: show resolved events in the console so developers can confirm coordinates are present
    if (typeof console !== 'undefined' && console.debug) console.debug('events', events);

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
      // Sidebar click is enhanced later once per-event markers are known; avoid referencing global markers[] here which may not map 1:1 to events
      container.appendChild(div);
    }

    (async function() {
      // Keep an index of markers per event to support start/end markers.
      const eventMarkers = [];
      for (let i = 0; i < events.length; i++) {
        const e = events[i];
        addEventToSidebar(e, i);
        eventMarkers[i] = [];

        // Legacy single-point
        if (e.lat && e.lon) {
          const marker = L.marker([e.lat, e.lon]).addTo(map);
          const title = e.display_name || e.location || '';
          marker.bindPopup(`<div><b>${title}</b><div>${e.start_time} → ${e.end_time}</div><div>${e.details || ''}</div></div>`);
          eventMarkers[i].push(marker);
          markers.push(marker);
        }

        // Start/end points (new model)
        if (e.start_lat && e.start_lon) {
          const marker = L.marker([e.start_lat, e.start_lon]).addTo(map);
          const title = e.start_location || e.display_name || e.location || 'Start';
          marker.bindPopup(`<div><b>Start: ${title}</b><div>${e.start_time} → ${e.end_time}</div><div>${e.details || ''}</div></div>`);
          eventMarkers[i].push(marker);
          markers.push(marker);
        }
        if (e.end_lat && e.end_lon) {
          const marker = L.marker([e.end_lat, e.end_lon]).addTo(map);
          const title = e.end_location || e.display_name || e.location || 'End';
          marker.bindPopup(`<div><b>End: ${title}</b><div>${e.start_time} → ${e.end_time}</div><div>${e.details || ''}</div></div>`);
          eventMarkers[i].push(marker);
          markers.push(marker);
        }

        // If both start and end coords exist, draw a connecting line (useful for transportation events)
        if (e.start_lat && e.start_lon && e.end_lat && e.end_lon) {
          try {
            const line = L.polyline([[e.start_lat, e.start_lon], [e.end_lat, e.end_lon]], {
              color: '#0077cc',
              weight: 2,
              opacity: 0.75,
              dashArray: '6 4'
            }).addTo(map);
            line.bindPopup(`<div><b>${e.display_name || e.location || ''}</b><div>${e.start_time} → ${e.end_time}</div><div>${e.details || ''}</div></div>`);
            eventMarkers[i].push(line);
          } catch (err) {
            console.warn('polyline draw failed', err);
          }
        }

        // If this event produced no markers, annotate the sidebar entry so users know this place has no exact coordinates
        if (eventMarkers[i].length === 0) {
          const evs = document.getElementById('events').children;
          const last = evs[evs.length - 1];
          if (last) {
            const span = document.createElement('div');
            span.style.fontSize = '90%';
            span.style.color = '#999';
            span.textContent = ' (no exact coordinates)';
            const loc = last.querySelector('.loc');
            if (loc) loc.appendChild(span);
          }
        }

        // Enhance sidebar click: focus the first marker for this event (if any)
        (function(idx){
          const ev = document.getElementById('events').children[idx];
          if (ev) {
            ev.onclick = () => {
              const mlist = eventMarkers[idx] || [];
              if (mlist.length > 0) {
                try {
                  map.setView(mlist[0].getLatLng(), 14);
                  mlist[0].openPopup();
                } catch (err) { console.warn('focus fail', err); }
              }
            };
          }
        })(i);
      }

      // wire up controls
      document.getElementById('fit-btn').onclick = () => {
          // Build a layer list from all eventMarkers (markers + lines) so fit includes polylines
          const layers = [];
          for (let arr of eventMarkers) {
            if (arr && arr.length > 0) layers.push(...arr);
          }
          if (layers.length > 0) {
            const group = L.featureGroup(layers);
            try { map.fitBounds(group.getBounds().pad(0.2)); } catch (err) { console.warn('fit bounds failed', err); }
          }
      };

      // if we placed markers or lines, fit map bounds to them by default
      const allLayers = [];
      for (let arr of eventMarkers) { if (arr && arr.length > 0) allLayers.push(...arr); }
      if (allLayers.length > 0) {
        const group = L.featureGroup(allLayers);
        map.fitBounds(group.getBounds().pad(0.2));
      }
    })();
  </script>
</body>
</html>
"""
    html = html_template.replace("__EVENTS_JSON__", events_json).replace(
        "__TITLE__", title
    )
    return html

