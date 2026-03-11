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

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.page_load_strategy = 'normal'
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(45)

def judge_status(content):
    if any(k in content for k in ["チャーター可", "チャーター募", "チャーターOK"]): return "○"
    if any(k in content for k in ["満船", "満", "予約済", "貸切", "×", "済", "Full", "完売", "締切", "チャーター"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか"]): return "△"
    return "○"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【解析開始】 {boat['name']} ---")
    boat_schedules = []
    
    try:
        # パラメータ設定
        target_url = boat['url']
        params = "&mode=AGENDA&weeks=14&hl=ja&ctz=Asia/Tokyo"
        target_url += params if "?" in target_url else "?" + params[1:]
        driver.get(target_url)

        # iframe対策：Googleカレンダーの内部フレームに切り替え
        time.sleep(6)
        if len(driver.find_elements(By.TAG_NAME, "iframe")) > 0:
            driver.switch_to.frame(0)

        raw_text = driver.execute_script("return document.body.innerText;")
        
        if raw_text:
            lines = raw_text.splitlines()
            current_day = ""
            current_month = ""

            for i in range(len(lines)):
                line = lines[i].strip()
                if not line: continue

                # 1. 月の特定 ("3月," など)
                month_match = re.search(r'(\d{1,2})月,', line)
                if month_match:
                    current_month = f"{month_match.group(1)}月"
                    # 日付（数値）を探す
                    date_num_match = re.search(r',\s*(\d{1,2})', line)
                    if date_num_match:
                        current_day = date_num_match.group(1)
                    elif i > 0 and lines[i-1].strip().isdigit():
                        current_day = lines[i-1].strip()
                    continue

                # 2. 予定の抽出ロジック（ここを大幅強化）
                # 目印1: 「終日」または「All day」
                # 目印2: 「12:30」や「5am」などの時刻形式
                is_time_marker = (
                    line in ["終日", "All day"] or 
                    re.match(r'\d{1,2}:\d{2}', line) or # 12:30 形式
                    re.match(r'\d{1,2}(am|pm)', line.lower()) # 5am 形式
                )

                if current_day and is_time_marker:
                    # 目印の次の行、またはその次の行に予定内容がある
                    # Googleカレンダーの構造上、時刻と内容が別行になるため2行先まで見る
                    look_ahead_limit = min(i + 3, len(lines))
                    for j in range(i + 1, look_ahead_limit):
                        detail = lines[j].strip()
                        if not detail or any(k in detail for k in ["表示", "Google", "カレンダー", "詳細"]):
                            continue
                        
                        # 予定内容として採用
                        if current_month and current_day:
                            boat_schedules.append({
                                "date": f"{current_month}{current_day}日",
                                "status": judge_status(detail),
                                "detail": detail
                            })
                        break # 1つ見つけたらその時刻の解析は終了

            # 重複排除
            unique_schedules = []
            seen = set()
            for s in boat_schedules:
                identifier = (s['date'], s['detail'])
                if identifier not in seen:
                    seen.add(identifier); unique_schedules.append(s)
            
            all_results[boat['name']] = {"data": unique_schedules}
            print(f"  ✅ {len(unique_schedules)}件抽出完了")

        driver.switch_to.default_content()
            
    except Exception as e:
        print(f"  💥 エラー: {boat['name']} ({str(e)})")

driver.quit()

# 保存処理（last_update付き）
output = {
    "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS},
    "schedules": all_results
}
json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fishing_schedule.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
