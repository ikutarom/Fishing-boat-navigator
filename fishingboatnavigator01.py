# --- 前略 ---

def judge_status(content):
    if any(k in content for k in ["満船", "満", "予約済", "貸切", "×", "済", "Full", "完売", "締切", "チャーター", "🈵"]): return "×"
    if any(k in content for k in ["残り", "残", "△", "わずか", "🈳", "募集中"]): return "△"
    return "○"

# 月名変換マップ（優の4月以降対策）
MONTH_MAP = {
    "Jan": "1月", "Feb": "2月", "Mar": "3月", "Apr": "4月", "May": "5月", "Jun": "6月",
    "Jul": "7月", "Aug": "8月", "Sep": "9月", "Oct": "10月", "Nov": "11月", "Dec": "12月"
}

all_results = {}

for boat in BOATS:
    print(f"\n🚀 --- 【解析開始】 {boat['name']} ---")
    boat_schedules = []
    
    try:
        target_url = boat['url']
        params = "&mode=AGENDA&weeks=14&hl=ja&ctz=Asia/Tokyo"
        target_url += params if "?" in target_url else "?" + params[1:]
        driver.get(target_url)

        time.sleep(8)
        if len(driver.find_elements(By.TAG_NAME, "iframe")) > 0:
            driver.switch_to.frame(0)

        # 💡 優対策：スクロールを少し深くして4月以降の描画を促す
        driver.execute_script("window.scrollTo(0, 800);")
        time.sleep(2)

        raw_text = driver.execute_script("return document.body.innerText;")
        
        if raw_text:
            lines = raw_text.splitlines()
            current_day = ""
            current_month = ""

            for i in range(len(lines)):
                line = lines[i].strip()
                if not line: continue

                # 1. 月・日の特定
                m_jp = re.search(r'(\d{1,2})月,', line)
                m_en = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),', line)

                if m_jp or m_en:
                    current_month = f"{m_jp.group(1)}月" if m_jp else MONTH_MAP[m_en.group(1)]
                    d_match = re.search(r',\s*(\d{1,2})', line)
                    if d_match:
                        current_day = d_match.group(1)
                    elif i > 0 and lines[i-1].strip().isdigit():
                        current_day = lines[i-1].strip()
                    continue

                # 2. 予定の抽出
                is_time_marker = (
                    line in ["終日", "All day"] or 
                    re.search(r'\d{1,2}(:\d{2})?\s*(am|pm)?', line.lower()) or
                    "–" in line or "—" in line
                )

                if current_day and is_time_marker:
                    details = []
                    for j in range(i + 1, min(i + 5, len(lines))):
                        detail = lines[j].strip()
                        
                        # 💡 ゴミ掃除・メールアドレス削除
                        if not detail or any(k in detail for k in ["表示", "Google", "詳細", "カレンダー:", "承諾", "辞退", "未定", "出船スケジュール"]):
                            continue
                        
                        # メールアドレスが含まれる行はスキップ
                        if re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', detail):
                            continue
                            
                        # 次の日付や時刻が来たらストップ
                        if "月," in detail or re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),', detail): break
                        if re.search(r'\d{1,2}(:\d{2})?\s*(am|pm)?', detail.lower()): break
                        
                        details.append(detail)
                    
                    if details:
                        full_detail = " / ".join(details)
                        if current_month and current_day:
                            boat_schedules.append({
                                "date": f"{current_month}{current_day}日",
                                "status": judge_status(full_detail),
                                "detail": full_detail
                            })

            # 重複排除
            unique_schedules = []
            seen = set()
            for s in boat_schedules:
                identifier = (s['date'], s['detail'])
                if identifier not in seen:
                    seen.add(identifier); unique_schedules.append(s)
            
            all_results[boat['name']] = {"data": unique_schedules}
            print(f"  ✅ {len(unique_schedules)}件抽出完了")

        driver.switch_to.default_content()
            
    except Exception as e:
        print(f"  💥 エラー: {boat['name']} ({str(e)})")

driver.quit()

# --- 保存処理 ---
output = {
    "last_update": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "boat_info": {b["name"]: {"area": b["area"], "link": b["official"]} for b in BOATS},
    "schedules": all_results
}
json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fishing_schedule.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=4)
