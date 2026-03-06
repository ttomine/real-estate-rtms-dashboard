#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


TRADE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
RENT_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"


@dataclass(frozen=True)
class LawdCode:
    code: str
    name: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch apartment trade/rent data from data.go.kr APIs."
    )
    parser.add_argument(
        "--service-key",
        default="",
        help="Data.go.kr service key. If empty, DATA_GO_KR_SERVICE_KEY env is used.",
    )
    parser.add_argument(
        "--lawd-codes-file",
        default="config/lawd_codes_seoul_incheon.csv",
        help="CSV file: LAWD_CD,지역명",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=12,
        help="How many recent months to fetch (KST 기준).",
    )
    parser.add_argument(
        "--num-of-rows",
        type=int,
        default=1000,
        help="Rows per API request page.",
    )
    parser.add_argument(
        "--pause-sec",
        type=float,
        default=0.12,
        help="Sleep seconds between API page requests.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=float,
        default=30,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--output",
        default=".tmp/raw_rtms.json",
        help="Output JSON path.",
    )
    return parser.parse_args()


def read_lawd_codes(path: Path) -> list[LawdCode]:
    if not path.exists():
        raise FileNotFoundError(f"LAWD code file not found: {path}")

    items: list[LawdCode] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip().lstrip("\ufeff")
        if not raw or raw.startswith("#"):
            continue
        parts = [p.strip() for p in raw.split(",", 1)]
        if len(parts) == 1:
            code, name = parts[0], parts[0]
        else:
            code, name = parts[0], parts[1]
        if not code.isdigit() or len(code) != 5:
            raise ValueError(f"Invalid LAWD_CD in {path}: {raw}")
        items.append(LawdCode(code=code, name=name))
    return items


def recent_months(month_count: int) -> list[str]:
    if month_count < 1:
        raise ValueError("--months must be >= 1")

    now = datetime.now(ZoneInfo("Asia/Seoul"))
    y = now.year
    m = now.month
    out: list[str] = []
    for _ in range(month_count):
        out.append(f"{y:04d}{m:02d}")
        m -= 1
        if m == 0:
            y -= 1
            m = 12
    return out


def parse_item_elem(item_elem: ET.Element) -> dict[str, str]:
    obj: dict[str, str] = {}
    for child in list(item_elem):
        obj[child.tag] = (child.text or "").strip()
    return obj


def request_page(
    *,
    endpoint: str,
    service_key: str,
    lawd_cd: str,
    deal_ymd: str,
    page_no: int,
    num_of_rows: int,
    timeout_sec: float,
) -> tuple[list[dict[str, str]], int]:
    params = {
        "serviceKey": service_key,
        "LAWD_CD": lawd_cd,
        "DEAL_YMD": deal_ymd,
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
    }
    query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    url = f"{endpoint}?{query}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; rtms-fetch/1.0)"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        body = resp.read().decode("utf-8", errors="replace")

    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        preview = body[:300].replace("\n", " ")
        raise RuntimeError(f"XML parse failed: {exc}. body={preview}") from exc

    result_code = (root.findtext("./header/resultCode") or "").strip()
    result_msg = (root.findtext("./header/resultMsg") or "").strip()
    if result_code != "000":
        raise RuntimeError(f"API result not OK ({result_code}): {result_msg}")

    total_count_text = (root.findtext("./body/totalCount") or "0").strip()
    try:
        total_count = int(total_count_text or "0")
    except ValueError as exc:
        raise RuntimeError(f"Invalid totalCount: {total_count_text}") from exc

    items: list[dict[str, str]] = []
    for elem in root.findall("./body/items/item"):
        items.append(parse_item_elem(elem))
    return items, total_count


def fetch_dataset(
    *,
    dataset_name: str,
    endpoint: str,
    service_key: str,
    lawd_codes: list[LawdCode],
    months: list[str],
    num_of_rows: int,
    pause_sec: float,
    timeout_sec: float,
) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    errors: list[str] = []

    for lawd in lawd_codes:
        for ymd in months:
            page_no = 1
            total_count = 0
            while True:
                try:
                    page_items, total_count = request_page(
                        endpoint=endpoint,
                        service_key=service_key,
                        lawd_cd=lawd.code,
                        deal_ymd=ymd,
                        page_no=page_no,
                        num_of_rows=num_of_rows,
                        timeout_sec=timeout_sec,
                    )
                except Exception as exc:  # noqa: BLE001
                    errors.append(
                        f"{dataset_name} LAWD_CD={lawd.code}({lawd.name}) DEAL_YMD={ymd} "
                        f"page={page_no}: {exc}"
                    )
                    break

                for row in page_items:
                    row["_lawdCd"] = lawd.code
                    row["_lawdNm"] = lawd.name
                    row["_dealYmd"] = ymd
                    rows.append(row)

                if page_no * num_of_rows >= total_count:
                    break
                page_no += 1
                if pause_sec > 0:
                    time.sleep(pause_sec)

            print(
                f"[{dataset_name}] {lawd.code} {lawd.name} {ymd} -> total={total_count}",
                flush=True,
            )
    return rows, errors


def main() -> int:
    args = parse_args()

    key_raw = args.service_key or ""
    if not key_raw:
        key_raw = str(os.environ.get("DATA_GO_KR_SERVICE_KEY", "")).strip()
    if not key_raw:
        print(
            "Missing service key. Set DATA_GO_KR_SERVICE_KEY or pass --service-key.",
            file=sys.stderr,
        )
        return 2

    service_key = urllib.parse.unquote(key_raw.strip())
    lawd_codes = read_lawd_codes(Path(args.lawd_codes_file))
    months = recent_months(args.months)

    trade_rows, trade_errors = fetch_dataset(
        dataset_name="trade",
        endpoint=TRADE_URL,
        service_key=service_key,
        lawd_codes=lawd_codes,
        months=months,
        num_of_rows=args.num_of_rows,
        pause_sec=args.pause_sec,
        timeout_sec=args.timeout_sec,
    )
    rent_rows, rent_errors = fetch_dataset(
        dataset_name="rent",
        endpoint=RENT_URL,
        service_key=service_key,
        lawd_codes=lawd_codes,
        months=months,
        num_of_rows=args.num_of_rows,
        pause_sec=args.pause_sec,
        timeout_sec=args.timeout_sec,
    )

    payload = {
        "meta": {
            "generatedAt": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
            "months": months,
            "lawdCodes": [{"code": x.code, "name": x.name} for x in lawd_codes],
            "tradeCount": len(trade_rows),
            "rentCount": len(rent_rows),
            "tradeErrors": trade_errors,
            "rentErrors": rent_errors,
        },
        "trade": trade_rows,
        "rent": rent_rows,
    }

    if not trade_rows and not rent_rows:
        print(
            "Both trade and rent records are empty. Check service key / API status.",
            file=sys.stderr,
        )
        return 3

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    print(
        f"Saved: {out_path} (trade={len(trade_rows)}, rent={len(rent_rows)}, "
        f"errors={len(trade_errors) + len(rent_errors)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

