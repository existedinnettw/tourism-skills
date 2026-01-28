# timed-geo-visual

render json tour plan display on html by jinja, OpenStreetMap or GoogleMap API.

expect create mark with time and location on map.

```bash
uv run python -m timed_geo_visual --input ./planned-KHH-NGO-CTS.json --output ./planned-KHH-NGO-CTS.html

uv run python -m http.server 8000
```

## develop

can debug through playright

```bash
uv run pytest
```

<!-- TODO: compare google map -->