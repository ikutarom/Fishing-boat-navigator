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

# (judge_status 関数は以前と同じ)
def judge_status(content):
    if any(k in content for k in ["満船", "満", "予約済", "貸切", "×", "済", "Full", "完売", "締切", "チャーター", "🈵"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか", "🈳", "募集中"]): return "△"
    return "○"

# 英語月名を数字に変換する辞書
MONTH_MAP = {'Jan': '1', 'Feb': '2', 'Mar': '3', 'Apr': '4', 'May': '5', 'Jun': '6',
             'Jul': '7', 'Aug': '8', 'Sep': '9', 'Oct': '10', 'Nov': '11', 'Dec': '12'}

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,2000')
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

all_results = {}

# boats.py の読み込み
try: from boats import BOATS
except: exit(1)

for boat in BOATS:
    print(f"\n🚀 --- 【解析開始】 {boat['name']} ---")
    boat_schedules = []
    
    try:
        # 💡 URLのクリーニング（暁対策：/u/0/ を除去し、安定した公開URLへ）
        clean_url = boat['url'].replace("/u/0/", "/")
        params = "&mode=AGENDA&weeks=14&hl=ja&ctz=Asia/Tokyo"
        target_url = clean_url + (params if "?" in clean_url else "?" + params[1:])
        
        driver.get(target_url)
        time.sleep(8) # 暁の描画待機

        # iframeの中へ（Googleカレンダーは必ずiframe内に本体がある）
        if len(driver.find_elements(By.TAG_NAME, "iframe")) > 0:
            driver.switch_to.frame(0)

        raw_text = driver.execute_script("return document.body.innerText;")
        
        if raw_text:
            lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            current_month = ""
            current_day = ""

            for i in range(len(lines)):
                line = lines[i]

                # 1. 日付判定 (例: "Mar, Wed" または "3月, 11")
                m_jp = re.search(r'(\d{1,2})月,', line)
                m_en = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),', line)

                if m_jp:
                    current_month = m_jp.group(1)
                    d_match = re.search(r',\s*(\d{1,2})', line)
                    if d_match: current_day = d_match.group(1)
                elif m_en:
                    current_month = MONTH_MAP[m_en.group(1)]
                    # 💡 暁スタイル：日付(11)が「前」の行にある
                    if i > 0 and lines[i-1].isdigit():
                        current_day = lines[i-1]
                
                # 2. 予定判定 (時刻形式をトリガーにする)
                # 5am, 5:30am, 12:30, 5am – 3pm など
                time_unit = r'\d{1,2}(:\d{2})?\s*(am|pm)?'
                time_pattern = f"({time_unit}(\s*[–\-]\s*{time_unit})?)"
                
                if current_day and (line in ["All day", "終日"] or re.match(time_pattern, line.lower())):
                    # 💡 暁対策：時刻の後の「予定名」と「空き情報」を最大2行拾う
                    details = []
                    for j in range(i + 1, min(i + 4, len(lines))):
                        # 次の日付や時刻が来たら終了
                        if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|月),', lines[j]): break
                        if re.match(time_pattern, lines[j].lower()): break
                        if any(k in lines[j] for k in ["表示", "Google"]): continue
                        details.append(lines[j])
                    
                    if details:
                        full_detail = " / ".join(details)
                        boat_schedules.append({
                            "date": f"{current_month}月{current_day}日",
                            "status": judge_status(full_detail),
                            "detail": full_detail
                        })

            all_results[boat['name']] = {"data": boat_schedules}
            print(f"  ✅ {len(boat_schedules)}件抽出完了")

    except Exception as e:
        print(f"  💥 エラー: {boat['name']} ({str(e)})")

driver.quit()

# (JSON保存処理は前回と同じ)
