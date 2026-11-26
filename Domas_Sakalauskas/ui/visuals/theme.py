"""Shared look for every visual. Change a colour here and all graphs change."""

BLACK = "#111111"
WHITE = "#FFFFFF"
GOLD = "#D4AF37"
CYAN = "#1FB9B4"  # rare contrast colour only
GREY = "#8A8A8A"

CLUB_NAME = "Our team"
FONT = "Inter, Helvetica, Arial, sans-serif"

# pitch styles (first one is the default): background, mowing stripe, lines, text, muted text
PITCHES = {
    "Black": {"bg": "#0D0D0D", "stripe": "#131313", "line": "rgba(255,255,255,0.42)", "text": WHITE, "muted": "#9A9A9A"},
    "White": {"bg": WHITE, "stripe": "#F4F4F4", "line": "rgba(0,0,0,0.42)", "text": BLACK, "muted": "#6B6B6B"},
}


def title_text(headline: str, *lines: str, muted: str = GREY) -> str:
    """Bold headline + small muted lines under it."""
    out = f"<b>{headline}</b>"
    for line in lines:
        if line:
            out += f"<br><span style='font-size:13px;color:{muted}'>{line}</span>"
    return out


def plotly_config(filename: str) -> dict:
    """Camera button in the graph's top-right corner downloads a sharp PNG (no extra package needed)."""
    return {
        "displaylogo": False,
        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        "toImageButtonOptions": {"format": "png", "filename": filename, "scale": 3},
    }