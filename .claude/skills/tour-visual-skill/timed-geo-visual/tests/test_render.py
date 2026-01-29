import json
import pytest

from timed_geo_visual.timed_geo_visual import _main_async
from playwright.async_api import Page



from playwright.sync_api import sync_playwright


def test_highlight_selected_tour_node_changes_color(tmp_path):
    """
    line of selected tour node is expected to change from blue to red
    """
    events = [
        {
            "type": "transportation",
            "start_time": "2026-01-01T00:00:00+00:00",
            "end_time": "2026-01-01T01:00:00+00:00",
            "start_lat": 0.0,
            "start_lon": 0.0,
            "end_lat": 0.0,
            "end_lon": 1.0,
            "start_location": "A",
            "end_location": "B",
            "details": "",
        }
    ]

    in_file = tmp_path / "events.json"
    in_file.write_text(json.dumps(events))
    out_file = tmp_path / "out.html"

    # Generate HTML (no geocoder needed because coords are present)
    import asyncio

    asyncio.run(
        _main_async(["--input", str(in_file), "--output", str(out_file), "--geocoder", "none"])
    )

    # Use Playwright sync API to avoid nested event loop issues
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        # Serve the generated file over HTTP to avoid file:// restrictions (CORS blocking external
        # network requests such as Leaflet assets or tile layers). Start a simple HTTP server
        # rooted at tmp_path and navigate to it.
        import threading
        from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
        from functools import partial

        handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            page.goto(f"http://127.0.0.1:{port}/{out_file.name}")
        finally:
            server.shutdown()
            thread.join(timeout=1)

        # Attach a console logger to capture browser errors (helps debugging in CI)
        console_messages = []

        def _on_console(msg):
            try:
                console_messages.append(f"{msg.type}: {msg.text}")
            except Exception:
                console_messages.append(str(msg))

        page.on("console", _on_console)

        # Wait for the polyline SVG path to be present; on timeout, surface console + page HTML
        try:
            # Wait for the path element to be attached to the DOM. Using "attached"
            # avoids Playwright's visibility heuristics which can mark an SVG
            # path as hidden even though it's present and has stroke attributes.
            page.wait_for_selector("svg path.leaflet-interactive", state="attached", timeout=5000)
        except Exception as exc:
            content = page.content()
            raise AssertionError(
                "SVG path not found; console messages:\n" + "\n".join(console_messages) + "\n\nPage HTML:\n" + content
            ) from exc

        path = page.query_selector("svg path.leaflet-interactive")
        stroke = (path.get_attribute("stroke") or "").lower()

        # initial color should match the default blue used in template
        assert stroke == "#0077cc"

        # Click the sidebar event to select it and trigger highlighting
        page.click(".event")

        # Wait for the stroke to update to red
        page.wait_for_function(
            "() => { const p = document.querySelector('svg path.leaflet-interactive'); return p && p.getAttribute('stroke') && p.getAttribute('stroke').toLowerCase() === '#cc0000'; }",
            timeout=2000,
        )

        stroke2 = (path.get_attribute("stroke") or "").lower()
        assert stroke2 == "#cc0000"


# def test_selected_line_has_arrow_direct_from_start_to_end(tmp_path):
#     """
#     the selected line connecting a start+end point should show an arrowhead pointing toward the end location
#     """


def test_selected_event_node_in_sidebar_should_be_highlighted(tmp_path):
    """
    selected event node in sidebar should be highlighted
    """
    events = [
        {
            "type": "transportation",
            "start_time": "2026-01-01T00:00:00+00:00",
            "end_time": "2026-01-01T01:00:00+00:00",
            "start_lat": 0.0,
            "start_lon": 0.0,
            "end_lat": 0.0,
            "end_lon": 1.0,
            "start_location": "A",
            "end_location": "B",
            "details": "",
        },
        {
            "type": "stay",
            "start_time": "2026-01-02T00:00:00+00:00",
            "end_time": "2026-01-02T01:00:00+00:00",
            "start_lat": 10.0,
            "start_lon": 10.0,
            "start_location": "C",
            "end_location": "C",
            "details": "",
        },

    ]

    in_file = tmp_path / "events.json"
    in_file.write_text(json.dumps(events))
    out_file = tmp_path / "out.html"

    # Generate HTML (no geocoder needed because coords are present)
    import asyncio

    asyncio.run(
        _main_async(["--input", str(in_file), "--output", str(out_file), "--geocoder", "none"])
    )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        import threading
        from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
        from functools import partial

        handler = partial(SimpleHTTPRequestHandler, directory=str(tmp_path))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            page.goto(f"http://127.0.0.1:{port}/{out_file.name}")
        finally:
            server.shutdown()
            thread.join(timeout=1)

        # Attach a console logger to capture browser errors (helps debugging in CI)
        console_messages = []

        def _on_console(msg):
            try:
                console_messages.append(f"{msg.type}: {msg.text}")
            except Exception:
                console_messages.append(str(msg))

        page.on("console", _on_console)

        # Wait for sidebar event elements to be present
        try:
            page.wait_for_selector(".event", state="attached", timeout=5000)
        except Exception as exc:
            content = page.content()
            raise AssertionError(
                "Sidebar events not found; console messages:\n" + "\n".join(console_messages) + "\n\nPage HTML:\n" + content
            ) from exc

        events_el = page.query_selector_all(".event")
        # Initially, no event should have 'selected' class
        assert all(((e.get_attribute("class") or "").find("selected") == -1) for e in events_el)

        # Click the first event to select it
        page.click(".event")
        # Wait for the selected class to appear
        page.wait_for_selector(".event.selected", state="attached", timeout=2000)

        first_class = (page.query_selector(".event").get_attribute("class") or "").lower()
        assert "selected" in first_class

        # Click the second event and ensure the highlight moves
        page.click(".event:nth-of-type(2)")
        page.wait_for_selector(".event.selected", state="attached", timeout=2000)
        all_events = page.query_selector_all(".event")
        classes = [ (e.get_attribute("class") or "").lower() for e in all_events ]
        assert "selected" in classes[1]
        assert "selected" not in classes[0]
