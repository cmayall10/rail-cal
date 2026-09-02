#!/usr/bin/env python3
"""
Scrapes the NCEL fixture page for Harrogate Railway Athletic and writes an
iCalendar feed. Upcoming games are timed events with a 3-hour alarm; played
games are all-day events carrying the score. Run daily by GitHub Actions.
"""
import re, sys
from datetime import datetime, timedelta, timezone
import requests
from bs4 import BeautifulSoup

SOURCE   = "https://www.ncefl.org.uk/teams/harrogaterailwayathletic/matches/"
US_SLUG  = "harrogaterailwayathletic"
US       = "Harrogate Railway"
OUT      = "docs/harrogate-railway.ics"

HOME = "Station View, Starbeck, Harrogate, HG2 7JA"
GROUNDS = {
 "Doncaster City": "The Marra Falcons Stadium, Church Street, Armthorpe, Doncaster, DN3 3AG",
 "Leeds UFCA": "The Welfare Stadium, Middle Lane, New Crofton, Wakefield, WF4 1LB",
 "Winterton Rangers": "West Street, Winterton, Scunthorpe, DN15 9QF",
 "Goole AFC": "Marcus Street, Goole, DN14 6TN",
 "Brigg Town": "The Hawthorns, Wrawby Road, Brigg, DN20 8DT",
 "Selby Town": "Richard Street, Selby, YO8 4BN",
 "Athersley Rec": "Sheerien Park, Ollerton Road, Athersley North, Barnsley, S71 3DP",
 "Appleby Frod": "Brumby Hall, Ashby Road, Scunthorpe, DN16 1AA",
 "Wakefield AFC": "DIY Kitchens Stadium, Doncaster Road, Wakefield, WF1 5EY",
 "Immingham Town": "Woodlands Avenue, Immingham, DN40 2JL",
 "Armthorpe Welfare": "Falcons Stadium, Church Street, Armthorpe, Doncaster, DN3 3AG",
 "South Leeds": "South Leeds Stadium, Belle Isle, Leeds, LS11 5DJ",
 "Ilkley Town": "MPM Stadium, Leeds Road, Ilkley, LS29 8AW",
 "Kinsley Boys": "Tombridge Crescent, Kinsley, Pontefract, WF9 5HA",
 "Route One Rovers": "Myra Shay, 489 Barkerend Road, Bradford, BD3 8QX",
 "Crowle Colts": "Godnow Road, Crowle, Scunthorpe, DN17 4EE",
 "Wombwell Town": "Recreation Ground, Station Road, Wombwell, Barnsley, S73 0BJ",
 "Field Olympic": "Olympic Park, Harrogate Road, Bradford, BD10 0HT",
 "Hemsworth Miners Welfare": "Wakefield Road, Fitzwilliam, Pontefract, WF9 5AJ",
 "Club Thorne Colliery": "Park Road, Moorends, Doncaster, DN8 4QR",
 "LIV": "Haworth Park, Dawson Drive, Hull, HU6 7AB",
 "Retford FC": "Cannon Park, Leverton Road, Retford, DN22 6TA",
}
COMPS = {"NCEL1":"NCEL Division One","LC1":"NCEL League Cup, First Round",
         "LC2":"NCEL League Cup, Second Round","LC3":"NCEL League Cup, Third Round",
         "LCQF":"NCEL League Cup, Quarter-Final","LCSF":"NCEL League Cup, Semi-Final",
         "LCF":"NCEL League Cup Final","FAV1Q":"FA Vase, First Round Qualifying",
         "FAV2Q":"FA Vase, Second Round Qualifying","FAV1":"FA Vase, First Round",
         "FAV2":"FA Vase, Second Round","FAC":"FA Cup","Frdly":"Pre-season friendly"}

def bst(d):
    """UK summer time: last Sunday in March to last Sunday in October."""
    def last_sun(y, m):
        d31 = datetime(y, m, 31)
        return d31 - timedelta(days=(d31.weekday() + 1) % 7)
    return last_sun(d.year, 3) <= d < last_sun(d.year, 10)

def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

def teams_in(row):
    """Team names from the row's links. The site prints each club twice
    (full name then short name), so collapse consecutive repeats of a slug."""
    out = []
    for a in row.select('a[href*="/teams/"]'):
        m = re.search(r"/teams/([a-z0-9]+)", a.get("href", ""))
        name = a.get_text(" ", strip=True)
        if not m or not name:
            continue
        slug = m.group(1)
        if out and out[-1][0] == slug:
            if len(name) > len(out[-1][1]):
                out[-1] = (slug, name)          # keep the fuller name
            continue
        out.append((slug, name))
    return out

def name_from_blob(blob):
    """Recover a club name from raw row text. The site prints each club twice
    (full name then short name), so the doubled prefix is the name."""
    b = re.sub(r"^\s*\d+(st|nd|rd|th)\b", " ", blob)
    b = re.sub(r"\b(" + "|".join(map(re.escape, COMPS)) + r")\b", " ", b)
    b = re.sub(r"Att:\s*\d+", " ", b)
    b = re.sub(r"HT:\s*\d+\s*[-\u2013\u2014]\s*\d+", " ", b)
    w = b.split()
    for k in range(min(6, len(w) // 2), 0, -1):
        if w[:k] == w[k:2 * k]:
            return " ".join(w[:k])
    return " ".join(w[:4]) if w else "TBC"

def ground_for(name):
    if name in GROUNDS:
        return GROUNDS[name]
    for k, v in GROUNDS.items():
        if k in name or name in k:
            return v
    return name

def parse():
    html = requests.get(SOURCE, timeout=30, headers={"User-Agent": "rail-cal/1.0"}).text
    soup = BeautifulSoup(html, "html.parser")
    best = {}
    for a in soup.select('a[href*="/matches/day/"]'):
        row = a.find_parent(["tr", "li", "div"])
        if row is None:
            continue
        m = re.search(r"/matches/day/\d{4}/(\d{8})", str(row))
        if not m:
            continue
        text = " ".join(row.get_text(" ", strip=True).split())
        sides = teams_in(row)
        if not any(s == US_SLUG for s, _ in sides[:2]):
            continue
        comp = next((v for k, v in COMPS.items() if re.search(rf"\b{k}\b", text)), None)
        datestr = m.group(1)
        # One game per date. Prefer the row that carries a competition code -
        # the site nests an inner row that omits it.
        prev = best.get(datestr)
        if prev is None or (comp and not prev[2]):
            best[datestr] = (text, sides[:2], comp)
    return sorted(best.items())

def build(rows):
    ev, n, skipped = [], 0, []
    for datestr, (text, sides, comp) in rows:
        d = datetime(int(datestr[:4]), int(datestr[4:6]), int(datestr[6:8]))
        comp = comp or "Fixture"

        t = re.search(r"(\d{1,2}):(\d{2})(am|pm)", text)
        s = None if t else re.search(r"(?<!\d)(\d{1,2})\s*[-\u2013\u2014]\s*(\d{1,2})(?!\d)", text)
        if not t and not s:
            skipped.append((datestr, text[:90]))
            continue

        mark = t or s
        if len(sides) >= 2:
            home = sides[0][0] == US_SLUG
            opp = sides[1][1] if home else sides[0][1]
        else:
            # opponent has no NCEL page - read the name out of the row text
            home = US in text[:mark.start()]
            opp = name_from_blob(text[mark.end():] if home else text[:mark.start()])

        n += 1
        loc = esc(HOME if home else ground_for(opp))
        uid = f"UID:rail-{datestr}@ncefl"
        stamp = f"DTSTAMP:{datetime.now(timezone.utc):%Y%m%dT%H%M%S}Z"

        if s:
            score = f"{s.group(1)}-{s.group(2)}"
            title = f"{US} {score} {opp}" if home else f"{opp} {score} {US}"
            title += " (H)" if home else " (A)"
            print(f"  {n:>3}. {datestr}  RESULT   {title}")
            ev += ["BEGIN:VEVENT", uid, "SEQUENCE:0", stamp,
                   f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
                   f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
                   f"SUMMARY:{esc(title)}", f"LOCATION:{loc}",
                   f"DESCRIPTION:{esc(comp + '. Result.')}", "END:VEVENT"]
        else:
            hh, mm, ap = int(t.group(1)), int(t.group(2)), t.group(3)
            if ap == "pm" and hh != 12: hh += 12
            if ap == "am" and hh == 12: hh = 0
            lo = d.replace(hour=hh, minute=mm)
            st = lo - timedelta(hours=1) if bst(lo) else lo
            en = st + timedelta(hours=2)
            title = f"{US} v {opp} (H)" if home else f"{opp} v {US} (A)"
            print(f"  {n:>3}. {datestr}  {hh:02d}:{mm:02d}    {title}")
            ev += ["BEGIN:VEVENT", uid, "SEQUENCE:0", stamp,
                   f"DTSTART:{st:%Y%m%dT%H%M%S}Z", f"DTEND:{en:%Y%m%dT%H%M%S}Z",
                   f"SUMMARY:{esc(title)}", f"LOCATION:{loc}",
                   f"DESCRIPTION:{esc(comp)}",
                   "BEGIN:VALARM", "TRIGGER:-PT3H", "ACTION:DISPLAY",
                   "DESCRIPTION:Match today", "END:VALARM", "END:VEVENT"]

    for datestr, snippet in skipped:
        print(f"  skipped {datestr}: {snippet}")
    return ev, n

def main():
    rows = parse()
    if not rows:
        sys.exit("No fixture rows found - the NCEL page layout has probably changed.")
    ev, n = build(rows)
    if n == 0:
        sys.exit("Rows found but nothing parsed - check the time and score patterns.")
    cal = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//rail-cal//EN",
           "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
           "X-WR-CALNAME:Harrogate Railway Athletic",
           "X-PUBLISHED-TTL:PT6H", "REFRESH-INTERVAL;VALUE=DURATION:PT6H"] + ev + ["END:VCALENDAR"]
    open(OUT, "w").write("\r\n".join(cal) + "\r\n")
    print(f"Wrote {n} events to {OUT}")

if __name__ == "__main__":
    main()
