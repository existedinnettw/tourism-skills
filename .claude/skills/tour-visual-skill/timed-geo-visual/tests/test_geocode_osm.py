import asyncio
from types import SimpleNamespace
import os

import pytest

from timed_geo_visual import geocode_osm
from timed_geo_visual.model import _Event


def test_diskcache_caches_and_reuses(tmp_path, monkeypatch):
    # Ensure cache directory is isolated for the test
    orig_Cache = geocode_osm.Cache

    def tmp_Cache(path):
        return orig_Cache(tmp_path / ".photon_cache")

    monkeypatch.setattr(geocode_osm, "Cache", tmp_Cache)

    # Fake client that records queries and returns a simple location
    calls = []

    class FakeClient:
        async def query(self, location, limit=1):
            calls.append(location)
            return SimpleNamespace(latitude=1.0, longitude=2.0)

    monkeypatch.setattr(geocode_osm.pyphoton.client, "Photon", lambda: FakeClient())

    events = [
        _Event(type="t", start_time=1, end_time=2, start_location="A", end_location="B", details=""),
        _Event(type="t", start_time=3, end_time=4, start_location="A", end_location="B", details=""),
    ]

    # Run geocoding once; both locations A and B should be queried once each
    results = asyncio.run(geocode_osm._geocode_with_osm(events))
    assert len(results) == 2
    assert set(calls) == {"A", "B"}

    # Now replace client with one that would fail if called -- cached values should be used
    class FailClient:
        async def query(self, location, limit=1):
            raise RuntimeError("network should not be called when using cache")

    monkeypatch.setattr(geocode_osm.pyphoton.client, "Photon", lambda: FailClient())
    calls.clear()

    results2 = asyncio.run(geocode_osm._geocode_with_osm(events))
    # No new queries should have been attempted
    assert calls == []
    assert len(results2) == 2
    for r in results2:
        assert r.start_lat == 1.0 and r.start_lon == 2.0
        assert r.end_lat == 1.0 and r.end_lon == 2.0


def test_cache_file_created_and_cleanup(tmp_path, monkeypatch):
    # Ensure the cache directory is created and can be closed without error
    orig_Cache = geocode_osm.Cache

    def tmp_Cache(path):
        return orig_Cache(tmp_path / ".photon_cache")

    monkeypatch.setattr(geocode_osm, "Cache", tmp_Cache)

    class DummyClient:
        async def query(self, location, limit=1):
            return SimpleNamespace(latitude=9.0, longitude=8.0)

    monkeypatch.setattr(geocode_osm.pyphoton.client, "Photon", lambda: DummyClient())

    events = [_Event(type="t", start_time=0, end_time=1, start_location="X", end_location="Y", details="")]
    results = asyncio.run(geocode_osm._geocode_with_osm(events))
    assert len(results) == 1

    # Check that the cache directory exists on disk
    cache_dir = tmp_path / ".photon_cache"
    assert cache_dir.exists()
