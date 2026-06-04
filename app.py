from flask import Flask, render_template_string, jsonify
import hid
import time
import threading
import logging
import os
from logging.handlers import RotatingFileHandler
from collections import deque

try:
    from liquidctl import find_liquidctl_devices
except ImportError:
    find_liquidctl_devices = None

# Logging configuration: console + rotating file handler
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'psu-meter.log')

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

fh = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=5)
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)


app = Flask(__name__)
history = deque(maxlen=60)
last_error = None
last_raw = None
last_source = None

VENDOR_ID = 0x1B1C
PRODUCT_ID = 0x1C27
PARSE_MODE = os.getenv('PSU_PARSE_MODE', 'be-first').strip().lower()

logger.info("=== Corsair PSU Power Meter Starting ===")
logger.info(f"Parse mode: {PARSE_MODE}")


def iter_candidates(data, byte_order):
    for i in range(len(data) - 1):
        if byte_order == 'be':
            value = (data[i] << 8) | data[i + 1]
        else:
            value = (data[i + 1] << 8) | data[i]
        yield i, value


def select_power(data):
    if len(data) < 2:
        return None

    mode_orders = {
        'be-first': ['be', 'le'],
        'le-first': ['le', 'be'],
    }
    for byte_order in mode_orders.get(PARSE_MODE, ['be', 'le']):
        for index, value in iter_candidates(data, byte_order):
            logger.debug(f"{byte_order.upper()} candidate @ {index}: {value}")
            if 10 < value < 2000:
                logger.debug(f"Selected {byte_order.upper()} candidate at {index}: {value}")
                return value

    if PARSE_MODE == 'max':
        candidates = []
        for byte_order in ('be', 'le'):
            for index, value in iter_candidates(data, byte_order):
                logger.debug(f"{byte_order.upper()} candidate @ {index}: {value}")
                if 10 < value < 2000:
                    candidates.append((value, byte_order, index))
        if candidates:
            value, byte_order, index = max(candidates, key=lambda item: item[0])
            logger.debug(f"Selected max {byte_order.upper()} candidate at {index}: {value}")
            return value

    for i in range(len(data) - 1):
        raw = (data[i + 1] << 8) | data[i]
        signed = raw if raw < 0x8000 else raw - 0x10000
        value = abs(signed)
        logger.debug(f"Signed candidate @ {i}: raw={raw} signed={signed}")
        if 10 < value < 2000:
            logger.debug(f"Selected signed candidate at {i}: {value}")
            return value

    return None


def get_power_from_liquidctl():
    global last_error, last_source

    if find_liquidctl_devices is None:
        logger.debug("liquidctl is not installed")
        return None

    devices = find_liquidctl_devices()
    logger.debug(f"liquidctl discovered {len(devices)} supported device(s)")

    for dev in devices:
        vendor_id = getattr(dev, 'vendor_id', None)
        if vendor_id is None:
            vendor_id = getattr(getattr(dev, 'device', None), 'vendor_id', None)

        product_id = getattr(dev, 'product_id', None)
        if product_id is None:
            product_id = getattr(getattr(dev, 'device', None), 'product_id', None)

        if vendor_id is not None and product_id is not None:
            if vendor_id != VENDOR_ID or product_id != PRODUCT_ID:
                continue

        description = getattr(dev, 'description', dev.__class__.__name__)

        try:
            with dev.connect():
                try:
                    dev.initialize(direct_access=True)
                except TypeError:
                    dev.initialize()

                try:
                    status = dev.get_status(direct_access=True)
                except TypeError:
                    status = dev.get_status()

            for prop, value, unit in status:
                if prop == 'Total power output':
                    watts = int(round(float(value)))
                    logger.info(f"Power: {watts} W (via liquidctl: {description})")
                    last_error = None
                    last_source = f"liquidctl:{description}"
                    return watts
        except Exception:
            logger.exception(f"liquidctl read failed for {description}")

    return None

def get_power():
    global last_error, last_raw, last_source

    power = get_power_from_liquidctl()
    if power is not None:
        last_raw = None
        return power

    try:
        logger.debug("Opening HID device")
        device = hid.device()
        device.open(VENDOR_ID, PRODUCT_ID)
        logger.debug(f"Device opened: vendor=0x{VENDOR_ID:X} product=0x{PRODUCT_ID:X}")
        # request data
        device.write([0x00, 0x02, 0x00] + [0x00]*17)
        time.sleep(0.15)
        data = device.read(64)
        logger.debug(f"Raw data ({len(data)} bytes): {data}")
        # store raw response for inspection
        try:
            last_raw = list(data)
        except Exception:
            last_raw = None

        power = select_power(data)

        if power is not None:
            logger.info(f"Power: {power} W (via hid fallback)")
            device.close()
            last_error = None
            last_source = "hid-fallback"
            return power
        device.close()
        last_error = None
    except Exception as e:
        last_error = str(e)
        last_raw = None
        logger.exception("Error reading from HID device")
    return 0


@app.route('/raw')
def raw():
    # Return last raw HID response (list of bytes) for debugging
    return jsonify({"raw": last_raw})

def update_loop():
    logger.info("Polling started")
    while True:
        try:
            power = get_power()
            logger.debug(f"Appending power={power} to history")
            history.append((time.time(), power))
        except Exception:
            logger.exception("Unhandled exception in update loop")
        time.sleep(5)
thread = threading.Thread(target=update_loop, daemon=True)
thread.start()
logger.info(f"Background poll thread started (daemon={thread.daemon})")

HTML = '''
<!DOCTYPE html><html><head><title>PSU Power</title></head><body>
<h1>Corsair HX1200i Power Meter</h1>
<p>Current: <b id="cur">0</b> W</p>
<canvas id="chart" width="900" height="400"></canvas>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<script>
let chart = new Chart(document.getElementById('chart'), {type:'line', data:{labels:[], datasets:[{label:'Power (W)', data:[]}]}});
setInterval(()=>{fetch('/data').then(r=>r.json()).then(d=>{document.getElementById('cur').textContent=d.current; chart.data.labels=d.times; chart.data.datasets[0].data=d.powers; chart.update();});}, 5000);
</script></body></html>
'''

@app.route('/')
def home():
    return render_template_string(HTML)

@app.route('/data')
def data():
    times = [time.strftime("%H:%M:%S", time.localtime(t)) for t,p in history]
    powers = [p for t,p in history]
    current = powers[-1] if powers else 0
    return jsonify({
        "current": current,
        "times": times,
        "powers": powers,
        "last_error": last_error,
        "last_raw": last_raw,
        "last_source": last_source,
        "parse_mode": PARSE_MODE,
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
