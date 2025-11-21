#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

# --- 監視対象リスト ---
MONITORING_TARGETS = [
    {"danchi_name": "【S】光が丘パークタウン プロムナード十番街", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4350.html"},
    {"danchi_name": "【A】光が丘パークタウン 公園南", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3500.html"},
    {"danchi_name": "【A】光が丘パークタウン 四季の香弐番街", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4100.html"},
    {"danchi_name": "【B】光が丘パークタウン 大通り中央", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4550.html"},
    {"danchi_name": "【B】光が丘パークタウン いちょう通り八番街", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3910.html"},
    {"danchi_name": "【C】光が丘パークタウン 大通り南", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3690.html"},
    {"danchi_name": "【D】グリーンプラザ高松", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4650.html"},
    {"danchi_name": "【E】(赤塚)アーバンライフゆりの木通り東", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_4590.html"},
    {"danchi_name": "【F】(赤塚古い)むつみ台", "url": "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_2410.html"}
]

# --- メール設定（環境変数） ---
SMTP_SERVER = os.environ.get('SMTP_SERVER')
SMTP_PORT = os.environ.get('SMTP_PORT')
SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
FROM_EMAIL = os.environ.get('FROM_EMAIL')
TO_EMAIL = os.environ.get('TO_EMAIL', FROM_EMAIL)

# --- 状態管理 ---
STATUS_FILE = 'status.json'

def get_current_status():
    initial_status = {d['danchi_name']: 'not_available' for d in MONITORING_TARGETS}
    try:
        with open(STATUS_FILE, 'r', encoding='utf-8') as f:
            saved_status = json.load(f)
            return {name: saved_status.get(name, 'not_available') for name in initial_status}
    except Exception:
        return initial_status

def update_status(new_statuses):
    with open(STATUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_statuses, f, ensure_ascii=False, indent=4)
    print("✅ 状態ファイル更新完了")

# --- メール送信 ---
def send_alert_email(subject, body):
    if not all([SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, FROM_EMAIL]):
        print("🚨 メール送信に必要な環境変数が未設定です。送信をスキップします。")
        return

    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = FROM_EMAIL
    msg['To'] = TO_EMAIL

    try:
        with smtplib.SMTP(SMTP_SERVER, int(SMTP_PORT)) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        print(f"✅ メール送信: {TO_EMAIL}（件名: {subject}）")
    except Exception as e:
        print(f"🚨 メール送信エラー: {e}")

# --- 空きチェック ---
NO_VACANCY_PHRASE = "当サイトからすぐにご案内できるお部屋がございません"

def check_vacancy(danchi):
    name = danchi['danchi_name']
    url = danchi['url']
    print(f"--- チェック開始: {name} ---")
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=15)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')}] HTTP GET: {url} (attempt {attempt+1})")
            if resp.status_code != 200:
                print(f"⚠ HTTPステータス: {resp.status_code}")
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')
            if NO_VACANCY_PHRASE in soup.get_text():
                print(f"{name}: 判定 -> not_available")
                return 'not_available'
            else:
                print(f"{name}: 判定 -> available")
                return 'available'
        except Exception as e:
            print(f"⚠ リクエストエラー: {e}")
            time.sleep(2)
    print(f"{name}: 判定 -> not_available (リトライ失敗)")
    return 'not_available'

# --- メイン ---
def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')}] === UR空き情報監視開始 ===")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')}] 対象団地数: {len(MONITORING_TARGETS)}")

    current_status = get_current_status()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')}] 🔁 現在のステータス読み込み: {current_status}")

    new_status = current_status.copy()
    newly_available = []

    for danchi in MONITORING_TARGETS:
        status = check_vacancy(danchi)
        new_status[danchi['danchi_name']] = status
        if status == 'available' and current_status.get(danchi['danchi_name']) == 'not_available':
            newly_available.append(danchi)
        time.sleep(1)

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')}] === チェック結果 ===")
    for d in MONITORING_TARGETS:
        print(f"{d['danchi_name']}: {new_status[d['danchi_name']]}")

    for d in newly_available:
        subject = f"【UR空き情報】{d['danchi_name']}"
        body = f"以下の団地で空き情報が出た可能性があります！\n\n・団地名: {d['danchi_name']}\n・URL: {d['url']}\n"
        send_alert_email(subject, body)

    update_status(new_status)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S JST')}] === 監視終了 ===")

if __name__ == "__main__":
    main()
