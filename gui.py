import os
import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Any

from core import (
    BASE_DIR,
    JMETER_REPORT_FOLDER,
    VERIFY_CONFIG_FOLDER,
    OUTPUT_DIR,
    extract_table_data,
    read_verify_config,
    verify_results,
    verify_results_detail,
    list_report_folders,
    list_verify_configs,
)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
BG_DARK = "#0d1b2a"
BG_PANEL = "#1a2332"
BG_CARD = "#162032"
FG_TEXT = "#e0e0e0"
FG_DIM = "#8899aa"
ACCENT = "#00bfa5"
ACCENT_HOVER = "#00e5c4"
ACCENT_DARK = "#007a6a"
PASS_CLR = "#00c853"
FAIL_CLR = "#ff5252"
LOG_BG = "#0a0f1a"
BORDER = "#253545"

WORKER_MSG = "worker_result"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("JMeter 報告通過標準驗證工具")
        self.geometry("1200x760")
        self.minsize(960, 600)
        self.configure(bg=BG_DARK)

        self._result_queue: queue.Queue[Any] = queue.Queue()
        self._worker_running = False

        self._apply_styles()
        self._build_ui()
        self._refresh_configs()

    # ------------------------------------------------------------------
    # Styles
    # ------------------------------------------------------------------
    def _apply_styles(self) -> None:
        s = ttk.Style()
        s.theme_use("clam")

        s.configure(".", background=BG_DARK, foreground=FG_TEXT, fieldbackground=BG_CARD,
                     bordercolor=BORDER, focuscolor=ACCENT)
        s.configure("TFrame", background=BG_DARK)
        s.configure("Panel.TFrame", background=BG_PANEL)
        s.configure("Card.TFrame", background=BG_CARD)
        s.configure("TLabel", background=BG_DARK, foreground=FG_TEXT, font=("Microsoft JhengHei UI", 10))
        s.configure("Header.TLabel", font=("Microsoft JhengHei UI", 16, "bold"), foreground=ACCENT)
        s.configure("Section.TLabel", font=("Microsoft JhengHei UI", 11, "bold"), foreground=FG_TEXT)
        s.configure("Dim.TLabel", foreground=FG_DIM, font=("Microsoft JhengHei UI", 9))

        s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff",
                     font=("Microsoft JhengHei UI", 11, "bold"), padding=(20, 8))
        s.map("Accent.TButton",
               background=[("active", ACCENT_HOVER), ("disabled", ACCENT_DARK)],
               foreground=[("disabled", "#aaaaaa")])

        s.configure("TButton", background=BG_CARD, foreground=FG_TEXT,
                     font=("Microsoft JhengHei UI", 10), padding=(12, 6))
        s.map("TButton", background=[("active", ACCENT_DARK)])

        s.configure("TCheckbutton", background=BG_PANEL, foreground=FG_TEXT,
                     font=("Microsoft JhengHei UI", 10))
        s.map("TCheckbutton", background=[("active", BG_PANEL)])

        s.configure("TCombobox", fieldbackground=BG_CARD, background=BG_CARD,
                     foreground=FG_TEXT, selectbackground=ACCENT_DARK,
                     font=("Microsoft JhengHei UI", 10))
        s.map("TCombobox", fieldbackground=[("readonly", BG_CARD)])

        s.configure("Treeview", background=BG_CARD, foreground=FG_TEXT,
                     fieldbackground=BG_CARD, rowheight=28,
                     font=("Consolas", 10))
        s.configure("Treeview.Heading", background=BG_PANEL, foreground=ACCENT,
                     font=("Microsoft JhengHei UI", 10, "bold"), relief="flat")
        s.map("Treeview", background=[("selected", ACCENT_DARK)],
               foreground=[("selected", "#ffffff")])

        s.configure("Vertical.TScrollbar", background=BG_PANEL, troughcolor=BG_DARK,
                     arrowcolor=FG_DIM)

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # Title bar
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, padx=20, pady=(14, 6))
        ttk.Label(title_frame, text="JMeter 報告通過標準驗證工具",
                  style="Header.TLabel").pack(side=tk.LEFT)

        # Main paned area
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4, 0))

        # --- Left panel ---
        left = ttk.Frame(paned, style="Panel.TFrame", width=300)
        paned.add(left, weight=0)

        # Jmeter directory
        dir_card = ttk.Frame(left, style="Card.TFrame")
        dir_card.pack(fill=tk.X, padx=12, pady=(12, 6))

        ttk.Label(dir_card, text="Jmeter 報告目錄", style="Section.TLabel").pack(
            anchor=tk.W, padx=12, pady=(10, 2))

        dir_inner = ttk.Frame(dir_card, style="Card.TFrame")
        dir_inner.pack(fill=tk.X, padx=12, pady=(0, 10))

        default_jmeter = str(BASE_DIR / JMETER_REPORT_FOLDER)
        self._jmeter_dir_var = tk.StringVar(value=default_jmeter)

        self._dir_label = tk.Label(dir_inner, textvariable=self._jmeter_dir_var,
                                    bg=BG_CARD, fg=FG_DIM, anchor=tk.W,
                                    font=("Consolas", 9), cursor="hand2",
                                    wraplength=220)
        self._dir_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._dir_label.bind("<Button-1>", lambda e: self._pick_jmeter_dir())

        ttk.Button(dir_inner, text="瀏覽", style="TButton",
                   command=self._pick_jmeter_dir).pack(side=tk.RIGHT, padx=(6, 0))

        # Verify config selector
        cfg_card = ttk.Frame(left, style="Card.TFrame")
        cfg_card.pack(fill=tk.X, padx=12, pady=6)

        ttk.Label(cfg_card, text="驗證設定檔", style="Section.TLabel").pack(
            anchor=tk.W, padx=12, pady=(10, 2))

        cfg_inner = ttk.Frame(cfg_card, style="Card.TFrame")
        cfg_inner.pack(fill=tk.X, padx=12, pady=(0, 10))

        self._config_var = tk.StringVar()
        self._config_combo = ttk.Combobox(cfg_inner, textvariable=self._config_var,
                                           state="readonly", width=28)
        self._config_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(cfg_inner, text="↻", style="TButton", width=3,
                   command=self._refresh_configs).pack(side=tk.RIGHT, padx=(6, 0))

        # Headless toggle
        opt_card = ttk.Frame(left, style="Card.TFrame")
        opt_card.pack(fill=tk.X, padx=12, pady=6)

        ttk.Label(opt_card, text="選項", style="Section.TLabel").pack(
            anchor=tk.W, padx=12, pady=(10, 2))

        self._headless_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_card, text="Headless 模式（無瀏覽器畫面）",
                        variable=self._headless_var,
                        style="TCheckbutton").pack(anchor=tk.W, padx=12, pady=(0, 10))

        # Start button
        btn_frame = ttk.Frame(left, style="Panel.TFrame")
        btn_frame.pack(fill=tk.X, padx=12, pady=(10, 12))

        self._start_btn = ttk.Button(btn_frame, text="開始檢查", style="Accent.TButton",
                                      command=self._on_start)
        self._start_btn.pack(fill=tk.X)

        # Status label
        self._status_var = tk.StringVar(value="就緒")
        self._status_label = ttk.Label(left, textvariable=self._status_var,
                                        style="Dim.TLabel")
        self._status_label.pack(anchor=tk.W, padx=14, pady=(0, 8))

        # --- Right panel ---
        right = ttk.Frame(paned, style="TFrame")
        paned.add(right, weight=1)

        # Table
        table_frame = ttk.Frame(right)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=(8, 12), pady=(8, 0))

        cols = ("script_name", "name_rule", "exp_p90", "act_p90", "exp_pass", "act_pass", "result")
        col_labels = {
            "script_name": "script_name",
            "name_rule": "name_rule",
            "exp_p90": "expected_pct_90th",
            "act_p90": "actual_pct_90th",
            "exp_pass": "expected_pass",
            "act_pass": "actual_pass",
            "result": "check_result",
        }
        col_widths = {
            "script_name": 120,
            "name_rule": 80,
            "exp_p90": 120,
            "act_p90": 120,
            "exp_pass": 120,
            "act_pass": 100,
            "result": 340,
        }

        self._tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                   selectmode="none")

        for c in cols:
            self._tree.heading(c, text=col_labels[c])
            anchor = tk.W if c == "script_name" or c == "result" else tk.CENTER
            self._tree.column(c, width=col_widths[c], minwidth=60, anchor=anchor)

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.tag_configure("pass", foreground=PASS_CLR)
        self._tree.tag_configure("fail", foreground=FAIL_CLR)

        # --- Bottom log area ---
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.BOTH, expand=False, padx=16, pady=(6, 10))

        log_card = ttk.Frame(bottom, style="Card.TFrame")
        log_card.pack(fill=tk.BOTH, expand=True)

        ttk.Label(log_card, text="執行日誌", style="Section.TLabel").pack(
            anchor=tk.W, padx=12, pady=(8, 2))

        log_inner = ttk.Frame(log_card, style="Card.TFrame")
        log_inner.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        self._log_text = tk.Text(log_inner, bg=LOG_BG, fg=FG_DIM,
                                  font=("Consolas", 9), wrap=tk.WORD,
                                  insertbackground=FG_DIM, relief=tk.FLAT,
                                  height=6, state=tk.DISABLED)
        log_vsb = ttk.Scrollbar(log_inner, orient=tk.VERTICAL,
                                 command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=log_vsb.set)
        self._log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Bottom action buttons
        action_bar = ttk.Frame(bottom, style="Card.TFrame")
        action_bar.pack(fill=tk.X, padx=0, pady=(0, 6))

        ttk.Button(action_bar, text="開啟輸出資料夾", style="TButton",
                   command=self._open_output_dir).pack(side=tk.LEFT, padx=8, pady=6)
        ttk.Button(action_bar, text="清除結果", style="TButton",
                   command=self._clear_results).pack(side=tk.LEFT, padx=4, pady=6)

    # ------------------------------------------------------------------
    # Config helpers
    # ------------------------------------------------------------------
    def _refresh_configs(self) -> None:
        configs = list_verify_configs()
        self._config_combo["values"] = configs
        if configs:
            self._config_combo.current(0)

    def _pick_jmeter_dir(self) -> None:
        d = filedialog.askdirectory(initialdir=self._jmeter_dir_var.get(),
                                     title="選擇 JMeter 報告目錄")
        if d:
            self._jmeter_dir_var.set(d)
            self._log(f"已選擇 Jmeter 目錄: {d}")

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _log(self, msg: str) -> None:
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.insert(tk.END, msg + "\n")
        self._log_text.see(tk.END)
        self._log_text.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _open_output_dir(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(OUTPUT_DIR))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{OUTPUT_DIR}"')
        else:
            os.system(f'xdg-open "{OUTPUT_DIR}"')

    def _clear_results(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        self._log_text.configure(state=tk.NORMAL)
        self._log_text.delete("1.0", tk.END)
        self._log_text.configure(state=tk.DISABLED)
        self._status_var.set("已清除")

    # ------------------------------------------------------------------
    # Start verification
    # ------------------------------------------------------------------
    def _on_start(self) -> None:
        if self._worker_running:
            return

        jmeter_dir = self._jmeter_dir_var.get().strip()
        config_name = self._config_var.get().strip()

        if not jmeter_dir or not Path(jmeter_dir).is_dir():
            messagebox.showerror("錯誤", "請選擇有效的 JMeter 報告目錄")
            return
        if not config_name:
            messagebox.showerror("錯誤", "請選擇驗證設定檔")
            return

        config_file = str(BASE_DIR / VERIFY_CONFIG_FOLDER / f"{config_name}.csv")
        if not Path(config_file).is_file():
            messagebox.showerror("錯誤", f"找不到設定檔: {config_file}")
            return

        # Find index.html
        # folders = list_report_folders(jmeter_dir)
        # if not folders:
        #     messagebox.showerror("錯誤", f"在 {jmeter_dir} 中找不到包含 index.html 的子目錄")
        #     return

        report_subdir= Path(jmeter_dir).name

        report_path = Path(jmeter_dir) / "index.html"
        if not report_path.is_file():
            messagebox.showerror("錯誤", f"在 {jmeter_dir} 中找不到包含 index.html 的子目錄")
            return

        html_file = str(report_path)

        headless = self._headless_var.get()

        self._worker_running = True
        self._start_btn.configure(state=tk.DISABLED)
        self._status_var.set("正在檢查中，請稍候…")
        self._log(f"開始檢查: {report_subdir}")
        self._log(f"設定檔: {config_name}.csv")
        self._log(f"Headless: {headless}")

        t = threading.Thread(target=self._worker, args=(html_file, config_file, headless),
                              daemon=True)
        t.start()
        self.after(200, self._poll_queue)

    def _worker(self, html_file: str, config_file: str, headless: bool) -> None:
        """Runs in background thread; posts result dict to queue."""
        try:
            self._result_queue.put(("log", "正在載入 JMeter 報告…"))
            df_report = extract_table_data(html_file, headless=headless,
                                            output_dir=OUTPUT_DIR)

            self._result_queue.put(("log", "正在讀取驗證設定…"))
            df_config = read_verify_config(config_file)

            self._result_queue.put(("log", "正在比對結果…"))
            detail = verify_results_detail(df_report, df_config)
            failures = verify_results(df_report, df_config)

            fail_count = sum(1 for r in detail if str(r["check_result"]) != "PASS")
            total = len(detail)
            pass_count = sum(1 for r in detail if str(r["check_result"]) == "PASS")

            if failures:
                self._result_queue.put(("log",
                    f"Verification FAILED ({len(failures)} issues):"))
                for f in failures:
                    self._result_queue.put(("log", f"  - {f}"))
            else:
                self._result_queue.put(("log", "Verification PASSED"))

            self._result_queue.put(("done", detail, fail_count, pass_count, total))
        except Exception as exc:
            self._result_queue.put(("error", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                msg = self._result_queue.get_nowait()
                kind = msg[0]

                if kind == "log":
                    self._log(msg[1])
                elif kind == "error":
                    self._log(f"錯誤: {msg[1]}")
                    self._status_var.set("檢查失敗")
                    self._worker_running = False
                    self._start_btn.configure(state=tk.NORMAL)
                elif kind == "done":
                    detail, fail_count, pass_count, total = msg[1], msg[2], msg[3], msg[4]
                    self._populate_table(detail)
                    if fail_count == 0:
                        status = f"全部通過 ({pass_count}/{total} 項)"
                        self._log(f"✅ {status}")
                    else:
                        status = f"有 {fail_count} 項不合格 (通過 {pass_count}/{total})"
                        self._log(f"❌ {status}")
                    self._status_var.set(status)
                    self._worker_running = False
                    self._start_btn.configure(state=tk.NORMAL)
        except queue.Empty:
            pass

        if self._worker_running:
            self.after(200, self._poll_queue)

    def _populate_table(self, detail: list[dict[str, object]]) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)

        for row in detail:
            script_name = str(row["script_name"])
            name_rule = str(row["name_rule"])
            exp_p90 = str(row["expected_pct_90th"])
            act_p90 = str(row["actual_pct_90th"])
            exp_pass = str(row["expected_pass"])
            act_pass = str(row["actual_pass"])
            result = str(row["check_result"])

            tag = "fail" if result != "PASS" else "pass"

            self._tree.insert("", tk.END, values=(
                script_name, name_rule, exp_p90, act_p90, exp_pass, act_pass, result
            ), tags=(tag,))


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
