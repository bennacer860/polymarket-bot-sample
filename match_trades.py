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
        for row_num, row in enumerate(csv.DictReader(f), start=2):  # row 1 = header
            slug = row.get("event_slug", "")
            if "5min-up-or-down" in slug or "15min-up-or-down" in slug:
                row["_source_file"] = path
                row["_source_row"] = row_num
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
            raw_lines = list(f)
        # Track original line numbers before stripping conflict markers
        clean_pairs: list[tuple[int, str]] = []
        for i, line in enumerate(raw_lines):
            if not is_conflict_line(line):
                clean_pairs.append((i + 1, line))  # 1-based line number
        # First clean line is the header; data rows start after that
        header_line = clean_pairs[0][1] if clean_pairs else ""
        clean_lines = [header_line] + [line for _, line in clean_pairs[1:]]
        orig_row_nums = [num for num, _ in clean_pairs[1:]]  # line numbers for data rows
        rows = list(csv.DictReader(clean_lines))
        for row, orig_num in zip(rows, orig_row_nums):
            row["_source_file"] = path
            row["_source_row"] = orig_num
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
                "wallet_source_file": t.get("_source_file", ""),
                "wallet_source_rows": [],
            }
        pos = key_map[key]
        pos["total_size"] += float(t["size"])
        pos["total_usdc"] += float(t["usdc_value"])
        pos["num_fills"] += 1
        pos["wallet_source_rows"].append(t.get("_source_row", ""))
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


# ── last_trade_price matching ────────────────────────────────────────────────

def build_ltp_index(sweeper_rows: list[dict]) -> dict[str, list[dict]]:
    """Build an index of last_trade_price events keyed by token_id.

    Returns:
        Dict mapping token_id -> list of LTP event rows (sorted by timestamp).
    """
    ltp_by_token: dict[str, list[dict]] = defaultdict(list)
    for row in sweeper_rows:
        if row.get("event_type") == "last_trade_price":
            token = row.get("token_id", "")
            if token:
                ltp_by_token[token].append(row)
    # Sort each token's events by timestamp for efficient proximity search
    for token in ltp_by_token:
        ltp_by_token[token].sort(key=lambda r: int(r.get("timestamp_ms", 0)))
    return dict(ltp_by_token)


def ltp_summary(
    ltp_events: list[dict],
    trade_ts_sec: int,
    trade_price: float,
    trade_size: float,
    window_sec: int = 60,
) -> dict:
    """Analyse last_trade_price events for a wallet position.

    Matches by token_id (already filtered), then by timestamp proximity.
    Also checks for price/size confirmation of the wallet's exact fill.

    Args:
        ltp_events: LTP events for this token_id (sorted by timestamp).
        trade_ts_sec: Wallet trade timestamp in seconds.
        trade_price: Wallet trade price.
        trade_size: Wallet total position size.
        window_sec: Time window in seconds for "nearby" classification (default ±60s).

    Returns:
        Dict with LTP match statistics.
    """
    trade_ts_ms = trade_ts_sec * 1000
    window_ms = window_sec * 1000

    total = len(ltp_events)
    nearby: list[dict] = []
    closest_event: dict | None = None
    closest_delta_ms: int | None = None

    for e in ltp_events:
        try:
            ets = int(e.get("timestamp_ms", 0))
        except (ValueError, TypeError):
            continue
        delta = abs(ets - trade_ts_ms)
        if delta <= window_ms:
            nearby.append(e)
        if closest_delta_ms is None or delta < closest_delta_ms:
            closest_delta_ms = delta
            closest_event = e

    # Check for price/size confirmation among nearby events
    price_match = False
    size_match = False
    confirmed_event: dict | None = None
    for e in nearby:
        try:
            ep = float(e.get("price", 0))
            es = float(e.get("size", 0))
        except (ValueError, TypeError):
            continue
        p_match = abs(ep - trade_price) < 0.002  # within 0.2 cents
        s_match = abs(es - trade_size) < 0.1      # within 0.1 tokens
        if p_match:
            price_match = True
        if s_match:
            size_match = True
        if p_match and s_match and confirmed_event is None:
            confirmed_event = e

    # Nearest event details
    nearest_price = ""
    nearest_size = ""
    nearest_side = ""
    nearest_ts_est = ""
    nearest_delta_sec = ""
    nearest_source_file = ""
    nearest_source_row = ""
    if closest_event:
        nearest_price = closest_event.get("price", "")
        nearest_size = closest_event.get("size", "")
        nearest_side = closest_event.get("side", "")
        nearest_ts_est = closest_event.get("timestamp_est", "")
        nearest_source_file = closest_event.get("_source_file", "")
        nearest_source_row = closest_event.get("_source_row", "")
        if closest_delta_ms is not None:
            nearest_delta_sec = f"{closest_delta_ms / 1000:.1f}"

    return {
        "ltp_total": total,
        "ltp_nearby": len(nearby),
        "ltp_nearest_price": nearest_price,
        "ltp_nearest_size": nearest_size,
        "ltp_nearest_side": nearest_side,
        "ltp_nearest_time": nearest_ts_est,
        "ltp_nearest_delta_sec": nearest_delta_sec,
        "ltp_nearest_source_file": nearest_source_file,
        "ltp_nearest_source_row": nearest_source_row,
        "ltp_price_match": price_match,
        "ltp_size_match": size_match,
        "ltp_confirmed": confirmed_event is not None,
    }


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

    # Build last_trade_price index by token_id
    ltp_index = build_ltp_index(sweeper_rows)
    ltp_token_count = len(ltp_index)
    ltp_event_count = sum(len(v) for v in ltp_index.values())
    print(f"  → {ltp_event_count} last_trade_price events across {ltp_token_count} tokens\n")

    # Counters
    cond_matches = 0
    exact_matches = 0
    slug_only_matches = 0
    no_match = 0
    ltp_matched = 0
    ltp_confirmed = 0

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

        # ── Last-trade-price matching (token_id + timestamp) ──
        ltp_events = ltp_index.get(token, [])
        if ltp_events:
            ltp = ltp_summary(ltp_events, pos["first_ts"], pos["price"], pos["total_size"])
            ltp_matched += 1
            if ltp["ltp_confirmed"]:
                ltp_confirmed += 1
        else:
            ltp = {
                "ltp_total": 0, "ltp_nearby": 0,
                "ltp_nearest_price": "", "ltp_nearest_size": "",
                "ltp_nearest_side": "", "ltp_nearest_time": "",
                "ltp_nearest_delta_sec": "",
                "ltp_price_match": False, "ltp_size_match": False,
                "ltp_confirmed": False,
            }

        ltp_status = "—"
        if ltp["ltp_confirmed"]:
            ltp_status = "CONFIRMED (price+size)"
        elif ltp["ltp_price_match"]:
            ltp_status = "PRICE MATCH"
        elif ltp["ltp_nearby"] > 0:
            ltp_status = f"NEARBY ({ltp['ltp_nearby']} within ±60s)"
        elif ltp["ltp_total"] > 0:
            ltp_status = f"TOKEN MATCH ({ltp['ltp_total']} LTPs)"

        # Source file origins
        wallet_file = pos.get("wallet_source_file", "")
        wallet_rows = pos.get("wallet_source_rows", [])
        wallet_rows_str = ", ".join(str(r) for r in wallet_rows)
        ltp_src_file = ltp.get("ltp_nearest_source_file", "")
        ltp_src_row = ltp.get("ltp_nearest_source_row", "")

        # Only include positions with at least some match
        has_match = match_level != "NONE" or ltp["ltp_total"] > 0
        if not has_match:
            continue

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
            "match_level": match_level,
            "result": win_str,
            "ltp_total": ltp["ltp_total"],
            "ltp_nearby": ltp["ltp_nearby"],
            "ltp_nearest_price": ltp["ltp_nearest_price"],
            "ltp_nearest_size": ltp["ltp_nearest_size"],
            "ltp_nearest_side": ltp["ltp_nearest_side"],
            "ltp_nearest_time": ltp["ltp_nearest_time"],
            "ltp_nearest_delta_sec": ltp["ltp_nearest_delta_sec"],
            "ltp_confirmed": ltp["ltp_confirmed"],
            "wallet_source_file": wallet_file,
            "wallet_source_rows": wallet_rows_str,
            "ltp_source_file": ltp_src_file,
            "ltp_source_row": ltp_src_row,
            "token_id": pos["asset"],
            "condition_id": cond_id,
        })

    # ── Summary ──────────────────────────────────────────────────────────────
    confirmed_rows = [r for r in csv_rows if r["ltp_confirmed"]]

    print(f"\n{len(positions)} wallet positions  |  {len(csv_rows)} with sweeper data  |  {no_match} no data (sweeper not running)")
    print(f"{ltp_matched} with LTP events  |  {len(confirmed_rows)} confirmed (price + size match within ±60s)\n")

    if confirmed_rows:
        print("═" * 95)
        print(f"CONFIRMED MATCHES ({len(confirmed_rows)}):")
        for r in confirmed_rows:
            print("─" * 95)
            print(f"  Market:      {r['event_slug']}  |  {r['outcome']}  |  {r['side']}")
            print(f"  Wallet:      price={r['price']}  size={r['total_size']}  USDC=${r['total_usdc']}")
            print(f"  Wallet time: {r['trade_time_est']} EST")
            print(f"  Wallet src:  {r['wallet_source_file']}  row(s): {r['wallet_source_rows']}")
            print(f"  LTP match:   price={r['ltp_nearest_price']}  size={r['ltp_nearest_size']}  side={r['ltp_nearest_side']}  Δ {r['ltp_nearest_delta_sec']}s")
            print(f"  LTP src:     {r['ltp_source_file']}  row: {r['ltp_source_row']}")
            print(f"  Result:      {r['result']}")
    else:
        print("No confirmed LTP matches (price + size within ±60s).")
        if ltp_matched > 0:
            print(f"  {ltp_matched} position(s) had LTP events on the same token but no exact fill match.")
            print("  This usually means the sweeper wasn't capturing at the exact moment of the trade.")

    if csv_rows:
        with open(args.output, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)
        print(f"\nResults written to {args.output}")


if __name__ == "__main__":
    main()
