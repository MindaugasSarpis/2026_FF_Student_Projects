"""Pure pandas logic for the dashboard (no Streamlit in this file).

app.py only draws things; every table is built here, so it is easy to test and to extend.
"""
from __future__ import annotations

import re

import pandas as pd

# ----------------------------------------------------------------------------- colour rules
SIMILAR_PCT = 0.10      # a value within +-10 % of the average counts as "similar" (yellow)
SMALL_COUNT_TOL = 0.5   # for whole-number stats (goals, shots...) +-0.5 is always "similar"
GREEN = "background-color: rgba(46, 160, 67, 0.40)"
YELLOW = "background-color: rgba(227, 179, 31, 0.45)"
RED = "background-color: rgba(218, 54, 51, 0.40)"

# derived percentage metric -> the metric it should be sorted next to
BASE_OVERRIDE = {"pass_accuracy_pct": "passes_made", "shot_accuracy_percent": "total_shots"}


# ----------------------------------------------------------------------------- matches
def prepare_matches(m: pd.DataFrame) -> pd.DataFrame:
    m = m.copy()
    m["date"] = pd.to_datetime(m["date"])
    m["venue"] = m["venue"].fillna("home")
    m["competition"] = m["competition"].fillna("-")

    def result(r):
        if pd.isna(r.goals_for) or pd.isna(r.goals_against):
            return "?"
        return "W" if r.goals_for > r.goals_against else "L" if r.goals_for < r.goals_against else "D"

    m["result"] = m.apply(result, axis=1)
    m["score"] = m.apply(lambda r: "?" if r.result == "?" else f"{int(r.goals_for)}-{int(r.goals_against)}", axis=1)
    return m.sort_values(["date", "session_id"], ascending=False).reset_index(drop=True)


def summary_labels(n: int | None) -> tuple[str, str]:
    """Names of the two summary columns."""
    return ("Season average", "Season best") if n is None else (f"Average (last {n})", f"Best (last {n})")


def game_labels(games: pd.DataFrame) -> dict[int, str]:
    """Column header per game: the opponent's name; the date is added only if the name repeats."""
    names = dict(zip(games["session_id"], games["opponent"].fillna("?")))
    dup = pd.Series(names).duplicated(keep=False)
    dates = dict(zip(games["session_id"], pd.to_datetime(games["date"]).dt.strftime("%d %b")))
    for sid in names:
        if dup[sid]:
            names[sid] = f"{names[sid]} ({dates[sid]})"
    dup = pd.Series(names).duplicated(keep=False)  # same opponent on the same day: add the id
    for sid in names:
        if dup[sid]:
            names[sid] = f"{names[sid]} #{sid}"
    return names


def metric_order_key(key: str):
    """Sort metrics alphabetically, but put '<x>_percent' right after '<x>'."""
    base = BASE_OVERRIDE.get(key, re.sub(r"_(percent|percentage)$", "", key))
    return (base, 0 if base == key else 1, key)


# ----------------------------------------------------------------------------- team: averages
TEAM_PERCENT_DEFS = {
    "passes_success_percent": ("passes_completed", "passes_made"),
    "passes_forward_percentage": ("passes_forward", "passes_made"),
    "shot_accuracy_percent": ("shots_on_target", "total_shots"),
}


def team_table(team_stats: pd.DataFrame, games: pd.DataFrame, period: str) -> pd.DataFrame:
    """Per-game average of every team metric over the chosen games.

    Percentages listed in TEAM_PERCENT_DEFS are NOT averaged: they are recalculated from the summed counts
    (e.g. 100 completed of 120 passes over two games = 83.3 %, not the 70 % you get by averaging 90 % and 50 %).
    """
    d = team_stats[team_stats["session_id"].isin(games["session_id"]) & (team_stats["period"] == period)]
    g = d.groupby("metric", sort=False).agg(
        label=("label", "first"), type=("type", "first"),
        ours=("ours", "mean"), opponent=("opponent", "mean"), games=("session_id", "nunique"),
    )

    sums = d.groupby("metric")[["ours", "opponent"]].sum(min_count=1)
    if "passes_total" in sums.index:
        lost = sums.loc["pass_lost_after_reception"] if "pass_lost_after_reception" in sums.index else 0
        sums.loc["passes_made"] = sums.loc["passes_total"] - lost

    g["recomputed"] = False
    for key, (num, den) in TEAM_PERCENT_DEFS.items():
        if key in g.index and num in sums.index and den in sums.index:
            for side in ("ours", "opponent"):
                total = sums.loc[den, side]
                g.loc[key, side] = sums.loc[num, side] / total * 100 if total > 0 else float("nan")
            g.loc[key, "recomputed"] = True

    g["diff"] = g["ours"] - g["opponent"]
    return g.reset_index()


# ----------------------------------------------------------------------------- game-by-game tables
def _finish(wide: pd.DataFrame, names: dict, n: int | None) -> tuple[pd.DataFrame, list[str], str, str]:
    """Rename game columns, drop empty rows, add the average and best columns."""
    avg_label, best_label = summary_labels(n)
    out = wide.rename(columns=names).dropna(how="all")
    game_cols = list(out.columns)
    out[avg_label] = out[game_cols].mean(axis=1)
    out[best_label] = out[game_cols].max(axis=1)
    out.index.name = "Metric"
    return out, game_cols, avg_label, best_label

def _recompute_percentages(p: pd.DataFrame):
    """p: rows = metrics, columns = games (one side only).

    Replaces the per-game value of every metric in TEAM_PERCENT_DEFS by numerator / denominator * 100 for that game,
    and returns (p, {metric: pooled season value}), the pooled value being sum(numerator) / sum(denominator) * 100.
    """
    p = p.copy()
    if "passes_total" in p.index:
        lost = p.loc["pass_lost_after_reception"].fillna(0) if "pass_lost_after_reception" in p.index else 0
        p.loc["passes_made"] = p.loc["passes_total"] - lost
    pooled = {}
    for key, (num, den) in TEAM_PERCENT_DEFS.items():
        if key in p.index and num in p.index and den in p.index:
            denom = p.loc[den]
            p.loc[key] = p.loc[num] / denom.where(denom > 0) * 100
            total = denom.sum()
            pooled[key] = p.loc[num].sum() / total * 100 if total > 0 else float("nan")
    return p.drop(index="passes_made", errors="ignore"), pooled

def team_game_table(team_stats, games, period, n=None, sides=("ours", "opponent")):
    """Rows = team metrics (ours / opponent), columns = games oldest -> newest, + average and best."""
    g = games.sort_values(["date", "session_id"])
    sids = list(g["session_id"])
    d = team_stats[team_stats["session_id"].isin(sids) & (team_stats["period"] == period)]
    if d.empty:
        return pd.DataFrame(), [], *summary_labels(n)
    order = list(dict.fromkeys(d["metric"]))  # keeps the club system's order (percentages sit next to their stat)
    info = d.drop_duplicates("metric").set_index("metric")[["label", "type"]]

    parts, pooled = [], {}
    for side_i, side in enumerate(sides):
        p = d.pivot_table(index="metric", columns="session_id", values=side, aggfunc="first").reindex(index=order, columns=sids)
        p, side_pooled = _recompute_percentages(p)  # per-game % from that game's counts + the pooled season value
        pooled.update({(key, side): val for key, val in side_pooled.items()})
        label = [(info.loc[m, "label"] if pd.notna(info.loc[m, "label"]) else m)
                 + (" (s)" if info.loc[m, "type"] == "Time" else "")
                 + (" ~" if info.loc[m, "type"] == "Percentage" and m not in TEAM_PERCENT_DEFS else "")  # ~ = no formula yet
                 for m in p.index]
        p["_key"] = p.index
        p["_side"] = side
        p["_label"] = [f"{lab} ({side})" for lab in label]
        p["_order"] = [order.index(m) * 2 + side_i for m in p.index]
        parts.append(p)
    wide = pd.concat(parts).sort_values("_order")
    dup = wide["_label"].duplicated(keep=False)  # two metrics with the same label: add the key
    wide.loc[dup, "_label"] = wide.loc[dup, "_label"] + " [" + wide.loc[dup, "_key"] + "]"
    label_of = {(k, sd): lab for k, sd, lab in zip(wide["_key"], wide["_side"], wide["_label"])}
    wide = wide.set_index("_label").drop(columns=["_key", "_side", "_order"])

    out, game_cols, avg_label, best_label = _finish(wide, game_labels(g), n)
    for (key, side), value in pooled.items():  # season average of a recalculated % = sum of counts, not mean of %
        lab = label_of.get((key, side))
        if lab in out.index:
            out.loc[lab, avg_label] = value
    return out, game_cols, avg_label, best_label


# Player percentages that we recalculate from counts. Season value = sum(numerator) / sum(denominator) * 100.
# Every other percentage metric is the club system's own value (its definition changes between versions): shown with "~".
PLAYER_PERCENT_DEFS = {
    "pass_accuracy_pct": ("passes_completed", "passes_made"),   # our own row; replaces the system's passes_success_percent
    "passes_forward_percentage": ("passes_forward", "passes_made"),
    "shot_accuracy_percent": ("shots_on_target", "total_shots"),
}


def player_game_table(appearances, player_stats, games, n, min_minutes, player_id):
    """Rows = one player's metrics, columns = the games he played (oldest -> newest), + average and best."""
    a = appearances[(appearances["player_id"] == player_id) & appearances["session_id"].isin(games["session_id"])
                    & (appearances["minutes_played"] >= min_minutes)]
    a = a.merge(games[["session_id", "date", "opponent"]], on="session_id").sort_values(["date", "session_id"], ascending=False)
    if n:
        a = a.head(n)  # his last N games PLAYED
    a = a.sort_values(["date", "session_id"])
    if a.empty:
        return pd.DataFrame(), [], *summary_labels(n)
    sids = list(a["session_id"])

    ps = player_stats[(player_stats["player_id"] == player_id) & player_stats["session_id"].isin(sids)]
    wide = ps.pivot_table(index="metric", columns="session_id", values="value", aggfunc="first").reindex(columns=sids)

    if "passes_total" in wide.index:  # real passes = passes_total minus balls lost after a bad reception
        lost = wide.loc["pass_lost_after_reception"].fillna(0) if "pass_lost_after_reception" in wide.index else 0
        wide.loc["passes_made"] = wide.loc["passes_total"] - lost

    pooled = {}
    for key, (num, den) in PLAYER_PERCENT_DEFS.items():
        if num in wide.index and den in wide.index:
            denom = wide.loc[den]
            wide.loc[key] = wide.loc[num] / denom.where(denom > 0) * 100
            total = denom.sum()
            pooled[key] = wide.loc[num].sum() / total * 100 if total > 0 else float("nan")
    wide = wide.drop(index="passes_success_percent", errors="ignore")  # system value uses a different definition

    wide = wide.loc[sorted(wide.index, key=metric_order_key)]
    top = pd.DataFrame([a["minutes_played"].to_numpy()], index=["minutes_played"], columns=sids)
    wide = pd.concat([top, wide])

    out, game_cols, avg_label, best_label = _finish(wide, game_labels(a), n)
    for key, value in pooled.items():  # season average of a recalculated % = sum of counts, not mean of %
        if key in out.index:
            out.loc[key, avg_label] = value
    # "~" = the club system's own percentage, averaged simply (its definition is not known / not stable)
    marked = {k: f"{k} ~" for k in out.index if k.endswith(("_percent", "_percentage")) and k not in PLAYER_PERCENT_DEFS}
    return out.rename(index=marked), game_cols, avg_label, best_label


# ----------------------------------------------------------------------------- player: averages
def player_table(appearances, player_stats, games, n, min_minutes, mode):
    """One row per player. Window = each player's last N games PLAYED (>= min_minutes)."""
    a = appearances[appearances["session_id"].isin(games["session_id"]) & (appearances["minutes_played"] >= min_minutes)]
    a = a.merge(games[["session_id", "date"]], on="session_id").sort_values("date", ascending=False)
    if n:
        a = a.groupby("player_id", group_keys=False).head(n)

    wide = player_stats.pivot_table(index=["session_id", "player_id"], columns="metric", values="value", aggfunc="first").reset_index()
    d = a.merge(wide, on=["session_id", "player_id"], how="left")

    # real passes made = passes_total minus balls lost after a bad reception (not his pass)
    if "passes_total" in d:
        lost = d["pass_lost_after_reception"].fillna(0) if "pass_lost_after_reception" in d else 0
        d["passes_made"] = d["passes_total"] - lost

    metric_cols = [c for c in d.columns if c in set(wide.columns) - {"session_id", "player_id"} or c == "passes_made"]
    g = d.groupby("player_id")
    out = g[metric_cols].sum(min_count=1)
    out["Player"] = g["name"].first()
    out["Pos"] = g["position"].agg(lambda s: s.mode().iat[0])
    out["Games"] = g.size()
    out["Minutes"] = g["minutes_played"].sum()

    # ratios are calculated from the SUMMED counts (never an average of percentages)
    if {"passes_completed", "passes_made"} <= set(out.columns):
        out["pass_accuracy_pct"] = (out["passes_completed"] / out["passes_made"].where(out["passes_made"] > 0)) * 100

    ratio_cols = [c for c in ("pass_accuracy_pct",) if c in out.columns]
    count_cols = [c for c in metric_cols if c in out.columns]
    if mode == "Per 90":
        out[count_cols] = out[count_cols].div(out["Minutes"], axis=0) * 90
    elif mode == "Per game":
        out[count_cols] = out[count_cols].div(out["Games"], axis=0)
    return out.reset_index(drop=True), count_cols + ratio_cols


# ----------------------------------------------------------------------------- styling
def format_value(v) -> str:
    if pd.isna(v):
        return ""
    return f"{v:.0f}" if float(v).is_integer() else f"{v:.2f}"


def color_row(row: pd.Series, game_cols: list[str], avg_col: str) -> pd.Series:
    """Colour every game cell of one row against that row's average."""
    styles = pd.Series("", index=row.index)
    avg = row[avg_col]
    if pd.isna(avg):
        return styles
    vals = row[game_cols].dropna()
    is_count = all(float(v).is_integer() for v in vals)
    tol = max(SIMILAR_PCT * abs(avg), SMALL_COUNT_TOL if is_count else 0.0) + 1e-9
    for c in game_cols:
        v = row[c]
        if pd.isna(v):
            continue
        diff = v - avg
        styles[c] = YELLOW if abs(diff) <= tol else GREEN if diff > 0 else RED
    return styles


def style_game_table(df: pd.DataFrame, game_cols: list[str], avg_col: str, compare: bool):
    sty = df.style.format(format_value, na_rep="")
    if compare:
        sty = sty.apply(color_row, axis=1, game_cols=game_cols, avg_col=avg_col)
    return sty