from flask import Flask, render_template_string, jsonify
import hid
import time
import threading
import logging
import os
from logging.handlers import RotatingFileHandler
from collections import deque

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

VENDOR_ID = 0x1B1C
PRODUCT_ID = 0x1C27

logger.info("=== Corsair PSU Power Meter Starting ===")

def get_power():
    global last_error
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

        if len(data) > 20:
            power = (data[17] << 8) | data[16]
            if power == 0:
                power = (data[19] << 8) | data[18]
            logger.debug(f"Parsed power value: {power}")
            if 10 < power < 2000:
                logger.info(f"Power: {power} W")
                device.close()
                last_error = None
                return power
        device.close()
        last_error = None
    except Exception as e:
        last_error = str(e)
        logger.exception("Error reading from HID device")
    return 0

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
    return jsonify({"current": current, "times": times, "powers": powers, "last_error": last_error})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
