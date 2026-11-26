"""Football Analysis Hub - demo dashboard.

Run from the project root:   python -m streamlit run ui/app.py
(or double-click run.command on Mac / run.bat on Windows)

Reads only the small tables in data/processed/ that import_game.py creates.
All numbers are calculated on the fly in hub_tables.py; this file only draws the pages.
"""
from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitAPIException

import hub_tables as ht

from visuals import discover
from visuals import theme as vtheme
from visuals.data import load as load_visual_data

ROOT = Path(__file__).resolve().parent.parent
PROC = Path(os.environ.get("HUB_DATA_DIR", ROOT / "data" / "processed"))

st.set_page_config(page_title="Football Analysis Hub", page_icon="⚽", layout="wide")

WINDOWS = {"Whole season": None, "Last 10 games": 10, "Last 5 games": 5, "Last 3 games": 3}
PERIODS = {"Full match": "total", "1st half": "first_half", "2nd half": "second_half", "Extra time": "extra_time"}
MODES = ["Per 90", "Per game", "Total"]
# Shown by default in the player overview table (only those that exist in your data are used).
DEFAULT_PLAYER_METRICS = [
    "passes_made", "pass_accuracy_pct", "passes_forward", "passes_progresive", "passes_key",
    "total_shots", "shots_on_target", "shots_goals", "box_entry", "final_third_entry",
    "dribbling", "duels", "ball_recovered", "ball_lost_after_control",
]
COLOUR_HELP = (
    f"Green = above the average, red = below, yellow = similar (within ±{int(ht.SIMILAR_PCT * 100)}% of the average, "
    f"or within ±{ht.SMALL_COUNT_TOL} for small whole-number stats). Season best = the highest value."
)


# ----------------------------------------------------------------------------- loading
@st.cache_data(show_spinner=False)
def _read(path: str, mtime: float) -> pd.DataFrame:
    return pd.read_csv(path)  # mtime is only here so the cache refreshes when a file changes


def load(name: str) -> pd.DataFrame:
    p = PROC / f"{name}.csv"
    return _read(str(p), p.stat().st_mtime) if p.exists() else pd.DataFrame()


# ----------------------------------------------------------------------------- UI helpers
def show_table(df: pd.DataFrame) -> None:
    """st.dataframe across Streamlit versions (the 'full width' argument was renamed)."""
    try:
        st.dataframe(df, width="stretch", hide_index=True)
    except (TypeError, StreamlitAPIException):
        st.dataframe(df, use_container_width=True, hide_index=True)


def show_game_table(sty, rows: int) -> None:
    """Styled game-by-game table. The index column (metric names) stays frozen when scrolling sideways."""
    height = int(min(700, 40 + 35 * rows))
    try:
        st.dataframe(sty, width="stretch", height=height,
                     column_config={"_index": st.column_config.Column(pinned=True)})
    except (TypeError, StreamlitAPIException):
        st.dataframe(sty, use_container_width=True, height=height)


def open_folder(path: Path) -> None:
    """Opens the folder on the computer that RUNS the app (fine when you run it locally)."""
    try:
        if platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        elif platform.system() == "Windows":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:  # noqa: BLE001
        st.sidebar.warning(f"Could not open the folder: {e}")


def game_filters(matches: pd.DataFrame):
    """Sidebar filters shared by all pages. Returns (filtered matches newest-first, N or None)."""
    st.sidebar.subheader("Games")
    seasons = sorted(matches["season"].dropna().unique(), reverse=True)
    season = st.sidebar.selectbox("Season", seasons)
    venues = sorted(matches["venue"].unique())
    venue_sel = st.sidebar.multiselect("Venue", venues, default=venues)
    comps = sorted(matches["competition"].unique())
    comp_sel = st.sidebar.multiselect("Competition", comps, default=comps)
    window = st.sidebar.selectbox("Games to include", list(WINDOWS))
    f = matches[(matches["season"] == season) & matches["venue"].isin(venue_sel) & matches["competition"].isin(comp_sel)]
    return f, WINDOWS[window]


def games_expander(games: pd.DataFrame) -> None:
    with st.expander(f"Games included ({len(games)})"):
        show_table(games[["date", "opponent", "venue", "competition", "score", "result"]].assign(date=lambda d: d["date"].dt.date))


# ----------------------------------------------------------------------------- Overview
def page_overview(matches, team_stats):
    st.header("Overview")
    f, n = game_filters(matches)
    games = f.head(n) if n else f
    if games.empty:
        st.info("No games match the filters.")
        return
    w, d, l = (int((games["result"] == r).sum()) for r in "WDL")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games", len(games))
    c2.metric("W - D - L", f"{w} - {d} - {l}")
    c3.metric("Goals for", int(games["goals_for"].sum()))
    c4.metric("Goals against", int(games["goals_against"].sum()))

    tbl = games.assign(date=games["date"].dt.date)[["session_id", "date", "opponent", "venue", "competition", "score", "result"]]
    if not team_stats.empty:
        xg = team_stats[(team_stats["metric"] == "xg") & (team_stats["period"] == "total")]
        xg = xg[["session_id", "ours", "opponent"]].rename(columns={"ours": "xG", "opponent": "xG against"})
        tbl = tbl.merge(xg, on="session_id", how="left")
    show_table(tbl.drop(columns="session_id").round(2))


# ----------------------------------------------------------------------------- Team stats
def page_team(matches, team_stats):
    st.header("Team stats")
    f, n = game_filters(matches)
    games = f.head(n) if n else f
    if games.empty:
        st.info("No games match the filters.")
        return
    period_name = st.sidebar.selectbox("Period", list(PERIODS))
    period = PERIODS[period_name]

    tab_avg, tab_games = st.tabs(["Averages", "Game by game"])

    # ---- averages (ours vs opponent)
    with tab_avg:
        search = st.text_input("Search metric", placeholder="e.g. shots, press, pass", key="team_avg_search")
        t = ht.team_table(team_stats, games, period)
        if search:
            s = search.lower()
            t = t[t["label"].fillna("").str.lower().str.contains(s) | t["metric"].str.lower().str.contains(s)]
        t["label"] = t.apply(
            lambda r: r["label"] + (" (s)" if r["type"] == "Time" else "")
            + (" ~" if r["type"] == "Percentage" and not r["recomputed"] else ""), axis=1)
        view = t.rename(columns={"label": "Metric", "ours": "Ours", "opponent": "Opponent", "diff": "Difference",
                                 "games": "Games with data", "metric": "Key"})
        cols = ["Metric", "Ours", "Opponent", "Difference", "Games with data", "Key"]
        st.caption(f"Average per game over {len(games)} game(s). Percentages are calculated from the summed counts "
                   "(e.g. pass success = all completed passes / all passes made, not counting balls lost after reception). "
                   "Rows marked ~ have no known formula yet: they are a simple average of the per-game percentages. "
                   "Click a column header to sort.")
        show_table(view[view["type"] != "Percentage"][cols].round(2))
        with st.expander("Percentage metrics (simple average of the per-game values, not weighted: use with caution)"):
            show_table(view[view["type"] == "Percentage"][cols].round(2))
        games_expander(games)

    # ---- game by game
    with tab_games:
        c1, c2, c3 = st.columns([1.4, 1.6, 2])
        compare = c1.checkbox("Compare to avg", key="team_compare")
        show = c2.radio("Show", ["Both", "Ours", "Opponent"], horizontal=True, key="team_side")
        search = c3.text_input("Search metric", placeholder="e.g. shots, press, pass", key="team_game_search")
        sides = {"Both": ("ours", "opponent"), "Ours": ("ours",), "Opponent": ("opponent",)}[show]

        df, game_cols, avg_col, _best = ht.team_game_table(team_stats, games, period, n, sides)
        if search:
            df = df[df.index.str.lower().str.contains(search.lower())]
        if df.empty:
            st.info("Nothing to show.")
        else:
            show_game_table(ht.style_game_table(df, game_cols, avg_col, compare), len(df))
            st.caption(f"Games oldest to newest. Percentages are calculated from the counts of each game, and the "
                       f"season average from the summed counts. Rows marked ~ have no known formula yet (simple "
                       f"average of the per-game values). {COLOUR_HELP}")


# ----------------------------------------------------------------------------- Player stats
def page_players(matches, appearances, player_stats):
    st.header("Player stats")
    f, n = game_filters(matches)
    if f.empty:
        st.info("No games match the filters.")
        return
    min_minutes = st.sidebar.number_input("Min. minutes for a game to count", min_value=1, max_value=90, value=1)

    tab_over, tab_player = st.tabs(["Season overview", "One player, game by game"])

    # ---- overview of all players
    with tab_over:
        mode = st.radio("Values", MODES, horizontal=True)
        table, available = ht.player_table(appearances, player_stats, f, n, min_minutes, mode)
        available = sorted(c for c in available if "percent" not in c or c == "pass_accuracy_pct")
        default = [m for m in DEFAULT_PLAYER_METRICS if m in available]
        chosen = st.multiselect("Metrics", available, default=default)

        cols = ["Player", "Pos", "Games", "Minutes"] + chosen
        show_table(table[cols].sort_values("Minutes", ascending=False).round(2))
        scope = f"each player's last {n} games played" if n else "all games in the season"
        st.caption(f"{mode} values over {scope}. Pass accuracy = completed / (passes_total - lost after reception), "
                   "calculated from summed counts. Click a column header to sort.")

    # ---- one player, every game
    with tab_player:
        a = appearances[appearances["session_id"].isin(f["session_id"]) & (appearances["minutes_played"] >= min_minutes)]
        if a.empty:
            st.info("No appearances for these filters.")
            return
        mins = a.groupby("player_id")["minutes_played"].sum().sort_values(ascending=False)
        names = a.groupby("player_id")["name"].first()
        pid = st.selectbox("Player", list(mins.index), format_func=lambda i: names[i])

        c1, c2 = st.columns([1.4, 2])
        compare = c1.checkbox("Compare to avg", key="player_compare")
        search = c2.text_input("Search metric", placeholder="e.g. shots, pass, duels", key="player_game_search")

        df, game_cols, avg_col, _best = ht.player_game_table(appearances, player_stats, f, n, min_minutes, pid)
        if search:
            df = df[df.index.str.lower().str.contains(search.lower())]
        if df.empty:
            st.info("Nothing to show.")
        else:
            show_game_table(ht.style_game_table(df, game_cols, avg_col, compare), len(df))
            scope = f"his last {n} games played" if n else "all games he played this season"
            st.caption(f"Games oldest to newest ({scope}). Values are per game, not per 90, so check the "
                       f"minutes_played row. Pass accuracy, forward pass share and shot accuracy are calculated from "
                       f"counts (season average from the summed counts). Rows marked ~ are the club system's own "
                       f"percentage, averaged simply; their definition is not confirmed. {COLOUR_HELP}")

def page_visuals():
    st.title("Visuals")
    visuals, errors = discover()
    for name, msg in errors.items():
        st.warning(f"Visual '{name}' failed to load: {msg}")
    if not visuals:
        st.info("No visuals found in ui/visuals/.")
        return
    choice = st.selectbox("Visual", list(visuals))
    mod = visuals[choice]
    st.caption(mod.DESCRIPTION)
    data = load_visual_data()
    cfg = mod.settings(st, data)
    try:
        fig = mod.render(data, cfg)
    except Exception as exc:
        st.error(f"{choice} failed: {type(exc).__name__}: {exc}")
        return
    if fig is None:
        st.info("Nothing to show for these settings.")
    else:
        st.plotly_chart(fig, width="stretch", config=vtheme.plotly_config(choice.lower().replace(" ", "_")))

# ----------------------------------------------------------------------------- main
def main() -> None:
    st.sidebar.title("Football Analysis Hub")
    page = st.sidebar.radio("Tool", ["Overview", "Team stats", "Player stats", "Visuals"])
    if st.sidebar.button("Open data folder"):
        open_folder(PROC)
    st.sidebar.divider()

    matches = load("matches")
    if matches.empty:
        st.title("Football Analysis Hub")
        st.info("No games imported yet. Import one with:  python scripts/import_game.py path/to/game.json")
        return
    matches = ht.prepare_matches(matches)
    team_stats, appearances, player_stats = load("team_stats"), load("appearances"), load("player_stats")

    if page == "Overview":
        page_overview(matches, team_stats)
    elif page == "Team stats":
        page_team(matches, team_stats)
    elif page == "Player stats":
        page_players(matches, appearances, player_stats)
    else:
        page_visuals()


main()