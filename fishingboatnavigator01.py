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
# 重要：画面を大きくして、カレンダー内の文字が省略されないようにする
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
        time.sleep(15) # サイト全体の読み込みをじっくり待つ

        # ページ内の全iframeをチェック（カレンダーURLの判定を緩める）
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        found_data = False
        
        for ifr in iframes:
            try:
                src = ifr.get_attribute("src") or ""
                # google以外にも「calendar」が含まれればチェック対象
                if "calendar" in src.lower() or "google.com" in src.lower():
                    driver.switch_to.frame(ifr)
                    time.sleep(10) # 枠内が描画されるのを待つ

                    # 【必殺】iframe内の全テキストを取得して解析
                    body_text = driver.find_element(By.TAG_NAME, "body").text
                    
                    # 予定を抽出するためのスキャナ
                    # 「日付」「予定名」「日付」「予定名」...という並び順を想定
                    schedules = []
                    lines = body_text.split('\n')
                    
                    last_date = ""
                    for line in lines:
                        line = line.strip()
                        if not line: continue
                        
                        # 「15」「15日」「3月15日」などの日付パターンを探す
                        # 月の指定がない場合は、現在の月を補完（簡易版）
                        date_match = re.search(r"(\d{1,2})月(\d{1,2})日", line)
                        day_only_match = re.match(r"^(\d{1,2})$", line) # 数字だけの行
                        
                        if date_match:
                            last_date = f"{date_match.group(1)}月{date_match.group(2)}日"
                        elif day_only_match:
                            # ひとまず今の月(3月)を付与
                            last_date = f"3月{day_only_match.group(1)}日"
                        else:
                            # 日付の後に来た文字は「予定」とみなす
                            if last_date and not line.isdigit() and len(line) > 1:
                                if "前月" in line or "翌月" in line or "曜日" in line: continue
                                
                                schedules.append({
                                    "date": last_date,
                                    "status": judge_status(line),
                                    "detail": line
                                })

                    if schedules:
                        all_results[boat['name']] = {"data": schedules}
                        print(f"  ✅ {len(schedules)}件のテキストを抽出成功")
                        found_data = True
                        driver.switch_to.default_content()
                        break
                    
                    driver.switch_to.default_content()
            except:
                driver.switch_to.default_content()
                continue
        
        if not found_data:
            print(f"  ⚠️ 予定が取得できませんでした")

    except Exception as e:
        print(f"  💥 エラー: {boat['name']}")

driver.quit()

output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
