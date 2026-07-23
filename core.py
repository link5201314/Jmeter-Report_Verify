from playwright.sync_api import sync_playwright, Browser, Page
import pandas as pd
import re
from typing import Final, cast
import os
from pathlib import Path
import time


JMETER_REPORT_FOLDER: Final[str] = "jmeter_report"
VERIFY_CONFIG_FOLDER: Final[str] = "verify_config"
BASE_DIR: Final[Path] = Path(__file__).resolve().parent
OUTPUT_DIR: Final[Path] = BASE_DIR / "output"

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(BASE_DIR / "ms-playwright")


def extract_table_data(
    html_file: str,
    headless: bool = True,
    output_dir: Path = OUTPUT_DIR,
) -> pd.DataFrame:
    output_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(headless=headless, slow_mo=500)
        page: Page = browser.new_page()

        page.goto(f"file://{html_file}")

        header_cells = page.locator('#statisticsTable thead tr').nth(1).locator('th, td')
        headers = header_cells.all_inner_texts()
        headers = [h.strip() for h in headers]

        second_tbody_rows = page.locator('#statisticsTable tbody').nth(1).locator('tr')

        data = []
        row_count = second_tbody_rows.count()

        for i in range(row_count):
            row = second_tbody_rows.nth(i)
            cells = row.locator('th, td').all_inner_texts()
            clean_cells = [cell.strip() for cell in cells]
            if clean_cells:
                data.append(clean_cells)

        page.wait_for_timeout(2000)

        screenshot = output_dir / f"check_{int(time.time())}.png"
        page.screenshot(path=str(screenshot), full_page=True)

        browser.close()

    df = pd.DataFrame(data, columns=headers)

    df['#Samples'] = pd.to_numeric(df['#Samples'], errors='coerce').fillna(0)  # type: ignore
    df['FAIL'] = pd.to_numeric(df['FAIL'], errors='coerce').fillna(0)  # type: ignore
    df['90th pct'] = pd.to_numeric(df['90th pct'], errors='coerce').fillna(0)  # type: ignore

    df['pass_cnt'] = df['#Samples'] - df['FAIL']
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


def _select_pass_row(
    matching: pd.DataFrame,
    script_name: str,
    name_rule: str,
) -> tuple[pd.Series | None, str | None]:
    """Select the representative row for pass_cnt check.

    Returns ``(selected_row, error_message)``.
    *error_message* is ``None`` on success.
    """
    if name_rule == "final":
        final_matching = matching[matching["Label"].str.contains("<Final>", regex=False)]
        if len(final_matching) == 0:
            return None, f"{script_name}: No <Final> label found in report"
        if len(final_matching) > 1:
            return None, (
                f"{script_name}: Multiple <Final> labels found ({len(final_matching)}), "
                "expected exactly one"
            )
        return final_matching.iloc[0], None

    if name_rule == "single":
        if len(matching) == 0:
            return None, f"{script_name}: No matching labels found in report"
        if len(matching) > 1:
            labels = ", ".join(matching["Label"].tolist())
            return None, (
                f"{script_name}: Multiple labels found ({labels}), "
                "expected exactly one for single"
            )
        return matching.iloc[0], None

    # seq
    max_label_idx = matching["Label"].apply(
        lambda lb: _extract_step_tuple(lb, script_name)
    ).idxmax()
    return matching.loc[max_label_idx], None


def verify_results(df_report: pd.DataFrame, df_config: pd.DataFrame) -> list[str]:
    failures: list[str] = []

    for _, row in df_config.iterrows():
        script_name: str = str(row['script_name'])
        name_rule: str = str(row['name_rule'])
        expected_pct_90th: int = int(str(row['90th_pct']))
        expected_pass: int = int(str(row['expected_pass_samples']))

        if name_rule == "single":
            pattern = f"^{re.escape(script_name)}"
        else:
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

        pass_row, select_err = _select_pass_row(cast(pd.DataFrame, matching), script_name, name_rule)
        if select_err is not None:
            failures.append(select_err)
            continue

        actual_pass = int(pass_row['pass_cnt'])  # type: ignore[union-attr]
        if actual_pass < expected_pass:
            failures.append(
                f"{pass_row['Label']}: pass_cnt ({actual_pass}) < expected ({expected_pass})"  # type: ignore[index]
            )

    return failures


# ---------------------------------------------------------------------------
# Detailed results for GUI table display (per script_name)
# ---------------------------------------------------------------------------

def verify_results_detail(
    df_report: pd.DataFrame,
    df_config: pd.DataFrame,
) -> list[dict[str, object]]:
    """Return structured per-script_name verification results for GUI display.

    Each dict contains:
        script_name, name_rule, expected_pct_90th, actual_pct_90th,
        expected_pass, actual_pass, check_result

    *actual_pct_90th* is ``"PASS"`` when every step passes, otherwise the
    largest failing pct_90th value.  *check_result* aggregates all failure
    reasons including name_rule matching errors.
    """
    results: list[dict[str, object]] = []

    for _, row in df_config.iterrows():
        script_name: str = str(row['script_name'])
        name_rule: str = str(row['name_rule'])
        expected_pct_90th: int = int(str(row['90th_pct']))
        expected_pass: int = int(str(row['expected_pass_samples']))

        if name_rule == "single":
            pattern = f"^{re.escape(script_name)}"
        else:
            pattern = f"^{re.escape(script_name)}-"

        matching = df_report[df_report['Label'].str.match(pattern)]

        checks: list[str] = []

        # --- P90 check across all matched labels ---
        max_failing_p90: int | None = None
        if matching.empty:
            checks.append("No matching labels found in report")
        else:
            for _, report_row in matching.iterrows():
                actual_p90 = int(report_row['90th pct'])
                if actual_p90 >= expected_pct_90th:
                    if max_failing_p90 is None or actual_p90 > max_failing_p90:
                        max_failing_p90 = actual_p90
            if max_failing_p90 is not None:
                checks.append(
                    f"90th pct FAIL (max {max_failing_p90} >= {expected_pct_90th})"
                )

        # --- pass_cnt check via name_rule strategy ---
        actual_pass: object = "-"
        if not matching.empty:
            pass_row, select_err = _select_pass_row(
                cast(pd.DataFrame, matching), script_name, name_rule
            )
            if select_err is not None:
                checks.append(select_err)
            else:
                actual_pass_val = int(pass_row['pass_cnt'])  # type: ignore[union-attr]
                actual_pass = actual_pass_val
                if actual_pass_val < expected_pass:
                    checks.append(
                        f"pass_cnt ({actual_pass_val}) < expected ({expected_pass})"
                    )

        actual_pct_90th_display: object = "PASS" if max_failing_p90 is None else max_failing_p90
        check_result = "PASS" if not checks else "; ".join(checks)

        results.append({
            "script_name": script_name,
            "name_rule": name_rule,
            "expected_pct_90th": expected_pct_90th,
            "actual_pct_90th": actual_pct_90th_display,
            "expected_pass": expected_pass,
            "actual_pass": actual_pass,
            "check_result": check_result,
        })

    return results


def list_report_folders(jmeter_dir: str) -> list[str]:
    """List subdirectories under jmeter_dir that contain index.html."""
    jmeter_path = Path(jmeter_dir)
    if not jmeter_path.is_dir():
        return []
    folders: list[str] = []
    for child in sorted(jmeter_path.iterdir()):
        if child.is_dir() and (child / "index.html").exists():
            folders.append(child.name)
    return folders


def list_verify_configs(config_dir: str | None = None) -> list[str]:
    """List .csv files under the verify_config directory."""
    cfg_path = Path(config_dir) if config_dir else BASE_DIR / VERIFY_CONFIG_FOLDER
    if not cfg_path.is_dir():
        return []
    return sorted(f.stem for f in cfg_path.iterdir() if f.suffix == ".csv")
