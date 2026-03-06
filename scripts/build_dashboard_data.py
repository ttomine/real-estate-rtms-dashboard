#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build dashboard JSON from fetched trade/rent raw JSON."
    )
    parser.add_argument("--input", default=".tmp/raw_rtms.json", help="Raw JSON path.")
    parser.add_argument(
        "--output",
        default="docs/data/dashboard.json",
        help="Dashboard JSON output path.",
    )
    parser.add_argument(
        "--min-ratio-count",
        type=int,
        default=5,
        help="Minimum trade/jeonse sample count for jeonse ratio ranking.",
    )
    return parser.parse_args()


def to_int(value: str) -> int | None:
    raw = (value or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def to_float(value: str) -> float | None:
    raw = (value or "").strip().replace(",", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def build_contract_date(row: dict[str, str]) -> str:
    y = (row.get("dealYear") or "").strip()
    m = (row.get("dealMonth") or "").strip()
    d = (row.get("dealDay") or "").strip()
    if not (y and m and d):
        return ""
    try:
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    except ValueError:
        return ""


def median_or_none(values: list[float | int]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


@dataclass
class RegionAgg:
    code: str
    name: str
    trade_prices: list[int] = field(default_factory=list)
    trade_unit_prices: list[float] = field(default_factory=list)
    rent_deposits: list[int] = field(default_factory=list)
    jeonse_deposits: list[int] = field(default_factory=list)
    trade_count: int = 0
    rent_count: int = 0
    jeonse_count: int = 0


def normalize_region_code(row: dict[str, str]) -> str:
    return (row.get("sggCd") or row.get("_lawdCd") or "").strip()


def normalize_region_name(row: dict[str, str]) -> str:
    candidate = (row.get("_lawdNm") or "").strip()
    if candidate:
        return candidate
    candidate = (row.get("estateAgentSggNm") or "").strip()
    if candidate:
        return candidate.split(",")[0].strip()
    return ""


def build_dashboard(raw_data: dict, min_ratio_count: int) -> dict:
    trade_rows: list[dict[str, str]] = raw_data.get("trade", [])
    rent_rows: list[dict[str, str]] = raw_data.get("rent", [])
    meta = raw_data.get("meta", {})

    regions: dict[str, RegionAgg] = {}

    for row in trade_rows:
        code = normalize_region_code(row)
        if not code:
            continue
        name = normalize_region_name(row) or code
        agg = regions.setdefault(code, RegionAgg(code=code, name=name))
        agg.trade_count += 1

        price = to_int(row.get("dealAmount", ""))
        area = to_float(row.get("excluUseAr", ""))
        if price is not None:
            agg.trade_prices.append(price)
        if price is not None and area and area > 0:
            agg.trade_unit_prices.append(price / area)

    latest_trade_rows = []
    for row in trade_rows:
        amount = to_int(row.get("dealAmount", ""))
        latest_trade_rows.append(
            {
                "date": build_contract_date(row),
                "regionCode": normalize_region_code(row),
                "regionName": normalize_region_name(row),
                "aptNm": (row.get("aptNm") or "").strip(),
                "umdNm": (row.get("umdNm") or "").strip(),
                "excluUseAr": to_float(row.get("excluUseAr", "")),
                "amountManwon": amount,
            }
        )
    latest_trade_rows = [x for x in latest_trade_rows if x["date"]]
    latest_trade_rows.sort(
        key=lambda x: (
            x["date"],
            x["amountManwon"] if x["amountManwon"] is not None else -1,
        ),
        reverse=True,
    )

    for row in rent_rows:
        code = normalize_region_code(row)
        if not code:
            continue
        name = normalize_region_name(row) or code
        agg = regions.setdefault(code, RegionAgg(code=code, name=name))
        agg.rent_count += 1

        deposit = to_int(row.get("deposit", ""))
        monthly_rent = to_int(row.get("monthlyRent", ""))
        if deposit is not None:
            agg.rent_deposits.append(deposit)
        if deposit is not None and monthly_rent == 0:
            agg.jeonse_count += 1
            agg.jeonse_deposits.append(deposit)

    latest_rent_rows = []
    for row in rent_rows:
        deposit = to_int(row.get("deposit", ""))
        monthly_rent = to_int(row.get("monthlyRent", ""))
        latest_rent_rows.append(
            {
                "date": build_contract_date(row),
                "regionCode": normalize_region_code(row),
                "regionName": normalize_region_name(row),
                "aptNm": (row.get("aptNm") or "").strip(),
                "umdNm": (row.get("umdNm") or "").strip(),
                "excluUseAr": to_float(row.get("excluUseAr", "")),
                "depositManwon": deposit,
                "monthlyRentManwon": monthly_rent,
            }
        )
    latest_rent_rows = [x for x in latest_rent_rows if x["date"]]
    latest_rent_rows.sort(
        key=lambda x: (
            x["date"],
            x["depositManwon"] if x["depositManwon"] is not None else -1,
        ),
        reverse=True,
    )

    region_rows = []
    for code, agg in regions.items():
        median_trade = median_or_none(agg.trade_prices)
        median_trade_unit = median_or_none(agg.trade_unit_prices)
        median_rent = median_or_none(agg.rent_deposits)
        median_jeonse = median_or_none(agg.jeonse_deposits)
        jeonse_ratio = None
        if median_trade and median_jeonse:
            jeonse_ratio = (median_jeonse / median_trade) * 100.0
        region_rows.append(
            {
                "regionCode": code,
                "regionName": agg.name,
                "tradeCount": agg.trade_count,
                "rentCount": agg.rent_count,
                "jeonseCount": agg.jeonse_count,
                "medianTradeManwon": median_trade,
                "medianTradePerM2Manwon": median_trade_unit,
                "medianRentDepositManwon": median_rent,
                "medianJeonseDepositManwon": median_jeonse,
                "jeonseRatioPct": jeonse_ratio,
            }
        )

    region_rows.sort(key=lambda x: (x["tradeCount"], x["rentCount"]), reverse=True)

    ratio_rows = [
        x
        for x in region_rows
        if (
            x["jeonseRatioPct"] is not None
            and x["tradeCount"] >= min_ratio_count
            and x["jeonseCount"] >= min_ratio_count
        )
    ]
    ratio_rows.sort(key=lambda x: x["jeonseRatioPct"], reverse=True)

    summary = {
        "tradeCount": len(trade_rows),
        "rentCount": len(rent_rows),
        "regionCount": len(region_rows),
        "months": meta.get("months", []),
        "generatedAt": meta.get("generatedAt")
        or datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "tradeErrorCount": len(meta.get("tradeErrors", [])),
        "rentErrorCount": len(meta.get("rentErrors", [])),
    }

    return {
        "summary": summary,
        "regions": region_rows,
        "rankings": {
            "topTradeCount": region_rows[:15],
            "topJeonseRatio": ratio_rows[:15],
        },
        "latest": {
            "trade": latest_trade_rows[:30],
            "rent": latest_rent_rows[:30],
        },
        "meta": {
            "source": "data.go.kr RTMSDataSvcAptTradeDev + RTMSDataSvcAptRent",
            "notes": [
                "거래금액/보증금 단위는 만원",
                "전세가율은 지역 중앙값(전세 보증금 중앙값 / 매매가 중앙값) 기반",
                "전세가율 계산에는 월세 0건(전세)만 반영",
            ],
            "tradeErrors": meta.get("tradeErrors", []),
            "rentErrors": meta.get("rentErrors", []),
        },
    }


def main() -> int:
    args = parse_args()
    src_path = Path(args.input)
    if not src_path.exists():
        raise FileNotFoundError(f"Input file not found: {src_path}")

    raw = json.loads(src_path.read_text(encoding="utf-8"))
    dashboard = build_dashboard(raw, min_ratio_count=args.min_ratio_count)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(dashboard, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"Saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
