import os
import re
import pdfplumber
import pandas as pd

import pdfplumber
import re
import os

# 全域 Regex 定義
K_NUMBER_PATTERN = re.compile(r"\bK\d{6}\b", re.IGNORECASE)

def extract_devices_from_pdf(pdf_path, filename):
    """
    單階段提取策略 (v12) - 熱啟動版本：Stage 10 幾何座標精準定位 + Stage 11 表格提取
    """
    predicates = set()
    references = set()

    # 從檔名取得當前的 K Number
    current_k_match = K_NUMBER_PATTERN.search(filename)
    current_k = current_k_match.group(0).upper() if current_k_match else None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
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

                # === [Stage 11] 表格提取 ===
                try:
                    tables = page.extract_tables()
                    for table in tables:
                        for row in table:
                            for cell in row:
                                if cell and K_NUMBER_PATTERN.match(cell):
                                    k_val = K_NUMBER_PATTERN.search(cell).group(0).upper()
                                    if k_val != current_k:
                                        # 猜測表格中 "Predicate" 或 "Reference Device" 可能會在附近
                                        if any("predicate" in cell.lower() for row in table) or \
                                           any("reference device" in cell.lower() for row in table):
                                            predicates.add(k_val)
                                        else:
                                            references.add(k_val)
                except Exception:
                    pass

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