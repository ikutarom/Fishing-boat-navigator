# --- 前略 ---

for boat in BOATS:
    print(f"\n🚀 --- 【解析開始】 {boat['name']} ---")
    boat_schedules = []
    
    try:
        target_url = boat['url']
        params = "&mode=AGENDA&weeks=14&hl=ja&ctz=Asia/Tokyo"
        target_url += params if "?" in target_url else "?" + params[1:]
        driver.get(target_url)
        
        # 💡 昨日の成功体験：暁などのために、まずはしっかり待つ
        time.sleep(10) 

        if len(driver.find_elements(By.TAG_NAME, "iframe")) > 0:
            driver.switch_to.frame(0)

        # 💡 改善：ボタン連打は「優」など特定が必要な場合のみ、または慎重に行う
        # 暁で0件になるのを防ぐため、ボタンが見つからない場合は即座に解析へ進む
        if any(k in boat['name'] for k in ["優", "エルクルーズ", "Wingar", "GOD"]):
            for i in range(2): # 回数を2回に絞って安定させる
                try:
                    next_btn = driver.find_element(By.ID, "nextButton")
                    if next_btn.is_displayed():
                        driver.execute_script("arguments[0].click();", next_btn)
                        print(f"  👆 {boat['name']}: 次の期間を読み込み中...")
                        time.sleep(4)
                except:
                    break

        # 暁対策：解析直前にもう一度少し待つ（昨日成功した時のリズム）
        time.sleep(2)
        raw_text = driver.execute_script("return document.body.innerText;")
        
        if raw_text:
            lines = raw_text.splitlines()
            current_day = ""
            current_month = ""

            for i in range(len(lines)):
                line = lines[i].strip()
                if not line: continue

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

                time_unit_regex = r'\d{1,2}(:\d{2})?\s*(am|pm)?'
                is_time_marker = (
                    line in ["終日", "All day"] or 
                    re.match(f"^{time_unit_regex}$", line.lower()) or
                    "–" in line or "—" in line
                )

                if current_day and is_time_marker:
                    details = []
                    for j in range(i + 1, min(i + 5, len(lines))):
                        detail = lines[j].strip()
                        # ゴミ掃除
                        if not detail or detail == "カレンダー" or "(No title)" in detail: continue
                        if any(k in detail for k in ["表示", "Google", "詳細", "カレンダー:", "承諾", "辞退", "未定", "出船スケジュール"]):
                            continue
                        if re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', detail):
                            continue
                        if "月," in detail or re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),', detail): break
                        if detail in ["終日", "All day"] or re.match(f"^{time_unit_regex}$", detail.lower()): break
                        details.append(detail)
                    
                    if details:
                        full_detail = " / ".join(details)
                        if current_month and current_day:
                            boat_schedules.append({
                                "date": f"{current_month}{current_day}日",
                                "status": judge_status(full_detail),
                                "detail": full_detail
                            })

            # 重複排除のロジック（そのまま維持）
            unique_schedules = []
            for s in boat_schedules:
                is_duplicate = False
                for existing in unique_schedules:
                    if existing['date'] == s['date']:
                        if s['detail'] in existing['detail'] or existing['detail'] in s['detail']:
                            is_duplicate = True
                            if len(s['detail']) > len(existing['detail']):
                                existing['detail'] = s['detail']
                                existing['status'] = s['status']
                            break
                if not is_duplicate:
                    unique_schedules.append(s)
            
            all_results[boat['name']] = {"data": unique_schedules}
            print(f"  ✅ {len(unique_schedules)}件抽出完了")

        driver.switch_to.default_content()
# --- 以下省略 ---
