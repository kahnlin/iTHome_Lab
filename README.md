# itHome_Lab: FDA 510(k) PDF 資訊萃取實作

這是一個用於從 PDF 檔案中提取特定資訊（Predicate / Reference Devices 的 K Numbers）的 Python 專案，為教學或實作練習的範例專案。

## 專案結構

- `lab_01_regex.py`: 使用正規表達式 (Regex) 進行文字提取的基礎實作。
- `lab_02_geometric.py`: 使用幾何座標定位與表格分析進行進階提取的實作。
- `auto_healing_extractor.py`: 結合 LangGraph 與 OpenAI LLM 的自動修復/進化式提取器，能在遇到新格式時自動生成並優化解析策略。
- `final_universal_extractor.py`: 最終生成的通用版提取器。
- `input_pdfs/`: 存放待處理 PDF 檔案的目錄（請將您的 PDF 放入此資料夾）。
- `output_data/`: 存放產出結果的目錄。

## 環境設定與安裝

1. 確保您已安裝 Python 3.8+ 版本。
2. 建立並啟動虛擬環境（建議）：
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # macOS / Linux
   # 或是
   .venv\Scripts\activate     # Windows
   ```
3. 安裝必要套件：
   ```bash
   pip install -r requirements.txt
   ```
4. **環境變數設定**：
   如果需要執行 `auto_healing_extractor.py`，請在專案根目錄建立一個 `.env` 檔案，並放入您的 OpenAI API Key：
   ```env
   OPENAI_API_KEY="your_api_key_here"
   ```

## 如何執行

1. 將欲解析的 PDF 檔案放入 `input_pdfs/` 資料夾內。
2. 執行對應的實驗腳本，例如：
   ```bash
   python lab_01_regex.py
   ```
3. 執行完成後，解析結果會自動儲存為 `.csv` 檔案（例如 `lab_01_regex.csv` 或 `final_results.csv`）。

## 注意事項

- **安全提醒**：絕對不要將您的 `.env` 檔案或真實的 API Key 上傳至 GitHub。本專案的 `.gitignore` 已經預設忽略了 `.env` 檔案。
- 專案產出的 `.csv` 結果檔預設不會被加入版本控制。
# iTHome_Lab
