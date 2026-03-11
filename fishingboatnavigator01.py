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

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def judge_status(content):
    if not content: return "○"
    if any(k in content for k in ["満", "×", "済", "貸", "チャーター", "Full", "予約有", "締切", "1 event"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか"]): return "△"
    return "○"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【開始】 {boat['name']} ---")
    try:
        driver.get(boat['url'])
        time.sleep(10)

        # 全てのiframeを調査
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        found_data = False
        
        for ifr in iframes:
            src = ifr.get_attribute("src") or ""
            if "google.com/calendar" not in src and "calendar" not in src:
                continue

            print(f"  🎯 カレンダーiframeを発見。解析中...")
            driver.switch_to.frame(ifr)
            time.sleep(5) # 描画待ち

            schedules = []
            
            # Googleカレンダーの「日」の枠（クラス名: st-dgo, st-bg など）を全取得
            # ロジック：カレンダー内の全テキストを取得し、改行で分割
            try:
                # ほとんどのカレンダーで有効な要素を広めに取得
                elements = driver.find_elements(By.XPATH, "//*[contains(@class, 'st-')] | //*[contains(@role, 'gridcell')]")
                
                current_month = "3月" # ひとまず3月固定、あるいはページから取得
                
                for el in elements:
                    text = el.text.strip()
                    if not text: continue
                    
                    # 「数字（日付）」から始まるテキストを探す (例: "15\nタイラバ" または "15 満員")
                    lines = text.split('\n')
                    day_match = re.match(r"^(\d{1,2})", lines[0])
                    
                    if day_match:
                        day = day_match.group(1)
                        date_str = f"{current_month}{day}日"
                        
                        # 2行目以降があればそれが「内容」
                        content = " ".join(lines[1:]) if len(lines) > 1 else ""
                        
                        if content:
                            schedules.append({
                                "date": date_str,
                                "status": judge_status(content),
                                "detail": content
                            })

                # aria-label（バックアップ策）
                if not schedules:
                    cells = driver.find_elements(By.XPATH, "//*[@aria-label]")
                    for cell in cells:
                        label = cell.get_attribute("aria-label")
                        # "3月15日, 予定あり" のような形式を抽出
                        date_m = re.search(r"(\d{1,2}月\d{1,2}日)", label)
                        if date_m:
                            # 「イベントなし」以外を抽出
                            if "なし" not in label and "No events" not in label:
                                date_str = date_m.group(1)
                                schedules.append({
                                    "date": date_str,
                                    "status": judge_status(label),
                                    "detail": label.replace(date_str, "").strip(" ,")
                                })

            except Exception as inner_e:
                print(f"    解析中にエラー: {inner_e}")

            if schedules:
                all_results[boat['name']] = {"data": schedules}
                print(f"  ✅ {len(schedules)}件取得")
                found_data = True
                driver.switch_to.default_content()
                break
            
            driver.switch_to.default_content()

        if not found_data:
            print(f"  ⚠️ iframeは見つかりましたが中身が空、または読み込めていません")

    except Exception as e:
        print(f"  💥 エラー: {boat['name']}")

driver.quit()

output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
