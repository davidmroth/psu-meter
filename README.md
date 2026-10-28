# psu-meter

Reads output power from a Corsair PSU (the GPU rail) and shows it in a browser.

## Layout

| Path | Job |
|---|---|
| `src/psu_meter/pmbus.py` | Pure decoding of HID reports into watts (PMBus LINEAR11 and the legacy guessing modes) |
| `src/psu_meter/hid_port.py` | Narrow HID port interface; `hidapi_port.py` is the real USB adapter |
| `src/psu_meter/sources.py` | The three ways of reading the PSU: HID PMBus, liquidctl, legacy HID |
| `src/psu_meter/reader.py` | Tries each source in order and time-stamps the first answer |
| `src/psu_meter/poller.py` | Polls every few seconds, keeps recent samples and hands each one to listeners |
| `src/psu_meter/energy.py` | Turns each GPU reading into wall watts and saves it to energy history |
| `src/psu_meter/web.py` | Flask routes: `/`, `/data`, `/raw` |
| `src/psu_meter/main.py` | Wires everything together and starts the app |
| `psu-meter.sh` | Prints watts from a Linux `hwmon` sensor in the terminal |

A failed read is stored as a gap (`null` watts) with the reason in `last_error`; it is never recorded as 0 W.

## Running

```bash
docker compose up -d --build
```

Then open `http://localhost:5000`.

The image installs the shared `energy-cost` package from the sibling `../energy-cost` folder, passed in as the named build context `energy-cost` (see `docker-compose.yml`). Without compose, build with:

```bash
docker build --build-context energy-cost=../energy-cost -t psu-meter .
```

Energy history is saved to `./data/energy.sqlite3`, so it survives restarts and rebuilds. The container clock is UTC; the web page shows times in the viewer's own time zone.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `PSU_PARSE_MODE` | `be-first` | Legacy HID parsing: `be-first`, `le-first` or `max` |
| `PSU_METER_INTERVAL_SEC` | `5` | Seconds between reads |
| `PSU_METER_HISTORY` | `60` | Samples kept for `/data` |
| `PSU_METER_PORT` | `5000` | Web port |
| `PSU_VENDOR_ID` / `PSU_PRODUCT_ID` | `0x1B1C` / `0x1C27` | USB ids of the PSU |
| `LOG_LEVEL` | `INFO` | Console log level; the file in `logs/` always has DEBUG detail |
| `PSU_METER_LOG_DIR` | `/app/logs` | Where the rotating log file is written |
| `PSU_EFFICIENCY` | `1.0` | Share of wall power the PSU delivers (for example `0.90`). Energy history divides output watts by this to estimate wall watts; `/data` still shows output watts |
| `ENERGY_RATE_PER_KWH` | none | Starting price per kWh, used only until a price is saved in the page's Settings panel |
| `ENERGY_CURRENCY` | `USD` | Currency for that starting price |
| `ENERGY_DB_PATH` | `/data/energy.sqlite3` | Energy history database |
| `RAW_RETENTION_HOURS` | `48` | How long every 5-second reading is kept |
| `DETAIL_RETENTION_DAYS` | `30` | How long one-minute rows are kept |
| `HISTORY_RETENTION_DAYS` | `365` | How long UTC daily rows are kept |

## Tests

```bash
./scripts/test.sh
```

Runs the unit tests in a `python:3.12-slim` container; no PSU or USB access is needed.
