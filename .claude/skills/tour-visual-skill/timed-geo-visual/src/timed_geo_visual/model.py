from pydantic import BaseModel

from typing import List, Optional
from datetime import datetime


class _Event(BaseModel):
    """Pydantic model for an input event used for validating and normalizing times.

    Only declares the time fields explicitly; other fields are permitted via
    `extra = "allow"` so we can safely round-trip unknown properties.
    """

    type: str
    start_time: datetime
    end_time: datetime
    start_location: str
    end_location: str
    details: str = ""

    model_config = {"extra": "allow"}


class _Event_render(BaseModel):
    """
    Type for HTML rendering which includes optional latitude/longitude fields.
    """

    type: str
    start_time: datetime
    end_time: datetime
    start_location: str
    end_location: str
    details: str = ""
    # Template expects fields named `start_lat`, `start_lon`, `end_lat`, `end_lon`.
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None


class _PendingItem(BaseModel):
    """Typed representation of a search we will run against pyphoton.

    Fields:
    - event: the original event dict which may be mutated with lat/lon and props
    - src_field, lat_field, lon_field: strings indicating which fields relate
    - query: the (possibly country-appended) query string to send to pyphoton
    - pref_cc: optional country code used as bias when selecting features
    """

    event: _Event
    src_field: str
    lat_field: str
    lon_field: str
    query: str
    pref_cc: Optional[str] = None
