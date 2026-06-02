from flask import Flask, render_template_string, jsonify
import hid
import time
import threading
import logging
from collections import deque

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
history = deque(maxlen=60)

VENDOR_ID = 0x1B1C
PRODUCT_ID = 0x1C27

logger.info("=== Corsair PSU Power Meter Starting ===")

def get_power():
    try:
        device = hid.device()
        device.open(VENDOR_ID, PRODUCT_ID)
        device.write([0x00, 0x02, 0x00] + [0x00]*17)
        time.sleep(0.15)
        data = device.read(64)

        if len(data) > 20:
            power = (data[17] << 8) | data[16]
            if power == 0:
                power = (data[19] << 8) | data[18]
            if 10 < power < 2000:
                logger.info(f"Power: {power} W")
                device.close()
                return power
        device.close()
    except Exception as e:
        logger.error(f"Error: {e}")
    return 0

def update_loop():
    logger.info("Polling started")
    while True:
        power = get_power()
        history.append((time.time(), power))
        time.sleep(5)

threading.Thread(target=update_loop, daemon=True).start()

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
    return jsonify({"current": current, "times": times, "powers": powers})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
