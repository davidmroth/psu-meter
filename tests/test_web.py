from collections import deque

import pytest

from energy_cost.domain import WattReading
from psu_meter.domain import PowerReading
from psu_meter.energy import build_energy_service
from psu_meter.exceptions import PsuReadError
from psu_meter.pmbus import ParseMode
from psu_meter.poller import ReadingPoller
from psu_meter.web import create_app

IN_MEMORY_ENERGY_ENV = {"ENERGY_DB_PATH": ":memory:", "ENERGY_RATE_PER_KWH": "0.15"}
HOUR_FROM = "2026-10-13T00:00:00Z"
HOUR_TO = "2026-10-13T01:00:00Z"


class StubReader:
    def __init__(self, outcomes):
        self._outcomes = list(outcomes)

    def read(self):
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


@pytest.fixture
def energy(clock):
    return build_energy_service(IN_MEMORY_ENERGY_ENV, clock)


@pytest.fixture
def make_client(clock, energy):
    def build(outcomes):
        meter = ReadingPoller(StubReader(outcomes), clock, deque(maxlen=60), 5.0, lambda _s: None)
        for _ in outcomes:
            meter.tick()
        return create_app(meter, ParseMode.BE_FIRST, energy).test_client()

    return build


def test_data_is_empty_before_the_first_poll(make_client):
    body = make_client([]).get("/data").get_json()

    assert body == {
        "current": None,
        "timestamps": [],
        "powers": [],
        "last_error": None,
        "last_raw": None,
        "last_source": None,
        "parse_mode": "be-first",
    }


def test_data_lists_history_with_a_gap_for_a_failed_read(make_client, clock):
    client = make_client([
        PowerReading(clock.now - 5, 300, "hid-pmbus", (3, 238)),
        PsuReadError("psu", "unplugged"),
    ])

    body = client.get("/data").get_json()

    assert body["powers"] == [300, None]
    assert body["timestamps"] == [clock.now - 5, clock.now]
    assert (body["current"], body["last_error"], body["last_source"]) == (None, "psu: unplugged", None)


def test_data_reports_the_current_reading_and_its_source(make_client, clock):
    body = make_client([PowerReading(clock.now, 312, "hid-pmbus", (3, 238))]).get("/data").get_json()

    assert (body["current"], body["last_source"], body["last_raw"]) == (312, "hid-pmbus", [3, 238])


def test_raw_returns_the_latest_report_bytes(make_client, clock):
    client = make_client([PsuReadError("hid-fallback", "no value", (1, 2, 3))])

    assert client.get("/raw").get_json() == {"raw": [1, 2, 3]}


def test_home_page_has_no_inline_script_and_no_old_polling_graph(make_client):
    page = make_client([]).get("/")

    assert page.status_code == 200
    assert b"<script>" not in page.data
    assert b"/static/psu-meter.js" not in page.data
    assert b'id="chart"' not in page.data


def test_home_page_loads_chart_js_from_the_meter_not_a_cdn(make_client):
    client = make_client([])

    page = client.get("/")

    assert b'src="/energy-static/vendor/chart-4.4.4.umd.js"' in page.data
    assert b"cdn.jsdelivr" not in page.data


def test_home_page_has_the_energy_widgets_and_price_settings(make_client):
    page = make_client([]).get("/").get_data(as_text=True)

    assert 'data-energy-widget="tiles"' in page
    assert 'data-energy-widget="graph"' in page
    assert 'data-energy-widget="settings"' in page
    assert '"meter": "psu"' in page
    assert '<script type="module" src="/energy-static/energy-page.js">' in page
    assert 'href="/energy-static/energy.css"' in page


def _record_steady_hour(energy, start, watts):
    for step in range(0, 3601, 5):
        energy.recorder.record(WattReading(start + step, watts))


def test_energy_answers_as_the_gpu_meter(make_client, energy, clock):
    _record_steady_hour(energy, clock.now, 1000)

    body = make_client([]).get(f"/energy?from={HOUR_FROM}&to={HOUR_TO}").get_json()

    assert (body["meter"], body["measures"]) == ("psu", "gpu")
    assert (body["kwh"], body["cost"], body["currency"]) == (1.0, 0.15, "USD")
    assert "estimated_kwh" not in body


def test_stats_and_readings_are_served_for_the_gpu(make_client, energy, clock):
    _record_steady_hour(energy, clock.now, 250)
    client = make_client([])

    stats = client.get(f"/stats?from={HOUR_FROM}&to={HOUR_TO}").get_json()
    readings = client.get(f"/readings?from={HOUR_FROM}&to={HOUR_TO}&max_points=12").get_json()

    assert stats["watts"]["max"] == 250.0
    assert len(readings["points"]) == 12


def test_zoneless_time_is_rejected_with_400(make_client):
    response = make_client([]).get("/energy?from=2026-10-13T00:00:00&to=2026-10-13T01:00:00Z")

    assert response.status_code == 400
    assert response.get_json()["field"] == "from"


def test_first_time_price_comes_from_the_environment(make_client):
    body = make_client([]).get("/settings/rates").get_json()

    assert body["current"]["price_per_kwh"] == 0.15
