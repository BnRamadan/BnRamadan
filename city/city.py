# -*- coding: utf-8 -*-
"""
profile_city.py - a year of GitHub contributions drawn as an isometric city in the person's own
identity, with a light that runs across the days like the snake does: one SVG, no third-party
renderer, no token.

    python profile_city.py USER --out city.svg [--tokens tokens.json] [--title "BUILD CITY"] [--font-css fonts.css]
    python profile_city.py --self-test

Data: the public calendar at https://github.com/users/USER/contributions - the same page the
profile renders, so it already counts private work when the person has switched on "Include
private contributions on my profile", and it needs no token. Every day becomes a block; its
height follows the day's count (square root, so one busy day does not flatten the year), its
colour steps through five tones of the palette. The blocks rise in a wave on load, a cyan
runner travels the busiest stretch, and the stats are computed from the same data (total,
longest streak, busiest day) - nothing typed by hand.

Meant to run in a daily GitHub Actions job inside the profile repo (copy this one file in);
stdlib only; ASCII output; exit 0 = written, 2 = the calendar could not be read.
"""
import argparse, datetime as dt, html, io, json, math, re, sys, urllib.request

DEFAULT_TOKENS = {"bg": "#04060A", "elevated": "#0A111F", "fg": "#DEDEDE", "primary": "#AECAEA",
                  "secondary": "#00B4EF", "muted": "#B5B5B5", "border": "#3D3D3D",
                  "levels": ["#0E1726", "#1B3555", "#3B6491", "#7FA6D2", "#AECAEA"]}


def say(msg):
    print(str(msg).encode("ascii", "replace").decode("ascii"))


def parse_calendar(page):
    """[(date, level 0-4, count)] from the public contributions page."""
    tips = {m.group(1): m.group(2) for m in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>([^<]+)</tool-tip>', page)}
    days = []
    for m in re.finditer(r'<td\b[^>]*>', page):
        tag = m.group(0)
        d = re.search(r'data-date="([\d-]+)"', tag)
        lv = re.search(r'data-level="(\d)"', tag)
        if not (d and lv):
            continue
        tid = re.search(r'\bid="([^"]+)"', tag)
        tip = tips.get(tid.group(1), "") if tid else ""
        c = re.match(r"\s*(\d[\d,]*)\s+contribution", tip)
        count = int(c.group(1).replace(",", "")) if c else 0
        days.append((d.group(1), int(lv.group(1)), count))
    return sorted(days)


def fetch(user):
    url = "https://github.com/users/%s/contributions" % user
    req = urllib.request.Request(url, headers={"User-Agent": "profile-city"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")


def stats(days):
    total = sum(c for _, _, c in days)
    best = max(days, key=lambda x: x[2]) if days else ("", 0, 0)
    run = longest = 0
    for _, _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    active = sum(1 for _, _, c in days if c > 0)
    week = sum(c for _, _, c in days[-7:])
    return {"total": total, "longest": longest, "active": active, "best_date": best[0], "best": best[2], "week": week}


def city_svg(days, tok=None, title="BUILD CITY", subtitle="", font_css=""):
    """font_css: @font-face rules for the families Display and Body (subset, data: URLs) - an <img> SVG
    cannot fetch a font, and the Actions runner has no font tools, so they are made once and committed."""
    tok = dict(DEFAULT_TOKENS, **(tok or {}))
    st = stats(days)
    W, H = 1200, 470
    # a shallow dimetric grid so a year spans the card: weeks run right (wx, wy), weekdays run
    # toward the viewer (dx, dy). A tile is the parallelogram p, p+w, p+w+d, p+d.
    wx, wy, dx, dy = 15.0, 3.2, -9.0, 7.0
    ox, oy = 200, 222
    first = dt.date.fromisoformat(days[0][0]) if days else dt.date.today()
    peak = max([c for _, _, c in days] + [1])
    placed = []
    for date, lv, c in days:
        d = dt.date.fromisoformat(date)
        week = ((d - first).days + (first.weekday() + 1) % 7) // 7   # columns start on Sunday, as GitHub's do
        wd = (d.weekday() + 1) % 7                                    # Sunday = 0
        x, y = ox + week * wx + wd * dx, oy + week * wy + wd * dy
        h = 0 if c == 0 else 6 + 74 * math.sqrt(c / float(peak))
        placed.append((y + wy + dy, week, x, y, h, lv))
    cells, runner = [], []
    for _, week, x, y, h, lv in sorted(placed):            # back to front, so nearer blocks cover farther ones
        col = tok["levels"][min(lv, 4)]
        A, B, C, D = (x, y), (x + wx, y + wy), (x + wx + dx, y + wy + dy), (x + dx, y + dy)
        top = "M%.1f %.1fL%.1f %.1fL%.1f %.1fL%.1f %.1fz" % (A[0], A[1] - h, B[0], B[1] - h, C[0], C[1] - h, D[0], D[1] - h)
        if h:
            front = "M%.1f %.1fL%.1f %.1fL%.1f %.1fL%.1f %.1fz" % (D[0], D[1] - h, C[0], C[1] - h, C[0], C[1], D[0], D[1])
            side = "M%.1f %.1fL%.1f %.1fL%.1f %.1fL%.1f %.1fz" % (B[0], B[1] - h, C[0], C[1] - h, C[0], C[1], B[0], B[1])
            cells.append('<g class="b" style="animation-delay:%.2fs"><path d="%s" fill="%s" opacity=".5"/>'
                         '<path d="%s" fill="%s" opacity=".75"/><path d="%s" fill="%s"/></g>'
                         % (.03 * week, front, col, side, col, top, col))
        else:
            cells.append('<path d="%s" fill="%s"/>' % (top, tok["levels"][0]))
    for date, lv, c in days:                                 # the runner follows the calendar order, not the paint order
        d = dt.date.fromisoformat(date)
        week = ((d - first).days + (first.weekday() + 1) % 7) // 7
        wd = (d.weekday() + 1) % 7
        h = 0 if c == 0 else 6 + 74 * math.sqrt(c / float(peak))
        runner.append((ox + week * wx + wd * dx + (wx + dx) / 2, oy + week * wy + wd * dy + (wy + dy) / 2 - h))
    # the snake: a head and a fading tail that crawl the whole year along the tops of the blocks, then loop.
    # pathLength=1000 makes the dash period exactly one path, so there is one snake and no seam, whatever
    # the year's real length in pixels.
    d_run = ("M" + "L".join("%.1f %.1f" % p for p in runner[::2])) if runner else "M0 0"
    s_total, s_long, s_best = "{:,}".format(st["total"]), st["longest"], st["best"]
    css = (font_css +
           ".bg{fill:%(bg)s}.t{font:500 13px Body,Roboto,'Segoe UI',Arial,sans-serif;letter-spacing:.3em;fill:%(se)s}"
           ".h{font:400 46px Display,'Rubik Doodle Shadow',Impact,sans-serif;fill:%(fg)s}"
           ".n{font:400 36px Display,'Rubik Doodle Shadow',Impact,sans-serif;fill:%(pr)s}"
           ".l{font:500 12px Body,Roboto,'Segoe UI',Arial,sans-serif;letter-spacing:.24em;fill:%(mu)s}"
           ".ld{fill:%(se)s}.lr{fill:none;stroke:%(se)s;stroke-width:1.5;transform-box:fill-box;transform-origin:center;"
           "animation:ping 1.8s ease-out infinite}@keyframes ping{from{transform:scale(1);opacity:.9}to{transform:scale(3.4);opacity:0}}"
           ".b{transform-box:fill-box;transform-origin:bottom;animation:rise .9s cubic-bezier(.2,.9,.3,1.2) backwards}"
           ".run,.tail{fill:none;stroke:%(se)s;stroke-linecap:round;stroke-linejoin:round}"
           ".run{stroke-width:4;stroke-dasharray:9 991;animation:run 16s linear infinite;filter:drop-shadow(0 0 6px %(se)s)}"
           ".tail{stroke-width:2.5;stroke-opacity:.4;stroke-dasharray:34 966;animation:tail 16s linear infinite}"
           "@keyframes rise{from{transform:scaleY(0)}}@keyframes run{from{stroke-dashoffset:1000}to{stroke-dashoffset:0}}"
           "@keyframes tail{from{stroke-dashoffset:1025}to{stroke-dashoffset:25}}"
           "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"
           ) % {"bg": tok["bg"], "se": tok["secondary"], "fg": tok["fg"], "pr": tok["primary"], "mu": tok["muted"]}
    # live numbers, recomputed by every run: the year, the last seven days, the longest streak
    stat_el = "".join('<text x="%d" y="128" class="n" text-anchor="end">%s</text><text x="%d" y="150" class="l" text-anchor="end">%s</text>'
                      % (x, v, x, l) for x, v, l in ((1124, s_total, "THIS YEAR"), (1124 - 190, "{:,}".format(st["week"]), "THIS WEEK"),
                                                     (1124 - 380, "%d DAYS" % s_long, "LONGEST STREAK")))
    stat_el += ('<circle cx="81" cy="73" r="4.5" class="ld"/><circle cx="81" cy="73" r="4.5" class="lr"/>')
    # the same glass language as the rest of the profile: a soft glow of the palette behind the city
    # and a lit edge around the card
    glow = ('<defs><radialGradient id="g1"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="g2"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>'
            '<linearGradient id="ge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="%s" stop-opacity=".7"/>'
            '<stop offset=".5" stop-color="%s" stop-opacity=".08"/><stop offset="1" stop-color="%s" stop-opacity=".35"/></linearGradient></defs>'
            '<circle cx="420" cy="300" r="320" fill="url(#g1)" opacity=".16"/><circle cx="980" cy="380" r="200" fill="url(#g2)" opacity=".12"/>'
            % (tok["primary"], tok["primary"], tok["secondary"], tok["secondary"], tok["primary"], tok["primary"], tok["primary"]))
    edge = ('<rect x=".7" y=".7" width="%.1f" height="%.1f" rx="23.3" fill="none" stroke="url(#ge)" stroke-width="1.4"/>'
            '<path d="M24 1.2H%d" stroke="#fff" stroke-opacity=".2" stroke-linecap="round"/>' % (W - 1.4, H - 1.4, W - 24))
    alt = "Build city: %s contributions in the last year as an isometric city, longest streak %d days, busiest day %d." % (s_total, s_long, s_best)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s">'
            '<title>%s</title><style>%s</style><rect class="bg" width="%d" height="%d" rx="24"/>%s'
            '<text x="96" y="78" class="t">%s</text><text x="76" y="124" class="h">%s</text>%s'
            '<g>%s<path class="tail" d="%s" pathLength="1000"/><path class="run" d="%s" pathLength="1000"/></g>%s</svg>'
            % (W, H, W, H, html.escape(alt), html.escape(alt), css, W, H, glow, html.escape(subtitle.upper()), html.escape(title),
               stat_el, "".join(cells), d_run, d_run, edge))


def sky_phase(hour):
    """The hero variant for a local hour: morning 5-11, afternoon 11-17, evening 17-21, night otherwise."""
    return "morning" if 5 <= hour < 11 else "afternoon" if 11 <= hour < 17 else "evening" if 17 <= hour < 21 else "night"


def pick_sky(src_dir, out, tz, now=None):
    """Copy src_dir/hero-<phase>.svg to out for the current hour in tz (an IANA zone, e.g. Africa/Cairo)."""
    import os, shutil
    if now is None:
        try:
            from zoneinfo import ZoneInfo
            now = dt.datetime.now(ZoneInfo(tz))
        except Exception:   # no tz database (Windows without the tzdata package): fall back to the UTC clock + 2 h
            say("no time-zone data for %s - using UTC+2" % tz)
            now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)
    ph = sky_phase(now.hour)
    shutil.copyfile(os.path.join(src_dir, "hero-%s.svg" % ph), out)
    return ph


def self_test():
    fails = 0

    def ok(name, cond):
        nonlocal fails
        fails += not cond
        say("%s %s" % ("PASS" if cond else "FAIL", name))

    page = ('<td data-date="2026-01-04" id="a" data-level="0"></td><tool-tip for="a">No contributions on January 4th.</tool-tip>'
            '<td data-date="2026-01-05" id="b" data-level="3"></td><tool-tip for="b">12 contributions on January 5th.</tool-tip>'
            '<td data-date="2026-01-06" id="c" data-level="1"></td><tool-tip for="c">1 contribution on January 6th.</tool-tip>'
            '<td data-date="2026-01-07" id="d" data-level="4"></td><tool-tip for="d">1,204 contributions on January 7th.</tool-tip>')
    days = parse_calendar(page)
    ok("parses date, level and count (commas, singular, none)", days == [("2026-01-04", 0, 0), ("2026-01-05", 3, 12), ("2026-01-06", 1, 1), ("2026-01-07", 4, 1204)])
    s = stats(days)
    ok("stats: total, longest streak, busiest day", (s["total"], s["longest"], s["best"], s["best_date"]) == (1217, 3, 1204, "2026-01-07"))
    svg = city_svg(days, title="BUILD CITY", subtitle="2026")
    ok("a block per active day, a flat tile per empty day", svg.count('class="b"') == 3 and svg.count("<path d=") >= 10)
    ok("stats printed from the data, runner present, reduced motion honoured",
       "1,217" in svg and "3 DAYS" in svg and "THIS WEEK" in svg and 'class="run"' in svg and "prefers-reduced-motion" in svg)
    ok("one seamless snake: head and tail share a normalised path", svg.count('pathLength="1000"') == 2 and 'class="tail"' in svg)
    ok("identity fonts are embedded when given", "@font-face{x}" in city_svg(days, font_css="@font-face{x}"))
    ok("an empty calendar still renders", "<svg" in city_svg([], title="X"))
    ok("sky phases cover the clock", [sky_phase(h) for h in (4, 5, 12, 18, 22)] == ["night", "morning", "afternoon", "evening", "night"])
    say("%d failure(s)" % fails)
    return 1 if fails else 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    ap = argparse.ArgumentParser(description="Contribution calendar -> isometric city SVG in your identity.")
    ap.add_argument("user")
    ap.add_argument("--out", default="city.svg")
    ap.add_argument("--tokens", help="JSON with bg/elevated/fg/primary/secondary/muted/border/levels")
    ap.add_argument("--title", default="BUILD CITY")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--html", help="read the calendar from a saved page instead of the network")
    ap.add_argument("--font-css", help="a CSS file with @font-face rules for the families Display and Body")
    ap.add_argument("--sky-from", help="also copy DIR/hero-<phase>.svg for the local hour to --sky-to")
    ap.add_argument("--sky-to", default="hero.svg")
    ap.add_argument("--tz", default="Africa/Cairo")
    a = ap.parse_args()
    try:
        page = io.open(a.html, encoding="utf-8").read() if a.html else fetch(a.user)
    except Exception as e:
        say("could not read the calendar: %s" % e)
        return 2
    days = parse_calendar(page)
    if not days:
        say("no days found on the calendar page - GitHub may have changed its markup")
        return 2
    tok = json.load(io.open(a.tokens, encoding="utf-8")) if a.tokens else None
    sub = a.subtitle or "LIVE  /  UPDATED %s" % days[-1][0]
    fc = io.open(a.font_css, encoding="utf-8").read() if a.font_css else ""
    io.open(a.out, "w", encoding="utf-8", newline="\n").write(city_svg(days, tok, a.title, sub, fc))
    if a.sky_from:
        say("sky: %s -> %s" % (pick_sky(a.sky_from, a.sky_to, a.tz), a.sky_to))
    st = stats(days)
    say("city: %d days, %d contributions, longest streak %d -> %s" % (len(days), st["total"], st["longest"], a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
