import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
    if any(k in content for k in ["満", "×", "済", "貸", "チャーター", "Full", "予約有", "締切", "満員", "1 event"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか"]): return "△"
    return "○"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【開始】 {boat['name']} ---")
    try:
        driver.get(boat['url'])
        # サイトの読み込みを待つ
        time.sleep(12)

        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        found_data = False
        
        for ifr in iframes:
            src = ifr.get_attribute("src") or ""
            if "google.com/calendar" in src:
                driver.switch_to.frame(ifr)
                # カレンダーの内部要素が出るまで待機
                time.sleep(8)
                
                schedules = []
                # aria-label属性を持つ全ての要素を対象にする
                elements = driver.find_elements(By.XPATH, "//*[@aria-label]")
                
                month_map = {"January":"1","February":"2","March":"3","April":"4","May":"5","June":"6",
                             "July":"7","August":"8","September":"9","October":"10","November":"11","December":"12"}
                
                for el in elements:
                    label = el.get_attribute("aria-label")
                    if not label: continue
                    
                    # デバッグ用に「イベントなし」系はスキップ
                    if "イベントなし" in label or "No events" in label: continue
                    
                    date_found = None
                    # 日本語形式 (例: 3月15日)
                    m_ja = re.search(r"(\d{1,2})月(\d{1,2})日", label)
                    if m_ja:
                        date_found = f"{m_ja.group(1)}月{m_ja.group(2)}日"
                    else:
                        # 英語形式 (例: March 15)
                        for m_name, m_num in month_map.items():
                            if m_name in label:
                                d_match = re.search(rf"{m_name}\s+(\d{{1,2}})", label, re.IGNORECASE)
                                if d_match:
                                    date_found = f"{m_num}月{d_match.group(1)}日"
                                    break
                    
                    if date_found:
                        # 予定の中身を抽出（日付以外の部分）
                        # カンマ区切りの最初の方にあることが多い
                        parts = label.split(',')
                        detail = parts[0].strip()
                        
                        # もしdetailが日付そのものだった場合は、次のパーツを見る
                        if re.match(r"^\d+月\d+日$", detail) or any(m in detail for m in month_map) and len(parts) > 1:
                            detail = parts[1].strip()

                        if detail and not detail.isdigit():
                            schedules.append({
                                "date": date_found,
                                "status": judge_status(label),
                                "detail": detail
                            })
                
                if schedules:
                    unique_days = {}
                    for s in schedules:
                        d = s["date"]
                        if d not in unique_days:
                            unique_days[d] = s
                        else:
                            # 同じ日の予定をマージ
                            if s['detail'] not in unique_days[d]['detail']:
                                unique_days[d]["detail"] += f" / {s['detail']}"
                            unique_days[d]["status"] = judge_status(unique_days[d]["detail"])
                    
                    all_results[boat['name']] = {"data": list(unique_days.values())}
                    print(f"  ✅ {len(unique_days)}件の予定を取得")
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
