import pyphoton
from pyphoton.models import Location
from timed_geo_visual.model import _Event, _Event_render
from functools import cache
from typing import List, Optional
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


async def _geocode_with_osm(events: List[_Event]) -> List[_Event_render]:
    """Resolve locations using pyphoton and return events prepared for rendering.

    Operates on shallow copies of the input models and returns a list of
    `_Event_render` models where coordinates (lat/lon, start_lat/start_lon,
    end_lat/end_lon) and common address properties have been added where
    available. The original input models are not mutated.
    """
    if events is None:
        return []
    client = pyphoton.client.Photon()
    if client is None:
        raise RuntimeError("pyphoton client not available for OSM geocoding")

    # concurrency control
    max_conc = int(_os.getenv("TIMED_GEO_PHOTON_CONCURRENCY", "4"))
    sem = asyncio.Semaphore(max_conc)

    async def per_event_query(event: _Event) -> _Event_render:
        resp_start: Optional[Location] = None
        resp_end: Optional[Location] = None
        async with sem:
            try:
                task = _cached_pyphoton_task(client, event.start_location)
                resp_start = await task

            except Exception as exc:
                print("pyphoton query failed for", event.start_location, exc)
        async with sem:
            try:
                task = _cached_pyphoton_task(client, event.end_location)
                resp_end = await task

            except Exception as exc:
                print("pyphoton query failed for", event.end_location, exc)
        # return (resp_start, resp_end)
        return _Event_render(
            type=event.type,
            start_time=event.start_time,
            end_time=event.end_time,
            start_location=event.start_location,
            end_location=event.end_location,
            details=event.details,
            start_lat=resp_start.latitude if resp_start else None,
            start_lon=resp_start.longitude if resp_start else None,
            end_lat=resp_end.latitude if resp_end else None,
            end_lon=resp_end.longitude if resp_end else None,
        )

    task = [asyncio.create_task(per_event_query(event)) for event in events]
    results: list[_Event_render | BaseException] = await asyncio.gather(
        *task, return_exceptions=True
    )
    return [r for r in results if isinstance(r, _Event_render)]
