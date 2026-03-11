import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# 日本語表示を強制するパラメータ hl=ja を追加
BOATS = [
    {
        "name": "M-selection",
        "url": "https://calendar.google.com/calendar/u/0/embed?src=bXNlbGVjdGlvbi5zaGlwQGdtYWlsLmNvbQ&ctz=Asia/Tokyo&hl=ja",
        "area": "糸島",
        "official": "https://m-selection.com/"
    }
]

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

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
        time.sleep(15) # 描画完了まで長めに待機

        schedules = []
        
        # カレンダー内の「すべての要素」から aria-label を持つものを探す
        # これが最も確実なデータ源
        elements = driver.find_elements(By.XPATH, "//*[@aria-label]")
        
        for el in elements:
            label = el.get_attribute("aria-label")
            if not label: continue
            
            # 「○月○日」という日付が含まれているかチェック
            date_match = re.search(r'(\d{1,2})月(\d{1,2})日', label)
            if date_match:
                date_str = f"{date_match.group(1)}月{date_match.group(2)}日"
                
                # ラベルから日付を消した残りを「予定名」とする
                # 例: "鰆ミノー, 2026年3月1日" -> "鰆ミノー"
                clean_label = label.split(',')[0].replace(date_str, "").strip()
                
                # 余計な記号や曜日を削除
                clean_label = re.sub(r'[\(\)（）\s]', '', clean_label)
                
                # 「今日」「カレンダー」「○件の予定」などは除外
                if any(k in clean_label for k in ["今日", "印刷", "Google", "カレンダー", "予定あり", "件のイベント", "event"]):
                    continue
                
                # 有効な文字列が残れば採用
                if len(clean_label) >= 2 and not clean_label.isdigit():
                    schedules.append({
                        "date": date_str,
                        "status": judge_status(clean_label),
                        "detail": clean_label
                    })

        if schedules:
            # 同じ日の同じ予定を統合
            unique_data = {}
            for s in schedules:
                key = (s['date'], s['detail'])
                unique_data[key] = s
            
            # 日付順に並び替え
            sorted_data = sorted(unique_data.values(), key=lambda x: [int(d) for d in re.findall(r'\d+', x['date'])])
            
            all_results[boat['name']] = {"data": sorted_data}
            print(f"  ✅ {len(sorted_data)}件の予定を抽出しました")
        else:
            # 最終手段：デバッグ用に取得したテキストの一部を表示
            print("  ⚠️ 予定が見つかりません。")

    except Exception as e:
        print(f"  💥 エラー: {str(e)}")

driver.quit()

output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
