# 🛰️ Space Debris Tracker

A real-time interactive tracker for every object in Earth orbit — active satellites, rocket bodies, and debris — powered by live TLE data from Celestrak and the SGP4 propagation algorithm used by NORAD.

## Features

- **Live data** — fetches TLE sets directly from Celestrak on startup
- **Real physics** — SGP4 orbital propagation (same algorithm NORAD uses)
- **3D globe** — interactive rotating Earth with objects plotted in 3D space
- **2D ground track map** — flat equirectangular view
- **Filter by category** — active satellites, debris, Starlink, ISS/stations, etc.
- **Colour by altitude band** or category (LEO / MEO / GEO / HEO)
- **Auto-refresh** — positions re-propagated every 60 seconds as objects move
- **Stats panel** — live breakdown by orbital regime

## Setup

```bash
# 1. Clone / copy the project folder
cd space-debris-tracker

# 2. Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py
```

Then open **http://localhost:8050** in your browser.

## Project Structure

```
space-debris-tracker/
├── app.py          # Dash app — layout, callbacks, auto-refresh loop
├── fetcher.py      # Celestrak TLE fetcher + parser
├── propagator.py   # SGP4 propagation + ECI → geodetic conversion
├── visualizer.py   # Plotly figure builders (3D globe, 2D map, charts)
└── requirements.txt
```

## How It Works

1. **`fetcher.py`** — Downloads plain-text TLE files from Celestrak (e.g. `active.txt`, `starlink.txt`). Parses 3-line TLE blocks into Python dicts. Deduplicates by NORAD catalog ID when merging categories.

2. **`propagator.py`** — Feeds each TLE into `sgp4`'s `Satrec.twoline2rv()`, then calls `.sgp4(jd, fr)` with the current Julian date to get the ECI (Earth-Centered Inertial) position vector in km. Converts to geodetic lat/lon/altitude using the WGS-84 ellipsoid.

3. **`visualizer.py`** — Takes the propagated positions and builds Plotly figures: a textured 3D sphere (`go.Surface`) with objects as `go.Scatter3d` points, a `go.Scattergeo` 2D map, and mini bar/pie charts.

4. **`app.py`** — Dash wires it all together. A background thread re-propagates positions every 60 seconds. A `dcc.Interval` triggers callback refreshes in the browser.

## Data Source

TLE data from [Celestrak](https://celestrak.org) — free, public, updated every few hours. No API key required.

## Ideas for Extending

- **Collision risk (SOCRATES)** — compute close-approach pairs using distance between propagated ECI vectors
- **Pass predictor** — given a lat/lon on Earth, compute when satellites will be visible overhead
- **Historical replay** — propagate backwards to visualize past events (e.g. the Cosmos-2251 / Iridium-33 collision)
- **ML layer** — cluster debris clouds by origin, predict decay dates from TLE drag terms
- **Streamlit / FastAPI** — swap Dash for a different frontend framework
- **Deploy to Render / Railway** — one `Procfile` and it's live on the web

## Tech Stack

| Library | Purpose |
|---------|---------|
| `sgp4` | SGP4/SDP4 orbital propagation |
| `dash` + `plotly` | Interactive web UI and 3D/2D visualizations |
| `dash-bootstrap-components` | Dark-theme UI components |
| `requests` | HTTP fetch from Celestrak |
| `numpy` | Coordinate math |
