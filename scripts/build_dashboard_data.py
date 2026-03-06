#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


SIDO_NAME_BY_CODE: dict[str, str] = {
    "11": "서울특별시",
    "26": "부산광역시",
    "27": "대구광역시",
    "28": "인천광역시",
    "29": "광주광역시",
    "30": "대전광역시",
    "31": "울산광역시",
    "36": "세종특별자치시",
    "41": "경기도",
    "42": "강원특별자치도",
    "43": "충청북도",
    "44": "충청남도",
    "45": "전북특별자치도",
    "46": "전라남도",
    "47": "경상북도",
    "48": "경상남도",
    "50": "제주특별자치도",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build menu dashboard JSON from fetched trade/rent raw JSON."
    )
    parser.add_argument("--input", default=".tmp/raw_rtms.json", help="Raw JSON path.")
    parser.add_argument(
        "--output",
        default="docs/data/dashboard.json",
        help="Dashboard JSON output path.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Top N count for growth rankings.",
    )
    return parser.parse_args()


def to_ymd(row: dict[str, str]) -> str:
    ymd = (row.get("_dealYmd") or "").strip()
    if len(ymd) == 6 and ymd.isdigit():
        return ymd
    y = (row.get("dealYear") or "").strip()
    m = (row.get("dealMonth") or "").strip()
    if y.isdigit() and m.isdigit():
        return f"{int(y):04d}{int(m):02d}"
    return ""


def normalize_sigungu_name(row: dict[str, str]) -> str:
    name = (row.get("_lawdNm") or "").strip()
    if name:
        return name
    alt = (row.get("estateAgentSggNm") or "").strip()
    if alt:
        return alt.split(",")[0].strip()
    sgg = (row.get("sggCd") or "").strip()
    return sgg if sgg else "미상"


def normalize_umd_name(row: dict[str, str]) -> str:
    name = (row.get("umdNm") or "").strip()
    return name if name else "미상"


def normalize_complex_name(row: dict[str, str]) -> str:
    name = (row.get("aptNm") or "").strip()
    return name if name else "미상단지"


def ym_to_int(ymd: str) -> int:
    return int(ymd)


def shift_month(ymd: str, delta: int) -> str:
    year = int(ymd[:4])
    month = int(ymd[4:6])
    total = year * 12 + (month - 1) + delta
    new_year = total // 12
    new_month = (total % 12) + 1
    return f"{new_year:04d}{new_month:02d}"


def month_seq_to_latest(latest_ymd: str, count: int) -> list[str]:
    seq = [shift_month(latest_ymd, -idx) for idx in range(count - 1, -1, -1)]
    return seq


def month_label(ymd: str) -> str:
    return f"{ymd[:4]}-{ymd[4:6]}"


def percent(delta: int, base: int) -> float | None:
    if base <= 0:
        return None
    return (delta / base) * 100.0


def ensure_bucket(buckets: dict, key: str, meta: dict) -> dict:
    if key not in buckets:
        buckets[key] = {"meta": dict(meta), "months": {}}
        return buckets[key]

    current_meta = buckets[key]["meta"]
    for mk, mv in meta.items():
        if (not current_meta.get(mk)) and mv:
            current_meta[mk] = mv
    return buckets[key]


def add_month_count(bucket: dict, ymd: str, add: int = 1) -> None:
    months = bucket["months"]
    months[ymd] = int(months.get(ymd, 0)) + add


def row_with_recent3(meta: dict, months: dict[str, int], recent3: list[str]) -> dict:
    m1, m2, m3 = recent3
    v1 = int(months.get(m1, 0))
    v2 = int(months.get(m2, 0))
    v3 = int(months.get(m3, 0))
    delta = v3 - v2
    pct = percent(delta, v2)
    out = dict(meta)
    out.update(
        {
            "m1": v1,
            "m2": v2,
            "m3": v3,
            "momDelta": delta,
            "momRatePct": pct,
        }
    )
    return out


def build_rows_from_buckets(buckets: dict[str, dict], recent3: list[str]) -> list[dict]:
    rows: list[dict] = []
    for item in buckets.values():
        rows.append(row_with_recent3(item["meta"], item["months"], recent3))
    return rows


def sort_recent_table(rows: list[dict]) -> list[dict]:
    return sorted(
        rows,
        key=lambda r: (int(r.get("m3", 0)), int(r.get("momDelta", 0))),
        reverse=True,
    )


def top_growth_rows(rows: list[dict], top_n: int) -> list[dict]:
    valid = [r for r in rows if r.get("momRatePct") is not None]
    positive = [r for r in valid if int(r.get("momDelta", 0)) > 0]
    target = positive if positive else valid
    target.sort(
        key=lambda r: (
            float(r["momRatePct"]),
            int(r.get("momDelta", 0)),
            int(r.get("m3", 0)),
        ),
        reverse=True,
    )
    return target[:top_n]


def build_national_trend(national_months: dict[str, int]) -> dict:
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    years = [now.year - 2, now.year - 1, now.year]
    month_numbers = list(range(1, 13))
    series = []
    for y in years:
        vals = [int(national_months.get(f"{y:04d}{m:02d}", 0)) for m in month_numbers]
        series.append({"year": y, "values": vals, "yearTotal": sum(vals)})
    return {
        "years": years,
        "monthNumbers": month_numbers,
        "monthLabels": [f"{m}월" for m in month_numbers],
        "series": series,
    }


def build_dashboard(raw_data: dict, top_n: int) -> dict:
    trade_rows: list[dict[str, str]] = raw_data.get("trade", [])
    rent_rows: list[dict[str, str]] = raw_data.get("rent", [])
    meta = raw_data.get("meta", {})

    all_months_set: set[str] = set()
    national_months: dict[str, int] = {}
    sido_buckets: dict[str, dict] = {}
    sigungu_buckets: dict[str, dict] = {}
    umd_buckets: dict[str, dict] = {}
    complex_buckets: dict[str, dict] = {}

    for row in trade_rows:
        ymd = to_ymd(row)
        sgg_cd = (row.get("sggCd") or row.get("_lawdCd") or "").strip()
        if not ymd or not sgg_cd:
            continue

        all_months_set.add(ymd)
        national_months[ymd] = int(national_months.get(ymd, 0)) + 1

        sido_cd = sgg_cd[:2]
        sigungu_name = normalize_sigungu_name(row)
        umd_name = normalize_umd_name(row)
        umd_cd = (row.get("umdCd") or "").strip()
        apt_seq = (row.get("aptSeq") or "").strip()
        apt_name = normalize_complex_name(row)

        sido_meta = {
            "sidoCode": sido_cd,
            "sidoName": SIDO_NAME_BY_CODE.get(sido_cd, f"{sido_cd}권역"),
        }
        add_month_count(ensure_bucket(sido_buckets, sido_cd, sido_meta), ymd)

        sigungu_meta = {
            "sggCd": sgg_cd,
            "sigunguName": sigungu_name,
            "sidoCode": sido_cd,
            "sidoName": SIDO_NAME_BY_CODE.get(sido_cd, f"{sido_cd}권역"),
        }
        add_month_count(ensure_bucket(sigungu_buckets, sgg_cd, sigungu_meta), ymd)

        umd_key = f"{sgg_cd}-{umd_cd if umd_cd else umd_name}"
        umd_meta = {
            "umdKey": umd_key,
            "sggCd": sgg_cd,
            "sigunguName": sigungu_name,
            "sidoCode": sido_cd,
            "sidoName": SIDO_NAME_BY_CODE.get(sido_cd, f"{sido_cd}권역"),
            "umdCd": umd_cd,
            "umdName": umd_name,
        }
        add_month_count(ensure_bucket(umd_buckets, umd_key, umd_meta), ymd)

        complex_key = apt_seq if apt_seq else f"{sgg_cd}:{umd_name}:{apt_name}"
        complex_meta = {
            "complexKey": complex_key,
            "aptSeq": apt_seq,
            "aptName": apt_name,
            "sggCd": sgg_cd,
            "sigunguName": sigungu_name,
            "sidoCode": sido_cd,
            "sidoName": SIDO_NAME_BY_CODE.get(sido_cd, f"{sido_cd}권역"),
            "umdName": umd_name,
        }
        add_month_count(ensure_bucket(complex_buckets, complex_key, complex_meta), ymd)

    now = datetime.now(ZoneInfo("Asia/Seoul"))
    now_ymd = now.strftime("%Y%m")
    all_months = sorted(all_months_set, key=ym_to_int)
    if all_months:
        latest_for_recent = all_months[-1]
        if latest_for_recent == now_ymd and now.day < 28:
            latest_for_recent = shift_month(latest_for_recent, -1)
        recent3 = month_seq_to_latest(latest_for_recent, 3)
    else:
        recent3 = month_seq_to_latest(now_ymd, 3)

    trend3y = build_national_trend(national_months)

    sido_rows = sort_recent_table(build_rows_from_buckets(sido_buckets, recent3))
    sigungu_rows = sort_recent_table(build_rows_from_buckets(sigungu_buckets, recent3))
    umd_rows = sort_recent_table(build_rows_from_buckets(umd_buckets, recent3))
    complex_rows = sort_recent_table(build_rows_from_buckets(complex_buckets, recent3))

    summary = {
        "generatedAt": meta.get("generatedAt")
        or datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "tradeCount": len(trade_rows),
        "rentCount": len(rent_rows),
        "monthsFetched": meta.get("months", []),
        "availableMonthCount": len(all_months),
        "recent3Months": recent3,
        "recent3MonthLabels": [month_label(x) for x in recent3],
        "coverage": {
            "sidoCount": len(sido_rows),
            "sigunguCount": len(sigungu_rows),
            "umdCount": len(umd_rows),
            "complexCount": len(complex_rows),
            "sidoNames": [row["sidoName"] for row in sido_rows],
        },
        "errors": {
            "tradeErrorCount": len(meta.get("tradeErrors", [])),
            "rentErrorCount": len(meta.get("rentErrors", [])),
        },
    }

    return {
        "summary": summary,
        "national": {
            "trend3y": trend3y,
            "recent3mBySido": sido_rows,
        },
        "sigungu": {
            "top20MoM": top_growth_rows(sigungu_rows, top_n),
            "recent3mTable": sigungu_rows,
        },
        "umd": {
            "top20MoM": top_growth_rows(umd_rows, top_n),
            "recent3mTable": umd_rows,
        },
        "complex": {
            "top20MoM": top_growth_rows(complex_rows, top_n),
            "recent3mTable": complex_rows,
        },
        "meta": {
            "source": "data.go.kr RTMSDataSvcAptTradeDev + RTMSDataSvcAptRent",
            "notes": [
                "화면 지표는 아파트 매매 거래건수 기준입니다.",
                "전월대비 증감률 = (당월-전월)/전월 * 100",
                "서울+인천 샘플 데이터 기준으로 먼저 구성되었습니다.",
            ],
            "tradeErrors": meta.get("tradeErrors", []),
            "rentErrors": meta.get("rentErrors", []),
            "sidoCodeMap": SIDO_NAME_BY_CODE,
        },
    }


def main() -> int:
    args = parse_args()
    src_path = Path(args.input)
    if not src_path.exists():
        raise FileNotFoundError(f"Input file not found: {src_path}")

    raw = json.loads(src_path.read_text(encoding="utf-8"))
    dashboard = build_dashboard(raw, top_n=args.top_n)

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
