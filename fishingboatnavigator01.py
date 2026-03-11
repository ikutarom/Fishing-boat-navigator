import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# 整理したScheduleモードのURL
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
    """予定内容から記号を判定"""
    if any(k in content for k in ["満船", "満", "チャーター", "予約済", "貸切", "×", "済", "Full"]):
        return "×"
    if re.search(r"残り([1-2])名", content) or "△" in content:
        return "△"
    return "○"

all_schedules = []

print(f"🚀 --- スキャン開始 ---")
try:
    driver.get(TARGET_URL)
    time.sleep(10) # 予定リストの読み込みを待機

    # Body全体のテキストを取得
    raw_text = driver.find_element(By.TAG_NAME, "body").text
    
    if raw_text:
        # 日付パターン: 「3月11日(水曜日)」や「3月 11日 (水)」などに対応
        date_pattern = r"(\d+月\s?\d+日)\s?\(.*?\)"
        lines = raw_text.splitlines()
        
        current_date = None
        
        for i in range(len(lines)):
            line = lines[i].strip()
            if not line: continue

            # 1. 日付行を見つけた場合
            date_match = re.search(date_pattern, line)
            if date_match:
                # スペースを詰めて「3月11日」形式に統一
                current_date = date_match.group(1).replace(" ", "")
                continue
            
            # 2. 日付が決まっている状態で、その下の予定行を解析
            if current_date:
                # 除外すべきシステム用語
                if any(k in line for k in ["今日", "印刷", "Google", "カレンダー", "件の予定", "予定はありません"]):
                    continue
                
                # 時刻表記（06:00など）が含まれる場合は、時刻を除去して内容のみ抽出
                clean_content = re.sub(r'\d{2}:\d{2}', '', line).strip()
                
                if len(clean_content) > 1:
                    all_schedules.append({
                        "date": current_date,
                        "status": judge_status(clean_content),
                        "detail": clean_content
                    })

    if all_schedules:
        print(f"  ✅ {len(all_schedules)}件の予定を抽出しました")
    else:
        print("  ⚠️ 予定が見つかりませんでした。テキスト取得に失敗している可能性があります。")

except Exception as e:
    print(f"  💥 エラー発生: {str(e)}")

driver.quit()

# JSON出力（M-selectionなどのキー構造に合わせて出力）
output = {
    "schedules": {
        "Combined-Calendar": {
            "data": all_schedules
        }
    }
}

with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)

print("\n💾 fishing_schedule.json に保存完了しました")
