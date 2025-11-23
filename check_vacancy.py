#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright

# タイムゾーン／状態ファイル
JST = timezone(timedelta(hours=9))
STATUS_FILE = "status.json"

# 監視対象（名前→URL）
TARGETS = {
    "【S】光が丘パークタウン プロムナード十番街": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4350.html",
    "【A】光が丘パークタウン 公園南": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3500.html",
    "【A】光が丘パークタウン 四季の香弐番街": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4100.html",
    "【B】光が丘パークタウン 大通り中央": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4550.html",
    "【B】光が丘パークタウン いちょう通り八番街": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3910.html",
    "【C】光が丘パークタウン 大通り南": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3690.html",
    "【D】グリーンプラザ高松": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4650.html",
    "【E】(赤塚)アーバンライフゆりの木通り東": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4590.html",
    "【E】(赤塚)光が丘パークタウン ゆりの木通り３３番街": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_6801.html",
    "【F】(赤塚古い)むつみ台": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2410.html",
    "【F】(赤塚古い)光が丘パークタウン ゆりの木通り北": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3470.html",
}

def timestamp() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")

def judge_vacancy(url: str) -> str:
    """
    空室判定ロジック（冗長化）:
    - 空室あり (available) 条件:
      1) tbody.rep_room > tr が存在
      2) a.rep_room-link が存在
      3) table.rep_room に tr が存在
      4) .rep_room 内に tr/td が存在
    - 空室なし (not_available):
      div.err-box.err-box--empty-room のテキストに「ございません」等を含む
    - 上記いずれでも確定不可なら unknown
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=30000)
        page.wait_for_timeout(5000)

        if page.query_selector("tbody.rep_room tr"):
            return "available"
        if page.query_selector("a.rep_room-link"):
            return "available"
        rows = page.query_selector_all("table.rep_room tr")
        if rows and len(rows) > 0:
            return "available"
        if page.query_selector(".rep_room tr") or page.query_selector(".rep_room td"):
            return "available"

        empty_box = page.query_selector("div.err-box.err-box--empty-room")
        if empty_box:
            text = (empty_box.inner_text() or "").strip()
            if ("ございません" in text) or ("ご案内できるお部屋がございません" in text):
                return "not_available"

        return "unknown"

def check_targets() -> dict:
    results = {}
    for name, url in TARGETS.items():
        status = judge_vacancy(url)
        print(f"[{timestamp()}] {name}: {status}")
        results[name] = status
    return results

def load_status() -> dict:
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # status.json が存在しない場合は全物件 not_available とみなす
    return {name: "not_available" for name in TARGETS.keys()}

def save_status(status: dict) -> None:
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

def send_mail(name: str, url: str) -> None:
    subject = f"【UR空き物件】{name}"
    body = f"{name}\n{url}\n解析日時: {timestamp()}"
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = os.getenv("FROM_EMAIL")
    msg["To"] = os.getenv("TO_EMAIL")

    with smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT"))) as server:
        server.starttls()
        server.login(os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD"))
        server.send_message(msg)
    print(f"[{timestamp()}] メール送信完了: {subject}")

def main() -> None:
    prev = load_status()
    current = check_targets()

    # 差分通知（前回 not_available → 今回 available）
    new_vacancies = [(n, TARGETS[n]) for n, s in current.items()
                     if prev.get(n, "not_available") == "not_available" and s == "available"]
    for name, url in new_vacancies:
        send_mail(name, url)

    save_status(current)

if __name__ == "__main__":
    main()
