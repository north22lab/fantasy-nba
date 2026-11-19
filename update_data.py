"""Pulls your ESPN fantasy basketball league and writes docs/data.json.
Run locally or on a schedule via GitHub Actions (see README.md)."""
import json, os, datetime as dt
from espn_api.basketball import League

YEAR = int(os.environ.get("ESPN_YEAR", 2027))  # ESPN names a season by the year it ends: 2026-27 = 2027
OUT = os.path.join(os.path.dirname(__file__), "docs", "data.json")
TEAM_ID = os.environ.get("ESPN_TEAM_ID")  # optional: your team's id, to get a "My team" view

league = League(
    league_id=int(os.environ["ESPN_LEAGUE_ID"]),
    year=YEAR,
    espn_s2=os.environ.get("ESPN_S2") or None,   # only needed for private leagues
    swid=os.environ.get("ESPN_SWID") or None,
)
now = dt.datetime.now()

def avg(p, period):
    """Average fantasy points for a period: total, last_7, last_15, last_30."""
    s = p.stats.get(f"{YEAR}_{period}") or {}
    v = s.get("applied_avg")
    if v is None:
        v = (s.get("avg") or {}).get("PTS")  # fallback for category leagues: points only
    return round(v, 1) if isinstance(v, (int, float)) else None

def games_next_7(p):
    try:
        return sum(1 for g in p.schedule.values() if now <= g["date"] < now + dt.timedelta(days=7))
    except Exception:
        return None

def row(p, owner):
    return {
        "name": p.name, "team": p.proTeam, "pos": p.position,
        "status": getattr(p, "injuryStatus", "ACTIVE") or "ACTIVE",
        "owner": owner, "pct_owned": getattr(p, "percent_owned", None),
        "season": avg(p, "total"), "l7": avg(p, "last_7"),
        "l15": avg(p, "last_15"), "l30": avg(p, "last_30"),
        "games": games_next_7(p),
    }

players, mine = [], []
for t in league.teams:
    for p in t.roster:
        players.append(row(p, t.team_name))
        if TEAM_ID and str(t.team_id) == TEAM_ID:
            mine.append(p.name)
for p in league.free_agents(size=150):
    players.append(row(p, None))

# injury status changes since the last run
changes = []
try:
    with open(OUT) as f:
        old = json.load(f)
    prev = {x["name"]: x["status"] for x in old["players"]}
    for x in players:
        if x["name"] in prev and prev[x["name"]] != x["status"]:
            changes.append({"name": x["name"], "from": prev[x["name"]], "to": x["status"],
                            "at": now.isoformat(timespec="minutes")})
    changes = changes + old.get("changes", [])
except Exception:
    pass

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump({"updated": now.isoformat(timespec="minutes"), "league": league.settings.name,
               "mine": mine, "players": players, "changes": changes[:40]}, f)
print(f"Wrote {len(players)} players, {len(changes)} status changes")
