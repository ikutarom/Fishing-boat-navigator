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
    {"name": "Winger", "url": "https://www.wingar.net/%E4%BA%88%E7%B4%84%E7%8A%B6%E6%B3%81", "official": "https://www.wingar.net/", "area": "唐津"}, 
    {"name": "GOD", "url": "https://www.god-fishing-boat.com/%E3%82%B9%E3%82%B1%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB/", "official": "https://www.god-fishing-boat.com/", "area": "姪浜"},
]

# --- 2. ブラウザ設定 ---
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1280,1024')
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def judge_status(content):
    """内容から記号を判定"""
    if any(k in content for k in ["満", "×", "済", "貸", "チャーター", "Full"]): return "×"
    if "残り" in content or "残" in content: return "△"
    return "○"

all_results = {}

try:
    for boat in BOATS:
        print(f"\n🚀 --- 【開始】 {boat['name']} ---")
        try:
            driver.get(boat['url'])
            time.sleep(15)

            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            print(f"  🔍 発見したiframeの数: {len(iframes)}")
            
            target_found = False
            for i, f in enumerate(iframes):
                try:
                    src = f.get_attribute("src") or ""
                    if "google.com/calendar" in src:
                        # 予定リスト形式(AGENDA)にURLを書き換えて直接ジャンプ
                        agenda_url = src.replace("mode=WEEK", "mode=AGENDA").replace("mode=MONTH", "mode=AGENDA")
                        if "mode=AGENDA" not in agenda_url:
                            agenda_url += "&mode=AGENDA"
                        
                        print(f"  🎯 リスト形式(AGENDA)で読み込み直します...")
                        driver.get(agenda_url)
                        time.sleep(10)
                        
                        body_text = driver.find_element(By.TAG_NAME, "body").text
                        print(f"  📄 取得テキスト(冒頭): {body_text[:120].replace(os.linesep, ' ')}")
                        
                        schedules = []
                        # 日付パターン: 「3月 12日」, 「3月12日」, 「Mar 12」, 「12 Mar」
                        date_pattern = r"(\d+月\s?\d+日|[A-Z][a-z]{2}\s\d+|\d+\s[A-Z][a-z]{2})"
                        lines = body_text.splitlines()

                        for idx, line in enumerate(lines):
                            match = re.search(date_pattern, line)
                            if match:
                                # 取得した日付を「M月D日」形式に極力寄せる（表示用）
                                date_raw = match.group(1)
                                detail = "空き"
                                
                                # 次の行に予定名があるかチェック
                                if idx + 1 < len(lines):
                                    next_line = lines[idx+1].strip()
                                    # 次の行が日付でも「件の予定」でもなければ詳細とする
                                    if next_line and not re.search(date_pattern, next_line) and "件の予定" not in next_line:
                                        detail = next_line
                                
                                schedules.append({
                                    "date": date_raw,
                                    "status": judge_status(detail),
                                    "detail": detail
                                })
                        
                        if schedules:
                            all_results[boat['name']] = {"data": schedules}
                            print(f"  ✅ 【成功】 {len(schedules)}日分のデータを取得")
                            target_found = True
                            break
                        
                        driver.back() # 元のページに戻る（次のiframe調査用）
                        time.sleep(2)

                except Exception as e:
                    print(f"  ⚠️ iframe[{i}] 処理中にエラー: {e}")
                    continue

            if not target_found:
                print(f"  ❌ 【失敗】 有効なデータが見つかりませんでした")

        except Exception as e:
            print(f"  💥 サイトアクセスエラー: {boat['name']} - {e}")

finally:
    driver.quit()

# 最終保存
output = {
    "boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS},
    "schedules": all_results
}

with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)

print("\n💾 JSON保存完了。Actionsの反映を待ちます。")