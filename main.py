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
        df['#Samples'] = pd.to_numeric(df['#Samples'], errors='coerce').fillna(0) # type: ignore
        df['FAIL'] = pd.to_numeric(df['FAIL'], errors='coerce').fillna(0) # type: ignore
        df['90th pct'] = pd.to_numeric(df['90th pct'], errors='coerce').fillna(0) # type: ignore

        # 2. 一次性計算所有 Label 的 pass_cnt 並直接新增為新欄位
        df['pass_cnt'] = df['#Samples'] - df['FAIL']

        # 3. 轉成整數型態 (選擇性)
        df['pass_cnt'] = df['pass_cnt'].astype(int)

        return df

def read_verify_config(config_file: str) -> pd.DataFrame:
    df = pd.read_csv(config_file)
    df['expected_pass_samples'] = (
        df['expected_pass_samples']
        .astype(str)
        .str.replace(',', '', regex=False)
        .astype(int)
    )
    return df

def _extract_step_tuple(label: str, script_name: str) -> tuple[int, ...]:
    step_match = re.search(
        rf'(?<={re.escape(script_name)}-)[0-9_\-]+(?=_[^0-9_])', label
    )
    if step_match:
        parts = re.split(r'[_\-]', step_match.group())
        return tuple(int(p) for p in parts)
    return (-1,)


def verify_results(df_report: pd.DataFrame, df_config: pd.DataFrame) -> list[str]:
    failures: list[str] = []

    for _, row in df_config.iterrows():
        script_name: str = str(row['script_name'])
        expected_pct_90th: int = int(str(row['90th_pct']))
        expected_pass: int = int(str(row['expected_pass_samples']))

        pattern = f"^{re.escape(script_name)}-"
        matching = df_report[df_report['Label'].str.match(pattern)]

        if matching.empty:
            failures.append(f"{script_name}: No matching labels found in report")
            continue

        for _, report_row in matching.iterrows():
            label = report_row['Label']
            actual_pct_90th = report_row['90th pct']
            if actual_pct_90th >= expected_pct_90th:
                failures.append(
                    f"{label}: 90th pct ({actual_pct_90th}) >= expected ({expected_pct_90th})"
                )

        max_label_idx = matching.Label.apply(
            lambda lb: _extract_step_tuple(lb, script_name)
        ).idxmax()
        max_label_row = matching.loc[max_label_idx]
        actual_pass = max_label_row['pass_cnt']

        if actual_pass < expected_pass:
            failures.append(
                f"{max_label_row['Label']}: pass_cnt ({actual_pass}) < expected ({expected_pass})"
            )

    return failures

if __name__ == "__main__":
    current_dir: str = os.path.dirname(os.path.abspath(__file__))

    html_file: str = os.path.join(
        current_dir, JMETER_REPORT_FOLDER,
        "core_PT_1__report-core_PT_1-2026-07-21_154922", "index.html"
    )
    df_report = extract_table_data(html_file)

    config_file = os.path.join(current_dir, VERIFY_CONFIG_FOLDER, "core_PT_1.csv")
    df_config = read_verify_config(config_file)

    failures = verify_results(df_report, df_config)
    if failures:
        print(f"Verification FAILED ({len(failures)} issues):")
        for f in failures:
            print(f"  - {f}")
    else:
        print("Verification PASSED")
