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
# 【重要】ボットだとバレないための偽装
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

# 判定関数
def judge_status(content):
    if any(k in content for k in ["満", "×", "済", "貸", "チャーター", "Full", "予約有", "締切", "満員"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか"]): return "△"
    return "○"

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【開始】 {boat['name']} ---")
    try:
        driver.get(boat['url'])
        
        # 【最重要】予定（role="button"）が表示されるまで最大20秒待機する
        # これがないと、中身が空の状態でスクレイピングが終わってしまいます
        wait = WebDriverWait(driver, 20)
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='button']")))
            print("  ✨ 予定の描画を確認しました")
        except:
            print("  ⏳ 描画待ちタイムアウト（予定がないか、読み込みが遅すぎます）")

        time.sleep(3) # 念のため追加の安定待ち

        schedules = []
        # 全ての aria-label 付き要素を取得
        elements = driver.find_elements(By.XPATH, "//*[@aria-label]")
        
        for el in elements:
            label = el.get_attribute("aria-label")
            if not label: continue

            # 明らかに予定ではないUIテキストを除外
            if any(k in label for k in ["今日", "Today", "次へ", "前へ", "設定", "印刷", "Google"]): continue
            
            # 日付の抽出 (3月11日)
            m_ja = re.search(r"(\d{1,2})月(\d{1,2})日", label)
            if m_ja:
                date_str = f"{m_ja.group(1)}月{m_ja.group(2)}日"
                # ラベルから日付を消して内容を取り出す
                # 例: "鰆ミノー, 2026年3月1日" -> "鰆ミノー"
                content = label.split(',')[0].strip()
                
                # 内容が日付そのものでなければ採用
                if content != date_str and not content.isdigit() and "event" not in content.lower():
                    schedules.append({
                        "date": date_str,
                        "status": judge_status(content),
                        "detail": content
                    })

        if schedules:
            # 重複排除とマージ
            unique_days = {}
            for s in schedules:
                d = s["date"]
                if d not in unique_days:
                    unique_days[d] = s
                else:
                    if s['detail'] not in unique_days[d]['detail']:
                        unique_days[d]["detail"] += f" / {s['detail']}"
                        unique_days[d]["status"] = judge_status(unique_days[d]["detail"])
            
            all_results[boat['name']] = {"data": sorted(list(unique_days.values()), key=lambda x: int(re.search(r'\d+', x['date']).group()))}
            print(f"  ✅ {len(unique_days)}件の予定を取得！")
        else:
            print("  ⚠️ 予定データが空でした（フィルタリングで消えた可能性があります）")

    except Exception as e:
        print(f"  💥 エラー発生: {str(e)}")

driver.quit()

# JSON保存
output = {"boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS}, "schedules": all_results}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
print("\n💾 保存完了")
