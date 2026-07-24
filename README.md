# Bird Watch

Uptime monitoring for Early Bird client sites. Runs on GitHub Actions, costs nothing, needs no server.

## Setup

**1. Create a private repo and push these files.**

```
.github/workflows/uptime.yml
scripts/check.py
data/status.json
docs/index.html
docs/img/logo.png
sites.json
```

**2. Add your sites to `sites.json`.**

```json
{
  "name": "Valley Plumbing",
  "url": "https://valleyplumbing.com",
  "expect_status": [200],
  "expect_text": "Request a quote",
  "timeout": 15
}
```

- `expect_status` — status codes that count as healthy. Use `[200, 301, 302]` if the site redirects.
- `expect_text` — optional. A string that must appear in the page. This is what catches a site that technically loads but has a broken database or a blank WordPress white screen. Pick something from the page that only renders when things are working, like a contact form heading.
- `timeout` — seconds to wait before calling it down.

**3. Add repository secrets** (Settings → Secrets and variables → Actions):

| Secret | Purpose |
|---|---|
| `MAIL_USERNAME` | Gmail address that sends alerts |
| `MAIL_PASSWORD` | Gmail **app password**, not your login password |
| `ALERT_EMAIL` | Where alerts go |
| `TWILIO_SID` | Optional, for SMS |
| `TWILIO_TOKEN` | Optional, for SMS |
| `TWILIO_FROM` | Optional, your Twilio number |
| `ALERT_PHONE` | Optional, your cell |

Gmail app passwords are at myaccount.google.com/apppasswords and require 2FA enabled. If you skip the Twilio secrets, the SMS step logs a skip and moves on.

**4. Turn on the dashboard.** Settings → Pages → Source: Deploy from branch, Branch: `main`, Folder: `/docs`. Your board lands at `https://YOURNAME.github.io/REPO/`.

**5. Run it once manually.** Actions tab → Uptime check → Run workflow. This generates the first `status.json`, which the dashboard needs before it will show anything.

## How alerts work

Alerts fire on **state changes only**. A site that goes down sends one notification. It does not re-notify every five minutes while it stays down. When it comes back, you get a recovery notice.

## What counts as down

- The connection fails, times out, or DNS doesn't resolve
- SSL certificate is expired or invalid
- The status code isn't in `expect_status` (catches 500s, 502s, 404s)
- `expect_text` is set and missing from the page

That last one is the difference between this and a naive pinger. A hacked or database-broken WordPress site often still returns 200.

## Timing note

GitHub's cron queues jobs on shared runners. A 5-minute schedule usually lands every 5 to 12 minutes, and can drift further when GitHub is busy. For client-facing SLA promises, describe it as roughly every 10 minutes rather than exactly every 5.

## Adding a client

Edit `sites.json`, commit, done. The next scheduled run picks it up.

## Fonts

Both faces load from Google Fonts, so there's nothing to install. Rubik Mono One sets the headline, stat numbers, client names, and status labels. JetBrains Mono handles everything else.
