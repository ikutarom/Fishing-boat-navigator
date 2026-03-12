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

# --- 1. 設定・準備 ---
try:
    from boats import BOATS
except ImportError:
    print("Error: boats.py が見つかりません。")
    exit(1)

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,2000') 
options.page_load_strategy = 'normal'
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(45)

def judge_status(content):
    if any(k in content for k in ["満船", "満", "予約済", "貸切", "×", "済", "Full", "完売", "締切", "チャーター", "🈵", "休"]): 
        return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか", "🈳", "名募集", "人募集", "様募集", "名空"]): 
        return "△"
    return "○"

MONTH_MAP = {
    "Jan": "1月", "Feb": "2月", "Mar": "3月", "Apr": "4月", "May": "5月", "Jun": "6月",
    "Jul": "7月", "Aug": "8月", "Sep": "9月", "Oct": "10月", "Nov": "11月", "Dec": "12月"
}

all_results = {}

# --- 2. メインループ ---
for boat in BOATS:
    print(f"\n🚀 --- 【解析開始】 {boat['name']} ---")
    boat_schedules = []
    
    try:
        target_url = boat['url']
        params = "&mode=AGENDA&weeks=14&hl=ja&ctz=Asia/Tokyo"
        target_url += params if "?" in target_url else "?" + params[1:]
        driver.get(target_url)
        
        # 💡 暁対策：初期待機を少し長めの12秒に設定
        time.sleep(12) 

        if len(driver.find_elements(By.TAG_NAME, "iframe")) > 0:
            driver.switch_to.frame(0)

        # 💡 暁以外の「40件の壁」がある船のみボタン操作を試行
        # 暁は予定が少ないため、ボタン操作をスキップして安定性を高めます
        if boat['name'] != "暁" and any(k in boat['name'] for k in ["優", "エルクルーズ", "Wingar", "GOD", "武蔵丸"]):
            for i in range(2): 
                try:
                    next_btn = driver.find_element(By.ID, "nextButton")
                    if next_btn.is_displayed():
                        driver.execute_script("arguments[0].click();", next_btn)
                        print(f"  👆 {boat['name']}: 次の期間(Page {i+1})を読み込み中...")
                        time.sleep(5) # 読み込み待ちを4秒から5秒へ
                except:
                    break

        # 💡 解析直前の最終待機（ここで暁の遅延読み込みを確実にキャッチする）
        time.sleep(3)
        raw_text = driver.execute_script("return document.body.innerText;")
        
        if raw_text:
            lines = raw_text.splitlines()
            current_day = ""
            current_month = ""

            for i in range(len(lines)):
                line = lines[i].strip()
                if not line: continue

                m_jp = re.search(r'(\d{1,2})月,', line)
                m_en = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),', line)

                if m_jp or m_en:
                    current_month = f"{m_jp.group(1)}月" if m_jp else MONTH_MAP[m_en.group(1)]
                    d_match = re.search(r',\s*(\d{1,2})', line)
                    if d_match:
                        current_day = d_match.group(1)
                    elif i > 0 and lines[i-1].strip().isdigit():
                        current_day = lines[i-1].strip()
                    continue

                time_unit_regex = r'\d{1,2}(:\d{2})?\s*(am|pm)?'
                is_time_marker = (
                    line in ["終日", "All day"] or 
                    re.match(f"^{time_unit_regex}$", line.lower()) or
                    "–" in line or "—" in line
                )

                if current_day and is_time_marker:
                    details = []
                    for j in range(i + 1, min(i + 5, len(lines))):
                        detail = lines[j].strip()
                        # ゴミ掃除（暁の "(No title)" も除外対象）
                        if not detail or detail == "カレンダー" or "(No title)" in detail: continue
                        if any(k in detail for k in ["表示", "Google", "詳細", "カレンダー:", "承諾", "辞退", "未定", "出船スケジュール"]):
                            continue
                        if re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', detail):
                            continue
                        if "月," in detail or re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),', detail): break
                        if detail in ["終日", "All day"] or re.match(f"^{time_unit_regex}$", detail.lower()): break
                        
                        details.append(detail)
                    
                    if details:
                        full_detail = " / ".join(details)
                        if current_month and current_day:
                            boat_schedules.append({
                                "date": f"{current_month}{current_day}日",
                                "status": judge_status(full_detail),
                                "detail": full_detail
                            })

            unique_schedules = []
            for s in boat_schedules:
                is_duplicate = False
                for existing in unique_schedules:
                    if existing['date'] == s['date']:
                        if s['detail'] in existing['detail'] or existing['detail'] in s['detail']:
                            is_duplicate = True
                            if len(s['detail']) > len(existing['detail']):
                                existing['detail'] = s['detail']
                                existing['status'] = s['status']
                            break
                if not is_duplicate:
                    unique_schedules.append(s)
            
            all_results[boat['name']] = {"data": unique_schedules}
            print(f"  ✅ {len(unique_schedules)}件抽出完了")

        driver.switch_to.default_content()
            
    except Exception as e:
        print(f"  💥 エラー: {boat['name']} ({str(e)})")

driver.quit()

# --- 3. 保存処理 ---
output = {
    "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS},
    "schedules": all_results
}
json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fishing_schedule.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)

print("\n💾 処理が完了しました。")
