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
options.set_capability("goog:loggingPrefs", {"performance": "ALL"}) 

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
        time.sleep(10) # サイト自体の読み込み待ち

        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        target_iframe = None
        for ifr in iframes:
            try:
                src = ifr.get_attribute("src") or ""
                if "google.com/calendar" in src:
                    target_iframe = ifr
                    break
            except: continue
        
        if target_iframe:
            print(f"  🎯 Googleカレンダーを発見。")
            driver.switch_to.frame(target_iframe)
            time.sleep(8) # カレンダー描画待ち
            
            body_element = driver.find_element(By.TAG_NAME, "body")
            full_text = body_element.text
            print(f"  📄 取得文字数: {len(full_text)}字")
            
            schedules = []
            
            # 1. リスト形式(AGENDA)の解析パターン
            # 「3月12日」の後に続く行を拾う
            lines = full_text.splitlines()
            for i, line in enumerate(lines):
                date_m = re.search(r"(\d+月\d+日)", line)
                if date_m and i + 1 < len(lines):
                    date_str = date_m.group(1)
                    detail = lines[i+1].strip()
                    if detail and not re.search(r"(\d+月\d+日|今日|印刷|Google)", detail):
                        schedules.append({"date": date_str, "status": judge_status(detail), "detail": detail})

            # 2. カレンダー形式(MONTH)の解析パターン（1個も取れなかった場合の予備）
            if not schedules:
                # 「12予定あり」や「12×」のような並びを探す
                # 数字(1〜31)の直後に特定の文字がある場合を抽出
                month_match = re.search(r"(\d+)月", full_text)
                target_month = month_match.group(1) if month_match else "3" # デフォルト3月
                
                # 数字と予定が混在するテキストから抽出を試みる
                items = re.findall(r"(\d+)\n([^\n]+)", full_text)
                for day, detail in items:
                    if 1 <= int(day) <= 31 and len(detail) > 1:
                        if not any(x in detail for x in ["日月火水木金土", "2026"]):
                            date_str = f"{target_month}月{day}日"
                            schedules.append({"date": date_str, "status": judge_status(detail), "detail": detail})

            if schedules:
                # 重複削除
                unique_schedules = list({v['date']: v for v in schedules}.values())
                all_results[boat['name']] = {"data": unique_schedules}
                print(f"  ✅ {len(unique_schedules)}日分のデータを取得")
            else:
                print(f"  ❌ 予定の抽出に失敗しました")
            
            driver.switch_to.default_content()
        else:
            print(f"  ⚠️ カレンダーiframeが見つかりません")

    except Exception as e:
        print(f"  💥 エラー回避: {boat['name']}")
        try: driver.switch_to.default_content()
        except: pass

driver.quit()

output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
