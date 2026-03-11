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
options.add_argument('--window-size=1920,1080') # 画面を広くしてカレンダーを安定させる

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
        time.sleep(10)

        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        found_data = False
        
        for ifr in iframes:
            src = ifr.get_attribute("src") or ""
            if "google.com/calendar" in src:
                driver.switch_to.frame(ifr)
                time.sleep(5)
                
                schedules = []
                # 全ての要素から aria-label を持つものを取得
                # Googleカレンダーの予定は aria-label に "March 8, 2026, ジギング" のように入っている
                elements = driver.find_elements(By.XPATH, "//*[@aria-label]")
                
                for el in elements:
                    label = el.get_attribute("aria-label")
                    if not label or "Calendar" not in label: continue
                    
                    # --- 日付の抽出 ---
                    # パターン1: "March 8, 2026" (英語設定の場合)
                    # パターン2: "2026年3月8日" (日本語設定の場合)
                    month_map = {"January":"1","February":"2","March":"3","April":"4","May":"5","June":"6",
                                 "July":"7","August":"8","September":"9","October":"10","November":"11","December":"12"}
                    
                    date_found = None
                    
                    # 日本語形式の検索
                    m_ja = re.search(r"(\d{1,2})月(\d{1,2})日", label)
                    if m_ja:
                        date_found = f"{m_ja.group(1)}月{m_ja.group(2)}日"
                    else:
                        # 英語形式の検索 (March 8, 2026)
                        for m_name, m_num in month_map.items():
                            if m_name in label:
                                d_match = re.search(rf"{m_name}\s+(\d{{1,2}})", label)
                                if d_match:
                                    date_found = f"{m_num}月{d_match.group(1)}日"
                                    break
                    
                    if date_found:
                        # 予定の内容をクリーンアップ（日付やカレンダー名を除去）
                        clean_detail = label.split(',')[0].strip() # 最初のカンマまでが予定名
                        
                        schedules.append({
                            "date": date_found,
                            "status": judge_status(label),
                            "detail": clean_detail
                        })
                
                if schedules:
                    # 同じ日付の予定をまとめる
                    unique_days = {}
                    for s in schedules:
                        d = s["date"]
                        if d not in unique_days:
                            unique_days[d] = s
                        else:
                            unique_days[d]["detail"] += f" / {s['detail']}"
                            unique_days[d]["status"] = judge_status(unique_days[d]["detail"])
                    
                    all_results[boat['name']] = {"data": list(unique_days.values())}
                    print(f"  ✅ {len(unique_days)}日分の予定を特定しました")
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
