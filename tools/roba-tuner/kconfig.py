"""roBa_R.conf (Kconfig) の読み書きを行うモジュール。

既知のキー以外の行はそのまま保持し、対象キーの行だけを書き換える。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_LINE_RE = re.compile(r"^(?P<comment>#\s*)?(?P<key>CONFIG_[A-Z0-9_]+)=(?P<value>.+?)\s*$")


@dataclass
class TunableSpec:
    key: str
    label: str
    kind: str  # "bool" / "int" / "str"
    optional: bool = False  # True: ファイル内でコメントアウトされた状態が「無効」を意味する
    default: int | str = 0
    min_value: int = 0
    max_value: int = 65535
    help: str = ""


TUNABLES: list[TunableSpec] = [
    TunableSpec("CONFIG_ZMK_KEYBOARD_NAME", "キーボード名 (PC/BLEに表示される名前)", "str",
                default="roBa",
                help="2台のキーボードを区別するための表示名。PCのBluetooth一覧やZMK Studioに表示される"),
    TunableSpec("CONFIG_PMW3610_CPI", "CPI (感度)", "int", default=800, min_value=200, max_value=3200,
                help="200〜3200。大きいほどカーソルが速く動く"),
    TunableSpec("CONFIG_PMW3610_CPI_DIVIDOR", "CPI分周比", "int", default=1, min_value=1, max_value=8,
                help="実効CPI = CPI / この値"),
    TunableSpec("CONFIG_PMW3610_ORIENTATION_180", "180度回転", "bool",
                help="トラックボールの取り付け向きが逆の場合に有効化"),
    TunableSpec("CONFIG_PMW3610_INVERT_X", "X軸反転", "bool"),
    TunableSpec("CONFIG_PMW3610_INVERT_SCROLL_X", "スクロール時X軸反転", "bool"),
    TunableSpec("CONFIG_PMW3610_SCROLL_TICK", "スクロール感度(tick)", "int", default=16, min_value=1, max_value=64,
                help="値が小さいほどスクロールが速い"),
    TunableSpec("CONFIG_PMW3610_AUTOMOUSE_TIMEOUT_MS", "オートマウスレイヤー タイムアウト(ms)", "int",
                default=700, min_value=100, max_value=10000),
    TunableSpec("CONFIG_PMW3610_RUN_DOWNSHIFT_TIME_MS", "低消費電力移行時間(ms)", "int",
                default=3264, min_value=100, max_value=30000),
    TunableSpec("CONFIG_PMW3610_REST1_SAMPLE_TIME_MS", "低消費電力時サンプル間隔(ms)", "int",
                default=20, min_value=1, max_value=1000),
    TunableSpec("CONFIG_PMW3610_MOVEMENT_THRESHOLD", "移動検出しきい値", "int",
                default=0, min_value=0, max_value=255,
                help="小さな揺れを無視したい場合に増やす"),
    TunableSpec("CONFIG_PMW3610_SMART_ALGORITHM", "スマートアルゴリズム", "bool"),
    TunableSpec("CONFIG_PMW3610_POLLING_RATE_125_SW", "125Hzポーリング(ソフトウェア)", "bool"),
    TunableSpec("CONFIG_PMW3610_SNIPE_CPI", "スナイプモード CPI", "int", optional=True,
                default=800, min_value=100, max_value=3200,
                help="有効化すると低速精密モード用のCPIを別途指定できる"),
    TunableSpec("CONFIG_PMW3610_SNIPE_CPI_DIVIDOR", "スナイプモード CPI分周比", "int", optional=True,
                default=4, min_value=1, max_value=8),
    TunableSpec("CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_MIN_FACTOR", "ポインタ加速: 低速時倍率(%)", "int",
                default=100, min_value=10, max_value=1000,
                help="ゆっくり動かした時の倍率。100=等倍"),
    TunableSpec("CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_MAX_FACTOR", "ポインタ加速: 高速時倍率(%)", "int",
                default=100, min_value=10, max_value=1000,
                help="素早く動かした時の倍率。低速時倍率と同じにすると加速なし"),
    TunableSpec("CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_SPEED_MIN", "ポインタ加速: 開始しきい値(count/report)", "int",
                default=3, min_value=0, max_value=200,
                help="この移動量以下では低速時倍率が適用される"),
    TunableSpec("CONFIG_ZMK_INPUT_PROCESSOR_ACCEL_SPEED_MAX", "ポインタ加速: 最大到達しきい値(count/report)", "int",
                default=18, min_value=1, max_value=200,
                help="この移動量以上では高速時倍率が適用される(間は線形補間)"),
]


class KconfigFile:
    def __init__(self, path: Path):
        self.path = path
        self.lines: list[str] = path.read_text(encoding="utf-8").splitlines()

    def _find(self, key: str) -> tuple[int, bool, str] | None:
        """(line_index, commented, value) を返す。見つからなければ None。"""
        for i, line in enumerate(self.lines):
            m = _LINE_RE.match(line)
            if m and m.group("key") == key:
                return i, m.group("comment") is not None, m.group("value")
        return None

    def get_bool(self, key: str) -> bool:
        found = self._find(key)
        if not found:
            return False
        _, commented, value = found
        return (not commented) and value == "y"

    def get_int(self, key: str, default: int) -> tuple[int, bool]:
        """(値, 有効か) を返す。無効(コメントアウト)でも値自体は読める。"""
        found = self._find(key)
        if not found:
            return default, False
        _, commented, value = found
        try:
            return int(value), not commented
        except ValueError:
            return default, not commented

    def set_bool(self, key: str, value: bool) -> None:
        found = self._find(key)
        new_line = f"{key}={'y' if value else 'n'}"
        if found:
            i, _, _ = found
            self.lines[i] = new_line
        elif value:
            self.lines.append(new_line)

    def get_str(self, key: str, default: str) -> str:
        found = self._find(key)
        if not found:
            return default
        _, commented, value = found
        if commented:
            return default
        return value.strip('"')

    def set_str(self, key: str, value: str) -> None:
        found = self._find(key)
        new_line = f'{key}="{value}"'
        if found:
            i, _, _ = found
            self.lines[i] = new_line
        else:
            self.lines.append(new_line)

    def set_int(self, key: str, value: int, enabled: bool = True) -> None:
        found = self._find(key)
        new_line = f"{key}={value}"
        if not enabled:
            new_line = f"# {new_line}"
        if found:
            i, _, _ = found
            self.lines[i] = new_line
        else:
            self.lines.append(new_line)

    def save(self) -> None:
        text = "\n".join(self.lines) + "\n"
        self.path.write_text(text, encoding="utf-8")
