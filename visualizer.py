"""
visualizer.py
-------------
Builds the Plotly figures used in the Dash app.

Two main views:
  1. 3D Globe  — objects plotted in 3D space above a sphere
  2. 2D Map    — ground tracks on a flat equirectangular map

Both are interactive (zoom, rotate, hover tooltips).
"""

import plotly.graph_objects as go
from propagator import altitude_band

# ── Colour palette by orbital regime ──────────────────────────────────────────
BAND_COLORS = {
    "LEO":     "#00d4ff",   # cyan
    "MEO":     "#ffa500",   # orange
    "GEO":     "#ff4444",   # red
    "HEO":     "#cc44ff",   # purple
    "decayed": "#444444",   # dark grey
    "unknown": "#888888",
}

CATEGORY_COLORS = {
    "active":   "#00ff88",
    "debris":   "#ff4444",
    "stations": "#ffff00",
    "starlink": "#00aaff",
    "oneweb":   "#ff88ff",
    "iridium":  "#ffaa00",
    "unknown":  "#888888",
}

# ── Public API ─────────────────────────────────────────────────────────────────

def build_3d_figure(objects: list[dict], color_by: str = "category") -> go.Figure:
    """
    Build an interactive globe view of orbital objects using an orthographic
    map projection. Shows real Earth geography (coastlines, countries, oceans)
    so you can immediately see which part of Earth each object is over.

    Marker size encodes altitude band:
      LEO  → 4 px   MEO  → 6 px   GEO  → 8 px   HEO  → 10 px

    Args:
        objects:   List of propagated object dicts (from propagator.py)
        color_by:  'category' | 'altitude' — what drives point colour

    Returns:
        A go.Figure ready to embed in Dash
    """
    valid = [o for o in objects if not o.get("error")]

    lats, lons, colors, hover, sizes = [], [], [], [], []

    _ALT_SIZES = {"LEO": 4, "MEO": 6, "GEO": 8, "HEO": 10, "decayed": 2, "unknown": 4}

    for obj in valid:
        lats.append(obj["lat"])
        lons.append(obj["lon"])

        band = altitude_band(obj["alt_km"])
        cat  = obj.get("category", "unknown")

        if color_by == "altitude":
            colors.append(BAND_COLORS.get(band, "#888888"))
        else:
            colors.append(CATEGORY_COLORS.get(cat, "#888888"))

        sizes.append(_ALT_SIZES.get(band, 4))

        if cat == "stations":
            hover.append(
                f"<b>🛸 {obj['name']}</b><br>"
                f"Category: Space Station<br>"
                f"Alt: {obj['alt_km']:.0f} km ({band})<br>"
                f"Lat: {obj['lat']:.2f}°  Lon: {obj['lon']:.2f}°"
            )
        else:
            hover.append(
                f"<b>{obj['name']}</b><br>"
                f"Category: {cat}<br>"
                f"Alt: {obj['alt_km']:.0f} km ({band})<br>"
                f"Lat: {obj['lat']:.2f}°  Lon: {obj['lon']:.2f}°"
            )

    scatter = go.Scattergeo(
        lat=lats,
        lon=lons,
        mode="markers",
        marker=dict(
            size=sizes,
            color=colors,
            opacity=0.85,
            line=dict(width=0),
        ),
        text=hover,
        hovertemplate="%{text}<extra></extra>",
        name="Objects",
    )

    fig = go.Figure(data=[scatter])
    fig.update_layout(
        geo=dict(
            projection_type="orthographic",
            # Land — dark forest green, realistic satellite view feel
            showland=True,
            landcolor="#2a5c30",
            # Ocean — deep dark blue
            showocean=True,
            oceancolor="#0d1f37",
            # Coastlines — subtle lighter green
            showcoastlines=True,
            coastlinecolor="#4a8a5a",
            coastlinewidth=0.8,
            # Country borders — very subtle
            showcountries=True,
            countrycolor="#1e3a28",
            countrywidth=0.5,
            # Lakes match the ocean
            showlakes=True,
            lakecolor="#0d1f37",
            # Frame off for a clean floating globe look
            showframe=False,
            bgcolor="#0a0a1a",
            # Start with a slight tilt — looks more natural than top-down
            projection=dict(
                rotation=dict(lon=0, lat=20, roll=0),
            ),
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#0a0a1a",
        showlegend=False,
        uirevision="constant",   # keeps rotation on data refresh
    )
    return fig


def build_2d_figure(objects: list[dict], color_by: str = "category") -> go.Figure:
    """
    Build a 2D ground-track scatter map.

    Args:
        objects:   List of propagated object dicts
        color_by:  'category' | 'altitude'

    Returns:
        A go.Figure ready to embed in Dash
    """
    valid = [o for o in objects if not o.get("error")]

    lats, lons, colors, hover = [], [], [], []

    for obj in valid:
        lats.append(obj["lat"])
        lons.append(obj["lon"])

        band = altitude_band(obj["alt_km"])
        cat  = obj.get("category", "unknown")
        color = BAND_COLORS.get(band) if color_by == "altitude" else CATEGORY_COLORS.get(cat, "#888888")
        colors.append(color)

        if cat == "stations":
            hover.append(
                f"<b>🛸 {obj['name']}</b><br>"
                f"Category: Space Station<br>"
                f"Alt: {obj['alt_km']:.0f} km ({band})<br>"
                f"Lat: {obj['lat']:.2f}°  Lon: {obj['lon']:.2f}°"
            )
        else:
            hover.append(
                f"<b>{obj['name']}</b><br>"
                f"Category: {cat}<br>"
                f"Alt: {obj['alt_km']:.0f} km ({band})<br>"
                f"Lat: {obj['lat']:.2f}°  Lon: {obj['lon']:.2f}°"
            )

    scatter = go.Scattergeo(
        lat=lats,
        lon=lons,
        mode="markers",
        marker=dict(
            size=3,
            color=colors,
            opacity=0.7,
            line=dict(width=0),
        ),
        text=hover,
        hovertemplate="%{text}<extra></extra>",
        name="Objects",
    )

    fig = go.Figure(data=[scatter])
    fig.update_layout(
        geo=dict(
            showland=True,      landcolor="#1a3a1a",
            showocean=True,     oceancolor="#0a1a2e",
            showcoastlines=True, coastlinecolor="#334455",
            showframe=False,
            bgcolor="#0a0a1a",
            projection_type="natural earth",
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="#0a0a1a",
        showlegend=False,
        uirevision="constant",
    )
    return fig


def build_altitude_histogram(objects: list[dict]) -> go.Figure:
    """Bar chart of object count by altitude band."""
    valid = [o for o in objects if not o.get("error")]
    bands = [altitude_band(o["alt_km"]) for o in valid]

    band_order = ["LEO", "MEO", "GEO", "HEO", "decayed"]
    counts = {b: bands.count(b) for b in band_order}

    fig = go.Figure(go.Bar(
        x=list(counts.keys()),
        y=list(counts.values()),
        marker_color=[BAND_COLORS[b] for b in band_order],
        text=list(counts.values()),
        textposition="outside",
        hovertemplate="%{x}: %{y} objects<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="#0a0a1a",
        plot_bgcolor="#0d0d2b",
        font=dict(color="#ccddee", size=12),
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="#1a2a3a"),
    )
    return fig


def build_category_pie(objects: list[dict]) -> go.Figure:
    """Donut chart of objects by category."""
    valid = [o for o in objects if not o.get("error")]
    cats  = [o.get("category", "unknown") for o in valid]
    unique_cats = list(set(cats))
    counts = [cats.count(c) for c in unique_cats]
    colors = [CATEGORY_COLORS.get(c, "#888888") for c in unique_cats]

    fig = go.Figure(go.Pie(
        labels=unique_cats,
        values=counts,
        hole=0.55,
        marker=dict(colors=colors, line=dict(color="#0a0a1a", width=2)),
        hovertemplate="%{label}: %{value} objects<extra></extra>",
        textinfo="label+percent",
        textfont=dict(color="#ccddee"),
    ))
    fig.update_layout(
        paper_bgcolor="#0a0a1a",
        font=dict(color="#ccddee"),
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    return fig


def build_legend_html(color_by: str = "category") -> str:
    """Return a small HTML string for the colour legend."""
    palette = CATEGORY_COLORS if color_by == "category" else BAND_COLORS
    items = "".join(
        f'<span style="display:inline-flex;align-items:center;margin-right:14px;">'
        f'<span style="width:12px;height:12px;border-radius:50%;background:{color};'
        f'display:inline-block;margin-right:5px;"></span>{label}</span>'
        for label, color in palette.items()
    )
    return f'<div style="font-size:12px;color:#aabbcc;">{items}</div>'
