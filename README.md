# JMeter Report Verify

自動化比對 JMeter 效能測試報告與預設驗收標準的工具。

## 功能簡介

本工具讀取 JMeter 產生的 HTML Dashboard 報告，自動提取效能統計數據，並依據 CSV 驗證設定檔進行以下兩項檢查：

1. **90th 百分位回應時間檢查** — 各腳本所有步驟的 P90 回應時間是否低於門檻值
2. **通過樣本數檢查** — 依 `name_rule` 策略選取代表步驟，檢查其成功請求數是否達到預期數量

檢查完成後輸出 **PASSED** 或列出所有不合格項目。

本工具提供兩種使用方式：

- **GUI 模式** — tkinter 圖形介面，深藍青綠色系現代化 UI
- **CLI 模式** — 命令列直接執行

## 環境需求

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) 套件管理工具

## 安裝與啟動

```bash
# 1. 安裝依賴
uv sync

# 2. 安裝 Playwright 瀏覽器（安裝至專案下的 ms-playwright/ 目錄）
uv run playwright install chromium

# 3. 啟動 GUI
uv run python gui.py

# 4. CLI 模式（直接編輯 main.py 中的路徑後執行）
uv run python main.py
```

> **備註**：本專案預設使用工作目錄下的 `ms-playwright/` 目錄存放 Playwright 瀏覽器，而非預設的 `%LOCALAPPDATA%\ms-playwright\`。此設計方便未來打包為獨立 exe 時，可將瀏覽器一併打包，無需額外安裝。

## 執行測試

```bash
uv run --group dev pytest -v
```

## 專案結構

```
.
├── core.py                  # 核心業務邏輯（報告抓取、設定檔讀取、驗證比對）
├── gui.py                   # tkinter GUI 入口
├── main.py                  # CLI 入口，引用 core.py
├── pyproject.toml           # 專案依賴設定
├── ms-playwright/           # Playwright 瀏覽器（本地存放，便於打包）
│   └── chromium-1228/
├── tests/
│   ├── test_core.py         # core 模組單元測試
│   └── test_verify_results.py  # verify_results 函式單元測試
├── verify_config/           # 驗證標準 CSV 設定檔
│   └── core_PT_1.csv        # 各腳本的 P90 門檻與預期通過樣本數
└── jmeter_report/           # JMeter 產出的 HTML 報告目錄
    └── core_PT_1__report-core_PT_1-2026-07-21_154922/
        └── index.html       # JMeter HTML Dashboard 報告
```

## 模組說明

### core.py

核心業務邏輯模組，提供以下函式：

| 函式 | 說明 |
|------|------|
| `extract_table_data(html_file, headless, output_dir)` | 使用 Playwright 從 JMeter HTML 報告提取表格資料 |
| `read_verify_config(config_file)` | 讀取 CSV 驗證設定檔 |
| `verify_results(df_report, df_config)` | 比對報告與設定，回傳失敗訊息列表 |
| `verify_results_detail(df_report, df_config)` | 回傳結構化逐列比對結果（供 GUI 使用） |
| `list_report_folders(jmeter_dir)` | 列出目錄下含 index.html 的子目錄 |
| `list_verify_configs(config_dir)` | 列出 verify_config 目錄下的 CSV 檔名 |

### gui.py

tkinter GUI 應用程式，提供：

- 左側控制面板：Jmeter 目錄選擇、verify_config 下拉選單、Headless 開關
- 右側結果表格：逐列顯示 Label、P90、pass_cnt 比對結果
- 底部執行日誌與操作按鈕
- Playwright 在 background worker thread 執行，不會卡住 UI

## 驗證設定檔格式

`verify_config/` 下的 CSV 欄位說明：

| 欄位 | 說明 | 範例 |
|------|------|------|
| `script_name` | 測試腳本名稱前綴 | `CAR_01` |
| `name_rule` | pass_cnt 取值策略，見下表 | `seq` |
| `90th_pct` | 90th 百分位回應時間上限（ms） | `5000` |
| `expected_pass_samples` | 預期通過樣本數 | `15,497` |

### name_rule 策略

| 值 | 說明 |
|----|------|
| `seq` | 以所有步驟中最大編號的 Label 作為代表，檢查其 `pass_cnt` |
| `final` | 以 Label 中包含 `<Final>` 的步驟作為代表，檢查其 `pass_cnt` |
| `single` | 該腳本僅有一個步驟，直接以該唯一 Label 作為代表，檢查其 `pass_cnt` |

每種策略選取代表時都必須 **恰好匹配一個** 目標：

- `seq`：匹配多個步驟是正常行為，最終會選取最高編號的那一筆
- `final`：匹配到 0 個或超過 1 個 `<Final>` Label 均視為失敗
- `single`：匹配到 0 個或超過 1 個 Label 均視為失敗

三種失敗情境的錯誤訊息不同，方便快速定位問題：

| 情境 | 錯誤訊息範例 |
|------|-------------|
| 找不到任何匹配 | `FES_01: No matching labels found in report` |
| `final` 找不到 `<Final>` | `CAR_01: No <Final> label found in report` |
| `final` 匹配多個 `<Final>` | `CAR_01: Multiple <Final> labels found (2), expected exactly one` |
| `single` 匹配多個 Label | `FES_01: Multiple labels found (FES_01, FES_01_extra), expected exactly one for single` |

## 運作原理

1. **`extract_table_data()`** — 使用 Playwright 啟動 Chromium，載入 JMeter HTML 報告，從 `#statisticsTable` 表格中抓取所有行資料，轉為 Pandas DataFrame，並計算 `pass_cnt`（= `#Samples` - `FAIL`）
2. **`read_verify_config()`** — 讀取 CSV 驗證設定檔，轉為 DataFrame
3. **`verify_results()`** — 依設定檔逐腳本比對：
   - 以正則比對 Label 前綴找到所有對應步驟
   - 檢查每個步驟的 P90 是否低於門檻
   - 依 `name_rule` 策略選取代表步驟，驗證匹配唯一性後檢查其通過樣本數是否達標
   - 所有失敗項目累積後一次回傳
4. **`verify_results_detail()`** — 回傳逐列結構化結果，每筆包含 Label、P90 比對、pass_cnt 比對與 check_result

## 授權條款

[Apache License 2.0](LICENSE)
