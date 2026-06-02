# psu-meter

Small tools for reading and displaying power usage from a Corsair PSU.

## Contents

- `app.py` runs a Flask web app that polls the PSU and shows the current wattage plus recent history in a browser.
- `psu-meter.sh` reads a Linux `hwmon` power sensor and prints the current wattage in the terminal.
- `Dockerfile` contains a containerized Python environment for the Flask app.

## Requirements

- Linux
- A supported Corsair PSU exposed either through HID USB access or `hwmon`
- Python 3
- Python packages: `flask`, `hidapi`

## Running the web app

Install dependencies:

```bash
pip install flask hidapi
```

Start the app:

```bash
python app.py
```

Then open `http://localhost:5000`.

The app polls the PSU every 5 seconds and serves:

- `/` for the web UI
- `/data` for the current reading and recent history as JSON

## Running the shell script

```bash
bash psu-meter.sh
```

If a matching `hwmon` sensor is available, it prints the current wattage in watts.

## Notes

- `app.py` is currently configured for Corsair vendor ID `0x1B1C` and product ID `0x1C27`.
- Access to the PSU may require running with appropriate permissions for USB/HID devices.
