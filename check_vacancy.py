import os
import requests
from bs4 import BeautifulSoup
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# --- 設定項目 ---
SLACK_BOT_TOKEN = "YOUR_SLACK_BOT_TOKEN" # ご自身のSlack Bot Tokenに置き換えてください
SLACK_CHANNEL = "#YOUR_CHANNEL_NAME"      # 通知先のチャンネル名に置き換えてください
# Slack通知メッセージの末尾に表示されるURLです。
# 動作確認対象の団地URLに置き換えてください。
UR_DANCI_URL = "https://www.ur-net.go.jp/chintai/kanto/tokyo/20_3470.html"

# --- 判定セレクタ ---
# 空きあり時にのみ存在する、部屋検索結果の親要素のID
AVAILABLE_SELECTOR = "div#js-room-search-result" 

# --- 関数定義 ---

def check_ur_availability(url, selector):
    """
    指定されたURLからHTMLを取得し、特定のセレクタが存在するかどうかを確認します。
    """
    try:
        # User-Agentを設定して、ブラウザからのアクセスに見せかける
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # HTTPエラーがあれば例外を発生させる
        
        # HTMLを解析
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 指定されたセレクタを持つ要素を検索
        # find()は最初に見つかった要素を返し、見つからない場合はNoneを返します。
        is_available = soup.select_one(selector) is not None
        
        return is_available

    except requests.exceptions.RequestException as e:
        print(f"ウェブサイトへのアクセス中にエラーが発生しました: {e}")
        return None

def send_slack_notification(message):
    """
    Slackに通知を送信します。
    """
    try:
        client = WebClient(token=SLACK_BOT_TOKEN)
        
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=message
        )
        print("Slack通知を送信しました。")
    except SlackApiError as e:
        print(f"Slack APIエラーが発生しました: {e.response['error']}")

# --- メイン処理 ---

if __name__ == "__main__":
    current_date = "2025-11-22 JST" # 現在日付を必ず明記
    
    # UR団地の空き状況をチェック
    is_available = check_ur_availability(UR_DANCI_URL, AVAILABLE_SELECTOR)

    if is_available is None:
        # アクセスエラーが発生した場合
        slack_message = f"🚨 *UR団地の空き状況確認エラー* 🚨\n現在日付: {current_date}\n対象URL: <{UR_DANCI_URL}|UR団地ページ>\nウェブサイトへのアクセスに失敗しました。URLまたはネットワーク接続を確認してください。"
        send_slack_notification(slack_message)
    elif is_available:
        # 空きがあった場合
        slack_message = f"✅ *空きありのお知らせ* ✅\n現在日付: {current_date}\n「空きあり」の可能性が高いです！すぐに確認してください。\n対象URL: <{UR_DANCI_URL}|UR団地ページ>"
        send_slack_notification(slack_message)
    else:
        # 空きがなかった場合
        print(f"現在、空きはありません。（{current_date}）")
        # Slackへの通知は行わない（空きがない場合）
        
# 根拠: 'div#js-room-search-result' の有無によって空きあり・なしを判定するロジックは、空きあり/なし両方のソースコードで有効であることが確認された。
# 出典: 提供されたHTMLソースコードの解析および requests, beautifulsoup4, slack_sdk のドキュメント。
# 確実性: 高
