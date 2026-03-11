import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

TARGET_URL = "https://calendar.google.com/calendar/u/0/embed?src=mctbqceknts09ssk81vck6npik@group.calendar.google.com&src=f06ic59ea23rpoopr54mf7sui0@group.calendar.google.com&src=0s2q9vsadci1eg09teq6pip3ms@group.calendar.google.com&src=g86rlbflghcqh7kfl5k4gkq69g@group.calendar.google.com&ctz=Asia/Tokyo&hl=ja&mode=AGENDA"

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def judge_status(content):
    if any(k in content for k in ["満船", "満", "チャーター", "予約済", "貸切", "×", "済", "Full", "完売"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか"]): return "△"
    return "○"

all_schedules = []

print(f"🚀 --- スキャン開始 (スケジュール表示解析モード) ---")
try:
    driver.get(TARGET_URL)
    time.sleep(15) 

    raw_text = driver.execute_script("return document.body.innerText;")
    
    if raw_text:
        lines = raw_text.splitlines()
        current_day = ""
        current_month = "3月" # デフォルト

        for i in range(len(lines)):
            line = lines[i].strip()
            if not line: continue

            # 1. 「月, 曜日」の形式（例：3月, 水）を探して月を更新
            month_match = re.search(r'(\d{1,2})月,\s?[一-龠]', line)
            if month_match:
                current_month = f"{month_match.group(1)}月"
                # その1行上が日付の数字（11 など）である可能性が高い
                if i > 0 and lines[i-1].strip().isdigit():
                    current_day = lines[i-1].strip()
                continue

            # 2. 予定本体の抽出
            # 「終日」または「時刻(00:00)」の次の行が本命の予定
            if line == "終日" or re.match(r'\d{2}:\d{2}', line):
                if i + 1 < len(lines):
                    detail = lines[i+1].strip()
                    # ゴミデータ除外
                    if any(k in detail for k in ["カレンダー:", "フィードバック", "Google", "表示"]):
                        continue
                    
                    if current_day:
                        full_date = f"{current_month}{current_day}日"
                        all_schedules.append({
                            "date": full_date,
                            "status": judge_status(detail),
                            "detail": detail
                        })

    # 重複排除 (同じ日の同じ予定をまとめる)
    seen = set()
    unique_schedules = []
    for s in all_schedules:
        identifier = (s['date'], s['detail'])
        if identifier not in seen:
            seen.add(identifier)
            unique_schedules.append(s)

except Exception as e:
    print(f"  💥 エラー発生: {str(e)}")

driver.quit()

output = {"schedules": {"Combined-Calendar": {"data": unique_schedules}}}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)

print(f"\n💾 保存完了: {len(unique_schedules)}件")
