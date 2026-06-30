import os
import re
import sys
import io
import contextlib
import pdfplumber
import pandas as pd
import warnings
from typing import TypedDict, Optional, List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

# 忽略 Pydantic V1 在 Python 3.14 的警告
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_core")

# 載入 .env 檔案中的環境變數
load_dotenv()

# ==========================================
# 🔥 定義 v11 黃金代碼 (熱啟動版本) 🔥
# [修正] 使用 r''' (三單引號) 避免與內部的 """ (三雙引號) 衝突
# ==========================================
INITIAL_GOLDEN_CODE = r'''
import pdfplumber
import re
import os

# 全域 Regex 定義
K_NUMBER_PATTERN = re.compile(r"\bK\d{6}\b", re.IGNORECASE)

def extract_devices_from_pdf(pdf_path, filename):
    """
    四階段提取策略 (v11) - 熱啟動版本：Stage 1 精準Regex / Stage 2 表格同行掃描 / Stage 3 上下文視窗 / Stage 10 幾何座標精準定位
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

            # （目前 golden code 僅包含上述 Stage 1/2/3/10，共 4 種策略）

    except Exception as e:
        print(f"Error processing {filename}: {e}")
        return [], []

    return list(predicates), list(references)
'''

# ==========================================
# 2. 定義最終生成的 Main Block 模板
# ==========================================
FINAL_MAIN_BLOCK = """
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
        print(f"[{i+1}/{total_files}] 正在處理: {filename} ...", end="\\r")

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

    print(f"\\n✅ 處理完成！")

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        print(f"📊 結果已儲存至: {OUTPUT_CSV}")
    else:
        print("⚠️ 沒有產出任何資料。")
"""

# --- 定義系統狀態 (State) ---
class AgentState(TypedDict):
    pdf_path: str
    current_code: str
    execution_result: Any
    execution_log: str
    error_message: Optional[str]
    feedback: Optional[str]
    attempts: int
    status: str


# ==========================================
# 節點 1: Coder (工程師) [Prompt 同步 v11]
# ==========================================
def coder_node(state: AgentState):
    current_attempt = state['attempts'] + 1
    
    # === 混合策略設定 ===
    MAX_LOCAL_ATTEMPTS = 4
    
    if current_attempt <= MAX_LOCAL_ATTEMPTS:
        # [Tier 1] Local LLM
        model_source = "Local LLM"
        print(f"\n🔵 [Coder] 第 {current_attempt} 次嘗試：使用 {model_source}...")
        try:
            llm = ChatOpenAI(
                base_url="http://localhost:1234/v1",
                api_key="lm-studio",
                model="local-model",
                temperature=0,
                # 🔥 增加 Timeout 時間 (解決 Request timed out)
                timeout=300,
                # 🔥 硬上限：防止小模型陷入重複退化、無限疊加 Stage 而生成超長代碼
                max_tokens=4000
            )
        except Exception as e:
            print(f"⚠️ Local LLM 連線失敗，切換至 GPT-4o...")
            model_source = "GPT-4o (Fallback)"
            llm = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=4000)
    else:
        # [Tier 2] GPT-4o
        model_source = "GPT-4o (Expert Mode)"
        print(f"\n🟣 [Coder] 第 {current_attempt} 次嘗試：切換為 {model_source} 救場...")
        llm = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=4000)

    # ------------------------------------------------------------------
    # 準備 Prompt 與 黃金模板 (v11 Escaped Version)
    # ------------------------------------------------------------------
    filename = os.path.basename(state['pdf_path'])
    current_k_match = re.search(r"K\d{6}", filename, re.IGNORECASE)
    current_k = current_k_match.group(0).upper() if current_k_match else "N/A"

    existing_code = state.get('current_code', '')

    # 🔥 Prompt 用的黃金參考模板：直接重用 INITIAL_GOLDEN_CODE，確保與實際執行版本一致 🔥
    reference_template = INITIAL_GOLDEN_CODE

    if not existing_code or "def extract_devices_from_pdf" not in existing_code:
        base_instruction = "請**嚴格依照**下方的【黃金參考模板】(v11) 編寫代碼。"
        context_code = f"【黃金參考模板 (Copy this structure)】:\n{reference_template}"
    else:
        base_instruction = """
        【進化/修復模式】
        1. 你現在擁有的是目前最佳版本的提取器 (v11)。
        2. 請依照實際錯誤或反饋自由判斷：可以新增、修改、移除策略，不必受限於現有架構。
        3. 你的目標是讓提取結果更準確，而非單純保留現狀。
        4. 🚫 禁止重複套用相同模板新增多個雷同策略：若現有策略真的無法解決問題，最多只能新增 1 個新策略，且必須是判斷邏輯明顯不同於現有策略的新方法。
        """
        context_code = f"【現有代碼 (v11)】:\n{existing_code}"

    special_note = ""
    if "Local" in model_source:
        special_note = """
        【Local Model 特別指令】
        1. 直接輸出 Python 代碼。
        2. 函數名稱必須是 `extract_devices_from_pdf`。
        3. 不要包含 ```python 標記。
        """

    instruction = f"""
    你是一個 Python 專家。你的目標是維護並優化一個 FDA 510(k) Predicate/Reference Device 提取器。

    【任務】
    修正/微調 Python 函數 `extract_devices_from_pdf(pdf_path, filename)`，從 `{filename}` 中提取 Predicate/Reference Device。

    {base_instruction}

    {context_code}

    【嚴格禁止事項】
    1. ❌ **禁止硬編碼 (Hardcoding)**。
    2. ❌ **注意 NoneType 錯誤**：處理表格時務必先檢查 `if cell`。

    【目標檔案資訊】
    路徑: {state['pdf_path']}
    Subject Device (必須排除): {current_k}

    【上一次錯誤/反饋】
    {state.get('feedback') or state.get('error_message', '無')}

    {special_note}

    【代碼要求】
    1. 函數簽章: `def extract_devices_from_pdf(pdf_path, filename):`
    2. 回傳格式: `(predicates_list, references_list)`
    3. 只輸出 Python 代碼。
    """

    try:
        response = llm.invoke(instruction)
        clean_code = response.content.replace("```python", "").replace("```", "").strip()
        
        if "def extract_devices_from_pdf" not in clean_code:
            match = re.search(r"(import.*?return.*?)", response.content, re.DOTALL)
            if match:
                clean_code = match.group(0)
            else:
                 match = re.search(r"(def extract_devices_from_pdf.*)", response.content, re.DOTALL)
                 if match:
                    clean_code = "import pdfplumber\nimport re\nimport os\nK_NUMBER_PATTERN = re.compile(r'\\bK\\d{6}\\b', re.IGNORECASE)\n" + match.group(0)

    except Exception as e:
        print(f"❌ 模型生成錯誤: {e}")
        clean_code = existing_code

    return {
        "current_code": clean_code,
        "attempts": state["attempts"] + 1,
        "error_message": None,
        "feedback": None
    }

# --- 節點 2: Executor (執行者) ---
def executor_node(state: AgentState):
    print("🟠 [Executor] 正在執行代碼...")

    code = state['current_code']
    pdf_path = state['pdf_path']
    filename = os.path.basename(pdf_path)

    global_vars = {"pdfplumber": pdfplumber, "re": re, "pd": pd, "os": os}
    stdout_capture = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout_capture):
            # 🔥 必須只傳一個 namespace dict：globals/locals 分開會讓函式看不到模組層級變數（如 K_NUMBER_PATTERN），導致 NameError
            exec(code, global_vars)

            if "extract_devices_from_pdf" in global_vars:
                result = global_vars["extract_devices_from_pdf"](pdf_path, filename)
            elif "extract_k_numbers" in global_vars:
                 result = global_vars["extract_k_numbers"](pdf_path)
            else:
                raise ValueError("生成的代碼中缺少函式定義。")
            
            print(f"執行結果: {result}")

        return {
            "execution_result": result,
            "execution_log": stdout_capture.getvalue(),
            "error_message": None
        }

    except Exception as e:
        return {
            "execution_result": None,
            "execution_log": stdout_capture.getvalue(),
            "error_message": str(e)
        }

# --- 節點 3: Critic (評審) ---
def critic_node(state: AgentState):
    print("🟢 [Critic] 正在檢驗結果...")

    result = state.get("execution_result")
    error = state.get("error_message")

    if error:
        if "NoneType" in str(error):
             return {"feedback": "檢測到表格處理錯誤 (NoneType)。請檢查 `if cell` 防呆。", "status": "retry"}
        return {"feedback": f"程式執行發生錯誤: {error}", "status": "retry"}

    # 處理回傳格式
    predicates = []
    references = []
    
    if isinstance(result, dict):
        predicates = result.get("predicate", [])
        references = result.get("reference", [])
    elif isinstance(result, tuple) or isinstance(result, list):
         if len(result) >= 1: predicates = result[0]
         if len(result) >= 2: references = result[1]
    else:
        return {"feedback": "回傳格式錯誤，必須是 (predicates, references) 的 Tuple 或 Dict。", "status": "retry"}

    if not predicates and not references:
        print("  -> 檢驗失敗: 提取結果為空。")
        return {
            "feedback": "提取結果為空。請檢查 Regex 或幾何範圍，但不要刪除任何現有的提取策略。",
            "status": "retry"
        }

    k_pattern = re.compile(r"K\d{6}", re.IGNORECASE)
    valid_preds = [k for k in predicates if k_pattern.match(k)]

    if not valid_preds and not references:
        return {
            "feedback": "提取內容不符合 K Number 格式。",
            "status": "retry"
        }
    
    print(f"  -> ✅ 檢驗通過! Predicate: {valid_preds}")
    return {"status": "success", "execution_result": {"predicate": valid_preds, "reference": references}}

# --- 路由與建置 ---
def decide_next_step(state: AgentState):
    if state["status"] == "success":
        return END
    if state["attempts"] >= 5:
        print("🛑 達到最大重試次數，放棄。")
        return END
    return "coder"

def build_agent():
    workflow = StateGraph(AgentState)
    workflow.add_node("coder", coder_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("critic", critic_node)
    workflow.set_entry_point("coder")
    workflow.add_edge("coder", "executor")
    workflow.add_edge("executor", "critic")
    workflow.add_conditional_edges("critic", decide_next_step, {"coder": "coder", END: END})
    return workflow.compile()

# --- 主程式 ---
if __name__ == "__main__":
    TRAINING_FOLDER = "input_pdfs"
    FINAL_SCRIPT_NAME = "final_universal_extractor.py"
    
    # 🔥 熱啟動 (Warm Start)
    global_best_code = INITIAL_GOLDEN_CODE  

    if not os.path.exists(TRAINING_FOLDER):
        print(f"錯誤: 找不到資料夾 {TRAINING_FOLDER}")
        sys.exit(1)

    pdf_files = [f for f in os.listdir(TRAINING_FOLDER) if f.lower().endswith('.pdf')]
    app = build_agent()

    print(f"🧬 開始進化式提取流程 (v12 穩定版)，共 {len(pdf_files)} 個訓練檔案...")

    for i, filename in enumerate(pdf_files):
        pdf_path = os.path.join(TRAINING_FOLDER, filename)
        print(f"\n🚀 [{i + 1}/{len(pdf_files)}] 訓練檔案: {filename}")

        # --- 步驟 A: Pre-check ---
        pre_check_success = False
        if global_best_code:
            print("⚡️ 嘗試使用現有最佳代碼 (v11)...")
            try:
                local_vars = {}
                exec_context = "import os\nimport re\nimport pdfplumber\nimport pandas as pd\n" + global_best_code
                # 🔥 必須只傳一個 namespace dict：globals/locals 分開會讓函式看不到模組層級變數（如 K_NUMBER_PATTERN），導致 NameError
                exec(exec_context, local_vars)

                result = None
                if "extract_devices_from_pdf" in local_vars:
                    result = local_vars["extract_devices_from_pdf"](pdf_path, filename)
                elif "extract_k_numbers" in local_vars:
                    result = local_vars["extract_k_numbers"](pdf_path)

                if result:
                    p = []
                    r = []
                    if isinstance(result, tuple): p, r = result
                    elif isinstance(result, dict): p, r = result.get('predicate', []), result.get('reference', [])
                    
                    if p or r:
                        print(f"✅ 現有代碼適用！直接通過。")
                        pre_check_success = True
                    else:
                        print("🔸 現有代碼提取為空，需要進化...")
                else:
                    print("🔸 現有代碼回傳 None，需要進化...")

            except Exception as e:
                print(f"🔸 現有代碼執行錯誤 ({e})，需要修復...")

        # --- 步驟 B: 自癒進化 ---
        if not pre_check_success:
            initial_state = {
                "pdf_path": pdf_path,
                "current_code": global_best_code,
                "execution_result": None,
                "execution_log": "",
                "error_message": None,
                "feedback": None,
                "attempts": 0,
                "status": "start"
            }

            try:
                final_state = app.invoke(initial_state)
                if final_state["status"] == "success":
                    print("🧬 代碼進化成功！更新 Global Best Code。")
                    global_best_code = final_state["current_code"]
                else:
                    print("❌ 進化失敗 (跳過此檔案)")
            except Exception as e:
                print(f"❌ System Error: {e}")

    # --- 步驟 C: 生成最終執行檔 ---
    if global_best_code:
        print("\n" + "=" * 50)
        print("🏆 正在生成最終執行檔...")
        try:
            with open(FINAL_SCRIPT_NAME, "w", encoding="utf-8") as f:
                f.write("import os\nimport re\nimport pdfplumber\nimport pandas as pd\n\n")
                f.write(global_best_code)
                f.write("\n\n")
                f.write(FINAL_MAIN_BLOCK.strip())
            print(f"✅ 成功！已建立 '{FINAL_SCRIPT_NAME}'")
            print(f"👉 請執行: python {FINAL_SCRIPT_NAME}")
        except Exception as e:
            print(f"❌ 寫入檔案失敗: {e}")
        print("=" * 50)
    else:
        print("❌ 訓練過程未能產生任何有效的代碼。")