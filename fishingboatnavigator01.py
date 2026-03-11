import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

BOATS = [
    {
        "name": "M-selection",
        # URLの末尾に &mode=AGENDA を追加して「リスト表示」を強制します
        "url": "https://calendar.google.com/calendar/u/0/embed?src=bXNlbGVjdGlvbi5zaGlwQGdtYWlsLmNvbQ&ctz=Asia/Tokyo&hl=ja&mode=AGENDA",
        "area": "糸島",
        "official": "https://m-selection.com/"
    }
]

options = Options()
options.add_argument('--headless') # GitHubでは必須
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
# ヘッドレスだとバレないための設定
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def judge_status(content):
    if any(k in content for k in ["満船", "満", "チャーター", "予約済", "貸切", "×", "済"]): return "×"
    if re.search(r"残り([1-2])名", content): return "△"
    if any(k in content for k in ["空き", "募集", "予約可", "○", "名", "あと"]): return "○"
    return "×"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【開始】 {boat['name']} ---")
    try:
        driver.get(boat['url'])
        time.sleep(10) # リスト表示の読み込み待ち

        # リスト表示（AGENDAモード）はbody.textに綺麗に情報が並びます
        raw_text = driver.find_element(By.TAG_NAME, "body").text
        
        if raw_text:
            # ローカルで成功したパターンを使用（月 と 日 の間の半角スペースにも対応）
            date_pattern = r"(\d+月\s?\d+日)\s?\(.*?曜日\)"
            lines = raw_text.splitlines()
            schedules = []

            for i in range(len(lines)):
                match = re.search(date_pattern, lines[i])
                if match:
                    date_str = match.group(1).replace(" ", "") # "3月 11日" -> "3月11日"
                    found_event = False
                    # 日付行の後の数行をチェック
                    for j in range(1, 4):
                        if i + j < len(lines):
                            content = lines[i + j].strip()
                            if len(content) <= 2 or any(k in content for k in ["件の予定", "終日", "予定はありません", "Google", "カレンダー"]):
                                continue
                            
                            schedules.append({
                                "date": date_str,
                                "status": judge_status(content),
                                "detail": content
                            })
                            found_event = True
                            break
                    
                    if not found_event:
                        schedules.append({"date": date_str, "status": "○", "detail": "空き（予定なし）"})

            if schedules:
                all_results[boat['name']] = {"data": schedules}
                print(f"  ✅ {len(schedules)}件の予定を解析しました")
            else:
                print("  ⚠️ テキストは取得できましたが、日付パターンが見つかりませんでした")
        else:
            print("  ⚠️ body.text が空でした")

    except Exception as e:
        print(f"  💥 エラー: {str(e)}")

driver.quit()

# JSON保存
output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
