"""roBa トラックボール設定ツール

トラックボール(PMW3610)のKconfig設定をGUIで編集し、
GitHubへpush -> GitHub Actionsでビルド -> UF2をダウンロード -> 書き込み、
までを行う。roBa/ZMK設定リポジトリ専用の個人用ツール。
"""
from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

import flash
import github_build
import zmk_studio
from kconfig import TUNABLES, KconfigFile

REPO_ROOT = Path(__file__).resolve().parents[2]
CONF_PATH = REPO_ROOT / "boards" / "shields" / "roBa" / "roBa_R.conf"
CONF_RELATIVE = "boards/shields/roBa/roBa_R.conf"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("roBa トラックボール設定ツール")
        self.geometry("640x760")

        self.bool_vars: dict[str, tk.BooleanVar] = {}
        self.int_vars: dict[str, tk.StringVar] = {}
        self.enable_vars: dict[str, tk.BooleanVar] = {}
        self.last_download_dir: Path | None = None

        self._build_widgets()
        self.load_from_file()

    # ---------- UI構築 ----------
    def _build_widgets(self) -> None:
        header = ttk.Label(self, text=f"編集対象: {CONF_RELATIVE}", font=("", 9))
        header.pack(fill="x", padx=10, pady=(10, 0))

        canvas = tk.Canvas(self, borderwidth=0)
        frame = ttk.Frame(canvas)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="top", fill="both", expand=True, padx=10, pady=10)
        canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        for spec in TUNABLES:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=4)

            if spec.kind == "bool":
                var = tk.BooleanVar()
                self.bool_vars[spec.key] = var
                ttk.Checkbutton(row, text=spec.label, variable=var).pack(side="left")
            else:
                if spec.optional:
                    enable_var = tk.BooleanVar()
                    self.enable_vars[spec.key] = enable_var
                    ttk.Checkbutton(row, text="有効", variable=enable_var).pack(side="left")
                ttk.Label(row, text=spec.label, width=28).pack(side="left")
                var = tk.StringVar()
                self.int_vars[spec.key] = var
                ttk.Entry(row, textvariable=var, width=10).pack(side="left")
                ttk.Label(row, text=f"({spec.min_value}〜{spec.max_value})", foreground="#888").pack(side="left")

            if spec.help:
                ttk.Label(frame, text="  " + spec.help, foreground="#666", font=("", 8)).pack(
                    fill="x", pady=(0, 2)
                )

        btn_row = ttk.Frame(self)
        btn_row.pack(fill="x", padx=10, pady=(0, 5))
        ttk.Button(btn_row, text="ファイルから読み込み直す", command=self.load_from_file).pack(side="left")
        ttk.Button(btn_row, text="保存してビルド", command=self.save_and_build).pack(side="left", padx=5)
        ttk.Button(btn_row, text="ボードに書き込み", command=self.flash_board).pack(side="left")
        ttk.Button(btn_row, text="ZMK Studioを開く（キーマップ編集）", command=self.open_zmk_studio).pack(
            side="left", padx=5
        )

        self.log_box = scrolledtext.ScrolledText(self, height=12, state="disabled")
        self.log_box.pack(fill="both", expand=False, padx=10, pady=(0, 10))

    def log(self, message: str) -> None:
        def _append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, _append)

    # ---------- ファイル読み書き ----------
    def load_from_file(self) -> None:
        kconfig = KconfigFile(CONF_PATH)
        for spec in TUNABLES:
            if spec.kind == "bool":
                self.bool_vars[spec.key].set(kconfig.get_bool(spec.key))
            else:
                value, enabled = kconfig.get_int(spec.key, spec.default)
                self.int_vars[spec.key].set(str(value))
                if spec.optional:
                    self.enable_vars[spec.key].set(enabled)
        self.log("設定ファイルを読み込みました")

    def _apply_to_kconfig(self, kconfig: KconfigFile) -> None:
        for spec in TUNABLES:
            if spec.kind == "bool":
                kconfig.set_bool(spec.key, self.bool_vars[spec.key].get())
            else:
                raw = self.int_vars[spec.key].get().strip()
                try:
                    value = int(raw)
                except ValueError:
                    raise ValueError(f"{spec.label} は整数で入力してください (入力値: {raw!r})")
                if not (spec.min_value <= value <= spec.max_value):
                    raise ValueError(
                        f"{spec.label} は {spec.min_value}〜{spec.max_value} の範囲で入力してください"
                    )
                enabled = self.enable_vars[spec.key].get() if spec.optional else True
                kconfig.set_int(spec.key, value, enabled=enabled)

    # ---------- ボタン動作 ----------
    def save_and_build(self) -> None:
        try:
            kconfig = KconfigFile(CONF_PATH)
            self._apply_to_kconfig(kconfig)
        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            return

        kconfig.save()
        self.log("設定ファイルを保存しました")

        if not github_build.has_changes(REPO_ROOT, CONF_RELATIVE):
            self.log("変更がないため、ビルドはスキップします")
            return

        threading.Thread(target=self._build_worker, daemon=True).start()

    def _build_worker(self) -> None:
        try:
            sha = github_build.commit_and_push(
                REPO_ROOT, CONF_RELATIVE, "roba-tuner: トラックボール設定を更新", self.log
            )
            run = github_build.wait_for_run(REPO_ROOT, sha, self.log)
            dest = REPO_ROOT / "tools" / "roba-tuner" / "_downloads" / str(run["databaseId"])
            github_build.download_artifacts(REPO_ROOT, run["databaseId"], dest, self.log)
            self.last_download_dir = dest
            uf2_files = github_build.find_uf2_files(dest)
            self.log(f"ビルド完了。取得したUF2: {[p.name for p in uf2_files]}")
            self.log("「ボードに書き込み」ボタンで書き込みができます")
        except Exception as e:  # noqa: BLE001
            self.log(f"エラー: {e}")
            messagebox.showerror("ビルドエラー", str(e))

    def open_zmk_studio(self) -> None:
        zmk_studio.open_zmk_studio(self.log)

    def flash_board(self) -> None:
        if not self.last_download_dir:
            messagebox.showinfo("書き込み", "先に「保存してビルド」を実行してください")
            return
        uf2_files = [p for p in github_build.find_uf2_files(self.last_download_dir) if "roBa_R" in p.name]
        if not uf2_files:
            uf2_files = github_build.find_uf2_files(self.last_download_dir)
        if not uf2_files:
            messagebox.showerror("書き込み", "UF2ファイルが見つかりません")
            return

        uf2_path = uf2_files[0]
        self.log(f"書き込み対象: {uf2_path.name}")
        self.log("ボード右側(roBa_R)のリセットボタンを2回押してブートローダーモードにしてください")
        threading.Thread(target=self._flash_worker, args=(uf2_path,), daemon=True).start()

    def _flash_worker(self, uf2_path: Path) -> None:
        import time

        self.log("UF2ドライブの出現を待っています... (最大60秒)")
        drive = None
        for _ in range(60):
            drive = flash.find_uf2_drive()
            if drive:
                break
            time.sleep(1)

        if not drive:
            self.log("ブートローダードライブが見つかりませんでした")
            messagebox.showerror("書き込み", "ブートローダードライブが見つかりませんでした")
            return

        self.log(f"ドライブを検出: {drive}")
        flash.flash(uf2_path, drive)
        self.log("書き込み完了。ボードが自動的に再起動します")


if __name__ == "__main__":
    App().mainloop()
