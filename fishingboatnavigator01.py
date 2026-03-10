import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- 1. 巡回リスト ---
BOATS = [
    {"name": "M-selection", "url": "https://m-selection.com/", "official": "https://m-selection.com/", "area": "糸島"},
    {"name": "もんじゃ丸", "url": "https://www.monjamaru.com/118935.html", "official": "https://www.monjamaru.com/", "area": "姪浜"},
    {"name": "ピスケス", "url": "https://pisces-gou.jimdofree.com/", "official": "https://pisces-gou.jimdofree.com/", "area": "姪浜"},
    {"name": "武蔵丸", "url": "https://www.musashimaru.com/#sch", "official": "https://www.musashimaru.com/", "area": "博多"}, 
    {"name": "優", "url": "http://yu-fishing.jp/", "official": "http://yu-fishing.jp/", "area": "博多"}, 
    {"name": "エルクルーズ", "url": "https://www.l-cruise.com/schedule", "official": "https://www.l-cruise.com/", "area": "箱崎"}, 
    {"name": "Wingar", "url": "https://www.wingar.net/%E4%BA%88%E7%B4%84%E7%8A%B6%E6%B3%81", "official": "https://www.wingar.net/", "area": "唐津"}, 
    {"name": "GOD", "url": "https://www.god-fishing-boat.com/%E3%82%B9%E3%82%B1%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB/", "official": "https://www.god-fishing-boat.com/", "area": "姪浜"},
]

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1280,1024')
# ★重要：日本語設定を強制する
options.add_argument('--lang=ja-JP')
options.add_experimental_option('prefs', {'intl.accept_languages': 'ja'})
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def judge_status(content):
    if any(k in content for k in ["満", "×", "済", "貸", "チャーター", "Full", "予約有"]): return "×"
    if any(k in content for k in ["残り", "残", "△"]): return "△"
    return "○"

all_results = {}

try:
    for boat in BOATS:
        print(f"\n🚀 --- 【開始】 {boat['name']} ---")
        try:
            driver.get(boat['url'])
            time.sleep(15)

            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            target_found = False
            
            for i, f in enumerate(iframes):
                src = f.get_attribute("src") or ""
                if "google.com/calendar" in src:
                    # AGENDA形式を強制
                    agenda_url = src.replace("mode=WEEK", "mode=AGENDA").replace("mode=MONTH", "mode=AGENDA")
                    if "mode=AGENDA" not in agenda_url:
                        agenda_url += "&mode=AGENDA"
                    # さらに日本語を強制するパラメータを追加
                    agenda_url += "&hl=ja"
                    
                    print(f"  🎯 日本語・リスト形式で読み込み中...")
                    driver.get(agenda_url)
                    time.sleep(10)
                    
                    body_text = driver.find_element(By.TAG_NAME, "body").text
                    lines = body_text.splitlines()
                    
                    schedules = []
                    # 日本語日付パターン: 「3月12日(木)」などの形式を狙う
                    date_pattern = r"(\d+月\s?\d+日)"
                    # ゴミとして除外するワード
                    trash_words = ["Schedule", "Look for more", "All day", "Calendar", "Accepted", "前へ", "次へ", "今日", "印刷"]

                    for idx, line in enumerate(lines):
                        match = re.search(date_pattern, line)
                        if match:
                            date_str = match.group(1).replace(" ", "")
                            detail = "空き"
                            
                            if idx + 1 < len(lines):
                                next_line = lines[idx+1].strip()
                                # ゴミワードでも日付でもない場合に詳細として採用
                                if next_line and not any(t in next_line for t in trash_words) and not re.search(r"\d+月", next_line):
                                    detail = next_line
                                
                            schedules.append({
                                "date": date_str,
                                "status": judge_status(detail),
                                "detail": detail
                            })
                    
                    if schedules:
                        all_results[boat['name']] = {"data": schedules}
                        print(f"  ✅ 【成功】 {len(schedules)}日分のデータを取得")
                        target_found = True
                        break

        except Exception as e:
            print(f"  💥 エラー: {boat['name']} - {e}")

finally:
    driver.quit()

output = {
    "boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS},
    "schedules": all_results
}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)