# timed-geo-visual

render json tour plan display on html by jinja, OpenStreetMap or GoogleMap API.

expect create mark with time and location on map.

```bash
uv run python -m timed_geo_visual --input ./planned-KHH-NGO-CTS.json --output ./planned-KHH-NGO-CTS.html

uv run python -m http.server 8000
```

## develop

```bash
uv run pytest
uvx ty check
```

can debug even through playright

<!-- TODO: compare google map -->