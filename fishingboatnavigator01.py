import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# M-selectionのURLに日本語指定(&hl=ja)を追加
BOATS = [
    {
        "name": "M-selection",
        "url": "https://calendar.google.com/calendar/u/0/embed?src=bXNlbGVjdGlvbi5zaGlwQGdtYWlsLmNvbQ&ctz=Asia/Tokyo&hl=ja",
        "area": "糸島",
        "official": "https://m-selection.com/"
    }
]

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
# 自動操作であることを隠す設定
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def judge_status(content):
    if any(k in content for k in ["満", "×", "済", "貸", "チャーター", "Full", "予約有", "締切", "満員"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか"]): return "△"
    return "○"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【開始】 {boat['name']} ---")
    try:
        driver.get(boat['url'])
        time.sleep(10) # 描画をしっかり待つ

        # ページ全体のテキストを一度に取得（これが一番エラーが出にくい）
        body_text = driver.find_element(By.TAG_NAME, "body").text
        lines = body_text.split('\n')
        
        schedules = []
        current_date = ""
        
        # テキストの中から「○月○日」と「その直後の予定」をペアにする
        for i in range(len(lines)):
            line = lines[i].strip()
            
            # 日付パターン (例: 3月11日(水) や 3月11日) を探す
            date_match = re.search(r'(\d{1,2})月(\d{1,2})日', line)
            
            if date_match:
                current_date = f"{date_match.group(1)}月{date_match.group(2)}日"
                continue # 次の行に予定名があることを期待
            
            # 日付が決まった後の行で、ゴミ（曜日、印刷、Googleなど）でないものを予定名とする
            if current_date and line:
                if any(k in line for k in ["今日", "印刷", "Google", "カレンダー", "曜日", "月", "火", "水", "木", "金", "土", "日"]):
                    continue
                
                # 数字だけ、または極端に短い文字は日付ラベルなので除外
                if line.isdigit() or len(line) < 2:
                    continue

                schedules.append({
                    "date": current_date,
                    "status": judge_status(line),
                    "detail": line
                })

        if schedules:
            # 重複排除
            unique_data = {}
            for s in schedules:
                key = (s['date'], s['detail'])
                if key not in unique_data:
                    unique_data[key] = s
            
            all_results[boat['name']] = {"data": list(unique_data.values())}
            print(f"  ✅ {len(unique_data)}件の予定を抽出しました")
        else:
            print("  ⚠️ 予定が見つかりませんでした。サイトの構造が変わった可能性があります。")

    except Exception as e:
        print(f"  💥 エラー: {boat['name']}")

driver.quit()

# 保存処理
output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
