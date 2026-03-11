import os
import time
import re
import json
import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

try:
    from boats import BOATS
except ImportError:
    print("Error: boats.py が見つかりません。")
    exit(1)

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.page_load_strategy = 'normal'
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(45)

def judge_status(content):
    # 暁の「🈵」「🈳」「募集中」を判定に含める
    if any(k in content for k in ["満船", "満", "予約済", "貸切", "×", "済", "Full", "完売", "締切", "チャーター", "🈵"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか", "🈳", "募集中"]): return "△"
    return "○"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【解析開始】 {boat['name']} ---")
    boat_schedules = []
    
    try:
        target_url = boat['url']
        params = "&mode=AGENDA&weeks=14&hl=ja&ctz=Asia/Tokyo"
        target_url += params if "?" in target_url else "?" + params[1:]
        driver.get(target_url)

        time.sleep(7)
        if len(driver.find_elements(By.TAG_NAME, "iframe")) > 0:
            driver.switch_to.frame(0)

        raw_text = driver.execute_script("return document.body.innerText;")
        
        if raw_text:
            lines = raw_text.splitlines()
            current_day = ""
            current_month = ""

            for i in range(len(lines)):
                line = lines[i].strip()
                if not line: continue

                # 1. 月・日の特定
                month_match = re.search(r'(\d{1,2})月,', line)
                month_en_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),', line)

                if month_match or month_en_match:
                    if month_match:
                        current_month = f"{month_match.group(1)}月"
                    else:
                        current_month = month_en_match.group(1)

                    date_num_match = re.search(r',\s*(\d{1,2})', line)
                    if date_num_match:
                        current_day = date_num_match.group(1)
                    elif i > 0 and lines[i-1].strip().isdigit():
                        current_day = lines[i-1].strip()
                    continue

                # 2. 予定の抽出ロジック（暁の時刻形式に対応）
                is_time_marker = (
                    line in ["終日", "All day"] or 
                    re.search(r'\d{1,2}(:\d{2})?\s*(am|pm)?', line.lower()) or
                    "–" in line or "—" in line
                )

                if current_day and is_time_marker:
                    details = []
                    for j in range(i + 1, min(i + 4, len(lines))):
                        detail = lines[j].strip()
                        if not detail or any(k in detail for k in ["表示", "Google", "詳細"]):
                            continue
                        if "月," in detail or re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),', detail):
                            break
                        if re.search(r'\d{1,2}(:\d{2})?\s*(am|pm)?', detail.lower()):
                            break
                        details.append(detail)
                    
                    if details:
                        full_detail = " / ".join(details)
                        
                        if current_month and current_day:
                            m_name = current_month
                            en_to_jp = {"Jan":"1月","Feb":"2月","Mar":"3月","Apr":"4月","May":"5月","Jun":"6月"}
                            if m_name in en_to_jp: m_name = en_to_jp[m_name]

                            boat_schedules.append({
                                "date": f"{m_name}{current_day}日",
                                "status": judge_status(full_detail),
                                "detail": full_detail
                            })

            unique_schedules = []
            seen = set()
            for s in boat_schedules:
                identifier = (s['date'], s['detail'])
                if identifier not in seen:
                    seen.add(identifier); unique_schedules.append(s)
            
            all_results[boat['name']] = {"data": unique_schedules}
            print(f"  ✅ {len(unique_schedules)}件抽出完了")

        driver.switch_to.default_content()
            
    except Exception as e:
        print(f"  💥 エラー: {boat['name']} ({str(e)})")

driver.quit()

# --- 保存処理（カッコの閉じ忘れを修正） ---
output = {
    "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS},
    "schedules": all_results
}
json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fishing_schedule.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)

print("\n💾 すべての処理が完了しました")
