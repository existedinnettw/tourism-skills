import pyphoton
from pyphoton.models import Location
from timed_geo_visual.model import _Event, _Event_render, _Feature, _Properties, _PendingItem
from functools import cache
from typing import List, Optional
from pydantic import ValidationError, TypeAdapter
import asyncio
import os as _os


@cache
def _cached_pyphoton_task(client: pyphoton.client.Photon, location: str):
    """Return an asyncio.Task for a pyphoton query, cached per (client, location).

    Caching the Task ensures repeated queries for the same location reuse the same
    in-flight or completed Task (safe to await multiple times).
    """
    loop = asyncio.get_running_loop()
    return loop.create_task(client.query(location, limit=1))


def _build_pending(events: List[_Event]) -> List[_PendingItem]:
    """Return a list of _PendingItem objects for events that need geocoding.

    This extracts the logic previously embedded inline and makes it easy to
    test and reason about.
    """

    def _preferred_country_for_event(ev: _Event) -> Optional[str]:
        # same logic as the local helper inside _geocode_with_osm
        if getattr(ev, "country", None):
            return str(getattr(ev, "country"))
        cc = getattr(ev, "country_code", None)
        if cc and isinstance(cc, str) and len(cc) == 2:
            return str(cc)
        env_cc = _os.getenv("TIMED_GEO_DEFAULT_COUNTRY")
        if env_cc:
            return env_cc
        return None

    pending: List[_PendingItem] = []
    for e in events:
        for src_field, lat_field, lon_field in (
            ("location", "start_lat", "start_lon"),
            ("start_location", "start_lat", "start_lon"),
            ("end_location", "end_lat", "end_lon"),
        ):
            if getattr(e, lat_field, None) is not None and getattr(e, lon_field, None) is not None:
                continue
            query = getattr(e, src_field, None) or getattr(e, "details", None)
            if not query:
                continue
            pref_cc = _preferred_country_for_event(e)
            p_query = query if not pref_cc else f"{query}, {pref_cc}"
            # Use model_construct to avoid re-validating/copying the event dict
            # and ensure we keep a reference to the original event object so that
            # later mutations affect the original events list.
            pending.append(
                _PendingItem.model_construct(
                    event=e,
                    src_field=src_field,
                    lat_field=lat_field,
                    lon_field=lon_field,
                    query=p_query,
                    pref_cc=pref_cc,
                )
            )
    return pending


def _apply_location_like(obj, e, lat_field, lon_field, query, src_field, tag="pyphoton Location"):
    """Apply a location-like object (has latitude/longitude and common properties) to an event.

    Returns True if coordinates were successfully applied, False otherwise.
    """
    try:
        lat = getattr(obj, "latitude", None)
        lon = getattr(obj, "longitude", None)
        if lat is None or lon is None:
            return False
        setattr(e, lat_field, float(lat))
        setattr(e, lon_field, float(lon))
        # Append resolved name into `details` so rendered models don't need extra fields
        name = getattr(obj, "name", None)
        if name:
            if getattr(e, "details", None):
                if name not in e.details:
                    e.details = f"{e.details} ({name})"
            else:
                e.details = str(name)
        print(
            f"Resolved '{query}' -> {getattr(e, lat_field)},{getattr(e, lon_field)} ({src_field} via {tag})"
        )
        return True
    except Exception:
        print("Failed parsing coords in pyphoton Location for", query)
        return False


async def _geocode_with_osm(events: List[_Event]) -> List[_Event_render]:
    """Resolve locations using pyphoton and return events prepared for rendering.

    Operates on shallow copies of the input models and returns a list of
    `_Event_render` models where coordinates (lat/lon, start_lat/start_lon,
    end_lat/end_lon) and common address properties have been added where
    available. The original input models are not mutated.
    """
    client = pyphoton.client.Photon()

    # Work on shallow model copies so we don't mutate the caller's data
    new_events = [e.model_copy(deep=False) for e in events]

    # Build typed pending items referencing models to be mutated
    pending = _build_pending(new_events)

    if pending and client is not None:
        # concurrency control
        max_conc = int(_os.getenv("TIMED_GEO_PHOTON_CONCURRENCY", "4"))
        sem = asyncio.Semaphore(max_conc)

        async def _run_one(item: _PendingItem):
            async with sem:
                try:
                    task = _cached_pyphoton_task(client, item.query)
                    return await task
                except Exception as exc:
                    print("pyphoton query failed for", item.query, exc)
                    return exc

        tasks = [asyncio.create_task(_run_one(item)) for item in pending]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Apply results back to events (models)
        for item, resp in zip(pending, results):
            query = item.query
            e = item.event
            lat_field = item.lat_field
            lon_field = item.lon_field

            if isinstance(resp, Exception):
                print("pyphoton search failed for", query, resp)
                continue

            # Handle pyphoton Location objects directly
            if isinstance(resp, Location):
                applied = _apply_location_like(resp, e, lat_field, lon_field, query, item.src_field)
                if not applied:
                    print("No coordinates found on pyphoton Location for", query)
                continue

            if isinstance(resp, list) and resp and isinstance(resp[0], Location):
                applied = _apply_location_like(
                    resp[0],
                    e,
                    lat_field,
                    lon_field,
                    query,
                    item.src_field,
                    tag="pyphoton Location list",
                )
                if not applied:
                    print("No coordinates found on first pyphoton Location for", query)
                continue

            # Handle feature dicts/lists (typical async client returns)
            features = None
            if isinstance(resp, dict):
                features = resp.get("features")
            elif isinstance(resp, list):
                features = resp

            if not features:
                continue

            # Normalize features via pydantic TypeAdapter to ensure predictable shapes
            try:
                feats = TypeAdapter(List[_Feature]).validate_python(features)
            except ValidationError as ve:
                print("Failed parsing pyphoton feature(s) for", query, ve)
                continue

            if not feats:
                continue

            feat = feats[0]
            coords = None
            props = feat.properties or _Properties()
            if feat.geometry and getattr(feat.geometry, "coordinates", None):
                coords = feat.geometry.coordinates

            if coords and len(coords) >= 2:
                country_ok = True
                if item.pref_cc:
                    c = props.country or props.countrycode or props.country_code
                    if isinstance(c, str) and item.pref_cc.lower() not in c.lower():
                        country_ok = False
                if country_ok:
                    try:
                        setattr(e, lat_field, float(coords[1]))
                        setattr(e, lon_field, float(coords[0]))
                        # Append resolved name into details (avoid adding extra model fields)
                        name = props.name or props.osm_value or props.osm_key
                        if name:
                            if getattr(e, "details", None):
                                if name not in e.details:
                                    e.details = f"{e.details} ({name})"
                            else:
                                e.details = str(name)

                        print(
                            f"Resolved '{query}' -> {getattr(e, lat_field)},{getattr(e, lon_field)} ({item.src_field} via pyphoton)"
                        )
                    except Exception:
                        print("Failed parsing coords in pyphoton response for", query)

    # Convert shallow _Event models to minimal dicts and validate as _Event_render
    def _to_render_dict(ev: _Event) -> dict:
        return {
            "type": ev.type,
            "start_time": ev.start_time,
            "end_time": ev.end_time,
            "start_location": getattr(ev, "start_location", ""),
            "end_location": getattr(ev, "end_location", ""),
            "details": getattr(ev, "details", ""),
            "start_lat": getattr(ev, "start_lat", None),
            "start_lon": getattr(ev, "start_lon", None),
            "end_lat": getattr(ev, "end_lat", None),
            "end_lon": getattr(ev, "end_lon", None),
        }

    rendered = TypeAdapter(List[_Event_render]).validate_python(
        [_to_render_dict(ev) for ev in new_events]
    )
    return rendered
