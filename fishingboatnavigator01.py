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
        found_data = False
        
        for ifr in iframes:
            src = ifr.get_attribute("src") or ""
            if "google.com/calendar/embed" in src:
                # 埋め込みカレンダー専用の解析
                driver.switch_to.frame(ifr)
                time.sleep(5)
                
                schedules = []
                # 予定が入っている要素（Googleカレンダー特有のクラス名）を狙い撃ち
                # st-ad-ln は「終日予定」のラベルが入るクラス
                items = driver.find_elements(By.CSS_SELECTOR, ".st-ad-ln, .rb-n, .te-s")
                
                for item in items:
                    try:
                        # 親要素のaria-labelに日付が入っていることが多い
                        # もしくは、その要素自体が持つテキストと、親の st-dgo などの日付を紐付ける
                        label = item.find_element(By.XPATH, "./ancestor::*[@aria-label]").get_attribute("aria-label")
                        content = item.text
                        
                        if not content or not label: continue
                        
                        # 日付抽出 (3月15日)
                        m_ja = re.search(r"(\d{1,2})月(\d{1,2})日", label)
                        if m_ja:
                            date_str = f"{m_ja.group(1)}月{m_ja.group(2)}日"
                            
                            # 数字だけの「日付ラベル」を誤爆して拾わないようにする
                            if content.strip() == date_str or content.strip().isdigit():
                                continue

                            schedules.append({
                                "date": date_str,
                                "status": judge_status(content),
                                "detail": content
                            })
                    except:
                        continue
                
                if schedules:
                    unique_days = {}
                    for s in schedules:
                        d = s["date"]
                        if d not in unique_days:
                            unique_days[d] = s
                        else:
                            unique_days[d]["detail"] += f" / {s['detail']}"
                            unique_days[d]["status"] = judge_status(unique_days[d]["detail"])
                    
                    all_results[boat['name']] = {"data": list(unique_days.values())}
                    print(f"  ✅ {len(unique_days)}件取得成功")
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
