#!/usr/bin/env python3
"""
Fetches real contribution stats (including private) via GitHub GraphQL API
and generates a streak-card.svg in the repo root.
"""

import os
import json
import sys
from datetime import datetime, timedelta, date, timezone
from urllib.request import urlopen, Request
from urllib.error import URLError

TOKEN    = os.environ.get("GH_PAT", "")
USERNAME = "Sparshjoshi-iit"

if not TOKEN:
    print("ERROR: GH_PAT environment variable not set", file=sys.stderr)
    sys.exit(1)

# ── GraphQL helper ────────────────────────────────────────────────────────────

def graphql(query: str) -> dict:
    req = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={
            "Authorization": f"bearer {TOKEN}",
            "Content-Type":  "application/json",
        },
    )
    with urlopen(req) as r:
        return json.loads(r.read())

# ── Date helpers ──────────────────────────────────────────────────────────────

def add_one_year(dt: datetime) -> datetime:
    try:
        return dt.replace(year=dt.year + 1)
    except ValueError:          # Feb 29 edge-case
        return dt.replace(year=dt.year + 1, day=28)

def fmt_date(d) -> str:
    return d.strftime("%b %d, %Y") if d else "N/A"

def fmt_range(s, e) -> str:
    if not s or not e:
        return "N/A"
    if s == e:
        return fmt_date(s)
    return f"{s.strftime('%b %d')} - {e.strftime('%b %d, %Y')}"

# ── Fetch account creation date ───────────────────────────────────────────────

print("Fetching account info...")
meta = graphql(f'{{ user(login: "{USERNAME}") {{ createdAt }} }}')
created_str = meta["data"]["user"]["createdAt"]
created_at  = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
now         = datetime.now(timezone.utc)

print(f"Account created: {created_str}")

# ── Fetch ALL contributions in 1-year chunks (API limit per request) ──────────

all_days: dict[str, int] = {}
chunk_start = created_at

while chunk_start < now:
    chunk_end = min(add_one_year(chunk_start), now)
    from_str  = chunk_start.strftime("%Y-%m-%dT%H:%M:%SZ")
    to_str    = chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"  Querying {from_str[:10]} → {to_str[:10]}")

    query = f"""{{
      user(login: "{USERNAME}") {{
        contributionsCollection(from: "{from_str}", to: "{to_str}") {{
          contributionCalendar {{
            weeks {{
              contributionDays {{
                date
                contributionCount
              }}
            }}
          }}
        }}
      }}
    }}"""

    resp  = graphql(query)
    weeks = resp["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]

    for week in weeks:
        for day in week["contributionDays"]:
            d = day["date"]
            if d not in all_days:           # don't double-count overlap days
                all_days[d] = day["contributionCount"]

    chunk_start = chunk_end

# ── Compute stats ─────────────────────────────────────────────────────────────

sorted_days = sorted(all_days.items())      # [(date_str, count), ...]

# Total
total = sum(c for _, c in sorted_days)

# Current streak (walk back from today; accept "no commit yet today")
today   = now.date()
check   = today if all_days.get(str(today), 0) > 0 else today - timedelta(days=1)
current_streak = 0
while str(check) in all_days and all_days[str(check)] > 0:
    current_streak += 1
    check -= timedelta(days=1)

streak_end   = today if all_days.get(str(today), 0) > 0 else today - timedelta(days=1)
streak_start = (streak_end - timedelta(days=current_streak - 1)
                if current_streak > 0 else streak_end)

# Longest streak
longest_streak = longest_start = longest_end = None
cur = cur_start = 0

for d_str, count in sorted_days:
    d = date.fromisoformat(d_str)
    if count > 0:
        if cur == 0:
            cur_start = d
        cur += 1
        if longest_streak is None or cur > longest_streak:
            longest_streak = cur
            longest_start  = cur_start
            longest_end    = d
    else:
        cur = 0

longest_streak = longest_streak or 0

print(f"Total: {total}  |  Current streak: {current_streak}  |  Longest streak: {longest_streak}")

# ── Write last-year count for the badge in README ─────────────────────────────

from_1yr = (now - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ")
to_now   = now.strftime("%Y-%m-%dT%H:%M:%SZ")

yr_query = f"""{{
  user(login: "{USERNAME}") {{
    contributionsCollection(from: "{from_1yr}", to: "{to_now}") {{
      contributionCalendar {{ totalContributions }}
    }}
  }}
}}"""

yr_resp      = graphql(yr_query)
last_year_ct = yr_resp["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
print(f"Last-year count: {last_year_ct}")

# Write to a file so the workflow shell step can read it
with open(".contribution_counts", "w") as f:
    f.write(f"LAST_YEAR={last_year_ct}\n")
    f.write(f"TOTAL={total}\n")

# ── Generate SVG card ─────────────────────────────────────────────────────────

account_since = created_at.strftime("%b %d, %Y")

svg = f"""<svg width="500" height="195" xmlns="http://www.w3.org/2000/svg">
  <style>
    .bg      {{ fill: #1a1b27; }}
    .border  {{ fill: none; stroke: #2d2d3f; stroke-width: 1; }}
    .div     {{ stroke: #2d2d3f; stroke-width: 1; }}
    .num     {{ font: 700 30px 'Segoe UI', sans-serif; fill: #ffffff; }}
    .label   {{ font: 600 13px 'Segoe UI', sans-serif; fill: #a0a0b8; }}
    .sub     {{ font: 400 11px 'Segoe UI', sans-serif; fill: #555570; }}
    .s-num   {{ font: 700 30px 'Segoe UI', sans-serif; fill: #f97316; }}
    .s-label {{ font: 600 13px 'Segoe UI', sans-serif; fill: #f97316; }}
  </style>

  <!-- Background & border -->
  <rect width="500" height="195" rx="12" class="bg"/>
  <rect width="498" height="193" x="1" y="1" rx="11" class="border"/>

  <!-- Dividers -->
  <line x1="166" y1="28" x2="166" y2="167" class="div"/>
  <line x1="334" y1="28" x2="334" y2="167" class="div"/>

  <!-- Left panel: Total Contributions -->
  <text x="83"  y="88"  text-anchor="middle" class="num"  >{total}</text>
  <text x="83"  y="110" text-anchor="middle" class="label">Total Contributions</text>
  <text x="83"  y="127" text-anchor="middle" class="sub"  >{account_since} - Present</text>

  <!-- Middle panel: Current Streak -->
  <circle cx="250" cy="86" r="33" fill="none" stroke="#f97316" stroke-width="3"/>
  <text x="250" y="74"  text-anchor="middle" style="font:22px serif">🔥</text>
  <text x="250" y="98"  text-anchor="middle" class="s-num"  >{current_streak}</text>
  <text x="250" y="138" text-anchor="middle" class="s-label">Current Streak</text>
  <text x="250" y="154" text-anchor="middle" class="sub"    >{fmt_range(streak_start, streak_end)}</text>

  <!-- Right panel: Longest Streak -->
  <text x="417" y="88"  text-anchor="middle" class="num"  >{longest_streak}</text>
  <text x="417" y="110" text-anchor="middle" class="label">Longest Streak</text>
  <text x="417" y="127" text-anchor="middle" class="sub"  >{fmt_range(longest_start, longest_end)}</text>
</svg>"""

with open("streak-card.svg", "w") as f:
    f.write(svg)

print("streak-card.svg written successfully.")
