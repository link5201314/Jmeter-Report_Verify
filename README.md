# JMeter Report Verify

自動化比對 JMeter 效能測試報告與預設驗收標準的工具。

## 功能簡介

本工具讀取 JMeter 產生的 HTML Dashboard 報告，自動提取效能統計數據，並依據 CSV 驗證設定檔進行以下兩項檢查：

1. **90th 百分位回應時間檢查** — 各腳本所有步驟的 P90 回應時間是否低於門檻值
2. **通過樣本數檢查** — 各腳本最終步驟的成功請求數是否達到預期數量

檢查完成後輸出 **PASSED** 或列出所有不合格項目。

## 環境需求

- Python >= 3.12
- [uv](https://github.com/astral-sh/uv) 套件管理工具

## 安裝與啟動

```bash
# 1. 安裝依賴
uv sync

# 2. 安裝 Playwright 瀏覽器
uv run playwright install chromium

# 3. 執行驗證
uv run main.py
```

## 專案結構

```
.
├── main.py                  # 主程式，包含報告抓取、設定檔讀取與驗證邏輯
├── pyproject.toml           # 專案依賴設定
├── verify_config/           # 驗證標準 CSV 設定檔
│   └── core_PT_1.csv        # 各腳本的 P90 門檻與預期通過樣本數
└── jmeter_report/           # JMeter 產出的 HTML 報告目錄
    └── core_PT_1__report-core_PT_1-2026-07-21_154922/
        └── index.html       # JMeter HTML Dashboard 報告
```

## 驗證設定檔格式

`verify_config/` 下的 CSV 欄位說明：

| 欄位 | 說明 | 範例 |
|------|------|------|
| `script_name` | 測試腳本名稱前綴 | `CAR_01` |
| `90th_pct` | 90th 百分位回應時間上限（ms） | `5000` |
| `expected_pass_samples` | 最終步驟預期通過樣本數 | `15,497` |

## 運作原理

1. **`extract_table_data()`** — 使用 Playwright 啟動 Chromium，載入 JMeter HTML 報告，從 `#statisticsTable` 表格中抓取所有行資料，轉為 Pandas DataFrame，並計算 `pass_cnt`（= `#Samples` - `FAIL`）
2. **`read_verify_config()`** — 讀取 CSV 驗證設定檔，轉為 DataFrame
3. **`verify_results()`** — 依設定檔逐腳本比對：
   - 以正則比對 Label 前綴找到所有對應步驟
   - 檢查每個步驟的 P90 是否低於門檻
   - 找出最大步驟編號的 Label，檢查其通過樣本數是否達標
   - 所有失敗項目累積後一次回傳

## 授權條款

[Apache License 2.0](LICENSE)
