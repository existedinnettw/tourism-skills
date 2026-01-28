# timed-geo-visual

render json tour plan display on html by jinja, openstreetmap map api

expect create mark with time and location on map.

```bash
uv run timed-geo-visual --input ./planned-KHH-NGO-CTS.json --output ./planned-KHH-NGO-CTS.html

uv run python -m http.server 8000
```

## develop

can debug through playright

```bash
uv run pytest
```

<!-- TODO: compare google map -->