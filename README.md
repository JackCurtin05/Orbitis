# 🛸 Orbitis
### *Vigilia Caelestium — real-time orbital surveillance*

An interactive real-time tracker for every object in Earth orbit — Starlink, space stations, OneWeb, Iridium, and debris — powered by live TLE data from Space-Track.org and the SGP4 propagation algorithm used by NORAD.

---

<!-- SCREENSHOT: Full app overview — 3D globe view with Starlink selected, sidebar visible, stats panel populated. Ideal size: 1280×800 or wider. -->
![App Overview](screenshots/overview.png)

---

## Features

- **Authenticated live data** — fetches TLEs directly from Space-Track.org on startup
- **Real physics** — SGP4 orbital propagation (same algorithm NORAD uses)
- **3D globe** — interactive rotating Earth with objects plotted in real position
- **2D ground track map** — flat equirectangular view for a different perspective
- **Filter by category** — Starlink, stations, OneWeb, Iridium, debris
- **Colour by altitude band** or category (LEO / MEO / GEO / HEO)
- **Station hover info** — hover any station dot to see its name, altitude, and position
- **Auto-refresh** — positions re-propagated every 60 seconds as objects move
- **Stats panel** — live breakdown by orbital regime

---

## Screenshots

<!-- SCREENSHOT: 3D globe with just Starlink enabled — shows the dense LEO shell of satellites evenly distributed. Good for showing scale. -->
![Starlink Constellation](screenshots/starlink_globe.png)

<!-- SCREENSHOT: Hover tooltip on a station dot (ISS or Tiangong) — should clearly show the station name, altitude, and coordinates in the tooltip. -->
![Station Hover](screenshots/station_hover.png)

<!-- SCREENSHOT: 2D flat map view with multiple categories enabled — shows ground tracks spread across the map. -->
![2D Map View](screenshots/2d_map.png)

<!-- SCREENSHOT: Sidebar close-up showing the stats panel with numbers populated and the category checklist. -->
![Stats Panel](screenshots/stats_panel.png)

---

## Setup

### 1. Get Space-Track credentials

Register for a free account at [space-track.org](https://www.space-track.org/auth/createAccount). This is required — Space-Track is the authoritative source for all tracked orbital objects.

### 2. Configure credentials

Create a `.env` file in the project root:

```
SPACETRACK_USER=your@email.com
SPACETRACK_PASS=yourpassword
```

### 3. Install and run

```bash
# Clone the repo
git clone https://github.com/JackCurtin05/Orbitis.git
cd Orbitis

# Create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac / Linux

# Install dependencies
pip install -r requirements.txt

# Run
python app.py
```

Then open **http://localhost:8050** in your browser.

---

## Project Structure

```
Orbitis/
├── app.py           # Dash app — layout, callbacks, auto-refresh loop
├── fetcher.py       # Celestrak TLE fetcher + fallback parser
├── space_track.py   # Authenticated Space-Track.org client
├── propagator.py    # SGP4 propagation + ECI → geodetic conversion
├── visualizer.py    # Plotly figure builders (3D globe, 2D map, charts)
├── requirements.txt
└── .env             # Your credentials (not committed)
```

---

## How It Works

1. **`space_track.py`** — Authenticates with Space-Track.org and queries the GP (General Perturbations) class for TLE data by category. Falls back to Celestrak if credentials aren't configured.

2. **`propagator.py`** — Feeds each TLE into `sgp4`'s `Satrec.twoline2rv()`, then calls `.sgp4(jd, fr)` with the current Julian date to get the ECI position vector. Converts to geodetic lat/lon/altitude using the WGS-84 ellipsoid.

3. **`visualizer.py`** — Takes the propagated positions and builds Plotly figures: an orthographic 3D globe with objects as `Scattergeo` points, a 2D natural-earth map, and mini bar/pie charts.

4. **`app.py`** — Dash wires it together. A background thread re-propagates every 60 seconds. A `dcc.Interval` triggers browser refreshes.

---

## Tech Stack

| Library | Purpose |
|---------|---------|
| `sgp4` | SGP4/SDP4 orbital propagation |
| `dash` + `plotly` | Interactive web UI and visualizations |
| `dash-bootstrap-components` | Dark-theme UI |
| `requests` | HTTP — Space-Track API calls |
| `python-dotenv` | Credential management via `.env` |

---

## Ideas for Extending

- **Collision risk** — compute close-approach pairs using distance between propagated ECI vectors
- **Pass predictor** — given a lat/lon, compute when satellites will be overhead
- **Historical replay** — propagate backwards to visualise past events
- **Deploy to Render / Railway** — one `Procfile` and it's live on the web
