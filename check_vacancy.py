import os
import json
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta, timezone

# タイムゾーン設定（JST）
JST = timezone(timedelta(hours=9))

# 監視対象団地とURL
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

# 空きなし判定ワード（完全一致）
PHRASE = "当サイトからすぐにご案内できるお部屋がございません"

# 状態ファイル
STATUS_FILE = "status.json"


def timestamp():
    return datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")


def fetch_html(url):
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return r.text
            else:
                print(f"[{timestamp()}] [WARN] HTTP {r.status_code} {url}")
        except Exception as e:
            print(f"[{timestamp()}] [WARN] Retry {attempt+1}: {e}")
    return None


def check_targets():
    results = {}
    for name, url in TARGETS.items():
        html = fetch_html(url)
        if html and PHRASE in html:
            results[name] = "not_available"
        else:
            results[name] = "available"
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
    print(f"[{timestamp()}] 状態ファイル更新完了")


def send_mail(new_vacancies):
    envs = ["SMTP_SERVER", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "TO_EMAIL", "FROM_EMAIL"]
    if not all(os.getenv(e) for e in envs):
        print("\033[91m[ERROR] メール送信設定が不足。送信をスキップ。\033[0m")
        return

    body = "新規空き検出：\n" + "\n".join(new_vacancies)
    msg = MIMEText(body)
    msg["Subject"] = "UR賃貸 新規空き情報"
    msg["From"] = os.getenv("FROM_EMAIL")
    msg["To"] = os.getenv("TO_EMAIL")

    try:
        with smtplib.SMTP(os.getenv("SMTP_SERVER"), int(os.getenv("SMTP_PORT"))) as server:
            server.starttls()
            server.login(os.getenv("SMTP_USERNAME"), os.getenv("SMTP_PASSWORD"))
            server.send_message(msg)
        print(f"[{timestamp()}] メール送信完了")
    except Exception as e:
        print(f"\033[91m[ERROR] メール送信失敗: {e}\033[0m")


def main():
    prev = load_status()
    current = check_targets()

    new_vacancies = [
        name for name, status in current.items()
        if prev.get(name) == "not_available" and status == "available"
    ]

    if new_vacancies:
        print(f"[{timestamp()}] 新規空き検出：{len(new_vacancies)}件")
        send_mail(new_vacancies)
    else:
        print(f"[{timestamp()}] 新規空きなし")

    save_status(current)


if __name__ == "__main__":
    main()
