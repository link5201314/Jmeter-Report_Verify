from playwright.sync_api import sync_playwright,Browser,Page
import pandas as pd
import re
from typing import Final
import os

JMETER_REPORT_FOLDER: Final[str] = "jmeter_report"
VERIFY_CONFIG_FOLDER: Final[str] = "verify_config"

def extract_table_data(html_file: str) -> pd.DataFrame:
    with sync_playwright() as p:
        # 啟動瀏覽器
        browser:Browser = p.chromium.launch(headless=False, slow_mo=500)
        page:Page = browser.new_page()

        # 訪問本地 HTML 檔案
        page.goto(f"file://{html_file}")

        # -------------------------------------------------------------
        # 1. 抓取【第二組 <tr>】的文字作為 Header
        # .nth(1) 代表索引 1，即第二個元素
        # -------------------------------------------------------------
        header_cells = page.locator('#statisticsTable thead tr').nth(1).locator('th, td')
        headers = header_cells.all_inner_texts()
        # 清理字串中的換行或多餘空白
        headers = [h.strip() for h in headers]

        # -------------------------------------------------------------
        # 2. 抓取【第二組 <tbody>】中的所有列資料
        # -------------------------------------------------------------
        second_tbody_rows = page.locator('#statisticsTable tbody').nth(1).locator('tr')

        data = []
        row_count = second_tbody_rows.count()

        for i in range(row_count):
            row = second_tbody_rows.nth(i)
            # 抓取該列裡的所有表格單元格 (th 或 td)
            cells = row.locator('th, td').all_inner_texts()
            # 整理文字（去除多餘空白）
            clean_cells = [cell.strip() for cell in cells]
            if clean_cells:  # 確保不是空列
                data.append(clean_cells)

        # 等待一下讓使用者看到結果
        page.wait_for_timeout(2000)

        # 關閉瀏覽器
        browser.close()

        # -------------------------------------------------------------
        # 3. 轉為 Pandas DataFrame，並增加pass_cnt欄位
        # -------------------------------------------------------------
        df = pd.DataFrame(data, columns=headers)

        # 1. 確保欄位型別為數字 (如果是從 HTML 抓出來的字串，這步很重要)
        # errors='coerce' 會把無法轉成數字的無效字串變成 NaN
        df['#Samples'] = pd.to_numeric(df['#Samples'], errors='coerce').fillna(0)
        df['FAIL'] = pd.to_numeric(df['FAIL'], errors='coerce').fillna(0)

        # 2. 一次性計算所有 Label 的 pass_cnt 並直接新增為新欄位
        df['pass_cnt'] = df['#Samples'] - df['FAIL']

        # 3. 轉成整數型態 (選擇性)
        df['pass_cnt'] = df['pass_cnt'].astype(int)

        return df

def read_verify_config(config_file: str) -> pd.DataFrame:
    # 將config_file讀入pandas DataFrame
    df = pd.read_csv(config_file)
    return df

def verify_result(df_report: pd.DataFrame, df_config: pd.DataFrame) -> bool:
    # verify actual_pass > expected_pass
    for _, row in df_config.iterrows():
        label = row['script_name']
        expected_pass = row['expected_pass_samples']
        actual_pass = df_report.loc[df_report['Label'] == label, 'pass_cnt'].values[0]
        if actual_pass < expected_pass:
            return False

    # verify actual_pct_90th > expected_pct_90th
    for _, row in df_config.iterrows():
        label = row['script_name']
        expected_pct_90th = row['expected_pct_90th']
        actual_pct_90th = df_report.loc[df_report['Label'] == label, '90th pct'].values[0]
        if actual_pct_90th < expected_pct_90th:
            return False

    return True

if __name__ == "__main__":
    # 取得當前檔案的絕對路徑
    current_dir:str = os.path.dirname(os.path.abspath(__file__))

    html_file:str = os.path.join(current_dir, JMETER_REPORT_FOLDER, "core_PT_1__report-core_PT_1-2026-07-21_154922", "index.html")
    print(html_file)

    df_report = extract_table_data(html_file)
    print(df_report)

    # Label規則: [script_name]-[step].*
    pass_cnt = df_report.loc[df_report['Label'] == 'VIL_04-06_點擊查詢', 'pass_cnt'].values[0]

    pct_90th = df_report.loc[df_report['Label'] == 'VIL_04-06_點擊查詢', '90th pct'].values[0]

    print(pass_cnt)
    print(pct_90th)

    config_file = os.path.join(current_dir, VERIFY_CONFIG_FOLDER, "core_PT_1.csv")
    df_config = read_verify_config(config_file)
    print(df_config)

    result = verify_result(df_report, df_config)
    print("verify_result=", result)
