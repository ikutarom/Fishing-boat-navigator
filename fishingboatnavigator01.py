import os
import time
import re
import json
import requests
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
        time.sleep(8)

        # 1. ページ内のiframeからGoogleカレンダーのソースURLを抽出
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        calendar_url = ""
        for ifr in iframes:
            src = ifr.get_attribute("src") or ""
            if "google.com/calendar/embed" in src:
                calendar_url = src
                break
        
        if not calendar_url:
            print(f"  ⚠️ カレンダーURLが見つかりません")
            continue

        print(f"  🎯 データソースURLを取得しました。直接解析します...")
        
        # 2. Seleniumではなく、requestsを使ってカレンダーのHTMLを直接取得
        # これにより、UI上の不要なラベルに邪魔されず、生データを取得できます
        response = requests.get(calendar_url)
        html_content = response.text

        # 3. 予定データの抽出
        # Googleカレンダーの生データに含まれる「[null,"予定名",null,null,null,"20260315",...]」のようなパターンを探す
        # 正規表現で「日付(YYYYMMDD形式)」と「予定名」のペアを力技で抜きます
        schedules = []
        
        # パターン: "予定名" と "YYYYMMDD" を含む構造を検索
        # ※Googleカレンダーの内部JavaScript変数(dataChunk)を解析対象にします
        found_items = re.findall(r'\[null,"([^"]+)",null,null,null,"(\d{8})"', html_content)
        
        if not found_items:
            # 別のデータ形式（新しい埋め込み形式）を検索
            found_items = re.findall(r'"([^"]+)","\d{8}",null,null,"(\d{8})"', html_content)

        for title, ymd in found_items:
            # タイトルが短すぎる数字だけ（日付ラベル）などは除外
            if title.isdigit() or len(title) < 2:
                continue
                
            month = int(ymd[4:6])
            day = int(ymd[6:8])
            date_str = f"{month}月{day}日"
            
            # 今月と来月のデータのみ対象にする（古いデータ除外）
            schedules.append({
                "date": date_str,
                "status": judge_status(title),
                "detail": title
            })

        if schedules:
            # 同一日のマージ処理
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
            print(f"  ✅ {len(unique_days)}件の予定を取得成功")
        else:
            print(f"  ❌ 有効な予定データが抽出できませんでした")

    except Exception as e:
        print(f"  💥 エラー: {boat['name']} ({str(e)})")

driver.quit()

output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
