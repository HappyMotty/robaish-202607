"""build.yaml内の特定エントリ(artifact-name)のcmake-argsを、
KconfigFileと同じインターフェース(get_bool/get_int/get_str/set_*/save)で
読み書きするクラス。2号機のように「同じシールドをcmake-argsで上書きする」
形式で管理している設定を、kconfig.KconfigFileと同じコードで編集できるようにする。
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path


class CmakeArgsStore:
    def __init__(self, path: Path, artifact_name: str):
        self.path = path
        self.artifact_name = artifact_name
        self.lines: list[str] = path.read_text(encoding="utf-8").splitlines()
        self._line_index = self._find_cmake_args_line()
        self._values: dict[str, str] = self._parse(self.lines[self._line_index])

    def _find_cmake_args_line(self) -> int:
        target = f"artifact-name: {self.artifact_name}"
        for i, line in enumerate(self.lines):
            if line.strip() == target:
                for j in list(range(i - 1, max(i - 5, -1), -1)) + list(range(i + 1, min(i + 5, len(self.lines)))):
                    if "cmake-args:" in self.lines[j]:
                        return j
                raise ValueError(f"{self.artifact_name} の cmake-args 行が見つかりません")
        raise ValueError(f"artifact-name: {self.artifact_name} が {self.path} に見つかりません")

    @staticmethod
    def _parse(line: str) -> dict[str, str]:
        _, _, raw = line.partition("cmake-args:")
        values: dict[str, str] = {}
        for token in shlex.split(raw.strip()):
            if not token.startswith("-D"):
                continue
            key, _, value = token[2:].partition("=")
            values[key] = value
        return values

    def get_bool(self, key: str) -> bool:
        return self._values.get(key) == "y"

    def get_int(self, key: str, default: int) -> tuple[int, bool]:
        raw = self._values.get(key)
        if raw is None:
            return default, False
        try:
            return int(raw), True
        except ValueError:
            return default, True

    def get_str(self, key: str, default: str) -> str:
        raw = self._values.get(key)
        if raw is None:
            return default
        return raw.strip('"')

    def set_bool(self, key: str, value: bool) -> None:
        self._values[key] = "y" if value else "n"

    def set_int(self, key: str, value: int, enabled: bool = True) -> None:
        if enabled:
            self._values[key] = str(value)
        else:
            self._values.pop(key, None)

    def set_str(self, key: str, value: str) -> None:
        self._values[key] = f'"{value}"'

    def save(self) -> None:
        indent_match = re.match(r"^(\s*)cmake-args:", self.lines[self._line_index])
        indent = indent_match.group(1) if indent_match else "   "

        parts = []
        for key, value in self._values.items():
            if value.startswith('"') and value.endswith('"'):
                parts.append(f"-D{key}='{value}'")
            else:
                parts.append(f"-D{key}={value}")

        self.lines[self._line_index] = f"{indent}cmake-args: {' '.join(parts)}"
        text = "\n".join(self.lines) + "\n"
        self.path.write_text(text, encoding="utf-8")
