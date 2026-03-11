import os
import time
import re
import json
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

try:
    from boats import BOATS
except ImportError:
    print("Error: boats.py が見つかりません。")
    exit(1)

# ブラウザ設定
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
# 💡 ページ全体の完了を待たず、HTMLが読み込まれたら制御を戻す（高速化）
options.page_load_strategy = 'eager'
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
# 💡 1ページあたりの読み込み上限を30秒に設定（スタック防止）
driver.set_page_load_timeout(30)

def judge_status(content):
    if any(k in content for k in ["チャーター可", "チャーター募", "チャーターOK"]):
        return "○"
    if any(k in content for k in ["満船", "満", "予約済", "貸切", "×", "済", "Full", "完売", "締切", "チャーター"]):
        return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか"]):
        return "△"
    return "○"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【開始】 {boat['name']} ---")
    boat_schedules = []
    
    try:
        target_url = boat['url']
        if "mode=AGENDA" not in target_url: target_url += "&mode=AGENDA"
        if "weeks=" not in target_url: target_url += "&weeks=14" 
        if "hl=ja" not in target_url: target_url += "&hl=ja"
            
        driver.get(target_url)

        # 💡 【改善】動的ループ待機
        # 15秒間じっと待つのではなく、2秒ごとにテキストを確認し、
        # カレンダーの中身が描画された瞬間にスクレイピングを開始する
        raw_text = ""
        for _ in range(10): # 最大約20秒間試行
            time.sleep(2)
            raw_text = driver.execute_script("return document.body.innerText;")
            if "月," in raw_text or "終日" in raw_text:
                break
        
        if raw_text:
            lines = raw_text.splitlines()
            current_day = ""
            current_month = ""

            for i in range(len(lines)):
                line = lines[i].strip()
                if not line: continue

                # 1. 日付の特定
                month_match = re.search(r'(\d{1,2})月,\s?[一-龠]', line)
                if month_match:
                    current_month = f"{month_match.group(1)}月"
                    if i > 0 and lines[i-1].strip().isdigit():
                        current_day = lines[i-1].strip()
                    continue

                # 2. 予定の抽出
                if current_day and (line == "終日" or re.match(r'\d{2}:\d{2}', line)):
                    if i + 1 < len(lines):
                        detail = lines[i+1].strip()
                        
                        # 期間表記（1日目など）の削除
                        detail = re.sub(r'\s*[（(]\d+\s*(日目|day[s]?)\s*/\s*\d+\s*(日間|day[s]?)[）)]', '', detail).strip()
                        
                        # システム行の除外
                        if any(k in detail for k in ["カレンダー:", "フィードバック", "Google", "表示", "詳細を表示"]):
                            continue
                        
                        if current_month and current_day:
                            full_date = f"{current_month}{current_day}日"
                            boat_schedules.append({
                                "date": full_date,
                                "status": judge_status(detail),
                                "detail": detail
                            })

            unique_schedules = []
            seen = set()
            for s in boat_schedules:
                identifier = (s['date'], s['detail'])
                if identifier not in seen:
                    seen.add(identifier)
                    unique_schedules.append(s)
            
            all_results[boat['name']] = {"data": unique_schedules}
            print(f"  ✅ {len(unique_schedules)}件の予定を抽出")
            
    except TimeoutException:
        print(f"  ⚠️ タイムアウト: {boat['name']} の読み込みが遅いためスキップしました")
    except Exception as e:
        print(f"  💥 エラー: {boat['name']} ({str(e)})")

driver.quit()

output = {
    # 💡 実行時刻を入れることで、Gitに必ず「変更あり」と認識させる
    "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS},
    "schedules": all_results
}

# 💡 保存パスをカレントディレクトリに確実に指定
json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fishing_schedule.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)

print("\n💾 すべての処理が完了しました")

