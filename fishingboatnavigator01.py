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
    # 暁の絵文字（🈵, 🈳）や「募集中」にも対応できるよう拡張
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

            # 時刻判定用の正規表現（5am, 5:30am, 12:30, 5am – 3pm などにマッチ）
            # \d{1,2}(:\d{2})?\s*(am|pm)?  => 時刻部分
            # [\-–—] => 各種ハイフン・ダッシュ記号
            time_unit = r'\d{1,2}(:\d{2})?\s*(am|pm)?'
            time_pattern = f"({time_unit}(\s*[\-–—]\s*{time_unit})?)"

            for i in range(len(lines)):
                line = lines[i].strip()
                if not line: continue

                # 1. 月の特定 ("3月," または "Mar," など)
                month_match = re.search(r'(\d{1,2})月,', line)
                # 暁などで英語表記(Mar, Apr)になっている場合への備え
                month_en_match = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),', line)

                if month_match or month_en_match:
                    if month_match:
                        current_month = f"{month_match.group(1)}月"
                    else:
                        # 英語表記を日本語に読み替え（暫定的にそのまま保持、必要なら変換マップ追加）
                        current_month = month_en_match.group(1) 
                    
                    # 日付（数値）を探す
                    date_num_match = re.search(r',\s*(\d{1,2})', line)
                    if date_num_match:
                        current_day = date_num_match.group(1)
                    elif i > 0 and lines[i-1].strip().isdigit():
                        current_day = lines[i-1].strip()
                    continue

                # 2. 予定の抽出ロジック（強化版）
                is_time_marker = (
                    line in ["終日", "All day"] or 
                    re.match(f"^{time_pattern}$", line.lower())
                )

                if current_day and is_time_marker:
                    # 💡 暁対策：時刻の後に続く「予定名」と「空き情報」を最大2行拾う
                    potential_details = []
                    # 時刻の次の行から最大3行先までスキャン
                    for j in range(i + 1, min(i + 4, len(lines))):
                        detail = lines[j].strip()
                        # 次の時刻目印や日付、システム文字が来たらストップ
                        if not detail or any(k in detail for k in ["表示", "Google", "カレンダー", "詳細"]):
                            continue
                        if re.match(f"^{time_pattern}$", detail.lower()) or "月," in detail:
                            break
                        potential_details.append(detail)
                    
                    if potential_details:
                        # 「Bジギング便 / 残り3名募集中」のように結合して保存
                        combined_detail = " / ".join(potential_details)
                        
                        if current_month and current_day:
                            boat_schedules.append({
                                "date": f"{current_month}{current_day}日",
                                "status": judge_status(combined_detail),
                                "detail": combined_detail
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

output = {
    "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS},
    "schedules": all_results
}
json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fishing_schedule.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)

print("\n💾 すべての処理が完了しました")
