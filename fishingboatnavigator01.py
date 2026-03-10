from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import re
import json

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

# --- 2. ブラウザ設定（サーバー実行対応版） ---
options = Options()
options.add_argument('--headless')          # 画面を表示しない
options.add_argument('--no-sandbox')        # サーバー環境での実行に必須
options.add_argument('--disable-dev-shm-usage') # メモリ不足エラー防止
options.add_argument('--window-size=1920,1080')

# ロボットだと見破られないためのユーザーエージェント設定
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# サーバー（Linux）上でも正しく動くように設定
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
        time.sleep(8) # 読み込み待ちを少し長めに

        # --- 粘り強くiframeを探す強化版 ---
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        target_iframe = None
        
        print(f"  (見つかったiframeの数: {len(iframes)})") # 状況確認用

        for f in iframes:
            try:
                src = (f.get_attribute("src") or "").lower()
                id_attr = (f.get_attribute("id") or "").lower()
                name_attr = (f.get_attribute("name") or "").lower()
                
                # 判定条件を大幅に緩和
                keywords = ["calendar", "google", "jimdo", "embed", "frame"]
                if any(k in src for k in keywords) or any(k in id_attr for k in keywords) or any(k in name_attr for k in keywords):
                    target_iframe = f
                    break
            except:
                continue
        
        # もしiframeで見つからない場合、武蔵丸さんは「ページ内の特定の場所」に直接ある可能性を考慮
        if not target_iframe:
             # 武蔵丸専用：もしiframeがなくてもbodyのテキストに日付パターンがあればそのまま解析へ
             raw_text_temp = driver.find_element(By.TAG_NAME, "body").text
             if re.search(r"\d+月 \d+日", raw_text_temp):
                 print(f"  -> {boat['name']} iframeなしで直接テキストを解析します")
                 # ここで解析処理へジャンプさせるためのダミー要素をセット
                 raw_text = raw_text_temp 
                 target_iframe = "DIRECT" # フラグ
        
        if target_iframe:
            # 1層目のiframeに切り替え
            driver.switch_to.frame(target_iframe)
            time.sleep(2)
            
            # Jimdo系(ピスケス)はiframeが入れ子になっているため、さらに奥を探す
            inner_found = False
            for _ in range(2): # 最大2回まで奥に潜る
                inner_iframes = driver.find_elements(By.TAG_NAME, "iframe")
                if inner_iframes:
                    driver.switch_to.frame(inner_iframes[0])
                    time.sleep(1)
                    inner_found = True
                else:
                    break
            
            # テキスト取得
            try:
                raw_text = driver.find_element(By.TAG_NAME, "body").text
                
                # 解析処理
                date_pattern = r"(\d+月 \d+日) \(.*?曜日\)"
                lines = raw_text.splitlines()
                schedules = []

                for i in range(len(lines)):
                    match = re.search(date_pattern, lines[i])
                    if match:
                        date_str = match.group(1)
                        found_event = False
                        for j in range(1, 5): # 探索範囲を少し広げる
                            if i + j < len(lines):
                                content = lines[i + j].strip()
                                # ゴミ取りキーワードを追加
                                if len(content) <= 2 or any(k in content for k in ["件の予定", "終日", "予定はありません", "Google", "カレンダー", "前へ", "次へ"]):
                                    continue
                                schedules.append({"date": date_str, "status": judge_status(content), "detail": content})
                                found_event = True
                                break
                        if not found_event:
                            schedules.append({"date": date_str, "status": "○", "detail": "空き"})
                
                if schedules:
                    all_results[boat['name']] = {"data": schedules}
                    print(f"-> {boat['name']} 完了 ({len(schedules)}日分)")
                else:
                    print(f"-> {boat['name']} カレンダー内の予定が見つかりませんでした")

            except Exception as e:
                print(f"-> {boat['name']} テキスト取得失敗: {e}")
            
            driver.switch_to.default_content()
        else:
            print(f"-> {boat['name']} のカレンダー(iframe)が見つかりませんでした")

finally:
    driver.quit()

# --- 4. JSON保存 ---
output_data = {
    "boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS},
    "schedules": all_results
}

with open("fishing_schedule.json", "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=4)

print("\n✅ 保存完了！index.htmlで確認してください。")