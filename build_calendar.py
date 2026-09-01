#!/usr/bin/env python3
"""
Scrapes the NCEL fixture page for Harrogate Railway Athletic and writes an
iCalendar feed. Run daily by GitHub Actions; output is served from GitHub Pages.
"""
import re, sys
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

SOURCE = "https://www.ncefl.org.uk/teams/harrogaterailwayathletic/matches/"
US = "Harrogate Railway"
OUT = "docs/harrogate-railway.ics"

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
         "FAC":"FA Cup","Frdly":"Pre-season friendly"}

def bst(d):
    """UK summer time: last Sun in March to last Sun in October."""
    def last_sun(y, m):
        d31 = datetime(y, m, 31) if m != 4 else datetime(y, 4, 30)
        return d31 - timedelta(days=(d31.weekday() + 1) % 7)
    return last_sun(d.year, 3) <= d < last_sun(d.year, 10)

def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

def parse():
    html = requests.get(SOURCE, timeout=30,
                        headers={"User-Agent": "rail-cal/1.0"}).text
    soup = BeautifulSoup(html, "html.parser")
    seen, rows = set(), []
    for a in soup.select('a[href*="/matches/day/"]'):
        row = a.find_parent(["tr", "li", "div"])
        if row is None:
            continue
        text = " ".join(row.get_text(" ", strip=True).split())
        m = re.search(r"/matches/day/\d{4}/(\d{8})", str(row))
        if not m or US not in text:
            continue
        key = (m.group(1), text[:120])
        if key in seen:
            continue
        seen.add(key)
        rows.append((m.group(1), text))
    return rows

def build(rows):
    ev, n = [], 0
    for datestr, text in rows:
        t = re.search(r"(\d{1,2}):(\d{2})(am|pm)", text)
        if not t:
            continue                      # already played, no kick-off time listed
        hh, mm, ap = int(t.group(1)), int(t.group(2)), t.group(3)
        if ap == "pm" and hh != 12: hh += 12
        if ap == "am" and hh == 12: hh = 0
        before, after = text[:t.start()], text[t.end():]
        home = US in before
        opp_blob = after if home else before
        opp = None
        for name in GROUNDS:
            if name in opp_blob:
                opp = name; break
        if opp is None:
            opp = re.sub(r"\s+", " ", opp_blob).strip()[:40] or "TBC"
        comp = next((v for k, v in COMPS.items() if re.search(rf"\b{k}\b", text)), "Fixture")
        lo = datetime(int(datestr[:4]), int(datestr[4:6]), int(datestr[6:8]), hh, mm)
        st = lo - timedelta(hours=1) if bst(lo) else lo
        en = st + timedelta(hours=2)
        n += 1
        title = f"{US} v {opp} (H)" if home else f"{opp} v {US} (A)"
        ev += ["BEGIN:VEVENT", f"UID:rail-{datestr}-{n:02d}@ncefl", "SEQUENCE:0",
               f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}Z",
               f"DTSTART:{st:%Y%m%dT%H%M%S}Z", f"DTEND:{en:%Y%m%dT%H%M%S}Z",
               f"SUMMARY:{esc(title)}",
               f"LOCATION:{esc(HOME if home else GROUNDS.get(opp, opp))}",
               f"DESCRIPTION:{esc(comp)}",
               "BEGIN:VALARM", "TRIGGER:-PT3H", "ACTION:DISPLAY",
               "DESCRIPTION:Match today", "END:VALARM", "END:VEVENT"]
    return ev, n

def main():
    rows = parse()
    if not rows:
        sys.exit("No fixture rows found - the NCEL page layout has probably changed.")
    ev, n = build(rows)
    if n == 0:
        sys.exit("Rows found but no upcoming fixtures parsed - check the time regex.")
    cal = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//rail-cal//EN",
           "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
           "X-WR-CALNAME:Harrogate Railway Athletic",
           "X-PUBLISHED-TTL:PT6H", "REFRESH-INTERVAL;VALUE=DURATION:PT6H"] + ev + ["END:VCALENDAR"]
    open(OUT, "w").write("\r\n".join(cal) + "\r\n")
    print(f"Wrote {n} fixtures to {OUT}")

if __name__ == "__main__":
    main()
