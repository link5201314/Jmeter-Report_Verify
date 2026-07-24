import argparse
import os
from core import (
    BASE_DIR,
    JMETER_REPORT_FOLDER,
    VERIFY_CONFIG_FOLDER,
    OUTPUT_DIR,
    extract_table_data,
    read_verify_config,
    verify_results,
)


def parse_args() -> argparse.Namespace:
    default_report = str(
        BASE_DIR / JMETER_REPORT_FOLDER
        / "core_PT_1__report-core_PT_1-2026-07-21_154922"
    )
    parser = argparse.ArgumentParser(
        description="JMeter 報告通過標準驗證工具（CLI）"
    )
    parser.add_argument(
        "--report",
        default=default_report,
        help="JMeter 報告目錄路徑（預設: %(default)s）",
    )
    parser.add_argument(
        "--config",
        default="core_PT_1",
        help="驗證設定檔名，不含 .csv 副檔名（預設: %(default)s）",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="使用 headless 模式執行 Playwright（預設: 顯示瀏覽器）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    report_dir = args.report
    html_file = os.path.join(report_dir, "index.html")
    if not os.path.isfile(html_file):
        print(f"錯誤: 找不到報告檔案 {html_file}")
        return

    config_file = os.path.join(
        str(BASE_DIR), VERIFY_CONFIG_FOLDER, f"{args.config}.csv"
    )
    if not os.path.isfile(config_file):
        print(f"錯誤: 找不到設定檔 {config_file}")
        return

    out = OUTPUT_DIR
    out.mkdir(exist_ok=True)

    print(f"報告目錄: {report_dir}")
    print(f"設定檔: {args.config}.csv")
    print(f"Headless: {args.headless}")

    df_report = extract_table_data(html_file, headless=args.headless, output_dir=out)
    df_config = read_verify_config(config_file)

    failures = verify_results(df_report, df_config)
    if failures:
        print(f"Verification FAILED ({len(failures)} issues):")
        for f in failures:
            print(f"  - {f}")
    else:
        print("Verification PASSED")


if __name__ == "__main__":
    main()
