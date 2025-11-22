#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# ====== 設定 ======
RUN_MODE = os.getenv("RUN_MODE", "scheduled").lower()
JST = timezone(timedelta(hours=9))

TARGETS = {
    "【S】光が丘パークタウン プロムナード十番街": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4350.html",
    "【A】光が丘パークタウン 公園南": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3500.html",
    "【A】光が丘パークタウン 四季の香弐番街": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4100.html",
    "【B】光が丘パークタウン 大通り中央": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4550.html",
    "【B】光が丘パークタウン いちょう通り八番街": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3910.html",
    "【C】光が丘パークタウン 大通り南": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3690.html",
    "【D】グリーンプラザ高松": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4650.html",
    "【E】(赤塚)アーバンライフゆりの木通り東": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4590.html",
    "【F】(赤塚古い)むつみ台": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2410.html",
}

STATUS_FILE = "status.json"


def timestamp():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")


def fetch_html(url):
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        print(f"[{timestamp()}] [WARN] fetch error: {e}")
    return None


def judge_vacancy(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    if soup.select_one("div.err-box.err-box--empty-room"):
        return "not_available"

    room_list = soup.select_one("div.article_property_list.js-no-room-hidden_result")
    if room_list and room_list.select("tbody.rep_room tr.js-log-item"):
        return "available"

    return "unknown"


def check_targets():
    results = {}
    for name, url in TARGETS.items():
        html = fetch_html(url)
        if not html:
            results[name] = "unknown"
        else:
            results[name] = judge_vacancy(html)
        print(f"[{timestamp()}] {name}: {results[name]}")
    return results


def load_status():
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_status(status):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def send_mail(name, url):
    subject = f"【UR空き物件】{name}"
    body = f"{name}\n{url}\n解析日時: {timestamp()}"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = os.getenv("FROM_EMAIL")
    msg["To"] = os.getenv("TO_EMAIL")

    try:
        with smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT"))) as server:
            server.starttls()
            server.login(os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD"))
            server.send_message(msg)
        print(f"[{timestamp()}] メール送信完了: {subject}")
    except Exception as e:
        print(f"[ERROR] メール送信失敗: {e}")


def main():
    prev = load_status()
    current = check_targets()

    if RUN_MODE == "manual":
        available_now = [(name, TARGETS[name]) for name, status in current.items() if status == "available"]
        if available_now:
            print(f"[{timestamp()}] 手動実行: 現在空きあり {len(available_now)}件")
            for name, url in available_now:
                send_mail(name, url)
        else:
            print(f"[{timestamp()}] 手動実行: 空き物件なし")
        save_status(current)
        return

    if not prev:
        print(f"[{timestamp()}] 初回実行のため通知せず、状態保存のみ")
        save_status(current)
        return

    new_vacancies = [
        (name, TARGETS[name]) for name, status in current.items()
        if prev.get(name) == "not_available" and status == "available"
    ]

    if new_vacancies:
        print(f"[{timestamp()}] 新規空き検出：{len(new_vacancies)}件")
        for name, url in new_vacancies:
            send_mail(name, url)
    else:
        print(f"[{timestamp()}] 新規空きなし")

    save_status(current)


if __name__ == "__main__":
    main()
