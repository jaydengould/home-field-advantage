import datetime as dt
import json
import pandas as pd
import pytest
from src.data import _espn
from src.data._espn import derive_capacity, check_coverage


def test_derive_capacity_self_reference_and_borrow():
    # venue "A": normal seasons self-reference their own max; treated 2020 borrows
    # the max over non-treated seasons (here 60000 from 2019), not its own 5000.
    df = pd.DataFrame({
        "stadium_id": ["A", "A", "A", "A"],
        "season":     [2019, 2019, 2020, 2020],
        "attendance": [40000, 60000, 5000, 0],
    })
    cap = derive_capacity(df, treated_seasons=[2020])
    assert cap[("A", 2019)] == 60000
    assert cap[("A", 2020)] == 60000  # borrowed, not 5000


def test_derive_capacity_only_treated_falls_back_to_own_max():
    df = pd.DataFrame({
        "stadium_id": ["B", "B"],
        "season":     [2020, 2020],
        "attendance": [0, 12000],
    })
    cap = derive_capacity(df, treated_seasons=[2020])
    assert cap[("B", 2020)] == 12000  # own max fallback, floored >= 1


def test_check_coverage_trips_above_5pct():
    check_coverage({2019: 1}, {2019: 100})       # 1% -> fine
    with pytest.raises(ValueError):
        check_coverage({2020: 2}, {2020: 10})    # 20% -> hard fail


def test_fetch_summary_uses_cache_no_network(tmp_path, monkeypatch):
    monkeypatch.setattr(_espn, "_RAW_ROOT", tmp_path)
    cache = tmp_path / "mlb" / "espn"
    cache.mkdir(parents=True)
    (cache / "555.json").write_text(json.dumps({"gameInfo": {"attendance": 22320}}))

    def boom(*a, **k):
        raise AssertionError("network hit despite cache")
    monkeypatch.setattr(_espn.requests, "get", boom)

    assert _espn.fetch_summary("mlb", "555") == 22320


def test_fetch_summary_missing_attendance_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(_espn, "_RAW_ROOT", tmp_path)
    cache = tmp_path / "mlb" / "espn"
    cache.mkdir(parents=True)
    (cache / "777.json").write_text(json.dumps({"gameInfo": {}}))
    assert _espn.fetch_summary("mlb", "777") is None


def _canned_scoreboard():
    return {"events": [
        {"id": "401", "date": "2019-06-15T20:00Z",
         "season": {"year": 2019, "type": 2},
         "competitions": [{
             "neutralSite": False,
             "venue": {"id": "31", "fullName": "Tropicana Field"},
             "status": {"type": {"name": "STATUS_FINAL"}},
             "competitors": [
                 {"homeAway": "home", "team": {"abbreviation": "TB"}, "score": "3"},
                 {"homeAway": "away", "team": {"abbreviation": "LAA"}, "score": "5"},
             ]}]},
        {"id": "999", "date": "2019-06-15T21:00Z",
         "season": {"year": 2019, "type": 2}},  # no competitions -> skipped
    ]}


def test_walk_scoreboard_parses_and_skips(tmp_path, monkeypatch):
    monkeypatch.setattr(_espn, "_RAW_ROOT", tmp_path)
    sb_dir = tmp_path / "mlb" / "espn" / "scoreboard"
    sb_dir.mkdir(parents=True)
    (sb_dir / "20190615.json").write_text(json.dumps(_canned_scoreboard()))

    def boom(*a, **k):
        raise AssertionError("network hit despite cache")
    monkeypatch.setattr(_espn.requests, "get", boom)

    day = dt.date(2019, 6, 15)
    rows = list(_espn.walk_scoreboard("mlb", day, day))
    assert len(rows) == 1                 # the no-competitions event was skipped
    r = rows[0]
    assert r["event_id"] == "401"
    assert r["season_type"] == 2
    assert r["home_abbr"] == "TB" and r["away_abbr"] == "LAA"
    assert r["home_score"] == 3 and r["away_score"] == 5
    assert r["venue_id"] == "31"
    assert r["neutral_site"] is False
    assert r["status"] == "STATUS_FINAL"


def test_cached_get_retries_transient_5xx(tmp_path, monkeypatch):
    monkeypatch.setattr(_espn.time, "sleep", lambda *a: None)  # no real backoff in test

    class FakeResp:
        def __init__(self, status, payload=None):
            self.status_code = status
            self._p = payload or {}
        def json(self):
            return self._p
        def raise_for_status(self):
            if self.status_code >= 400:
                raise _espn.requests.HTTPError(str(self.status_code))

    calls = {"n": 0}
    def fake_get(url, timeout=30):
        calls["n"] += 1
        return FakeResp(502) if calls["n"] == 1 else FakeResp(200, {"ok": True})
    monkeypatch.setattr(_espn.requests, "get", fake_get)

    out = _espn._cached_get(tmp_path / "x.json", "http://espn", throttle=0)
    assert out == {"ok": True}
    assert calls["n"] == 2          # retried the 502 exactly once, then succeeded
    assert (tmp_path / "x.json").exists()   # success is cached


def test_fetch_summary_returns_none_on_persistent_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(_espn, "_RAW_ROOT", tmp_path)
    monkeypatch.setattr(_espn.time, "sleep", lambda *a: None)  # no real backoff

    class Resp502:
        status_code = 502
        def raise_for_status(self):
            raise _espn.requests.HTTPError("502")

    monkeypatch.setattr(_espn.requests, "get", lambda url, timeout=30: Resp502())
    # no cache file -> _cached_get exhausts retries and raises -> fetch_summary must swallow -> None
    assert _espn.fetch_summary("mlb", "999") is None
