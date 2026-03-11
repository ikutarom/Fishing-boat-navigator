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
    if any(k in content for k in ["満", "×", "済", "貸", "チャーター", "Full", "予約有", "締切", "満員"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか"]): return "△"
    return "○"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【開始】 {boat['name']} ---")
    try:
        driver.get(boat['url'])
        time.sleep(10)

        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        target_iframe = None
        for ifr in iframes:
            try:
                src = ifr.get_attribute("src") or ""
                if "google.com/calendar" in src:
                    target_iframe = ifr
                    break
            except: continue
        
        if target_iframe:
            print(f"  🎯 Googleカレンダーを発見。")
            driver.switch_to.frame(target_iframe)
            time.sleep(8)
            
            schedules = []
            # --- 修正ポイント：aria-label属性から正確な日付と内容を抜く ---
            # Googleカレンダーの各マスや予定にはaria-labelに詳細が入っています
            elements = driver.find_elements(By.XPATH, "//*[@aria-label]")
            
            for el in elements:
                label = el.get_attribute("aria-label")
                # 例: "3月15日, 予定あり, タイラバ船" や "2026年3月15日"
                if not label: continue
                
                # 日付を抽出 (例: 3月15日)
                date_match = re.search(r"(\d+月\d+日)", label)
                if date_match:
                    date_str = date_match.group(1)
                    # 「今日」や曜日だけのラベルを除外、かつ「予定」という言葉が含まれるか、
                    # あるいは特定のキーワードが含まれる場合に採用
                    if "イベントなし" in label or "No events" in label:
                        continue
                    
                    # 予定の内容をクリーンアップ
                    clean_detail = label.replace(date_str, "").replace("のイベント:", "").strip(" ,")
                    if len(clean_detail) > 1:
                        schedules.append({
                            "date": date_str,
                            "status": judge_status(clean_detail),
                            "detail": clean_detail
                        })

            if schedules:
                # 重複削除（同じ日の予定が複数あれば結合するか、最初を採用）
                unique_schedules = {}
                for s in schedules:
                    d = s["date"]
                    if d not in unique_schedules:
                        unique_schedules[d] = s
                    else:
                        # 同じ日に複数の予定がある場合は結合
                        unique_schedules[d]["detail"] += f" / {s['detail']}"
                        unique_schedules[d]["status"] = judge_status(unique_schedules[d]["detail"])
                
                final_list = list(unique_schedules.values())
                all_results[boat['name']] = {"data": final_list}
                print(f"  ✅ {len(final_list)}日分のデータを正確に取得")
            else:
                print(f"  ❌ 有効な予定が見つかりませんでした")
            
            driver.switch_to.default_content()
        else:
            print(f"  ⚠️ カレンダーiframeが見つかりません")

    except Exception as e:
        print(f"  💥 エラー回避: {boat['name']}")
        try: driver.switch_to.default_content()
        except: pass

driver.quit()

output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
