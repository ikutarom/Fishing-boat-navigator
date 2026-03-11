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
options.page_load_strategy = 'normal' # 暁対策：完全に読み込むまで待つ設定に変更
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.set_page_load_timeout(40)

def judge_status(content):
    if any(k in content for k in ["チャーター可", "チャーター募", "チャーターOK"]): return "○"
    if any(k in content for k in ["満船", "満", "予約済", "貸切", "×", "済", "Full", "完売", "締切", "チャーター"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか"]): return "△"
    return "○"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【解析開始】 {boat['name']} ---")
    boat_schedules = []
    
    try:
        target_url = boat['url']
        # パラメータの補強（タイムゾーンと表示期間をさらに厳格に）
        params = "&mode=AGENDA&weeks=14&hl=ja&ctz=Asia/Tokyo"
        if "?" in target_url:
            target_url += params
        else:
            target_url += "?" + params[1:]
            
        driver.get(target_url)

        # 💡 暁/優 対策：最大30秒、2秒おきに中身をチェック
        raw_text = ""
        found = False
        for i in range(15):
            time.sleep(2)
            raw_text = driver.execute_script("return document.body.innerText;")
            # 「月,」という文字はAGENDAモードの日付見出しに必ず含まれる
            if "月," in raw_text:
                print(f"  💡 描画を確認しました ({i*2+2}秒経過)")
                found = True
                break
        
        if not found:
            print(f"  ⚠️ カレンダーの描画が確認できませんでした。取得できた文字数: {len(raw_text)}")

        if raw_text:
            lines = raw_text.splitlines()
            current_day = ""
            current_month = ""

            for i in range(len(lines)):
                line = lines[i].strip()
                if not line: continue

                # 日付の特定（正規表現を少し柔軟に）
                month_match = re.search(r'(\d{1,2})月,', line)
                if month_match:
                    current_month = f"{month_match.group(1)}月"
                    if i > 0:
                        prev_line = lines[i-1].strip()
                        if prev_line.isdigit():
                            current_day = prev_line
                    continue

                # 予定の抽出
                if current_day and (line == "終日" or re.match(r'\d{2}:\d{2}', line)):
                    if i + 1 < len(lines):
                        detail = lines[i+1].strip()
                        if any(k in detail for k in ["カレンダー:", "フィードバック", "表示", "詳細を表示"]): continue
                        
                        if current_month and current_day:
                            boat_schedules.append({
                                "date": f"{current_month}{current_day}日",
                                "status": judge_status(detail),
                                "detail": detail
                            })

            unique_schedules = []
            seen = set()
            for s in boat_schedules:
                identifier = (s['date'], s['detail'])
                if identifier not in seen:
                    seen.add(identifier); unique_schedules.append(s)
            
            all_results[boat['name']] = {"data": unique_schedules}
            print(f"  ✅ {len(unique_schedules)}件抽出完了")
            
    except Exception as e:
        print(f"  💥 エラー: {boat['name']} ({str(e)})")

driver.quit()

# 実行時刻を付けて保存
output = {
    "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS},
    "schedules": all_results
}

json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fishing_schedule.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)

print(f"\n💾 保存完了: {json_path}")
