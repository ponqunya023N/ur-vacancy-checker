import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import json
import time

# ... (監視対象リスト、メール送信設定、状態管理関数は変更なし) ...
# (前回の全文コードから省略)

# --- 検索設定 (最終確認) ---
# 「ただいま、ご紹介できるお部屋がございません。」という文字列がないことを空きありと判定する
EMPTY_STRING = 'ただいま、ご紹介できるお部屋がございません。'

# --- 状態管理関数 ---
# (中略)

def check_vacancy(danchi):
    """団地ごとの空き情報をチェックし、結果(文字列とブーリアン)を返す"""
    danchi_name = danchi["danchi_name"]
    url = danchi["url"]

    print(f"\n--- 団地チェック開始: {danchi_name} ---")
    print(f"🔍 対象URL: {url}")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        response.encoding = response.apparent_encoding 
        soup = BeautifulSoup(response.text, 'html.parser')
        page_text = soup.get_text()

        # --- 最終文字列判定ロジック ---
        # 空室がないことを示す文字列が存在するかチェック
        if EMPTY_STRING not in page_text:
            # 空きあり: 指定文字列（空きなしを示す）が存在しない
            print(f"🚨 検出: 検索文字列 '{EMPTY_STRING}' が**存在しません**。空きが出た可能性があります！")
            return f"空きあり: {danchi_name}", True
        else:
            # 空きなし: 指定文字列（空きなしを示す）が存在する
            print(f"✅ 検出: 検索文字列 '{EMPTY_STRING}' が存在します。空きなし。")
            return f"空きなし: {danchi_name}", False

    except requests.exceptions.HTTPError as e:
        # ... (エラー処理は中略)
        print(f"🚨 エラー: HTTPエラーが発生しました (ステータスコード: {response.status_code})。")
        return f"HTTPエラー: {danchi_name}", False
    except requests.exceptions.RequestException as e:
        print(f"🚨 エラー: ネットワークまたはリクエストのエラーが発生しました: {e}")
        return f"リクエストエラー: {danchi_name}", False
    except Exception as e:
        print(f"🚨 エラー: その他の予期せぬエラーが発生しました: {e}")
        return f"予期せぬエラー: {danchi_name}", False


if __name__ == "__main__":
    # ... (メインロジックは中略、メール送信失敗の場合のみ、専門家に確認が必要)
    print(f"=== UR空き情報監視スクリプト実行開始 ({len(MONITORING_TARGETS)} 件) ===")
    
    current_status = get_current_status()
    print(f"⭐ 現在の通知状態 (status.json): {current_status}")
    
    vacancy_detected = False
    available_danchis = []
    results = []
    
    for danchi_info in MONITORING_TARGETS:
        result_text, is_available = check_vacancy(danchi_info)
        results.append(result_text)
        
        if is_available:
            vacancy_detected = True
            available_danchis.append(danchi_info)
        
        time.sleep(1) 
        
    print("\n=== 全ての監視対象のチェックが完了しました ===")
    for res in results:
        print(f"- {res}")
        
    new_status = 'available' if vacancy_detected else 'not_available'

    if new_status == current_status:
        # 状態が変わっていない場合：通知スキップ
        print(f"✅ 状態に変化なし ('{new_status}')。メール送信はスキップします。")
    else:
        # 状態が変わった場合：メール送信
        print(f"🚨 状態が変化しました ('{current_status}' -> '{new_status}')。")
        
        if new_status == 'available':
            # 状態が not_available -> available に変化した瞬間（空きが出た瞬間）
            
            subject = f"【UR空き情報アラート】🚨 空きが出ました！({len(available_danchis)}団地)"
            body_lines = [
                "UR賃貸に空き情報が出た可能性があります！",
                "以下の団地を確認してください:\n"
            ]
            
            for danchi in available_danchis:
                body_lines.append(f"・【団地名】: {danchi['danchi_name']}")
                body_lines.append(f"  【URL】: {danchi['url']}\n")
            
            body = "\n".join(body_lines)
            
            send_alert_email(subject, body)
            update_status(new_status)
        else:
            # 状態が available -> not_available に変化した瞬間
            update_status(new_status)
            print("✅ '空きなし' への変化を確認しました。通知は行わず状態のみを更新します。")
    
    print("\n=== 監視終了 ===")
    
#EOF
