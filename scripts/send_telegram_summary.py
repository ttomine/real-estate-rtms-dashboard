#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send dashboard summary to Telegram channel/group."
    )
    parser.add_argument(
        "--input",
        default="docs/data/dashboard.json",
        help="Dashboard JSON path.",
    )
    parser.add_argument(
        "--bot-token",
        default="",
        help="Telegram bot token. If empty, TELEGRAM_BOT_TOKEN env is used.",
    )
    parser.add_argument(
        "--chat-id",
        default="",
        help="Telegram chat ID. If empty, TELEGRAM_CHAT_ID env is used.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print message only, do not send.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when token/chat_id is missing or send fails.",
    )
    return parser.parse_args()


def fmt_manwon(value: float | int | None) -> str:
    if value is None:
        return "-"
    v = float(value)
    return f"{v/10000:.2f}억 ({int(round(v)):,}만원)"


def fmt_pct(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f}%"


def build_message(payload: dict) -> str:
    summary = payload.get("summary", {})
    rankings = payload.get("rankings", {})
    top_trade = rankings.get("topTradeCount", [])[:3]
    top_ratio = rankings.get("topJeonseRatio", [])[:3]

    lines = []
    lines.append("부동산 실거래 아침 업데이트")
    lines.append(f"업데이트: {summary.get('generatedAt', '-')}")
    lines.append(f"수집월: {', '.join(summary.get('months', []))}")
    lines.append(
        f"매매 {summary.get('tradeCount', 0):,}건 | 전월세 {summary.get('rentCount', 0):,}건 | 지역 {summary.get('regionCount', 0):,}개"
    )
    lines.append("")
    lines.append("[매매 거래량 상위 3]")
    for idx, row in enumerate(top_trade, start=1):
        lines.append(
            f"{idx}. {row.get('regionName', row.get('regionCode', '-'))} - {row.get('tradeCount', 0):,}건"
        )
    lines.append("")
    lines.append("[전세가율 상위 3]")
    for idx, row in enumerate(top_ratio, start=1):
        lines.append(
            f"{idx}. {row.get('regionName', row.get('regionCode', '-'))} - {fmt_pct(row.get('jeonseRatioPct'))} "
            f"(매매중앙값 {fmt_manwon(row.get('medianTradeManwon'))})"
        )
    return "\n".join(lines)


def send_message(bot_token: str, chat_id: str, message: str) -> None:
    endpoint = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8", errors="replace"))
    if not result.get("ok", False):
        raise RuntimeError(f"Telegram API error: {result}")


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Input not found: {input_path}")
        return 1

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    message = build_message(payload)

    bot_token = (args.bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")).strip()
    chat_id = (args.chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")).strip()

    if args.dry_run:
        print(message)
        return 0

    if not bot_token or not chat_id:
        text = "Skip Telegram send: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing."
        if args.strict:
            print(text)
            return 2
        print(text)
        return 0

    try:
        send_message(bot_token=bot_token, chat_id=chat_id, message=message)
    except Exception as exc:  # noqa: BLE001
        if args.strict:
            print(f"Telegram send failed: {exc}")
            return 3
        print(f"Telegram send skipped due to error: {exc}")
        return 0

    print("Telegram summary sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
