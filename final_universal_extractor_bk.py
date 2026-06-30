import os
import re
import pdfplumber
import pandas as pd

import pdfplumber
import re
import os

def extract_k_numbers(pdf_path):
    results = {'predicate': [], 'reference': []}
    filename = os.path.basename(pdf_path)
    subject_k = re.search(r"K\d{6}", filename).group(0)
    pattern = re.compile(r"\bK\d{6}\b")

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Strategy A: Extract tables
            try:
                tables = page.extract_tables()
                if tables is not None:
                    for table in tables:
                        if table is not None:  # Check if table is not None
                            for row in table:
                                for cell in row:
                                    if "Predicate" in cell or "Reference" in cell:
                                        k_numbers = pattern.findall(cell)
                                        for k_val in k_numbers:
                                            if k_val != subject_k:
                                                results['predicate' if "Predicate" in cell else 'reference'].append(k_val)
            except Exception as e:
                print(f"Error in Strategy A: {e}")

            # Strategy B: Extract words geometrically
            try:
                words = page.extract_words()
                predicate_index = None
                for i, word in enumerate(words):
                    if "Predicate" in word['text']:
                        predicate_index = i
                    elif "Reference" in word['text']:
                        predicate_index = i

                if predicate_index is not None:
                    for j in range(predicate_index + 1, len(words)):
                        if words[j]['x0'] == words[predicate_index]['x0'] and words[j]['top'] > words[predicate_index]['top']:
                            k_numbers = pattern.findall(words[j]['text'])
                            for k_val in k_numbers:
                                if k_val != subject_k:
                                    results['predicate' if "Predicate" in words[predicate_index]['text'] else 'reference'].append(k_val)
                            break
            except Exception as e:
                print(f"Error in Strategy B: {e}")

            # Strategy C: Regex search
            try:
                text = page.extract_text()
                if text:
                    matches = re.findall(r"Predicate.*? (K\d{6})", text)
                    for k_val in matches:
                        if k_val != subject_k:
                            results['predicate'].append(k_val)

                    matches = re.findall(r"Reference.*? (K\d{6})", text)
                    for k_val in matches:
                        if k_val != subject_k:
                            results['reference'].append(k_val)
            except Exception as e:
                print(f"Error in Strategy C: {e}")

            # Strategy D: Full Text Scan
            try:
                text = page.extract_text()
                if text:
                    # Look for K numbers in the entire text
                    k_numbers = pattern.findall(text)
                    for k_val in k_numbers:
                        if k_val != subject_k:
                            # Use context to determine if it's a predicate or reference
                            context_window = 50  # Number of characters to look around the K number
                            k_index = text.find(k_val)
                            context = text[max(0, k_index - context_window):k_index + context_window]
                            if "Predicate" in context:
                                results['predicate'].append(k_val)
                            elif "Reference" in context:
                                results['reference'].append(k_val)
            except Exception as e:
                print(f"Error in Strategy D: {e}")

            # Strategy E: Contextual Search
            try:
                text = page.extract_text()
                if text:
                    # Search for K numbers with a more flexible context
                    matches = re.finditer(r"(Predicate|Reference).*?(K\d{6})", text)
                    for match in matches:
                        context, k_val = match.groups()
                        if k_val != subject_k:
                            if "Predicate" in context:
                                results['predicate'].append(k_val)
                            elif "Reference" in context:
                                results['reference'].append(k_val)
            except Exception as e:
                print(f"Error in Strategy E: {e}")

            # Strategy F: Enhanced Contextual Search
            try:
                text = page.extract_text()
                if text:
                    # Use a more flexible regex to capture K numbers with context
                    matches = re.finditer(r"(Predicate|Reference)[\s\S]{0,100}?(K\d{6})", text)
                    for match in matches:
                        context, k_val = match.groups()
                        if k_val != subject_k:
                            if "Predicate" in context:
                                results['predicate'].append(k_val)
                            elif "Reference" in context:
                                results['reference'].append(k_val)
            except Exception as e:
                print(f"Error in Strategy F: {e}")

            # Strategy G: Additional Contextual Search
            try:
                text = page.extract_text()
                if text:
                    # Use a more flexible regex to capture K numbers with context
                    matches = re.finditer(r"(Predicate|Reference)[\s\S]{0,200}?(K\d{6})", text)
                    for match in matches:
                        context, k_val = match.groups()
                        if k_val != subject_k:
                            if "Predicate" in context:
                                results['predicate'].append(k_val)
                            elif "Reference" in context:
                                results['reference'].append(k_val)
            except Exception as e:
                print(f"Error in Strategy G: {e}")

            # Strategy H: Fallback Full Text Search
            try:
                text = page.extract_text()
                if text:
                    # Fallback strategy to capture any K numbers not caught by other strategies
                    k_numbers = pattern.findall(text)
                    for k_val in k_numbers:
                        if k_val != subject_k:
                            # Use a simple heuristic to determine if it's a predicate or reference
                            if "Predicate" in text or "predicate" in text:
                                results['predicate'].append(k_val)
                            elif "Reference" in text or "reference" in text:
                                results['reference'].append(k_val)
            except Exception as e:
                print(f"Error in Strategy H: {e}")

    return {key: list(set(values)) for key, values in results.items()}


# ==========================================
# 👇 這裡是您原本缺少的 Main 執行區塊 👇
# ==========================================
if __name__ == "__main__":
    import os
    import pandas as pd

    # 1. 設定資料夾路徑
    INPUT_FOLDER = "input_pdfs"       # 請確保您的 PDF 放在這個資料夾
    OUTPUT_CSV = "final_results.csv"  # 結果輸出的檔名

    # 檢查輸入資料夾是否存在
    if not os.path.exists(INPUT_FOLDER):
        print(f"錯誤: 找不到資料夾 '{INPUT_FOLDER}'，請先建立並放入 PDF 檔案。")
        exit()

    # 2. 取得所有 PDF 檔案
    pdf_files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.pdf')]
    total_files = len(pdf_files)

    print(f"📂 找到 {total_files} 個 PDF 檔案，開始批次提取...")

    all_data = []

    # 3. 開始迴圈
    for i, filename in enumerate(pdf_files):
        pdf_path = os.path.join(INPUT_FOLDER, filename)
        print(f"[{i+1}/{total_files}] 正在處理: {filename} ...", end="\r")

        try:
            # 呼叫上面的提取函式
            extracted_data = extract_k_numbers(pdf_path)
            
            # --- 🔥 關鍵修正：在此處強制去重 (Double Deduplication) ---

            # 無論 AI 生成的代碼是否有去重，這裡都會再做一次，確保 CSV 乾淨

            raw_preds = extracted_data.get('predicate', [])
            raw_refs = extracted_data.get('reference', [])

            # 轉成 Set 去重，再轉回 List 排序

            unique_preds = sorted(list(set(raw_preds)))
            unique_refs = sorted(list(set(raw_refs)))

            # 整理結果格式
            pred_str = ", ".join(extracted_data['predicate']) if extracted_data['predicate'] else "N/A"
            ref_str = ", ".join(extracted_data['reference']) if extracted_data['reference'] else "N/A"

            # 加入清單
            all_data.append({
                "File Name": filename,
                "Predicate Devices": pred_str,
                "Reference Devices": ref_str
            })

        except Exception as e:
            print(f"\n❌ 處理 {filename} 時發生未預期錯誤: {e}")
            all_data.append({
                "File Name": filename,
                "Predicate Devices": "Error",
                "Reference Devices": str(e)
            })

    print(f"\n✅ 處理完成！")

    # 4. 儲存結果
    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        print(f"📊 結果已儲存至: {OUTPUT_CSV}")
    else:
        print("⚠️ 沒有產出任何資料。")
