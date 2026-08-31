"""
Daily stock alert script.
Fetches quotes for a list of tickers and pushes a notification via ntfy.sh.

Designed to be run by a GitHub Actions cron job (see .github/workflows/stock-alert.yml).
Handles EST/EDT automatically by checking the actual US/Eastern clock time before sending,
rather than relying on a fixed UTC cron time.
"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import yfinance as yf

# ---- CONFIG ---------------------------------------------------------------

# Edit this list with your tickers
TICKERS = [
    "VTI",    # Vanguard Total Stock Market ETF
    "VOO",    # Vanguard S&P 500 ETF
    "VXUS",   # Vanguard Total International Stock ETF
    "FSELX",  # Fidelity Select Semiconductors
    "MSFT",   # Microsoft
    "AAPL",   # Apple
    "DIS",    # Disney
    "COST",   # Costco
    "NVDA",   # Nvidia
    "^DJI",   # Dow Jones Industrial Average (index)
    "^GSPC",  # S&P 500 (index)
]

# ntfy.sh topic — pick a unique, hard-to-guess name (acts like a password).
# Set this as a GitHub Actions secret called NTFY_TOPIC, not hardcoded here.
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "CHANGE_ME_TO_SOMETHING_UNIQUE")

# Only actually send if the current US/Eastern time's hour matches this.
# This makes DST a non-issue -- see workflow file for why we run the script
# at multiple candidate UTC times and let this check gate the real send.
TARGET_HOUR_ET = 10

# ---- LOGIC ------------------------------------------------------------------

def get_quotes(tickers):
    lines = []
    data = yf.download(tickers, period="2d", interval="1d", progress=False, group_by="ticker")
    for t in tickers:
        try:
            closes = data[t]["Close"].dropna()
            if len(closes) >= 2:
                prev, latest = closes.iloc[-2], closes.iloc[-1]
            else:
                prev, latest = closes.iloc[-1], closes.iloc[-1]
            pct = (latest - prev) / prev * 100
            arrow = "▲" if pct >= 0 else "▼"
            lines.append(f"{t}: ${latest:,.2f} {arrow} {pct:+.2f}%")
        except Exception as e:
            lines.append(f"{t}: error ({e})")
    return lines


def send_notification(title, body):
    resp = requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=body.encode("utf-8"),
        headers={
            "Title": title,
            "Priority": "default",
            "Tags": "chart_with_upwards_trend",
        },
        timeout=15,
    )
    resp.raise_for_status()


def main():
    now_et = datetime.now(ZoneInfo("America/New_York"))

    # Gate: only send if we're actually at the target ET hour right now.
    # (See workflow comments for why this matters.)
    if now_et.hour != TARGET_HOUR_ET:
        print(f"Current ET hour is {now_et.hour}, not {TARGET_HOUR_ET}. Skipping send.")
        sys.exit(0)

    lines = get_quotes(TICKERS)
    body = "\n".join(lines)
    title = f"Stocks — {now_et.strftime('%a %b %d')}"
    send_notification(title, body)
    print("Notification sent:")
    print(body)


if __name__ == "__main__":
    main()
