import os
import re
import pdfplumber
import pandas as pd

import pdfplumber
import re

# 全域 Regex 定義
K_NUMBER_PATTERN = re.compile(r"\bK\d{6}\b", re.IGNORECASE)

def extract_devices_from_pdf(pdf_path, filename):
    """
    四階段提取策略 (v12) - 熱啟動版本：Stage 1 精準Regex / Stage 2 表格同行掃描 / Stage 3 上下文視窗 / Stage 10 幾何座標精準定位
    """
    predicates = set()
    references = set()

    # 從檔名取得當前的 K Number
    current_k_match = K_NUMBER_PATTERN.search(filename)
    current_k = current_k_match.group(0).upper() if current_k_match else None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            full_text = ""

            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

                # === [Stage 2] 表格同行掃描 ===
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if table:
                            for row in table:
                                if not row: continue
                                row_cells = [str(cell).strip() if cell else "" for cell in row]
                                row_text = " ".join(row_cells).lower()

                                found_ks = K_NUMBER_PATTERN.findall(row_text)
                                valid_ks = [k.upper() for k in found_ks if k.upper() != current_k]

                                if valid_ks:
                                    if "predicate" in row_text:
                                        predicates.update(valid_ks)
                                    elif "reference" in row_text:
                                        references.update(valid_ks)

                # === [Stage 10] 幾何座標精準定位 (含容錯) ===
                try:
                    words = page.extract_words(keep_blank_chars=False)
                    anchors = []
                    for word in words:
                        txt = word['text'].lower()
                        if "predicate" in txt or "primary" in txt or ("reference" in txt and "device" in txt):
                            anchors.append(word)

                    for anchor in anchors:
                        search_box = {
                            'x0': anchor['x0'] - 80,
                            'x1': anchor['x1'] + 80,
                            'top': anchor['bottom'],
                            'bottom': anchor['bottom'] + 150
                        }
                        for target in words:
                            # X 軸容錯
                            if (search_box['top'] <= target['top'] <= search_box['bottom']) and \
                               (target['x0'] >= search_box['x0']) and \
                               (target['x1'] <= search_box['x1']):
                                
                                k_match = K_NUMBER_PATTERN.match(target['text'])
                                if k_match:
                                    k_val = k_match.group(0).upper()
                                    if k_val != current_k:
                                        anchor_text = anchor['text'].lower()
                                        if "reference" in anchor_text:
                                            references.add(k_val)
                                        else:
                                            predicates.add(k_val)
                except Exception:
                    pass

            # === [Stage 1] 精準 Regex 匹配 ===
            precise_patterns = [
                (r"Predicate\s+(?:Device\s+)?K\s+number[:\s]+([Kk]\d{6})", "pred"),
                (r"Predicate\s+510\(k\).*?([Kk]\d{6})", "pred"),
                (r"Reference\s+(?:Device\s+)?K\s+number[:\s]+([Kk]\d{6})", "ref"),
                (r"predicate\s+device\s+is\s+([Kk]\d{6})", "pred")
            ]
            for pat, type_flag in precise_patterns:
                matches = re.finditer(pat, full_text, re.IGNORECASE | re.DOTALL)
                for m in matches:
                    if len(m.group(0)) < 150:
                        k_val = m.group(1).upper()
                        if k_val != current_k:
                            if type_flag == "pred":
                                predicates.add(k_val)
                            else:
                                references.add(k_val)

            # === [Stage 3] 上下文視窗 ===
            section_headers = [
                r"(?:3\.|4\.|5\.|Section)\s*Predicate\s+Device",
                r"PREDICATE\s+DEVICE",
                r"Predicate\s+Device\s+Information",
                r"Legally\s+Marketed\s+Predicate\s+Devices?",
                r"Equivalent\s+Device"
            ]
            target_pattern = re.compile(r"(?:510\(k\)[\s#\.:]*|K\s*Number|Number|Code|#)[^\n\r]*?([Kk]\d{6})",
                                        re.IGNORECASE | re.DOTALL)

            for header in section_headers:
                header_matches = list(re.finditer(header, full_text, re.IGNORECASE))
                for h_match in header_matches:
                    start_pos = h_match.end()
                    window_text = full_text[start_pos: start_pos + 1000]
                    t_matches = target_pattern.finditer(window_text)
                    for tm in t_matches:
                        k_val = tm.group(1).upper()
                        if k_val != current_k:
                            predicates.add(k_val)

            ref_headers = [r"Reference\s+Device"]
            for header in ref_headers:
                header_matches = list(re.finditer(header, full_text, re.IGNORECASE))
                for h_match in header_matches:
                    start_pos = h_match.end()
                    window_text = full_text[start_pos: start_pos + 1000]
                    t_matches = target_pattern.finditer(window_text)
                    for tm in t_matches:
                        k_val = tm.group(1).upper()
                        if k_val != current_k:
                            references.add(k_val)

            # === 新策略: 檢查全文中可能的 K Number ===
            # 這個策略會在全文中尋找所有可能的 K Number，並根據上下文判斷其類型
            all_k_numbers = K_NUMBER_PATTERN.findall(full_text)
            for k_number in all_k_numbers:
                k_number = k_number.upper()
                if k_number != current_k:
                    # 確認 K Number 周圍的上下文
                    k_index = full_text.find(k_number)
                    context_window = full_text[max(0, k_index - 100):k_index + 100].lower()
                    if "predicate" in context_window:
                        predicates.add(k_number)
                    elif "reference" in context_window:
                        references.add(k_number)

    except Exception as e:
        print(f"Error processing {filename}: {e}")
        return [], []

    return list(predicates), list(references)

# ==========================================
# 👇 批次執行區塊 (由 Agent 自動生成) 👇
# ==========================================
if __name__ == "__main__":
    import os
    import pandas as pd

    # 1. 設定資料夾路徑
    INPUT_FOLDER = "input_pdfs"       
    OUTPUT_CSV = "final_results.csv"  

    if not os.path.exists(INPUT_FOLDER):
        print(f"錯誤: 找不到資料夾 '{INPUT_FOLDER}'，請先建立並放入 PDF 檔案。")
        exit()

    pdf_files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.pdf')]
    total_files = len(pdf_files)

    print(f"📂 找到 {total_files} 個 PDF 檔案，開始批次提取...")

    all_data = []

    for i, filename in enumerate(pdf_files):
        pdf_path = os.path.join(INPUT_FOLDER, filename)
        print(f"[{i+1}/{total_files}] 正在處理: {filename} ...", end="\r")

        try:
            # 呼叫提取函式
            if 'extract_devices_from_pdf' in globals():
                extracted_data = extract_devices_from_pdf(pdf_path, filename)
                if isinstance(extracted_data, tuple):
                    raw_preds, raw_refs = extracted_data
                else: 
                    raw_preds = extracted_data.get('predicate', [])
                    raw_refs = extracted_data.get('reference', [])
            else:
                extracted_data = extract_k_numbers(pdf_path)
                raw_preds = extracted_data.get('predicate', [])
                raw_refs = extracted_data.get('reference', [])

            # --- 🔥 雙重保險去重 (Fix Duplicates) ---
            unique_preds = sorted(list(set(raw_preds)))
            unique_refs = sorted(list(set(raw_refs)))

            pred_str = ", ".join(unique_preds) if unique_preds else "N/A"
            ref_str = ", ".join(unique_refs) if unique_refs else "N/A"

            all_data.append({
                "File Name": filename,
                "Predicate Devices": pred_str,
                "Reference Devices": ref_str
            })

        except Exception as e:
            all_data.append({
                "File Name": filename,
                "Predicate Devices": "Error",
                "Reference Devices": str(e)
            })

    print(f"\n✅ 處理完成！")

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        print(f"📊 結果已儲存至: {OUTPUT_CSV}")
    else:
        print("⚠️ 沒有產出任何資料。")