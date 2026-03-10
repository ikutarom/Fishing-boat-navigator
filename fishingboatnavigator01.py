import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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
options.add_argument('--window-size=1920,1080')
options.add_argument('--lang=ja-JP')
options.add_experimental_option('prefs', {'intl.accept_languages': 'ja'})

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def judge_status(content):
    if any(k in content for k in ["満", "×", "済", "貸", "チャーター", "Full", "予約有", "締切"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか"]): return "△"
    return "○"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【開始】 {boat['name']} ---")
    try:
        driver.get(boat['url'])
        
        # iframeが見つかるまで待機
        wait = WebDriverWait(driver, 20)
        iframes = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "iframe")))
        
        target_iframe = None
        for ifr in iframes:
            src = ifr.get_attribute("src") or ""
            if "google.com/calendar" in src:
                target_iframe = ifr
                break
        
        if target_iframe:
            print(f"  🎯 Googleカレンダーを発見。切り替えます...")
            driver.switch_to.frame(target_iframe)
            
            # カレンダーの中身（日付など）が表示されるまで待つ
            time.sleep(10) 
            
            body_text = driver.find_element(By.TAG_NAME, "body").text
            lines = body_text.splitlines()
            
            schedules = []
            temp_date = None
            noise_words = ["これより後の予定を表示", "印刷", "今日", "前へ", "次へ", "予定はありません", "Google"]

            for line in lines:
                line = line.strip()
                if not line or any(nw in line for nw in noise_words):
                    continue
                
                # 日付の抽出 (3月12日 や 3/12 など)
                date_match = re.search(r"(\d+月\d+日|\d+/\d+)", line)
                
                if date_match:
                    temp_date = date_match.group(1)
                elif temp_date:
                    # 日付の後に続く行を予定として取得
                    schedules.append({
                        "date": temp_date,
                        "status": judge_status(line),
                        "detail": line
                    })
                    temp_date = None
            
            if schedules:
                all_results[boat['name']] = {"data": schedules}
                print(f"  ✅ {len(schedules)}日分のデータを取得")
            else:
                print(f"  ❌ カレンダーは見つかりましたが、予定が空、または読み取れませんでした")
            
            driver.switch_to.default_content()
        else:
            print(f"  ⚠️ Googleカレンダーのiframeが見つかりませんでした")

    except Exception as e:
        print(f"  💥 エラー発生: {str(e)[:100]}")
        driver.switch_to.default_content()

driver.quit()

output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")