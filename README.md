# Harrogate Railway Athletic fixture calendar

Scrapes the NCEL fixture page daily and publishes a subscribable calendar feed.

## Setup (once)

1. Create a new **public** GitHub repo, e.g. `rail-cal`.
2. Upload `build_calendar.py`, `README.md` and the `.github/workflows/update.yml` file
   (keep the folder structure - the workflow must sit at `.github/workflows/`).
3. Repo **Settings > Pages** > Source: *Deploy from a branch* > Branch: `main`, folder `/docs` > Save.
4. Repo **Actions** tab > *Update fixture calendar* > **Run workflow**. This does the first build.
5. Confirm `docs/harrogate-railway.ics` now exists in the repo.

Your feed URL is:

    https://YOURNAME.github.io/rail-cal/harrogate-railway.ics

## Share with the squad

Send that link. To subscribe:

- **iPhone**: Settings > Apps > Calendar > Accounts > Add Account > Other >
  Add Subscribed Calendar > paste URL. Set *Fetch* to hourly.
- **Android / Google**: calendar.google.com on desktop >
  Other calendars **+** > From URL > paste.
- **Outlook**: Calendar > Add calendar > Subscribe from web > paste.

Subscribing is read-only, so nobody can accidentally break it for everyone else.

## When it breaks

The scraper reads the NCEL page's HTML. If NCEL redesign the site, the workflow
will fail loudly rather than publish a wrong calendar - check the Actions tab for
a red X. Grounds are hardcoded in `GROUNDS` in `build_calendar.py`; add a line
when a new club joins the division.
