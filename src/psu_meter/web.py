from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template

from energy_cost.service import EnergyService
from energy_cost.web import create_energy_blueprint
from psu_meter.pmbus import ParseMode
from psu_meter.poller import ReadingPoller, Sample

APPLICATION_TITLE = "Corsair HX1200i Power Meter"
PACKAGE_DIR = Path(__file__).parent


def create_app(poller: ReadingPoller, parse_mode: ParseMode, energy: EnergyService) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(PACKAGE_DIR / "templates"),
        static_folder=None,
    )
    app.register_blueprint(create_energy_blueprint(energy))

    @app.get("/favicon.ico")
    def favicon():
        return ("", 204)

    @app.get("/")
    def home():
        return render_template("index.html", title=APPLICATION_TITLE)

    @app.get("/data")
    def data():
        return jsonify(serialize_history(poller.samples(), poller.latest(), parse_mode))

    @app.get("/raw")
    def raw():
        latest = poller.latest()
        return jsonify({"raw": _raw_list(latest)})

    return app


def serialize_history(samples: list[Sample], latest: Sample | None, parse_mode: ParseMode) -> dict[str, object]:
    return {
        "current": latest.watts if latest else None,
        "timestamps": [sample.observed_at for sample in samples],
        "powers": [sample.watts for sample in samples],
        "last_error": latest.error if latest else None,
        "last_raw": _raw_list(latest),
        "last_source": latest.reading.source if latest and latest.reading else None,
        "parse_mode": parse_mode.value,
    }


def _raw_list(sample: Sample | None) -> list[int] | None:
    if sample is None or sample.raw_report is None:
        return None
    return list(sample.raw_report)
