#!/usr/bin/env python3
"""Cross-reference wallet trades (5min / 15min markets) with sweeper analysis CSVs.

Matching priority:
  1. condition_id  — exact market instance match (best, requires updated sweeper CSV)
  2. event_slug + token_id  — exact token match (works with old or new CSV format)
  3. event_slug only  — same market time-slot, possibly different day (pattern info only)

Sweeper file auto-discovery:
  When --sweeper is not provided, the script automatically finds and merges all
  sweeper_analysis*.csv files in the current directory (e.g. sweeper_analysis_5min.csv,
  sweeper_analysis_15min.csv, sweeper_analysis.csv).

Usage:
    python3 match_trades.py
    python3 match_trades.py --sweeper sweeper_analysis_15min.csv
    python3 match_trades.py --sweeper sweeper_analysis_5min.csv sweeper_analysis_15min.csv
    python3 match_trades.py --wallet wallet_trades.csv --sweeper sweeper_analysis.csv
"""

import argparse
import csv
import glob
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

from pytz import timezone as pytz_tz

EST = pytz_tz("US/Eastern")

# ── helpers ──────────────────────────────────────────────────────────────────

GIT_CONFLICT_MARKERS = {"<<<<<<<", "=======", ">>>>>>>"}


def is_conflict_line(line: str) -> bool:
    return any(line.startswith(m) for m in GIT_CONFLICT_MARKERS)


def ts_sec_to_est(ts_sec: int) -> str:
    return datetime.fromtimestamp(ts_sec, tz=EST).strftime("%Y-%m-%d %H:%M:%S")


def normalise_slug(slug: str) -> str:
    """
    Normalise a slug so old-format (no date) and new-format (with date) can still match.
    
    Old:  btc-15min-up-or-down-20:15      / btc-5min-up-or-down-20:05
    New:  btc-15min-up-or-down-2026-02-20-20:15  / btc-5min-up-or-down-2026-02-20-20:05
    
    Returns the time-slot portion without the embedded date.
    """
    # Strip an embedded date like 2026-02-20- from the slug
    return re.sub(r'-\d{4}-\d{2}-\d{2}(-\d{2}:\d{2})$', r'\1', slug)


# ── loaders ──────────────────────────────────────────────────────────────────

def load_wallet_trades(path: str) -> list[dict]:
    trades = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            slug = row.get("event_slug", "")
            if "5min-up-or-down" in slug or "15min-up-or-down" in slug:
                trades.append(row)
    return trades


def discover_sweeper_files() -> list[str]:
    """Auto-discover sweeper analysis CSV files in the current directory.

    Looks for files matching sweeper_analysis*.csv (e.g. sweeper_analysis.csv,
    sweeper_analysis_5min.csv, sweeper_analysis_15min.csv).

    Returns:
        Sorted list of matching file paths.
    """
    pattern = "sweeper_analysis*.csv"
    matches = sorted(glob.glob(pattern))
    return matches


def load_sweeper(paths: list[str]) -> list[dict]:
    """Load and merge sweeper rows from one or more CSV files.

    Args:
        paths: List of sweeper CSV file paths to load and merge.

    Returns:
        Combined list of row dicts from all files.
    """
    all_rows: list[dict] = []
    for path in paths:
        with open(path, newline="") as f:
            clean_lines = [line for line in f if not is_conflict_line(line)]
        rows = list(csv.DictReader(clean_lines))
        all_rows.extend(rows)
    return all_rows


# ── aggregate wallet fills → positions ───────────────────────────────────────

def aggregate_positions(trades: list[dict]) -> list[dict]:
    key_map: dict[tuple, dict] = {}
    for t in trades:
        key = (t["event_slug"], t["asset"], t["outcome"], t["side"])
        if key not in key_map:
            key_map[key] = {
                "event_slug": t["event_slug"],
                "norm_slug": normalise_slug(t["event_slug"]),
                "asset": t["asset"],
                "outcome": t["outcome"],
                "side": t["side"],
                "price": float(t["price"]),
                "total_size": 0.0,
                "total_usdc": 0.0,
                "num_fills": 0,
                "first_ts": int(t["timestamp"]),
                "last_ts": int(t["timestamp"]),
                "condition_id": t["condition_id"],
            }
        pos = key_map[key]
        pos["total_size"] += float(t["size"])
        pos["total_usdc"] += float(t["usdc_value"])
        pos["num_fills"] += 1
        ts = int(t["timestamp"])
        pos["first_ts"] = min(pos["first_ts"], ts)
        pos["last_ts"] = max(pos["last_ts"], ts)
    return sorted(key_map.values(), key=lambda p: p["first_ts"], reverse=True)


# ── sweeper indices ──────────────────────────────────────────────────────────

def build_indices(sweeper_rows: list[dict]):
    """Return indices for matching: by condition_id, by (slug, token_id), by slug."""
    by_condition = defaultdict(list)   # condition_id -> rows
    by_token = defaultdict(list)       # (norm_slug, token_id) -> rows
    by_slug = defaultdict(list)        # norm_slug -> rows

    for row in sweeper_rows:
        slug = row.get("event_slug", "")
        norm = normalise_slug(slug)
        token = row.get("token_id", "")
        cond = row.get("condition_id", "")

        if norm:
            by_slug[norm].append(row)
            if token:
                by_token[(norm, token)].append(row)
        if cond:
            by_condition[cond].append(row)

    return by_condition, by_token, by_slug


def sweeper_summary(events: list[dict], trade_ts_sec: int, window_sec: int = 300) -> dict:
    """Summarise sweeper events around a trade timestamp."""
    trade_ts_ms = trade_ts_sec * 1000
    window_ms = window_sec * 1000

    nearby = []
    for e in events:
        try:
            ets = int(e.get("timestamp_ms", 0))
        except (ValueError, TypeError):
            continue
        if abs(ets - trade_ts_ms) <= window_ms:
            nearby.append(e)

    resolved = [e for e in events if e.get("event_type") == "market_resolved"]
    is_winning = None
    for r in resolved:
        v = r.get("is_winning_token", "").lower()
        if v == "true":
            is_winning = True
        elif v == "false":
            is_winning = False

    best_bid = best_ask = "—"
    candidates = []
    for e in events:
        try:
            ets = int(e.get("timestamp_ms", 0))
        except (ValueError, TypeError):
            continue
        if ets <= trade_ts_ms and e.get("best_bid"):
            candidates.append((ets, e))
    if candidates:
        candidates.sort(key=lambda x: x[0])
        _, closest = candidates[-1]
        best_bid = closest.get("best_bid", "—")
        best_ask = closest.get("best_ask", "—")

    return {
        "total": len(events),
        "nearby": len(nearby),
        "is_winning": is_winning,
        "best_bid": best_bid,
        "best_ask": best_ask,
    }


# ── main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cross-reference wallet trades with sweeper data")
    parser.add_argument("--wallet", default="wallet_trades.csv", help="Wallet trades CSV")
    parser.add_argument(
        "--sweeper",
        nargs="*",
        default=None,
        help="Sweeper analysis CSV file(s). If omitted, auto-discovers all sweeper_analysis*.csv files.",
    )
    parser.add_argument("--output", default="matched_trades.csv", help="Output CSV")
    args = parser.parse_args()

    print("Loading wallet trades …")
    all_trades = load_wallet_trades(args.wallet)
    print(f"  → {len(all_trades)} individual fills on 5/15-min markets")
    positions = aggregate_positions(all_trades)
    print(f"  → {len(positions)} aggregated positions\n")

    # Resolve sweeper files: explicit args or auto-discover
    if args.sweeper:
        sweeper_paths = args.sweeper
    else:
        sweeper_paths = discover_sweeper_files()
        if not sweeper_paths:
            print("Error: No sweeper_analysis*.csv files found in the current directory.")
            print("       Run the sweeper first, or pass --sweeper <file> explicitly.")
            return 1

    print("Loading sweeper analysis …")
    for sp in sweeper_paths:
        print(f"  • {sp}")
    sweeper_rows = load_sweeper(sweeper_paths)
    print(f"  → {len(sweeper_rows)} sweeper rows loaded (from {len(sweeper_paths)} file(s))")

    # Detect whether sweeper CSV has the new condition_id column
    has_condition_id = any(r.get("condition_id") for r in sweeper_rows[:100])
    has_raw_slug = any(r.get("raw_slug") for r in sweeper_rows[:100])
    print(f"  → Sweeper has condition_id column: {has_condition_id}")
    print(f"  → Sweeper has raw_slug column: {has_raw_slug}\n")

    by_condition, by_token, by_slug = build_indices(sweeper_rows)

    # Counters
    cond_matches = 0
    exact_matches = 0
    slug_only_matches = 0
    no_match = 0

    csv_rows = []

    for pos in positions:
        norm_slug = pos["norm_slug"]
        token = pos["asset"]
        cond_id = pos["condition_id"]

        # Priority 1: condition_id match
        cond_events = by_condition.get(cond_id, []) if cond_id else []
        # Priority 2: exact slug+token match
        exact_events = by_token.get((norm_slug, token), [])
        # Priority 3: slug-only match (same outcome preferred)
        slug_events = by_slug.get(norm_slug, [])
        slug_outcome_events = [e for e in slug_events if e.get("outcome") == pos["outcome"]]

        if cond_events:
            match_level = "CONDITION_ID"
            cond_matches += 1
            ctx = sweeper_summary(cond_events, pos["first_ts"])
        elif exact_events:
            match_level = "EXACT"
            exact_matches += 1
            ctx = sweeper_summary(exact_events, pos["first_ts"])
        elif slug_events:
            match_level = "SLUG-ONLY"
            slug_only_matches += 1
            ctx = sweeper_summary(slug_outcome_events or slug_events, pos["first_ts"])
        else:
            match_level = "NONE"
            no_match += 1
            ctx = {"total": 0, "nearby": 0, "is_winning": None, "best_bid": "—", "best_ask": "—"}

        win_str = "—"
        if ctx["is_winning"] is True:
            win_str = "✅ WIN"
        elif ctx["is_winning"] is False:
            win_str = "❌ LOSS"

        # Sweeper date range
        ref_events = cond_events or exact_events or slug_outcome_events or slug_events
        sw_dates = set()
        for e in ref_events:
            d = e.get("timestamp_est", "")[:10]
            if d:
                sw_dates.add(d)
        sw_date_str = ", ".join(sorted(sw_dates)) if sw_dates else "—"

        print("─" * 95)
        print(f"  Market:     {pos['event_slug']}")
        print(f"  Outcome:    {pos['outcome']}  |  Side: {pos['side']}  |  Price: {pos['price']}")
        print(f"  Size:       {pos['total_size']:,.2f} tokens  |  USDC: ${pos['total_usdc']:,.2f}  |  Fills: {pos['num_fills']}")
        print(f"  Trade time: {ts_sec_to_est(pos['first_ts'])} → {ts_sec_to_est(pos['last_ts'])} EST")
        print(f"  Cond. ID:   {cond_id[:42]}…" if len(cond_id) > 42 else f"  Cond. ID:   {cond_id}")
        print(f"  Match:      {match_level}  ({ctx['total']} sweeper events, {ctx['nearby']} within ±5 min)")
        print(f"  Sweeper dates: {sw_date_str}")
        if match_level != "NONE":
            print(f"  Bid/Ask:    {ctx['best_bid']} / {ctx['best_ask']}")
            print(f"  Result:     {win_str}")

        csv_rows.append({
            "event_slug": pos["event_slug"],
            "outcome": pos["outcome"],
            "side": pos["side"],
            "price": pos["price"],
            "total_size": round(pos["total_size"], 2),
            "total_usdc": round(pos["total_usdc"], 2),
            "num_fills": pos["num_fills"],
            "trade_time_est": ts_sec_to_est(pos["first_ts"]),
            "trade_date": ts_sec_to_est(pos["first_ts"])[:10],
            "token_id": pos["asset"],
            "condition_id": cond_id,
            "match_level": match_level,
            "sweeper_total_events": ctx["total"],
            "sweeper_nearby_events": ctx["nearby"],
            "sweeper_dates": sw_date_str,
            "best_bid_at_trade": ctx["best_bid"],
            "best_ask_at_trade": ctx["best_ask"],
            "result": win_str,
        })

    print("\n" + "═" * 95)
    print(f"MATCH SUMMARY ({len(positions)} positions total):")
    print(f"  CONDITION_ID matches:          {cond_matches}")
    print(f"  EXACT matches (slug + token):  {exact_matches}")
    print(f"  SLUG-ONLY matches (diff day):  {slug_only_matches}")
    print(f"  NO match in sweeper:           {no_match}")

    if no_match > 0:
        print(f"\n  ⚠  {no_match} positions had NO sweeper data.")
        print("     This means the sweeper was not running during those market windows.")
        print("     Ensure the sweeper runs continuously with: python monitor_multi_events.py continuous --markets BTC ETH SOL XRP --duration 15")

    if csv_rows:
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"\nResults written to {args.output}")


if __name__ == "__main__":
    main()
