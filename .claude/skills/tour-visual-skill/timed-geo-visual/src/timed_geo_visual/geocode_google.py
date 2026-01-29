from typing import List
from timed_geo_visual.model import _Event
import time


def _geocode_with_google(events: List[_Event], gm_client: object) -> List[_Event]:
    """Pure function: return a new list of _Event with geocoded fields added (no mutation).

    Performs the same logic as before but operates on shallow model copies and
    returns the modified copies.
    """

    new_events = [e.model_copy(deep=False) for e in events]

    for e in new_events:
        for src_field, lat_field, lon_field in (
            ("location", "start_lat", "start_lon"),
            ("start_location", "start_lat", "start_lon"),
            ("end_location", "end_lat", "end_lon"),
        ):
            # skip if already resolved
            if getattr(e, lat_field, None) is not None and getattr(e, lon_field, None) is not None:
                continue
            query = getattr(e, src_field, None) or getattr(e, "details", None)
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
                        setattr(e, lat_field, float(loc["lat"]))
                        setattr(e, lon_field, float(loc["lng"]))
                        # Append resolved address/name into details
                        name = results[0].get("formatted_address")
                        if name:
                            if getattr(e, "details", None):
                                if name not in e.details:
                                    e.details = f"{e.details} ({name})"
                            else:
                                e.details = str(name)
                        print(
                            f"Resolved '{query}' -> {getattr(e, lat_field)},{getattr(e, lon_field)} ({src_field})"
                        )
                    except Exception:
                        print("Failed parsing coords in Google response for", query)
                else:
                    print("No coordinates found in Google response for", query)
            # small throttle to be nice and respect rate limits
            time.sleep(0.1)

    return new_events
