"""Composition root: wires real USB access, polling and the web app together."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from typing import Sequence

from psu_meter.config import PsuMeterConfig
from psu_meter.energy import build_energy_service, energy_listener
from psu_meter.hidapi_port import hidapi_opener
from psu_meter.logging_setup import configure_logging
from psu_meter.poller import ReadingPoller, SampleListener
from psu_meter.reader import PsuReader
from psu_meter.sources import HidLegacySource, HidPmbusSource, LiquidctlSource
from psu_meter.web import create_app

logger = logging.getLogger(__name__)


def _liquidctl_discovery():
    try:
        from liquidctl import find_liquidctl_devices
    except ImportError:
        logger.info("liquidctl is not installed; that power source is disabled")
        return None
    return find_liquidctl_devices


def build_poller(config: PsuMeterConfig, listeners: Sequence[SampleListener] = ()) -> ReadingPoller:
    open_port = hidapi_opener(config.vendor_id, config.product_id)
    reader = PsuReader(
        sources=[
            HidPmbusSource(open_port),
            LiquidctlSource(_liquidctl_discovery(), config.vendor_id, config.product_id),
            HidLegacySource(open_port, config.parse_mode, time.sleep),
        ],
        clock=time.time,
    )
    return ReadingPoller(
        reader=reader,
        clock=time.time,
        history=deque(maxlen=config.history_size),
        interval_sec=config.interval_sec,
        sleeper=time.sleep,
        listeners=listeners,
    )


def main() -> None:
    config = PsuMeterConfig.from_env(os.environ)
    configure_logging(config.log_level, config.log_dir)
    logger.info("=== Corsair PSU Power Meter starting (parse mode %s) ===", config.parse_mode.value)
    energy = build_energy_service(os.environ, time.time)
    poller = build_poller(config, listeners=[energy_listener(energy, config.efficiency)])
    energy.start_background_jobs()
    threading.Thread(target=poller.run_forever, name="psu-poller", daemon=True).start()
    app = create_app(poller, config.parse_mode, energy)
    logger.info("PSU meter listening on 0.0.0.0:%s", config.port)
    app.run(host="0.0.0.0", port=config.port, threaded=True)


if __name__ == "__main__":
    main()
