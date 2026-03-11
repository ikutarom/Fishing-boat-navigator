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
options.add_argument('--window-size=1920,1080')

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
        time.sleep(15) # サイトの読み込みを十分に待つ

        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        found_data = False
        
        for ifr in iframes:
            src = ifr.get_attribute("src") or ""
            if "calendar" in src:
                driver.switch_to.frame(ifr)
                time.sleep(10) # カレンダー描画を待つ

                # カレンダー全体のテキストをドサッと取得
                entire_text = driver.find_element(By.TAG_NAME, "body").text
                lines = entire_text.split('\n')
                
                schedules = []
                current_day = ""
                
                # 今日の日付を取得（2026年3月）
                current_month = "3月" 

                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line: continue

                    # 1. 数字（日付）のみの行を見つけたら、それを基準日とする
                    if line.isdigit() and 1 <= int(line) <= 31:
                        # ただし、直後の行が「曜日」や「events」なら、それはカレンダーのヘッダーか空の日
                        current_day = f"{current_month}{line}日"
                        continue
                    
                    # 2. 数字以外の「予定らしき文字」が来た場合
                    if current_day and not line.isdigit():
                        # 除外キーワード（Googleカレンダーのシステム用語）
                        if any(k in line for k in ["曜日", "event", "前月", "翌月", "今日", "印刷", "月", "週"]):
                            continue
                        
                        # 予定として採用
                        schedules.append({
                            "date": current_day,
                            "status": judge_status(line),
                            "detail": line
                        })

                if schedules:
                    # 同じ日付の重複をまとめる
                    unique_days = {}
                    for s in schedules:
                        d = s["date"]
                        if d not in unique_days:
                            unique_days[d] = s
                        else:
                            if s['detail'] not in unique_days[d]['detail']:
                                unique_days[d]["detail"] += f" / {s['detail']}"
                            unique_days[d]["status"] = judge_status(unique_days[d]["detail"])
                    
                    all_results[boat['name']] = {"data": list(unique_days.values())}
                    print(f"  ✅ {len(unique_days)}件の予定を抽出しました")
                    found_data = True
                    driver.switch_to.default_content()
                    break
                
                driver.switch_to.default_content()
        
        if not found_data:
            print(f"  ⚠️ 予定が見つかりませんでした")

    except Exception as e:
        print(f"  💥 エラー: {boat['name']}")

driver.quit()

output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
