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
                # aria-labelを持つすべての要素を取得（予定の塊）
                elements = driver.find_elements(By.XPATH, "//*[@aria-label]")
                
                month_map = {"January":"1","February":"2","March":"3","April":"4","May":"5","June":"6",
                             "July":"7","August":"8","September":"9","October":"10","November":"11","December":"12"}

                for el in elements:
                    label = el.get_attribute("aria-label")
                    if not label: continue
                    
                    # 1. 不要なUIテキストを徹底排除
                    if any(k in label for k in ["No events", "イベントなし", "前月", "翌月", "Calendar", "Google"]):
                        continue
                    
                    # 2. 日付を抽出（英語形式: March 8, 2026 または 日本語形式: 3月8日）
                    date_found = None
                    # 日本語形式
                    m_ja = re.search(r"(\d{1,2})月(\d{1,2})日", label)
                    if m_ja:
                        date_found = f"{m_ja.group(1)}月{m_ja.group(2)}日"
                    else:
                        # 英語形式 (March 8, 2026)
                        for m_name, m_num in month_map.items():
                            if m_name in label:
                                d_match = re.search(rf"{m_name}\s+(\d{{1,2}})", label)
                                if d_match:
                                    date_found = f"{m_num}月{d_match.group(1)}日"
                                    break
                    
                    # 3. 予定の内容を抽出
                    if date_found:
                        # labelから日付部分を消して、残ったものを「内容」とする
                        # 例: "ジギング, Sunday, March 8, 2026" -> "ジギング"
                        content = label
                        # 日付文字列や曜日の単語を消去してクリーンアップ
                        for word in list(month_map.keys()) + ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday", "2025", "2026"]:
                            content = re.sub(rf",?\s*{word}\s*,?", "", content, flags=re.IGNORECASE)
                        content = re.sub(r"\d{1,2}月\d{1,2}日", "", content)
                        content = content.strip(" ,")

                        if content and not content.isdigit() and len(content) > 1:
                            schedules.append({
                                "date": date_found,
                                "status": judge_status(content),
                                "detail": content
                            })

                if schedules:
                    # 同じ日付の予定を整理（マージ）
                    unique_days = {}
                    for s in schedules:
                        d = s["date"]
                        if d not in unique_days:
                            unique_days[d] = s
                        else:
                            if s['detail'] not in unique_days[d]['detail']:
                                unique_days[d]["detail"] += f" / {s['detail']}"
                            unique_days[d]["status"] = judge_status(unique_days[d]["detail"])
                    
                    all_results[boat['name']] = {"data": sorted(list(unique_days.values()), key=lambda x: int(re.search(r'\d+', x['date']).group()))}
                    print(f"  ✅ {len(unique_days)}日分の有効な予定を抽出")
                    found_data = True
                    driver.switch_to.default_content()
                    break
                
                driver.switch_to.default_content()
        
        if not found_data:
            print(f"  ⚠️ 有効な予定が見つかりませんでした")

    except Exception as e:
        print(f"  💥 エラー: {boat['name']}")

driver.quit()

output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
