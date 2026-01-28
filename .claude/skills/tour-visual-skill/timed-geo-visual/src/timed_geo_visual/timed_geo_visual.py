import argparse
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import time
import os as _os
import asyncio
import googlemaps
import pyphoton
from src.timed_geo_visual.html_template import _render_html
from functools import cache

async def _main_async(argv: List[str] = None) -> None:
    args = _parse_cli(argv)

    input_path = args.input
    output_path = args.output

    if not os.path.exists(input_path):
        raise SystemExit(f"Input file not found: {input_path}")

    events = _load_events(input_path)

    _normalize_event_times(events)
    _backfill_location(events)

    use_google = _should_use_google(args)

    gm_client = None
    if use_google:
        api_key = _os.getenv("GOOGLE_MAPS_API_KEY") or _os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print(
                "GOOGLE_MAPS_API_KEY not set; skipping Google geocoding. To enable, set env var GOOGLE_MAPS_API_KEY to your API key."
            )
            use_google = False
        else:
            try:
                gm_client = googlemaps.Client(key=api_key)
            except Exception as exc:
                print(
                    "googlemaps library not available, skipping server-side google geocoding:",
                    exc,
                )
                print("Hint: install with: pip install googlemaps")
                use_google = False

    use_osm = args.geocoder == "osm" or (args.geocoder == "auto" and not use_google)

    if use_google and gm_client:
        print("Resolving locations using Google Maps Geocoding API")
        # run blocking Google geocoding in a thread to avoid blocking the event loop
        await asyncio.to_thread(_geocode_with_google, events, gm_client)

    if use_osm:
        print("Resolving locations using pyphoton client (Photon).")
        await _geocode_with_osm(events)

    html = await _render_html(
        events, title=f"Timed Geo Visual — {os.path.basename(input_path)}"
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote map to {output_path}")


# --- refactored helpers ---

def _parse_cli(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a timed geo visual map from a JSON itinerary"
    )
    parser.add_argument("--input", "-i", required=True, help="Path to JSON itinerary file")
    parser.add_argument("--output", "-o", required=True, help="Path to output HTML file")
    parser.add_argument(
        "--geocoder",
        choices=["auto", "google", "osm", "none"],
        default="auto",
        help=(
            "Geocoder to use for resolving locations before rendering (google uses "
            "Google Maps Geocoding API; requires GOOGLE_MAPS_API_KEY)"
        ),
    )
    return parser.parse_args(argv)


def _load_events(input_path: str) -> List[Dict[str, Any]]:
    with open(input_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_event_times(events: List[Dict[str, Any]]) -> None:
    for e in events:
        if "start_time" in e:
            try:
                e["start_time"] = datetime.fromisoformat(e["start_time"]).isoformat()
            except Exception:
                pass
        if "end_time" in e:
            try:
                e["end_time"] = datetime.fromisoformat(e["end_time"]).isoformat()
            except Exception:
                pass


def _backfill_location(events: List[Dict[str, Any]]) -> None:
    for e in events:
        if "location" not in e:
            start = e.get("start_location")
            end = e.get("end_location")
            if start and end:
                e["location"] = f"{start} → {end}"
            elif start:
                e["location"] = start
            elif end:
                e["location"] = end


def _should_use_google(args: argparse.Namespace) -> bool:
    return args.geocoder == "google" or (args.geocoder == "auto" and _os.getenv("TIMED_GEO_USE_GOOGLE") == "1")


def _geocode_with_google(events: List[Dict[str, Any]], gm_client: object) -> None:
    for e in events:
        for src_field, lat_field, lon_field in (
            ("location", "lat", "lon"),
            ("start_location", "start_lat", "start_lon"),
            ("end_location", "end_lat", "end_lon"),
        ):
            # skip if already resolved
            if lat_field in e and lon_field in e:
                continue
            query = e.get(src_field) or e.get("details")
            if not query:
                continue
            try:
                results = gm_client.geocode(query, language="en")
            except Exception as exc:
                print("Google geocode failed for", query, exc)
                continue

            if results and isinstance(results, list):
                loc = results[0].get("geometry", {}).get("location")
                if loc and ("lat" in loc) and ("lng" in loc):
                    try:
                        e[lat_field] = float(loc["lat"])
                        e[lon_field] = float(loc["lng"])
                        if not e.get("display_name"):
                            e.setdefault("display_name", results[0].get("formatted_address"))
                        print(f"Resolved '{query}' -> {e[lat_field]},{e[lon_field]} ({src_field})")
                    except Exception:
                        print("Failed parsing coords in Google response for", query)
                else:
                    print("No coordinates found in Google response for", query)
            # small throttle to be nice and respect rate limits
            time.sleep(0.1)


@cache
def _cached_pyphoton_task(client, location: str):
    """Return an asyncio.Task for a pyphoton query, cached per (client, location).

    Caching the Task ensures repeated queries for the same location reuse the same
    in-flight or completed Task (safe to await multiple times).
    """
    loop = asyncio.get_running_loop()
    return loop.create_task(client.query(location, limit=1))


async def _geocode_with_osm(events: List[Dict[str, Any]]) -> None:
    # Helper: return a 'country' bias string from event or env, no hard-coded country names.
    def _preferred_country_for_event(ev: Dict[str, Any]) -> Optional[str]:
        # Prefer explicit fields first, then fall back to env var.
        if ev.get("country"):
            return str(ev.get("country"))
        if ev.get("country_code") and isinstance(ev.get("country_code"), str) and len(ev.get("country_code")) == 2:
            return str(ev.get("country_code"))
        env_cc = _os.getenv("TIMED_GEO_DEFAULT_COUNTRY")
        if env_cc:
            return env_cc
        return None

    client = pyphoton.client.Photon()

    pending = []  # list of dicts: {event, src_field, lat_field, lon_field, query, pref_cc}
    for e in events:
        for src_field, lat_field, lon_field in (
            ("location", "lat", "lon"),
            ("start_location", "start_lat", "start_lon"),
            ("end_location", "end_lat", "end_lon"),
        ):
            if lat_field in e and lon_field in e:
                continue
            query = e.get(src_field) or e.get("details")
            if not query:
                continue
            pref_cc = _preferred_country_for_event(e)
            p_query = query if not pref_cc else f"{query}, {pref_cc}"
            pending.append(
                {
                    "event": e,
                    "src_field": src_field,
                    "lat_field": lat_field,
                    "lon_field": lon_field,
                    "query": p_query,
                    "pref_cc": pref_cc,
                }
            )

    if pending and client is not None:
        # concurrency control
        max_conc = int(_os.getenv("TIMED_GEO_PHOTON_CONCURRENCY", "8"))
        sem = asyncio.Semaphore(max_conc)

        async def _run_one(item):
            async with sem:
                location = item["query"]
                try:
                    print("Querying pyphoton for", location)
                    task = _cached_pyphoton_task(client, location)
                    return await task
                except Exception as exc:
                    print("pyphoton query failed for", location, exc)
                    return exc

        tasks = [asyncio.create_task(_run_one(item)) for item in pending]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Apply results back to events
        for item, resp in zip(pending, results):
            query = item["query"]
            e = item["event"]
            lat_field = item["lat_field"]
            lon_field = item["lon_field"]
            pref_cc = item["pref_cc"]

            if isinstance(resp, Exception):
                print("pyphoton search failed for", query, resp)
                continue

            features = None
            if isinstance(resp, dict):
                features = resp.get("features")
            elif isinstance(resp, list):
                features = resp
            else:
                features = getattr(resp, "features", None)

            if not features:
                continue

            feat = features[0]
            coords = feat.get("geometry", {}).get("coordinates")
            props = feat.get("properties", {})
            if coords and len(coords) >= 2:
                country_ok = True
                if pref_cc and isinstance(props, dict):
                    c = (
                        props.get("country")
                        or props.get("countrycode")
                        or props.get("country_code")
                    )
                    if isinstance(c, str) and pref_cc.lower() not in c.lower():
                        country_ok = False
                if country_ok:
                    try:
                        e[lat_field] = float(coords[1])
                        e[lon_field] = float(coords[0])
                        if not e.get("display_name"):
                            e.setdefault("display_name", props.get("name") or props.get("osm_value"))
                        print(
                            f"Resolved '{query}' -> {e[lat_field]},{e[lon_field]} ({item['src_field']} via pyphoton)"
                        )
                    except Exception:
                        print("Failed parsing coords in pyphoton response for", query)


def main(argv: List[str] = None) -> None:
    """Synchronous entrypoint kept for CLI/tests; runs the async main via asyncio."""
    return asyncio.run(_main_async(argv))
