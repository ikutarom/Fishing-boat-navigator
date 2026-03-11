import os
import time
import re
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

TARGET_URL = "https://calendar.google.com/calendar/u/0/embed?src=mctbqceknts09ssk81vck6npik@group.calendar.google.com&src=f06ic59ea23rpoopr54mf7sui0@group.calendar.google.com&src=0s2q9vsadci1eg09teq6pip3ms@group.calendar.google.com&src=g86rlbflghcqh7kfl5k4gkq69g@group.calendar.google.com&ctz=Asia/Tokyo&hl=ja&mode=AGENDA"

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1920,1080')
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)

def judge_status(content):
    if any(k in content for k in ["満船", "満", "チャーター", "予約済", "貸切", "×", "済", "Full", "締切"]): return "×"
    if re.search(r"残り([1-2])名", content) or "△" in content: return "△"
    return "○"

all_schedules = []

print(f"🚀 --- スキャン開始 (JS抽出モード) ---")
try:
    driver.get(TARGET_URL)
    time.sleep(5) # 描画を完全に待つ

    # 【新手法】innerTextを使って、ブラウザが見せている「生のテキスト」を直接取得
    # body.text よりも Ctrl+A に近い情報が取れます
    raw_text = driver.execute_script("return document.body.innerText;")
    
    if raw_text:
        # 取得した生テキストをデバッグ用に少し表示（ログで確認用）
        print(f"--- 取得テキスト冒頭 ---\n{raw_text[:200]}\n------------------------")
        
        lines = raw_text.splitlines()
        current_date = None
        
        # 日付パターン: 3月11日(水) などの形式
        date_pattern = r"(\d{1,2}月\s?\d{1,2}日)"

        for i in range(len(lines)):
            line = lines[i].strip()
            if not line: continue

            # 1. 日付の行かチェック
            if "曜日" in line:
                date_match = re.search(date_pattern, line)
                if date_match:
                    current_date = date_match.group(1).replace(" ", "")
                    continue
            
            # 2. 日付が決まっている状態で予定を探す
            if current_date:
                # 明らかなゴミを除外
                if any(k in line for k in ["今日", "印刷", "Google", "カレンダー", "予定はありません", "12月", "2026年"]):
                    if "2026年" not in line: # 年号表示はスルー
                        continue
                
                # 時刻表示(06:00など)がある行、またはその次の行が予定本体
                clean_content = re.sub(r'\d{2}:\d{2}', '', line).strip()
                
                if len(clean_content) > 2:
                    all_schedules.append({
                        "date": current_date,
                        "status": judge_status(clean_content),
                        "detail": clean_content
                    })

    if not all_schedules:
        print("  ⚠️ 予定が見つかりません。ロジックを微調整します...")
        # バックアッププラン: 予定リストの各項目を直接ループで回す
        events = driver.find_elements(By.CLASS_NAME, "event")
        for ev in events:
            try:
                txt = ev.text.replace("\n", " ")
                d_match = re.search(date_pattern, txt)
                if d_match:
                    all_schedules.append({
                        "date": d_match.group(1).replace(" ", ""),
                        "status": judge_status(txt),
                        "detail": txt
                    })
            except: continue

except Exception as e:
    print(f"  💥 エラー発生: {str(e)}")

driver.quit()

output = {"schedules": {"Combined-Calendar": {"data": all_schedules}}}
with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)

print(f"\n💾 保存完了: {len(all_schedules)}件")
