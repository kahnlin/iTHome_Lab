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
    OUTPUT_CSV = "lab_01_regex.csv"  

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