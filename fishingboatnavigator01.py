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
        time.sleep(12)

        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        found_data = False
        
        for ifr in iframes:
            src = ifr.get_attribute("src") or ""
            if "google.com/calendar" in src:
                driver.switch_to.frame(ifr)
                time.sleep(8)

                schedules = []
                # 【重要】日付の枠ではなく、個別の「予定項目」をピンポイントで取得する
                # 終日予定などは div[role='button'] か div[aria-label] に入っていることが多い
                event_elements = driver.find_elements(By.XPATH, "//div[@role='button' and contains(@aria-label, '2026')]")
                
                # 月名変換マップ
                month_map = {"January":"1","February":"2","March":"3","April":"4","May":"5","June":"6",
                             "July":"7","August":"8","September":"9","October":"10","November":"11","December":"12"}

                for el in event_elements:
                    label = el.get_attribute("aria-label")
                    if not label: continue
                    
                    # 予定名そのものは要素のテキストから取得
                    title = el.text.strip()
                    
                    # テキストが空（または数字のみ）の場合は、ラベルの最初のカンマより前を予定名とする
                    if not title or title.isdigit():
                        title = label.split(',')[0].strip()

                    # 「○ events」や「Today」などは除外
                    if "event" in title.lower() or "today" in title.lower() or "イベント" in title:
                        continue

                    # 日付の抽出
                    date_found = None
                    m_ja = re.search(r"(\d{1,2})月(\d{1,2})日", label)
                    if m_ja:
                        date_found = f"{m_ja.group(1)}月{m_ja.group(2)}日"
                    else:
                        for m_name, m_num in month_map.items():
                            if m_name in label:
                                d_match = re.search(rf"{m_name}\s+(\d{{1,2}})", label)
                                if d_match:
                                    date_found = f"{m_num}月{d_match.group(1)}日"
                                    break
                    
                    if date_found and title:
                        schedules.append({
                            "date": date_found,
                            "status": judge_status(title),
                            "detail": title
                        })

                if schedules:
                    # 同じ日付の予定をまとめる
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
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
