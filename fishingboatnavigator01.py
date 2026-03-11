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

# 別ファイルから読み込み
try:
    from boats import BOATS
except ImportError:
    print("Error: boats.py not found.")
    exit(1)

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
        wait = WebDriverWait(driver, 20)
        
        # iframeが1つ以上現れるのを待つ
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        
        target_iframe = None
        for ifr in iframes:
            src = ifr.get_attribute("src") or ""
            if "google.com/calendar" in src:
                target_iframe = ifr
                break
        
        if target_iframe:
            print(f"  🎯 Googleカレンダーを発見。切り替えます...")
            driver.switch_to.frame(target_iframe)
            
            # 【重要】カレンダー内の特定の要素（日付や予定を表示するクラス）が出るまで待機
            try:
                # 予定リストの行(クラス名: event)またはカレンダー全体が表示されるのを待つ
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                # Googleカレンダー特有の描画時間を考慮してさらに少し待つ
                time.sleep(7)
                
                body_text = driver.find_element(By.TAG_NAME, "body").text
                # デバッグ用：取得文字数を出力
                print(f"  📄 取得文字数: {len(body_text)}字")
                
                lines = body_text.splitlines()
                schedules = []
                temp_date = None
                noise_words = ["これより後の予定を表示", "印刷", "今日", "前へ", "次へ", "予定はありません", "Google"]

                for line in lines:
                    line = line.strip()
                    if not line or any(nw in line for nw in noise_words):
                        continue
                    
                    # 日付の抽出
                    date_match = re.search(r"(\d+月\d+日|\d+/\d+)", line)
                    
                    if date_match:
                        temp_date = date_match.group(1)
                    elif temp_date:
                        schedules.append({
                            "date": temp_date,
                            "status": judge_status(line),
                            "detail": line
                        })
                        temp_date = None # 1日付1予定でリセット
                
                if schedules:
                    all_results[boat['name']] = {"data": schedules}
                    print(f"  ✅ {len(schedules)}日分のデータを取得")
                else:
                    # 取得失敗時のテキストを少し表示して原因を探る
                    print(f"  ❌ 予定が読み取れません。テキスト断片: {body_text[:50]}...")
            
            finally:
                driver.switch_to.default_content()
        else:
            print(f"  ⚠️ Googleカレンダーのiframeが見つかりませんでした")

    except Exception as e:
        print(f"  💥 エラー発生: {str(e)[:100]}")
        # フレーム内にいた場合は外に戻す
        try: driver.switch_to.default_content()
        except: pass

driver.quit()

output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
