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
    print("Error: boats.py not found.")
    exit(1)

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--lang=ja-JP')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def judge_status(content):
    if any(k in content for k in ["満", "×", "済", "貸", "チャーター", "Full", "予約有", "締切", "満員", "1 event"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか"]): return "△"
    return "○"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【開始】 {boat['name']} ---")
    try:
        driver.get(boat['url'])
        time.sleep(10) # サイト自体の読み込み待機

        # iframeの全探索（Googleカレンダー以外も含む可能性を考慮）
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        found_data = False
        
        for i, ifr in enumerate(iframes):
            try:
                src = ifr.get_attribute("src") or ""
                # Googleカレンダー、またはそれに類する予約システムをターゲット
                if "google.com/calendar" in src or "calendar" in src:
                    print(f"  🎯 カレンダーiframe({i+1})へ切り替え中...")
                    driver.switch_to.frame(ifr)
                    time.sleep(5) # カレンダー内部の描画待機
                    
                    # --- ロジック変更：全テキストをぶっこ抜いて正規表現で解析 ---
                    page_text = driver.find_element(By.TAG_NAME, "body").text
                    
                    # 1. 予定がある日付を抽出
                    # Googleカレンダーの「予定あり」のテキストパターンを網羅
                    # パターン例: "3月15日\nタイラバ" や "15\n1 event"
                    lines = page_text.split('\n')
                    schedules = []
                    current_date = ""

                    for idx, line in enumerate(lines):
                        # 日付（○月○日）を見つけた場合
                        date_m = re.search(r"(\d{1,2})月(\d{1,2})日", line)
                        if date_m:
                            current_date = f"{date_m.group(1)}月{date_m.group(2)}日"
                            continue
                        
                        # 日付の直後に予定らしき文字列がある場合（空文字や数字のみは除外）
                        if current_date and len(line) > 1 and not line.isdigit():
                            if "前月" in line or "翌月" in line or "曜日" in line:
                                continue
                            
                            schedules.append({
                                "date": current_date,
                                "status": judge_status(line),
                                "detail": line
                            })
                    
                    if schedules:
                        all_results[boat['name']] = {"data": schedules}
                        print(f"  ✅ {len(schedules)}件の予定を取得しました")
                        found_data = True
                        driver.switch_to.default_content()
                        break
                    
                    driver.switch_to.default_content()
            except:
                driver.switch_to.default_content()
                continue
        
        if not found_data:
            print(f"  ⚠️ データが取得できませんでした。サイト構造が特殊な可能性があります。")

    except Exception as e:
        print(f"  💥 エラー: {boat['name']} - {str(e)}")

driver.quit()

output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
