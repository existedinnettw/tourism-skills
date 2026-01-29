import argparse
import json
import os
from typing import List, Optional, Union
from pydantic import TypeAdapter
import os as _os
import asyncio
import googlemaps
from timed_geo_visual.model import _Event_render, _Event
from src.timed_geo_visual.geocode_osm import _geocode_with_osm
from src.timed_geo_visual.geocode_google import _geocode_with_google


async def _render_html(
    events: List[_Event_render], title: str = "Timed Geo Visual"
) -> str:
    # Use Pydantic TypeAdapter to serialize models to JSON (handles datetimes)
    events_json = TypeAdapter(List[Union[_Event_render, _Event_render]]).dump_json(
        events
    )
    # Ensure non-ASCII characters are preserved by re-dumping with ensure_ascii=False
    parsed = json.loads(events_json)
    events_json = json.dumps(parsed, ensure_ascii=False)

    filepath = os.path.join(os.path.dirname(__file__), "template.html")
    with open(filepath, "r", encoding="utf-8") as file:
        html_template = file.read()
    html = html_template.replace("__EVENTS_JSON__", events_json).replace(
        "__TITLE__", title
    )
    return html


# --- refactored helpers ---


def _parse_cli(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a timed geo visual map from a JSON itinerary"
    )
    parser.add_argument(
        "--input", "-i", required=True, help="Path to JSON itinerary file"
    )
    parser.add_argument(
        "--output", "-o", required=True, help="Path to output HTML file"
    )
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


def _load_events(input_path: str) -> List[_Event]:
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Parse into Pydantic models; allow exceptions to surface to the caller
    return TypeAdapter(List[_Event]).validate_python(data)


def _should_use_google(args: argparse.Namespace) -> bool:
    return args.geocoder == "google" or (
        args.geocoder == "auto" and _os.getenv("TIMED_GEO_USE_GOOGLE") == "1"
    )


async def _main_async(argv: Optional[List[str]] = None) -> None:
    args = _parse_cli(argv)

    input_path = args.input
    output_path = args.output

    if not os.path.exists(input_path):
        raise SystemExit(f"Input file not found: {input_path}")

    events = _load_events(input_path)

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
    events_render: List[_Event_render] = [
        _Event_render.model_validate(e.model_dump()) for e in events
    ]
    if use_google and gm_client:
        print("Resolving locations using Google Maps Geocoding API")
        # run blocking Google geocoding in a thread to avoid blocking the event loop
        events_render = await asyncio.to_thread(_geocode_with_google, events, gm_client)

    if use_osm:
        print("Resolving locations using pyphoton client (Photon).")
        events_render = await _geocode_with_osm(events)

    html = await _render_html(
        events_render, title=f"Timed Geo Visual — {os.path.basename(input_path)}"
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote map to {output_path}")


def main(argv: Optional[List[str]] = None) -> None:
    """Synchronous entrypoint kept for CLI/tests; runs the async main via asyncio.

    When invoked as a module (python -m timed_geo_visual ...), callers should
    pass no argv so that argparse reads from sys.argv. Accepting ``None`` here
    preserves that behavior while still supporting tests that pass explicit
    argument lists.
    """
    return asyncio.run(_main_async(argv))
