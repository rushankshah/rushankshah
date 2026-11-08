#!/usr/bin/env python3
"""Build a static GitHub activity graph SVG from the public contribution calendar.

The shared hosts for this card are gone (activity-graph.herokuapp.com 404,
github-readme-activity-graph.vercel.app 402). This script uses the same public
GraphQL calendar and the xcode theme colors from
Ashutosh00710/github-readme-activity-graph, and draws the line in its final
state so the SVG stays visible inside an <img> tag.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

WIDTH = 1200
HEIGHT = 420
DAYS = 31
PLOT_LEFT = 90
PLOT_RIGHT = 1150
PLOT_TOP = 80
PLOT_BOTTOM = 350

BG = "202124"
BORDER = "ffffff"
INK = "fcfcfa"
LINE = "c4e3ff"
POINT = "ff8070"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    name
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def nice_max(value: int) -> int:
    if value <= 0:
        return 4
    magnitude = 10 ** len(str(value - 1)) // 10 or 1
    for factor in (1, 2, 4, 5, 10):
        ceiling = factor * magnitude
        if ceiling >= value:
            return ceiling
    return value


def y_ticks(ymax: int) -> list[int]:
    if ymax <= 5:
        return list(range(0, ymax + 1))
    step = ymax // 4
    ticks = list(range(0, ymax + 1, step))
    if ticks[-1] != ymax:
        ticks.append(ymax)
    return ticks


def select_days(days: list[dict]) -> list[dict]:
    """Match the upstream fetcher: drop a trailing empty day, then keep 31."""
    selected = list(days)
    if selected and selected[-1]["contributionCount"] == 0:
        selected.pop()
    extra = len(selected) - DAYS
    if extra > 0:
        selected = selected[extra:]
    return selected


def fetch_calendar(username: str, token: str) -> tuple[str, list[dict]]:
    now = datetime.now(timezone.utc)
    payload = {
        "query": QUERY,
        "variables": {
            "login": username,
            "from": (now - timedelta(days=DAYS)).isoformat(),
            "to": (now + timedelta(days=1)).isoformat(),
        },
    }
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "rushankshah-readme-cards",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")[:300]
        raise SystemExit(f"GitHub GraphQL HTTP {error.code}: {detail}") from error

    if body.get("errors"):
        message = body["errors"][0].get("message", "unknown GraphQL error")
        raise SystemExit(f"GitHub GraphQL error: {message}")

    user = (body.get("data") or {}).get("user")
    if not user:
        raise SystemExit(f"GitHub user {username!r} was not found")

    days = []
    calendar = user["contributionsCollection"]["contributionCalendar"]
    for week in calendar["weeks"]:
        days.extend(week["contributionDays"])
    days.sort(key=lambda day: day["date"])
    name = user.get("name") or username
    return name, select_days(days)


def render_svg(name: str, days: list[dict]) -> str:
    if not days:
        raise SystemExit("No contribution days returned")

    counts = [int(day["contributionCount"]) for day in days]
    ymax = nice_max(max(counts))
    ticks = y_ticks(ymax)
    title = f"{name}'s Contribution Graph"
    label = xml_escape(title)
    count = len(days)

    def x_at(index: int) -> float:
        if count == 1:
            return (PLOT_LEFT + PLOT_RIGHT) / 2
        span = PLOT_RIGHT - PLOT_LEFT
        return PLOT_LEFT + span * index / (count - 1)

    def y_at(value: int) -> float:
        span = PLOT_BOTTOM - PLOT_TOP
        return PLOT_BOTTOM - span * (value / ymax)

    grid = []
    for tick in ticks:
        y = y_at(tick)
        grid.append(
            f'<line x1="{PLOT_LEFT}" y1="{y:.1f}" x2="{PLOT_RIGHT}" y2="{y:.1f}" '
            f'stroke="#{INK}" stroke-opacity="0.3" stroke-dasharray="2 2"/>'
        )
        grid.append(
            f'<text x="{PLOT_LEFT - 10}" y="{y + 4:.1f}" fill="#{INK}" '
            f'font-size="12" text-anchor="end">{tick}</text>'
        )
    for index, day in enumerate(days):
        x = x_at(index)
        grid.append(
            f'<line x1="{x:.1f}" y1="{PLOT_TOP}" x2="{x:.1f}" y2="{PLOT_BOTTOM}" '
            f'stroke="#{INK}" stroke-opacity="0.15" stroke-dasharray="2 2"/>'
        )
        day_num = int(day["date"][8:10])
        grid.append(
            f'<text x="{x:.1f}" y="{PLOT_BOTTOM + 18}" fill="#{INK}" '
            f'font-size="11" text-anchor="middle">{day_num}</text>'
        )

    points = " ".join(f"{x_at(i):.1f},{y_at(value):.1f}" for i, value in enumerate(counts))
    dots = "\n".join(
        f'<circle cx="{x_at(i):.1f}" cy="{y_at(value):.1f}" r="4.5" fill="#{POINT}"/>'
        for i, value in enumerate(counts)
    )
    summary = ", ".join(f"{day['date']}={day['contributionCount']}" for day in days)
    mid_y = (PLOT_TOP + PLOT_BOTTOM) / 2

    return f"""<svg width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{label}">
  <title>{label}</title>
  <desc>{xml_escape(summary)}</desc>
  <rect x="0.5" y="0.5" width="{WIDTH - 1}" height="{HEIGHT - 1}" fill="#{BG}" stroke="#{BORDER}" stroke-width="1"/>
  <text x="{WIDTH / 2:.0f}" y="42" fill="#{INK}" font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="20" font-weight="600" text-anchor="middle">{label}</text>
  <text x="22" y="{mid_y:.1f}" fill="#{INK}" font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="13" text-anchor="middle" transform="rotate(-90 22 {mid_y:.1f})">Contributions</text>
  <text x="{(PLOT_LEFT + PLOT_RIGHT) / 2:.0f}" y="{HEIGHT - 12}" fill="#{INK}" font-family="Segoe UI, Ubuntu, Sans-Serif" font-size="13" text-anchor="middle">Days</text>
  {chr(10).join(grid)}
  <polyline points="{points}" fill="none" stroke="#{LINE}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>
  {dots}
</svg>
"""


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} OUTPUT.svg")
    output = sys.argv[1]
    username = (
        os.environ.get("README_USERNAME")
        or os.environ.get("GITHUB_REPOSITORY_OWNER")
        or "rushankshah"
    )
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("Set GITHUB_TOKEN or GH_TOKEN (public read is enough)")

    name, days = fetch_calendar(username, token)
    svg = render_svg(name, days)
    lowered = svg.lower()
    if "<svg" not in lowered or "something went wrong" in lowered or "contribution graph" not in lowered:
        raise SystemExit("Refusing to write an activity graph that does not look valid")
    with open(output, "w", encoding="utf-8") as handle:
        handle.write(svg)
    total = sum(int(day["contributionCount"]) for day in days)
    print(
        f"wrote {output} for {name}: {len(days)} days, {total} contributions, "
        f"{days[0]['date']} to {days[-1]['date']}"
    )


if __name__ == "__main__":
    main()
