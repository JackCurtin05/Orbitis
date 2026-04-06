# 🛸 Orbitis
### *Vigilia Caelestium — real-time orbital surveillance*

An interactive real-time tracker for every object in Earth orbit — Starlink, space stations, OneWeb, Iridium, and debris — powered by live TLE data from Space-Track.org and the SGP4 propagation algorithm used by NORAD.

---

<img width="3794" height="1816" alt="image" src="https://github.com/user-attachments/assets/abc2f04a-8c18-40bf-86cc-e31c318716e2" />
<img width="2871" height="598" alt="image" src="https://github.com/user-attachments/assets/b334ef83-ffd3-4352-a95b-81ec20ada97b" />



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

<img width="3831" height="1799" alt="image" src="https://github.com/user-attachments/assets/24baa84e-cbbd-49c4-8af1-9f85e2f1935a" />


<img width="3775" height="1671" alt="image" src="https://github.com/user-attachments/assets/40205ed9-b9e5-4e54-a4a2-ae410f9bedc4" />


<img width="3807" height="1831" alt="image" src="https://github.com/user-attachments/assets/5796e7ac-5045-4f83-98bb-a57ae5f8d6cc" />


<img width="910" height="436" alt="image" src="https://github.com/user-attachments/assets/a2fdd49b-5368-4ade-8199-94a2137515ec" />


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
