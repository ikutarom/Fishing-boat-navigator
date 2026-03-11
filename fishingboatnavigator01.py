import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# BOATSの定義（M-selectionだけテスト用に直接URLを差し替えてみてください）
# 本来は boats.py 側のURLを Google Calendar の Embed URL に書き換えるのがベストです
BOATS = [
    {
        "name": "M-selection",
        "url": "https://calendar.google.com/calendar/u/0/embed?height=600&wkst=1&bgcolor=%23ffffff&ctz=Asia/Tokyo&showTitle=0&showNav=1&showDate=0&showPrint=0&showTabs=0&showCalendars=0&showTz=0&src=bXNlbGVjdGlvbi5zaGlwQGdtYWlsLmNvbQ&color=%23039BE5",
        "area": "糸島",
        "official": "https://m-selection.com/"
    },
    # 他の船も同様にカレンダーURLが分かれば差し替え可能
]

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--lang=ja-JP')
options.add_argument('--window-size=1200,1000')

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
        # 直接GoogleカレンダーのURLを開く（iframeを介さないので確実）
        driver.get(boat['url'])
        time.sleep(5) # 埋め込み専用ページは軽いので5秒で十分

        schedules = []
        # 予定（イベント）の要素を抽出
        # 埋め込みカレンダーでは div.rb-n や [role='button'] が使われる
        elements = driver.find_elements(By.XPATH, "//*[@aria-label]")
        
        for el in elements:
            label = el.get_attribute("aria-label")
            if not label or "Calendar" in label or "Google" in label: continue

            # 予定名(title)と日付を分離するロジック
            # 例: "鰆　ミノー　ブレード, Sunday, March 1, 2026"
            parts = label.split(',')
            if len(parts) < 2: continue
            
            title = parts[0].strip()
            
            # 日付の抽出 (日本語・英語両対応)
            date_found = None
            m_ja = re.search(r"(\d{1,2})月(\d{1,2})日", label)
            if m_ja:
                date_found = f"{m_ja.group(1)}月{m_ja.group(2)}日"
            else:
                # 英語形式 (March 1)
                months = ["January","February","March","April","May","June","July","August","September","October","November","December"]
                for i, m_name in enumerate(months):
                    if m_name in label:
                        d_match = re.search(rf"{m_name}\s+(\d{{1,2}})", label)
                        if d_match:
                            date_found = f"{i+1}月{d_match.group(1)}日"
                            break

            if date_found and title and "event" not in title.lower():
                schedules.append({
                    "date": date_found,
                    "status": judge_status(title),
                    "detail": title
                })

        if schedules:
            unique_days = {}
            for s in schedules:
                d = s["date"]
                if d not in unique_days:
                    unique_days[d] = s
                else:
                    if s['detail'] not in unique_days[d]['detail']:
                        unique_days[d]["detail"] += f" / {s['detail']}"
                    unique_days[d]["status"] = judge_status(unique_days[d]["detail"])
            
            all_results[boat['name']] = {"data": list(unique_days.values())}
            print(f"  ✅ {len(unique_days)}日分の予定を取得成功！")
        else:
            print("  ⚠️ 予定が見つかりませんでした")

    except Exception as e:
        print(f"  💥 エラー: {boat['name']}")

driver.quit()

# JSON保存処理
output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")

