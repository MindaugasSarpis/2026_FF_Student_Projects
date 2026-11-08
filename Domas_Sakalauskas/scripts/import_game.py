#!/usr/bin/env python3
"""Import one game JSON from the club system into the processed tables.

Examples (run from the project root):

  python scripts/import_game.py data/raw/package.json                 # asks questions in the terminal
  python scripts/import_game.py game.json --venue away --competition "A lyga"
  python scripts/import_game.py game.json --venue home --score 3-1 --position 20=AM --position 4=LWB --no-prompt

Re-importing the same game (same session_id) REPLACES its rows; it never duplicates.
Settings you chose earlier (venue, competition, score, position overrides) are
remembered on re-import unless you pass new values.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from game_parser import goals_from_events, parse_all  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VENUES = ["home", "away", "neutral"]
COMMON_POSITIONS = ["GK", "RB", "RWB", "CB", "LB", "LWB", "DM", "CM", "AM", "RW", "LW", "RM", "LM", "ST", "CF"]

# table name -> key columns that identify one row inside a game (used for sorting only)
GAME_TABLES = [
    "team_stats", "appearances", "player_stats", "substitutions",
    "sequences", "sequence_players", "sequence_events", "sequence_overview", "events",
]


# --------------------------------------------------------------------------- storage helpers
def atomic_write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False, encoding="utf-8")
    os.replace(tmp, path)


def restore_int_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Reading a CSV turns integer columns that contain blanks into floats (16671 -> 16671.0).
    Turn float columns whose values are all whole numbers back into integers (blanks stay blank)."""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_float_dtype(df[col]):
            vals = df[col].dropna()
            if (vals % 1 == 0).all():
                df[col] = df[col].astype("Int64")
    return df


def upsert_game_rows(path: Path, new: pd.DataFrame, session_id: int) -> None:
    """Remove all old rows of this game from the CSV, then append the new ones."""
    if path.exists():
        old = pd.read_csv(path)
        old = old[old["session_id"] != session_id]
        # keep old columns first so files stay stable even if new columns appear
        new = pd.concat([old, new], ignore_index=True) if not old.empty else new
    atomic_write_csv(restore_int_columns(new), path)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "unknown"


# --------------------------------------------------------------------------- prompts
def ask_choice(question: str, options: list[str], default: str | None = None) -> str:
    print(f"\n{question}")
    for i, o in enumerate(options, 1):
        print(f"  {i}) {o}" + ("  [default]" if o == default else ""))
    while True:
        raw = input("> ").strip()
        if not raw and default:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        if raw in options:
            return raw
        print("  Please type a number from the list.")


def parse_score(text: str) -> tuple[int, int]:
    m = re.fullmatch(r"\s*(\d+)\s*[-:]\s*(\d+)\s*", text)
    if not m:
        raise ValueError(f"Bad score '{text}', use e.g. 3-1 (our goals first)")
    return int(m.group(1)), int(m.group(2))


def prompt_positions(app: pd.DataFrame) -> dict[int, str]:
    """Interactive position editor. Returns {player_id: new_position}."""
    changes: dict[int, str] = {}
    shown = app[(app["lineup_role"] != "bench") | (app["minutes_played"].fillna(0) > 0)].reset_index(drop=True)
    while True:
        print("\nPositions in this game (system value; * = changed by you):")
        for i, r in shown.iterrows():
            pos = changes.get(r.player_id, r.position)
            star = "*" if r.player_id in changes else " "
            print(f"  {i + 1:>2}) #{int(r.jersey_number) if pd.notna(r.jersey_number) else '?':<3} {r['name']:<28} {r.lineup_role:<11} {pos:<4}{star} {r.minutes_played:>6.1f} min")
        raw = input("Change a position? type 'row position' (e.g. '7 AM'), or press Enter to continue > ").strip()
        if not raw:
            return changes
        parts = raw.split()
        if len(parts) == 2 and parts[0].isdigit() and 1 <= int(parts[0]) <= len(shown):
            pos = parts[1].upper()
            if pos not in COMMON_POSITIONS:
                print(f"  (note: '{pos}' is not in the usual list {COMMON_POSITIONS}; keeping it anyway)")
            changes[int(shown.loc[int(parts[0]) - 1, "player_id"])] = pos
        else:
            print("  Format: row number, space, position. Example: 7 AM")


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json_file", type=Path)
    ap.add_argument("--venue", choices=VENUES, help="home / away / neutral (the JSON always treats us as 'home')")
    ap.add_argument("--competition", help="free text, e.g. 'A lyga' or 'Cup'")
    ap.add_argument("--score", help="our-opponent goals, e.g. 2-1 (only needed if the JSON score is empty)")
    ap.add_argument("--position", action="append", default=[], metavar="PLAYER_ID=POS",
                    help="override a player's position for this game (repeatable), e.g. --position 20=AM")
    ap.add_argument("--no-prompt", action="store_true", help="never ask questions; use flags / remembered values / defaults")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data", help="default: <project>/data")
    args = ap.parse_args()

    if not args.json_file.exists():
        print(f"File not found: {args.json_file}")
        return 1
    data = json.loads(args.json_file.read_text(encoding="utf-8"))
    for key in ("match", "players", "team_metrics", "events"):
        if key not in data:
            print(f"This does not look like a match_full export (missing '{key}').")
            return 1

    interactive = sys.stdin.isatty() and not args.no_prompt
    proc = args.data_dir / "processed"
    t = parse_all(data)
    match = t["match"]
    sid = match["session_id"]
    print(f"Game: {match['date']}  vs {match['opponent']}  (session {sid}, season {match['season']})")
    if data.get("package_version") not in {2}:
        print(f"  ! package_version {data.get('package_version')} is new; parser was written for 2. Check the output.")
    if (data.get("data_quality") or {}).get("status") != "clean":
        print(f"  ! data_quality status is '{(data.get('data_quality') or {}).get('status')}' (stats may still be calculating, re-export later).")

    # ---- remembered settings from a previous import of this game
    prev_match = None
    matches_path = proc / "matches.csv"
    if matches_path.exists():
        pm = pd.read_csv(matches_path)
        hit = pm[pm["session_id"] == sid]
        if not hit.empty:
            prev_match = hit.iloc[0].to_dict()
            print("  This game was imported before -> it will be REPLACED. Earlier settings are kept unless you change them.")
    prev_over: dict[int, str] = {}
    app_path = proc / "appearances.csv"
    if prev_match is not None and app_path.exists():
        pa = pd.read_csv(app_path)
        pa = pa[(pa["session_id"] == sid) & (pa["position_overridden"] == True)]  # noqa: E712
        prev_over = dict(zip(pa["player_id"].astype(int), pa["position"]))

    # ---- venue / competition
    venue = args.venue or (prev_match or {}).get("venue")
    if not venue:
        venue = ask_choice("Was this game home, away or neutral?", VENUES, default="home") if interactive else "home"
        if not interactive:
            print("  venue not given -> defaulting to 'home'")
    competition = args.competition if args.competition is not None else (prev_match or {}).get("competition")
    if competition is not None and pd.isna(competition):
        competition = None
    if competition is None and interactive:
        competition = input("\nCompetition (e.g. A lyga, Cup; Enter to skip) > ").strip() or None

    # ---- score
    gf, ga = match["goals_for"], match["goals_against"]
    if args.score:
        gf, ga = parse_score(args.score)
    elif gf is None or ga is None:
        pg, pa_ = (prev_match or {}).get("goals_for"), (prev_match or {}).get("goals_against")
        if prev_match and pd.notna(pg) and pd.notna(pa_):
            gf, ga = int(pg), int(pa_)
        else:
            ev_gf, ev_ga = goals_from_events(data)
            print(f"\nScore missing in the JSON. Goals found in events: {ev_gf}-{ev_ga}")
            if interactive:
                raw = input("Enter final score (ours-theirs), or Enter to accept the events count > ").strip()
                gf, ga = parse_score(raw) if raw else (ev_gf, ev_ga)
            else:
                gf, ga = ev_gf, ev_ga
                print("  -> using the events count")
    ev_gf, ev_ga = goals_from_events(data)
    if (gf, ga) != (ev_gf, ev_ga):
        print(f"  ! Score {gf}-{ga} differs from goal events {ev_gf}-{ev_ga} (own goals / missing tags?).")

    # ---- position overrides
    app = t["appearances"]
    overrides: dict[int, str] = dict(prev_over)
    for item in args.position:
        pid, _, pos = item.partition("=")
        if not pid.strip().isdigit() or not pos:
            print(f"Bad --position '{item}', use PLAYER_ID=POS")
            return 1
        overrides[int(pid)] = pos.strip().upper()
    if interactive and not args.position:
        # editor starts from what we know; previously changed values show as *
        app_view = app.copy()
        for pid, pos in overrides.items():
            app_view.loc[app_view.player_id == pid, "position"] = pos
        new = prompt_positions(app_view)
        # prompt_positions reports changes made in THIS session; keep previous ones too
        overrides.update(new)
    unknown = [p for p in overrides if p not in set(app.player_id)]
    if unknown:
        print(f"  ! Position override for player id(s) {unknown} ignored: not in this game's squad.")
        overrides = {k: v for k, v in overrides.items() if k not in unknown}
    for pid, pos in overrides.items():
        mask = app.player_id == pid
        app.loc[mask, "position"] = pos
        app.loc[mask, "position_overridden"] = app.loc[mask, "position_system"] != pos
    app = app.copy()
    # an override equal to the system value is not an override
    overrides = {k: v for k, v in overrides.items() if app.loc[app.player_id == k, "position_overridden"].any()}

    # ---- assemble matches row
    match.update(
        goals_for=gf, goals_against=ga, venue=venue, competition=competition,
        imported_at=datetime.now().isoformat(timespec="seconds"), source_file=args.json_file.name,
    )
    match_df = pd.DataFrame([match])
    if matches_path.exists():
        old = pd.read_csv(matches_path)
        old = old[old["session_id"] != sid]
        match_df = pd.concat([old, match_df], ignore_index=True)
    match_df = match_df.sort_values(["date", "session_id"]).reset_index(drop=True)

    # ---- write everything
    atomic_write_csv(match_df, matches_path)
    t["appearances"] = app
    # skip unused bench players in player_stats (they stay in appearances.csv)
    played = set(app.loc[(app["lineup_role"] != "bench") | (app["minutes_played"].fillna(0) > 0), "player_id"])
    t["player_stats"] = t["player_stats"][t["player_stats"]["player_id"].isin(played)]
    for name in GAME_TABLES:
        upsert_game_rows(proc / f"{name}.csv", t[name], sid)

    # players master list (keeps photo filenames you add later)
    players_path = proc / "players.csv"
    cur = app[["player_id", "name"]].drop_duplicates("player_id").copy()
    cur["last_seen"] = match["date"]
    if players_path.exists():
        old = pd.read_csv(players_path)
        merged = old.set_index("player_id")
        for _, r in cur.iterrows():
            if r.player_id in merged.index:
                merged.loc[r.player_id, "name"] = r["name"]
                if str(r.last_seen) > str(merged.loc[r.player_id, "last_seen"]):
                    merged.loc[r.player_id, "last_seen"] = r.last_seen
            else:
                merged.loc[r.player_id] = {"name": r["name"], "photo": None, "last_seen": r.last_seen}
        players = merged.reset_index()
    else:
        players = cur.assign(photo=None)[["player_id", "name", "photo", "last_seen"]]
    atomic_write_csv(players.sort_values("name"), players_path)

    # metrics dictionary: union by key, newest wins
    md_path = proc / "metrics_dictionary.csv"
    md = t["metrics_dictionary"]
    if md_path.exists():
        old = pd.read_csv(md_path)
        md = pd.concat([old[~old["key"].isin(md["key"])], md], ignore_index=True)
    atomic_write_csv(md.sort_values("key"), md_path)

    # raw JSON kept forever so everything can be re-parsed later
    raw_dir = args.data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for old_raw in raw_dir.glob(f"*_s{sid}_*.json"):
        old_raw.unlink()
    raw_target = raw_dir / f"{match['date']}_s{sid}_{slug(match['opponent'])}.json"
    if args.json_file.resolve() != raw_target.resolve():
        shutil.copyfile(args.json_file, raw_target)

    print(f"\nImported: {match['date']} vs {match['opponent']}  {gf}-{ga}  ({venue}"
          f"{', ' + competition if competition else ''})")
    print(f"  team stats rows: {len(t['team_stats'])}   player stat rows: {len(t['player_stats'])}   events: {len(t['events'])}   sequences: {len(t['sequences'])}")
    if overrides:
        print(f"  position overrides: {overrides}")
    print(f"  raw json:    {raw_target.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())