"""
app.py
------
Main Dash application for Orbitis.

Run with:
    python app.py

Then open http://localhost:8050 in your browser.

Features:
  • Live TLE fetch from Celestrak on startup (and manual refresh)
  • Interactive 3D globe + 2D map toggle
  • Filter by category (Starlink, stations, OneWeb, Iridium, debris)
  • Colour by category or altitude band
  • Stats panel: total objects, breakdown by orbit regime
  • Auto-refresh propagation every 60 seconds (positions update in real time)
"""

import datetime
import threading
import time

# Use timezone-aware UTC helper to avoid deprecation warnings in Python 3.12+
def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, callback_context

from fetcher import fetch_multiple, CATALOGS
from propagator import propagate_objects, altitude_band
import visualizer as viz

# ── Data source selection ──────────────────────────────────────────────────────
# Use Space-Track if credentials are configured in .env, else fall back to
# Celestrak / embedded TLEs.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import os as _os
import pathlib as _pathlib

# Load .env from the same directory as this file (explicit path is more reliable)
try:
    from dotenv import load_dotenv
    _env_path = _pathlib.Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=_env_path, override=True)
    print(f"[app] Loaded .env from {_env_path} (exists={_env_path.exists()})")
except ImportError:
    pass

_ST_USER = _os.getenv("SPACETRACK_USER", "")
_ST_PASS = _os.getenv("SPACETRACK_PASS", "")
_SPACETRACK_AVAILABLE = bool(
    _ST_USER and _ST_USER != "your@email.com" and
    _ST_PASS and _ST_PASS != "yourpassword"
)

if _SPACETRACK_AVAILABLE:
    from space_track import SpaceTrackClient
    print(f"[app] Space-Track credentials found (user={_ST_USER}) — using Space-Track.org.")
else:
    print(f"[app] No Space-Track credentials detected (user='{_ST_USER}') — using fallback TLEs.")

# ── App init ───────────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    title="Orbitis",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server   # expose Flask server for deployment

# ── Global state (shared between callbacks via a simple cache) ─────────────────

_cache = {
    "raw_tles":      [],    # raw TLE dicts from Celestrak
    "propagated":    [],    # latest propagated position dicts
    "last_fetched":  None,  # datetime of last TLE fetch
    "last_updated":  None,  # datetime of last propagation
    "loading":       False, # True while fetch is in progress
}

DEFAULT_CATEGORIES = ["starlink", "stations"]
MAX_PER_CATEGORY   = 1500   # cap per category to keep render fast


def _do_fetch(categories: list[str]):
    """Background fetch + propagate. Uses Space-Track if credentials exist."""
    _cache["loading"] = True
    try:
        if _SPACETRACK_AVAILABLE:
            with SpaceTrackClient() as st:
                tles = st.fetch_multiple(categories, max_per_category=MAX_PER_CATEGORY)
        else:
            tles = fetch_multiple(categories, max_per_category=MAX_PER_CATEGORY)

        _cache["raw_tles"]     = tles
        _cache["last_fetched"] = _utcnow()
        _cache["propagated"]   = propagate_objects(tles)
        _cache["last_updated"] = _utcnow()
    except Exception as exc:
        print(f"[app] Fetch error: {exc}")
    finally:
        _cache["loading"] = False


def _background_refresh():
    """Periodically re-propagate (positions change every second in orbit!)."""
    while True:
        time.sleep(60)
        if _cache["raw_tles"]:
            _cache["propagated"]  = propagate_objects(_cache["raw_tles"])
            _cache["last_updated"] = _utcnow()


# Initial load in background so the app starts quickly
threading.Thread(target=_do_fetch, args=(DEFAULT_CATEGORIES,), daemon=True).start()
threading.Thread(target=_background_refresh, daemon=True).start()


# ── Layout ─────────────────────────────────────────────────────────────────────

CATEGORY_OPTIONS = [{"label": cat.replace("_", " ").title(), "value": cat} for cat in CATALOGS]

app.layout = dbc.Container(
    fluid=True,
    style={"backgroundColor": "#0a0a1a", "minHeight": "100vh", "padding": "0"},
    children=[

        # ── Top navbar ────────────────────────────────────────────────────────
        dbc.Navbar(
            dbc.Container([
                html.Div([
                    html.Span("🛰️ ", style={"fontSize": "1.4rem"}),
                    html.Span("Orbitis", style={
                        "fontSize": "1.2rem", "fontWeight": "700",
                        "letterSpacing": "1px", "color": "#00d4ff",
                    }),
                ], style={"display": "flex", "alignItems": "center", "gap": "6px"}),
                html.Small("Vigilia Caelestium  ·  real-time orbital surveillance",
                           style={"color": "#667788", "fontStyle": "italic"}),
            ], fluid=True),
            color="#0d0d2b",
            dark=True,
            style={"borderBottom": "1px solid #1a2a3a"},
        ),

        # ── Main content ──────────────────────────────────────────────────────
        dbc.Row([

            # ── Left sidebar ─────────────────────────────────────────────────
            dbc.Col(width=3, children=[
                dbc.Card(style={"backgroundColor": "#0d0d2b", "border": "1px solid #1a2a3a"}, children=[
                    dbc.CardBody([

                        html.H6("Data Sources", style={"color": "#00d4ff", "marginBottom": "8px"}),
                        dcc.Checklist(
                            id="category-checklist",
                            options=CATEGORY_OPTIONS,
                            value=DEFAULT_CATEGORIES,
                            labelStyle={"display": "block", "color": "#aabbcc",
                                        "marginBottom": "4px", "cursor": "pointer"},
                            inputStyle={"marginRight": "8px", "accentColor": "#00d4ff"},
                        ),

                        html.Hr(style={"borderColor": "#1a2a3a"}),
                        html.H6("Colour By", style={"color": "#00d4ff", "marginBottom": "8px"}),
                        dcc.RadioItems(
                            id="color-by-radio",
                            options=[
                                {"label": "Category", "value": "category"},
                                {"label": "Altitude band", "value": "altitude"},
                            ],
                            value="category",
                            labelStyle={"display": "block", "color": "#aabbcc",
                                        "marginBottom": "4px"},
                            inputStyle={"marginRight": "8px", "accentColor": "#00d4ff"},
                        ),

                        html.Hr(style={"borderColor": "#1a2a3a"}),
                        html.H6("View", style={"color": "#00d4ff", "marginBottom": "8px"}),
                        dcc.RadioItems(
                            id="view-radio",
                            options=[
                                {"label": "3D Globe", "value": "3d"},
                                {"label": "2D Map",   "value": "2d"},
                            ],
                            value="3d",
                            labelStyle={"display": "block", "color": "#aabbcc",
                                        "marginBottom": "4px"},
                            inputStyle={"marginRight": "8px", "accentColor": "#00d4ff"},
                        ),

                        html.Hr(style={"borderColor": "#1a2a3a"}),
                        dbc.Button(
                            "🔄  Refresh Data",
                            id="refresh-btn",
                            color="primary",
                            outline=True,
                            size="sm",
                            style={"width": "100%", "borderColor": "#00d4ff",
                                   "color": "#00d4ff"},
                        ),
                        html.Div(id="fetch-status", style={"color": "#667788",
                                                           "fontSize": "11px",
                                                           "marginTop": "6px"}),

                        html.Hr(style={"borderColor": "#1a2a3a"}),

                        # Stats cards
                        html.H6("Statistics", style={"color": "#00d4ff", "marginBottom": "8px"}),
                        html.Div(id="stats-panel"),

                    ])
                ]),
            ], style={"padding": "12px 6px 12px 12px"}),

            # ── Main plot area ────────────────────────────────────────────────
            dbc.Col(width=9, children=[
                dbc.Card(style={"backgroundColor": "#0d0d2b", "border": "1px solid #1a2a3a",
                                "height": "calc(100vh - 100px)"}, children=[
                    dbc.CardBody(style={"padding": "0", "height": "100%"}, children=[
                        dcc.Loading(
                            id="main-loading",
                            type="circle",
                            color="#00d4ff",
                            children=dcc.Graph(
                                id="main-graph",
                                style={"height": "calc(100vh - 108px)"},
                                config={
                                    "displayModeBar": True,
                                    "modeBarButtonsToRemove": ["select2d", "lasso2d"],
                                    "displaylogo": False,
                                },
                            ),
                        ),
                        # Colour legend
                        html.Div(id="legend-div",
                                 style={"position": "absolute", "bottom": "18px",
                                        "left": "24px", "zIndex": "10"}),
                    ]),
                ]),

                # Mini charts row
                dbc.Row([
                    dbc.Col(width=6, children=[
                        dbc.Card(style={"backgroundColor": "#0d0d2b",
                                        "border": "1px solid #1a2a3a",
                                        "marginTop": "8px"}, children=[
                            html.Small("Objects by Altitude Band",
                                       style={"color": "#667788", "padding": "6px 12px",
                                              "display": "block"}),
                            dcc.Graph(id="alt-hist", style={"height": "160px"},
                                      config={"displayModeBar": False}),
                        ]),
                    ]),
                    dbc.Col(width=6, children=[
                        dbc.Card(style={"backgroundColor": "#0d0d2b",
                                        "border": "1px solid #1a2a3a",
                                        "marginTop": "8px"}, children=[
                            html.Small("Objects by Category",
                                       style={"color": "#667788", "padding": "6px 12px",
                                              "display": "block"}),
                            dcc.Graph(id="cat-pie", style={"height": "160px"},
                                      config={"displayModeBar": False}),
                        ]),
                    ]),
                ], style={"marginTop": "0"}),

            ], style={"padding": "12px 12px 12px 6px"}),

        ], style={"margin": "0"}),

        # Auto-refresh interval (re-propagates every 60 s)
        dcc.Interval(id="auto-refresh", interval=60_000, n_intervals=0),
    ]
)


# ── Callbacks ──────────────────────────────────────────────────────────────────

@app.callback(
    Output("fetch-status", "children"),
    Output("main-graph", "figure"),
    Output("alt-hist", "figure"),
    Output("cat-pie", "figure"),
    Output("stats-panel", "children"),
    Output("legend-div", "children"),
    Input("refresh-btn", "n_clicks"),
    Input("auto-refresh", "n_intervals"),
    Input("color-by-radio", "value"),
    Input("view-radio", "value"),
    Input("category-checklist", "value"),
    prevent_initial_call=False,
)
def update_dashboard(n_clicks, n_intervals, color_by, view, selected_cats):
    ctx = callback_context
    triggered = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    # Trigger a new fetch when the user clicks Refresh or changes categories
    if "refresh-btn" in triggered:
        cats = selected_cats or DEFAULT_CATEGORIES
        _do_fetch(cats)   # synchronous in callback (fine for moderate datasets)

    objects = _cache["propagated"]

    # Filter to selected categories
    if selected_cats:
        objects = [o for o in objects if o.get("category") in selected_cats]

    # ── Fetch status line ──
    if _cache["last_fetched"]:
        fetched_str = _cache["last_fetched"].strftime("%H:%M:%S UTC")
        updated_str = _cache["last_updated"].strftime("%H:%M:%S UTC") if _cache["last_updated"] else "—"
        status = f"TLE fetched: {fetched_str} | Propagated: {updated_str}"
    else:
        status = "Fetching data…"

    # ── Main figure ──
    if view == "3d":
        main_fig = viz.build_3d_figure(objects, color_by=color_by)
    else:
        main_fig = viz.build_2d_figure(objects, color_by=color_by)

    # ── Mini charts ──
    alt_fig = viz.build_altitude_histogram(objects)
    cat_fig = viz.build_category_pie(objects)

    # ── Stats panel ──
    valid = [o for o in objects if not o.get("error")]
    bands  = [altitude_band(o["alt_km"]) for o in valid]
    stats = _make_stats(valid, bands)

    # ── Legend ──
    legend = dcc.Markdown(viz.build_legend_html(color_by), dangerously_allow_html=True)

    return status, main_fig, alt_fig, cat_fig, stats, legend


def _make_stats(objects: list[dict], bands: list[str]) -> list:
    """Build the stats mini-cards for the sidebar."""
    total = len(objects)
    leo   = bands.count("LEO")
    meo   = bands.count("MEO")
    geo   = bands.count("GEO")
    heo   = bands.count("HEO")

    def stat_row(label, value, color="#00d4ff"):
        return html.Div([
            html.Span(label, style={"color": "#667788", "fontSize": "11px"}),
            html.Span(f"{value:,}", style={"color": color, "fontWeight": "700",
                                           "float": "right", "fontSize": "13px"}),
        ], style={"marginBottom": "4px", "overflow": "hidden"})

    return [
        stat_row("Total objects", total, "#ffffff"),
        stat_row("LEO  (< 2 000 km)", leo,  "#00d4ff"),
        stat_row("MEO  (2 000–35 786 km)", meo, "#ffa500"),
        stat_row("GEO  (~35 786 km)", geo,  "#ff4444"),
        stat_row("HEO  (> 35 786 km)", heo, "#cc44ff"),
    ]


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Starting Orbitis — open http://localhost:8050")
    app.run(debug=True, host="0.0.0.0", port=8050)
