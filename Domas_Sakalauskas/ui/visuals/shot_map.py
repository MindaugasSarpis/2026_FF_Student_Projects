"""Shot map on the attacking half: goal at the top, halfway line at the bottom."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import theme
from .data import pick_games, shots as load_shots

NAME = "Shot map"
DESCRIPTION = "Where shots were taken: one game, or all selected games together."

# --- how shot tags are understood (edit here if the tag names differ; see 'Shot stats') ---
GOAL_WORDS = ("goal",)
ON_TARGET_WORDS = ("on-target", "on_target", "ontarget", "target", "saved", "save")
OFF_WORDS = ("off",)
BLOCK_WORDS = ("block",)
FROM_BOX_WORDS = ("from-box", "from_box")

# pitch in metres, goal at the top: x = across (0-68), y = distance from own goal line (52.5-105)
LENGTH, WIDTH = 105.0, 68.0
STYLE = {  # outcome -> (symbol, size, colour or None = grey)
    "Goal": ("star", 22, theme.GOLD),
    "On target": ("circle", 14, theme.CYAN),
    "Blocked": ("square", 11, None),
    "Off target": ("circle", 11, None),
}


def _tag_list(tags) -> list:
    return [t.strip().lower() for t in tags.split("|") if t.strip()] if isinstance(tags, str) else []


def _has(tags: list, words) -> bool:
    return any(w in t for t in tags for w in words)


def outcome(tags) -> str:
    tags = _tag_list(tags)
    if _has(tags, GOAL_WORDS):
        return "Goal"
    if _has(tags, OFF_WORDS):
        return "Off target"
    if _has(tags, ON_TARGET_WORDS):
        return "On target"
    if _has(tags, BLOCK_WORDS):
        return "Blocked"
    return "Off target"


def _selection(data, cfg):
    """The shots for the current settings (+ how many glitch shots were ignored)."""
    clean, bad = load_shots(data)
    in_games = lambda d: d[d["session_id"].isin(cfg["games"])]
    s, n_bad = in_games(clean), len(in_games(bad))
    if cfg["mode"] == "Team":
        s = s[s["team"] == cfg["side"]]
        n_bad = n_bad if cfg["side"] == "opponent" else 0
    else:
        s, n_bad = s[s["shooter_id"] == cfg["player_id"]], 0
    s = s.dropna(subset=["ox", "oy"]).copy()
    s["outcome"] = s["tags"].map(outcome)
    return s, n_bad


def _stats(s, n_games):
    """Plain-language shot numbers for the current selection."""
    tags = s["tags"].map(_tag_list)
    from_box = int(tags.map(lambda t: _has(t, FROM_BOX_WORDS)).sum())
    rows = [
        ("Total shots", len(s)),
        ("Goals", int((s["outcome"] == "Goal").sum())),
        ("On target (incl. goals)", int(s["outcome"].isin(["Goal", "On target"]).sum())),
        ("Off target", int((s["outcome"] == "Off target").sum())),
        ("Blocked", int((s["outcome"] == "Blocked").sum())),
        ("Shots from box", from_box),
        ("Shots from outside the box", len(s) - from_box),
    ]
    known = GOAL_WORDS + ON_TARGET_WORDS + OFF_WORDS + BLOCK_WORDS + FROM_BOX_WORDS
    other = tags.explode().dropna()
    other = other[~other.map(lambda t: any(w in t for w in known))].value_counts()
    rows += [(t.replace("-", " ").replace("_", " ").capitalize(), int(n)) for t, n in other.items()]
    df = pd.DataFrame(rows, columns=["Stat", "Total"])
    if n_games > 1:
        df["Per game"] = (df["Total"] / n_games).round(2)
    return df

def _player_line(data, cfg, s):
    """'Played 5 of 8 games, 410 min | per 90: 2.1 shots, 0.2 goals' for one player."""
    a = data["appearances"]
    if a.empty or "minutes_played" not in a:
        return ""
    a = a[(pd.to_numeric(a["player_id"], errors="coerce") == cfg["player_id"]) & a["session_id"].isin(cfg["games"])]
    played = a[a["minutes_played"].fillna(0) > 0]
    mins = float(played["minutes_played"].sum())
    line = f"Played {len(played)} of {len(cfg['games'])} selected games, {mins:.0f} min"
    if mins > 0:
        goals = int((s["outcome"] == "Goal").sum())
        line += f"  |  per 90: {len(s) * 90 / mins:.2f} shots, {goals * 90 / mins:.2f} goals"
    return line

def settings(st, data):
    if data["events"].empty or data["matches"].empty:
        st.info("No data found. Import a game first.")
        return None
    clean, _ = load_shots(data)
    mode = st.radio("Show", ["Team", "Our player"], horizontal=True, key="shot_mode")
    cfg = {"mode": mode}
    if mode == "Team":
        cfg["side"] = st.radio("Team", ["ours", "opponent"], format_func=str.capitalize, horizontal=True, key="shot_side")
    else:
        names = clean[clean["team"] == "ours"].dropna(subset=["shooter_id"]).groupby("shooter_id")["shooter"].first().sort_values()
        if names.empty:
            st.info("No shots by our players found.")
            return None
        cfg["player_id"] = st.selectbox("Player", list(names.index), format_func=names.get, key="shot_player")
        cfg["player_name"] = names[cfg["player_id"]]
    cfg["games"] = pick_games(st, data, "shot")
    cfg["pitch"] = st.radio("Pitch", list(theme.PITCHES), horizontal=True, key="shot_pitch")

    s, n_bad = _selection(data, cfg)
    with st.expander("Shot stats (current selection)"):
        if s.empty:
            st.write("No shots for these settings.")
        else:
            if cfg["mode"] == "Our player":
                st.write(_player_line(data, cfg, s))
            st.dataframe(_stats(s, len(cfg["games"])), hide_index=True, width="stretch")
        if n_bad:
            st.caption(f"{n_bad} duplicate opponent shot row(s) (system glitch, right after our own shot) were ignored.")
    if not s.empty:
        with st.expander("Orientation check (for debugging)"):
            chk = s.groupby(["session_id", "team", "half"])[["flip_x", "flip_y"]].first().reset_index()
            st.dataframe(chk, hide_index=True, width="stretch")
            st.caption("True = that game/team/half was mirrored to the shooter's view (worked out from the zone codes).")
    return cfg


# ----------------------------------------------------------------------------- drawing
def _pitch(fig, p):
    line = dict(color=p["line"], width=1.4)
    none = "rgba(0,0,0,0)"
    for i in range(5):  # subtle mowing stripes
        if i % 2 == 0:
            y0 = LENGTH / 2 + i * LENGTH / 10
            fig.add_shape(type="rect", x0=0, x1=WIDTH, y0=y0, y1=y0 + LENGTH / 10, fillcolor=p["stripe"],
                          line=dict(width=0), layer="below")
    rect = lambda x0, y0, x1, y1, fill=none: fig.add_shape(type="rect", x0=x0, y0=y0, x1=x1, y1=y1, line=line, fillcolor=fill, layer="below")
    rect(0, LENGTH / 2, WIDTH, LENGTH)                    # half pitch (bottom edge = halfway line)
    rect(13.84, LENGTH - 16.5, 54.16, LENGTH)            # penalty box
    rect(24.84, LENGTH - 5.5, 43.16, LENGTH)             # six-yard box
    rect(30.34, LENGTH, 37.66, LENGTH + 2.0, "rgba(212,175,55,0.10)")  # goal frame
    fig.add_shape(type="line", x0=30.34, x1=37.66, y0=LENGTH, y1=LENGTH, line=dict(color=theme.GOLD, width=4))  # goal mouth

    def curve(x, y):
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=line, hoverinfo="skip", showlegend=False))
    a = np.arccos(5.5 / 9.15)
    t = np.linspace(-a, a, 60)
    curve(34 + 9.15 * np.sin(t), LENGTH - 11 - 9.15 * np.cos(t))                    # penalty arc
    t = np.linspace(0, np.pi, 60)
    curve(34 + 9.15 * np.cos(t), LENGTH / 2 + 9.15 * np.sin(t))                     # centre circle (upper half)
    t = np.linspace(-np.pi / 2, 0, 15)
    curve(0 + np.cos(t), LENGTH + np.sin(t))                                         # corner arcs
    t = np.linspace(np.pi, 1.5 * np.pi, 15)
    curve(WIDTH + np.cos(t), LENGTH + np.sin(t))
    fig.add_trace(go.Scatter(x=[34], y=[LENGTH - 11], mode="markers", marker=dict(size=4, color=p["line"]),
                             hoverinfo="skip", showlegend=False))                    # penalty spot


def _row_value(row, *cols):
    for c in cols:
        if c in row.index and pd.notna(row[c]) and str(row[c]).strip():
            return row[c]
    return None


def _header(data, cfg, s):
    """(headline, [lines]) for the figure title: opponent, result, date, competition, xG, player minutes."""
    m = data["matches"]
    sel = m[m["session_id"].isin(cfg["games"])]
    ts = data["team_stats"]
    xg = ts[(ts["metric"] == "xg") & (ts["period"] == "total") & ts["session_id"].isin(cfg["games"])] if not ts.empty else ts
    who = theme.CLUB_NAME if cfg["mode"] == "Team" and cfg["side"] == "ours" else \
          "Opponents" if cfg["mode"] == "Team" else cfg["player_name"]
    n_games = len(cfg["games"])
    n, goals = len(s), int((s["outcome"] == "Goal").sum())
    on_t = int(s["outcome"].isin(["Goal", "On target"]).sum())
    stats = f"{who}: {n} shots, {goals} goals, {on_t} on target"
    if n_games > 1:
        stats += f"  |  per game: {n / n_games:.1f} shots, {on_t / n_games:.1f} on target"

    if n_games == 1 and len(sel) == 1:
        r = sel.iloc[0]
        club = theme.CLUB_NAME
        opp = r.get("opponent", "Opponent")
        home = not str(r.get("venue", "")).lower().startswith("a")  # anything but 'away' = our club listed first
        gf, ga = (int(r["goals_for"]), int(r["goals_against"])) if pd.notna(r.get("goals_for")) else (None, None)
        score = "vs" if gf is None else (f"{gf} - {ga}" if home else f"{ga} - {gf}")
        headline = f"{club} {score} {opp}" if home else f"{opp} {score} {club}"
        bits = [str(r.get("date", ""))[:10], _row_value(r, "competition")]
        if len(xg) == 1:
            x_us, x_op = xg.iloc[0]["ours"], xg.iloc[0]["opponent"]
            bits.append(f"xG {x_us:.2f} - {x_op:.2f}" if home else f"xG {x_op:.2f} - {x_us:.2f}")
        lines = ["  |  ".join(str(b) for b in bits if b), stats]
        if cfg["mode"] == "Our player":
            lines.append(_player_line(data, cfg, s))
        return headline, lines

    headline = f"{who} - shot map"
    dates = sorted(str(d)[:10] for d in sel.get("date", []))
    line2 = f"{n_games} games" + (f", {dates[0]} to {dates[-1]}" if dates else "")
    if len(xg) and cfg["mode"] == "Team":
        col = "ours" if cfg["side"] == "ours" else "opponent"
        line2 += f"  |  xG per game {xg[col].sum() / n_games:.2f}"
    lines = [line2, stats]
    if cfg["mode"] == "Our player":
        lines.append(_player_line(data, cfg, s))
    return headline, lines


def render(data, cfg):
    if cfg is None:
        return None
    s, _ = _selection(data, cfg)
    if s.empty:
        return None

    # ox / oy come from data.shots(): already in the shooter's view (goal at the top, his left on the left)
    s["px"], s["py"] = s["oy"] / 100 * WIDTH, s["ox"] / 100 * LENGTH
    labels = dict(zip(data["matches"]["session_id"], data["matches"]["label"]))
    s["game"] = s["session_id"].map(labels).fillna("")

    p = theme.PITCHES[cfg["pitch"]]
    fig = go.Figure()
    _pitch(fig, p)

    goals = s[s["outcome"] == "Goal"]  # thin gold line from each goal to the goal mouth
    if not goals.empty:
        xs, ys = [], []
        for gx, gy in zip(goals["px"], goals["py"]):
            xs += [gx, 34, None]
            ys += [gy, LENGTH, None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=theme.GOLD, width=1), opacity=0.5,
                                 hoverinfo="skip", showlegend=False, legendgroup="Goal"))

    for name, (symbol, size, colour) in STYLE.items():
        d = s[s["outcome"] == name]
        if d.empty:
            continue
        col = colour or theme.GREY
        if colour:  # soft glow under coloured markers
            fig.add_trace(go.Scatter(x=d["px"], y=d["py"], mode="markers", hoverinfo="skip", showlegend=False, legendgroup=name,
                                     marker=dict(symbol="circle", size=size * 2, color=col, opacity=0.16)))
        fig.add_trace(go.Scatter(
            x=d["px"], y=d["py"], mode="markers", name=f"{name} ({len(d)})", legendgroup=name,
            marker=dict(symbol=symbol, size=size, color=col, opacity=1 if colour else 0.65, line=dict(color=p["bg"], width=1.5)),
            customdata=np.c_[d["shooter"].fillna(""), d["time"].fillna(""), d["outcome"], d["game"]],
            hovertemplate="%{customdata[0]}<br>%{customdata[1]} - %{customdata[2]}<br>%{customdata[3]}<extra></extra>",
        ))

    headline, lines = _header(data, cfg, s)
    fig.update_layout(
        title=dict(text=theme.title_text(headline, *lines, muted=p["muted"]), x=0.02),
        paper_bgcolor=p["bg"], plot_bgcolor=p["bg"], font=dict(family=theme.FONT, color=p["text"]),
        xaxis=dict(range=[-3, WIDTH + 3], visible=False, fixedrange=True),
        yaxis=dict(range=[LENGTH / 2 - 2, LENGTH + 4.5], visible=False, scaleanchor="x", fixedrange=True),
        legend=dict(orientation="h", y=-0.01, x=0.5, xanchor="center"),
        margin=dict(l=10, r=10, t=70 + 20 * len(lines), b=10), height=720 + 20 * len(lines),
    )
    return fig