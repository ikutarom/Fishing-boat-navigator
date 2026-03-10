import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- 1. 巡回リスト（URLを最新の成功パターンに修正） ---
BOATS = [
    {"name": "M-selection", "url": "https://m-selection.com/", "official": "https://m-selection.com/", "area": "糸島"},
    {"name": "もんじゃ丸", "url": "https://www.monjamaru.com/118935.html", "official": "https://www.monjamaru.com/", "area": "姪浜"},
    {"name": "ピスケス", "url": "https://pisces-gou.jimdofree.com/", "official": "https://pisces-gou.jimdofree.com/", "area": "姪浜"},
    {"name": "武蔵丸", "url": "https://www.musashimaru.com/#sch", "official": "https://www.musashimaru.com/", "area": "博多"},
    # 他の船も必要に応じてURLをカレンダーページに微調整してください
]

# --- 2. ブラウザ設定 ---
options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def judge_status(content):
    if any(k in content for k in ["満船", "満", "貸切", "×", "予約済", "チャーター"]): return "×"
    if "残り" in content and re.search(r"[1-2]名", content): return "△"
    if any(k in content for k in ["空き", "募集", "◎", "○", "名", "予約可"]): return "○"
    return "×"

all_results = {}

try:
    for boat in BOATS:
        print(f"--- {boat['name']} を取得中... ---")
        driver.get(boat['url'])
        time.sleep(12) # サーバー用に待ち時間を長めに（重要！）

        target_iframe = None
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        
        for f in iframes:
            try:
                src = (f.get_attribute("src") or "").lower()
                # 判定条件をさらに広げる
                if any(k in src for k in ["calendar", "google", "jimdo", "embed"]):
                    target_iframe = f
                    break
            except:
                continue
        
        # iframeが見つかった場合の処理
        if target_iframe:
            driver.switch_to.frame(target_iframe)
            time.sleep(3)
            
            # 再帰的に奥のiframeを探す（ピスケス対策）
            for _ in range(2):
                inner = driver.find_elements(By.TAG_NAME, "iframe")
                if inner:
                    driver.switch_to.frame(inner[0])
                    time.sleep(2)
            
            try:
                raw_text = driver.find_element(By.TAG_NAME, "body").text
                date_pattern = r"(\d+月 \d+日) \(.*?曜日\)"
                lines = raw_text.splitlines()
                schedules = []

                for i in range(len(lines)):
                    match = re.search(date_pattern, lines[i])
                    if match:
                        date_str = match.group(1)
                        found_event = False
                        for j in range(1, 5):
                            if i + j < len(lines):
                                content = lines[i + j].strip()
                                if len(content) <= 2 or any(k in content for k in ["件の予定", "終日", "予定はありません", "Google", "前へ", "次へ"]):
                                    continue
                                schedules.append({"date": date_str, "status": judge_status(content), "detail": content})
                                found_event = True
                                break
                        if not found_event:
                            schedules.append({"date": date_str, "status": "○", "detail": "空き"})
                
                if schedules:
                    all_results[boat['name']] = {"data": schedules}
                    print(f"-> {boat['name']} 完了: {len(schedules)}日分")
            except:
                print(f"-> {boat['name']} テキスト解析に失敗")
            
            driver.switch_to.default_content()
        else:
            print(f"-> {boat['name']} カレンダーが見つかりませんでした")

finally:
    driver.quit()

# 保存
output_data = {
    "boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS},
    "schedules": all_results
}

with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=4)