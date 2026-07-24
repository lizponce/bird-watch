#!/usr/bin/env python3
"""
Checks every site in sites.json and writes results to data/status.json.

Marks a site DOWN when any of these are true:
  - the request errors or times out
  - the status code is not in the site's expect_status list
  - expect_text is set and that string is missing from the response body

Keeps 288 history points per site (24h at a 5 minute interval).
Exits 1 if any site is down, so the workflow can branch on it.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITES_FILE = os.path.join(ROOT, "sites.json")
STATUS_FILE = os.path.join(ROOT, "data", "status.json")
HISTORY_POINTS = 288

UA = "EarlyBirdUptime/1.0 (+https://earlybirdlife.com)"


def load_json(path, fallback):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return fallback


def check_site(site):
    url = site["url"]
    timeout = site.get("timeout", 15)
    expect_status = site.get("expect_status") or [200]
    expect_text = site.get("expect_text")

    start = time.monotonic()
    result = {
        "name": site.get("name") or url,
        "url": url,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    try:
        r = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": UA},
            allow_redirects=True,
        )
        elapsed = int((time.monotonic() - start) * 1000)
        result["response_ms"] = elapsed
        result["status_code"] = r.status_code

        if r.status_code not in expect_status:
            result["up"] = False
            result["reason"] = f"Returned {r.status_code}, expected {expect_status}"
        elif expect_text and expect_text not in r.text:
            result["up"] = False
            result["reason"] = f"Page loaded but missing expected text: {expect_text!r}"
        else:
            result["up"] = True
            result["reason"] = None

    except requests.exceptions.SSLError as e:
        result.update(up=False, status_code=None,
                      response_ms=int((time.monotonic() - start) * 1000),
                      reason=f"SSL problem: {str(e)[:180]}")
    except requests.exceptions.ConnectTimeout:
        result.update(up=False, status_code=None,
                      response_ms=timeout * 1000,
                      reason=f"Connection timed out after {timeout}s")
    except requests.exceptions.ReadTimeout:
        result.update(up=False, status_code=None,
                      response_ms=timeout * 1000,
                      reason=f"Server accepted the connection but never responded ({timeout}s)")
    except requests.exceptions.ConnectionError as e:
        result.update(up=False, status_code=None,
                      response_ms=int((time.monotonic() - start) * 1000),
                      reason=f"Could not connect (DNS or network): {str(e)[:180]}")
    except Exception as e:
        result.update(up=False, status_code=None,
                      response_ms=int((time.monotonic() - start) * 1000),
                      reason=f"{type(e).__name__}: {str(e)[:180]}")

    return result


def main():
    config = load_json(SITES_FILE, {"sites": []})
    sites = config.get("sites", [])
    if not sites:
        print("No sites configured in sites.json")
        return 0

    previous = load_json(STATUS_FILE, {"sites": []})
    prev_by_url = {s["url"]: s for s in previous.get("sites", [])}

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    results = []
    newly_down = []
    recovered = []

    for site in sites:
        r = check_site(site)
        prev = prev_by_url.get(r["url"], {})

        history = prev.get("history", [])
        history.append({"t": now, "up": r["up"], "ms": r.get("response_ms")})
        history = history[-HISTORY_POINTS:]
        r["history"] = history

        checks = len(history)
        ups = sum(1 for h in history if h["up"])
        r["uptime_24h"] = round((ups / checks) * 100, 2) if checks else None

        was_up = prev.get("up")
        if r["up"]:
            r["down_since"] = None
            if was_up is False:
                recovered.append(r)
        else:
            r["down_since"] = prev.get("down_since") or now
            if was_up is not False:
                newly_down.append(r)

        results.append(r)
        state = "UP  " if r["up"] else "DOWN"
        detail = f"{r.get('response_ms')}ms" if r["up"] else r.get("reason")
        print(f"[{state}] {r['name']} - {detail}")

    output = {
        "generated_at": now,
        "total": len(results),
        "up": sum(1 for r in results if r["up"]),
        "down": sum(1 for r in results if not r["up"]),
        "sites": results,
    }

    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(output, f, indent=2)

    alerts = []
    for r in newly_down:
        alerts.append(f"DOWN: {r['name']} ({r['url']}) - {r['reason']}")
    for r in recovered:
        alerts.append(f"RECOVERED: {r['name']} ({r['url']}) - back up in {r.get('response_ms')}ms")

    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        body = "\\n".join(alerts) if alerts else ""
        with open(gh_out, "a") as f:
            f.write(f"has_alerts={'true' if alerts else 'false'}\n")
            f.write(f"alert_body={body}\n")
            f.write(f"down_count={output['down']}\n")

    if alerts:
        print("\n--- Alerts ---")
        for a in alerts:
            print(a)

    return 1 if output["down"] else 0


if __name__ == "__main__":
    sys.exit(main())
