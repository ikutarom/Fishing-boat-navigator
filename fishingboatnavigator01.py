import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

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
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def judge_status(content):
    if any(k in content for k in ["満船", "満", "チャーター", "予約済", "貸切", "×", "済", "Full", "完売", "締切"]):
        return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか"]):
        return "△"
    return "○"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【開始】 {boat['name']} ---")
    boat_schedules = []
    
    try:
        # AGENDAモードを強制
        target_url = boat['url']
        if "mode=AGENDA" not in target_url:
            target_url += "&mode=AGENDA"
        if "hl=ja" not in target_url:
            target_url += "&hl=ja"
            
        driver.get(target_url)
        time.sleep(12)

        raw_text = driver.execute_script("return document.body.innerText;")
        
        if raw_text:
            lines = raw_text.splitlines()
            current_day = ""
            current_month = "3月" 

            for i in range(len(lines)):
                line = lines[i].strip()
                if not line: continue

                # 1. 日付の特定（「月, 曜日」形式）
                month_match = re.search(r'(\d{1,2})月,\s?[一-龠]', line)
                if month_match:
                    current_month = f"{month_match.group(1)}月"
                    if i > 0 and lines[i-1].strip().isdigit():
                        current_day = lines[i-1].strip()
                    continue

                # 2. 予定の抽出（「終日」または「時刻」の次の行をすべて拾う）
                # current_day が確定している間、フラグを見つけたらその直後を拾い続ける
                if current_day and (line == "終日" or re.match(r'\d{2}:\d{2}', line)):
                    if i + 1 < len(lines):
                        detail = lines[i+1].strip()
                        
                        # システム行の除外
                        if any(k in detail for k in ["カレンダー:", "フィードバック", "Google", "表示", "詳細を表示"]):
                            continue
                        
                        full_date = f"{current_month}{current_day}日"
                        boat_schedules.append({
                            "date": full_date,
                            "status": judge_status(detail),
                            "detail": detail
                        })

            # 重複排除
            unique_schedules = []
            seen = set()
            for s in boat_schedules:
                identifier = (s['date'], s['detail'])
                if identifier not in seen:
                    seen.add(identifier)
                    unique_schedules.append(s)
            
            all_results[boat['name']] = {"data": unique_schedules}
            print(f"  ✅ {len(unique_schedules)}件の予定を抽出")
            
    except Exception as e:
        print(f"  💥 エラー: {boat['name']} ({str(e)})")

driver.quit()

output = {
    "boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS},
    "schedules": all_results
}

with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)

print("\n💾 保存完了")
