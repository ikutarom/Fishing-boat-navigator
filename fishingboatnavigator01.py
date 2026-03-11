import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# テスト用にM-selectionの直接URLを使用
BOATS = [
    {
        "name": "M-selection",
        "url": "https://calendar.google.com/calendar/u/0/embed?height=600&wkst=1&bgcolor=%23ffffff&ctz=Asia/Tokyo&showTitle=0&showNav=1&showDate=0&showPrint=0&showTabs=0&showCalendars=0&showTz=0&src=bXNlbGVjdGlvbi5zaGlwQGdtYWlsLmNvbQ&color=%23039BE5",
        "area": "糸島",
        "official": "https://m-selection.com/"
    }
]

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
        time.sleep(8) # 描画を待機

        schedules = []
        # グリッド内の「予定項目（role=button）」のみをターゲットにする
        # これによりヘッダーやボタンなどのゴミを排除
        elements = driver.find_elements(By.XPATH, "//div[@role='button' and @aria-label]")
        
        for el in elements:
            label = el.get_attribute("aria-label")
            if not label: continue

            # 除外：カレンダーの基本操作系ラベル
            ignore_list = ["今日", "Today", "次", "前", "印刷", "設定", "カレンダー", "Calendar", "Month", "Week"]
            if any(ignore in label for ignore in ignore_list):
                continue
            
            # 日付の抽出
            date_found = None
            m_ja = re.search(r"(\d{1,2})月(\d{1,2})日", label)
            if m_ja:
                date_found = f"{m_ja.group(1)}月{m_ja.group(2)}日"
            else:
                # 英語形式 (March 1) を探し、月を数字に置換
                months = ["January","February","March","April","May","June","July","August","September","October","November","December"]
                for i, m_name in enumerate(months):
                    if m_name in label:
                        d_match = re.search(rf"{m_name}\s+(\d{{1,2}})", label)
                        if d_match:
                            date_found = f"{i+1}月{d_match.group(1)}日"
                            break

            if date_found:
                # 予定の詳細は、aria-labelの最初のカンマより前の部分
                # 例: "鰆　ミノー　ブレード, 2026年3月1日" -> "鰆　ミノー　ブレード"
                detail = label.split(',')[0].strip()
                
                # detailが日付そのもの（例: 3月1日）なら予定なしとみなす
                if detail == date_found or re.match(r"^\d+$", detail):
                    continue

                schedules.append({
                    "date": date_found,
                    "status": judge_status(detail),
                    "detail": detail
                })

        if schedules:
            unique_days = {}
            for s in schedules:
                d = s["date"]
                # 重複排除とマージ
                if d not in unique_days:
                    unique_days[d] = s
                else:
                    if s['detail'] not in unique_days[d]['detail']:
                        unique_days[d]["detail"] += f" / {s['detail']}"
                        unique_days[d]["status"] = judge_status(unique_days[d]["detail"])
            
            # 日付順にソートして格納
            sorted_data = sorted(unique_days.values(), key=lambda x: int(re.search(r'\d+', x['date']).group()))
            all_results[boat['name']] = {"data": sorted_data}
            print(f"  ✅ {len(unique_days)}件の予定を取得成功")
        else:
            print("  ⚠️ 予定が見つかりませんでした")

    except Exception as e:
        print(f"  💥 エラー: {boat['name']}")

driver.quit()

# JSON書き出し
output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
