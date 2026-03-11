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
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
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
        wait = WebDriverWait(driver, 20)
        # role='button' かつ aria-label を持つ要素が出るまで待つ
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='button' and @aria-label]")))
        time.sleep(5) 

        schedules = []
        # 全ての候補要素を取得
        elements = driver.find_elements(By.XPATH, "//div[@role='button' and @aria-label]")
        
        for el in elements:
            label = el.get_attribute("aria-label")
            text_content = el.text.strip() # 画面に表示されている文字
            
            # システムUI（今日、前、次など）を排除
            if any(k in label for k in ["今日", "Today", "次へ", "前へ", "設定", "印刷"]): continue

            # 日付の抽出 (例: 3月1日)
            m_ja = re.search(r"(\d{1,2})月(\d{1,2})日", label)
            if m_ja:
                date_str = f"{m_ja.group(1)}月{m_ja.group(2)}日"
                
                # 【重要】予定名の特定
                # 1. 要素の中にテキストがあればそれを使う
                # 2. なければaria-labelの最初のカンマまでを使う
                title = text_content if text_content else label.split(',')[0].strip()

                # 数字だけの日付ラベルや「1 event」等は除外
                if not title or title.isdigit() or "event" in title.lower() or "イベント" in title:
                    continue

                # まれに日付がタイトルとして誤認されるのを防ぐ
                if title == date_str:
                    continue

                schedules.append({
                    "date": date_str,
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
                    # 同じ日の予定を統合
                    if s['detail'] not in unique_days[d]['detail']:
                        unique_days[d]["detail"] += f" / {s['detail']}"
                        unique_days[d]["status"] = judge_status(unique_days[d]["detail"])
            
            # 日付順（数字ベース）にソート
            sorted_list = sorted(unique_days.values(), key=lambda x: [int(v) for v in re.findall(r'\d+', x['date'])])
            all_results[boat['name']] = {"data": sorted_list}
            print(f"  ✅ {len(unique_days)}件の予定を取得しました")
        else:
            print("  ⚠️ 予定が見つかりませんでした（要素は見つかりましたが中身が空です）")

    except Exception as e:
        print(f"  💥 エラー: {str(e)}")

driver.quit()

output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
