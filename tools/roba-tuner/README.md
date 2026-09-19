# roBa トラックボール設定ツール

roBa (ZMK / PMW3610トラックボール) 用の個人利用ツール。
トラックボール設定をGUIで編集し、
GitHubへpush → GitHub Actionsでビルド → UF2取得 → ボードへ書き込み、まで行う。

同じroBaを2台所有している場合のために「1号機(roBa) / 2号機(roBa2)」を
画面上部で切り替えられる。それぞれ独立した設定ファイル
(`boards/shields/roBa/roBa_R.conf` / `boards/shields/roBa2/roBa2_R.conf`)
を持ち、キーボード名(PC/BLEに表示される名前)も個別に設定できるので、
2台をPCに接続したときに区別できる。

キーマップ自体の編集は [ZMK Studio](https://zmk.studio/) を使用する
(このリポジトリは `CONFIG_ZMK_STUDIO=y` で対応済み)。

## 事前準備

1. Git / Python 3 がインストール済みであること
2. [GitHub CLI (`gh`)](https://cli.github.com/) がインストール済みで、`gh auth login` でログイン済みであること
3. リポジトリがこのPCにクローンされ、`origin` へpushできる状態であること

## 使い方

```bash
python tools/roba-tuner/main.py
```

1. 起動すると現在の `roBa_R.conf` の内容が読み込まれる
2. CPIやスクロール量などを変更する
3. 「保存してビルド」を押すと、ファイル保存 → commit → push → GitHub Actionsのビルド完了待ち → UF2ダウンロード、まで自動実行される
4. ビルド完了後、roBa右側(トラックボール側)をブートローダーモード(リセット2回押し)にしてから「ボードに書き込み」を押すと、検出したUF2ドライブに書き込む
5. 「ZMK Studioを開く」ボタンで、インストール済みのZMK Studioアプリ(なければWeb版 https://studio.zmk.dev/ )を起動できる

## 注意

- このツールはリポジトリに実際に commit / push する。個人用リポジトリでの利用を前提とする
- ビルドはGitHub Actions上で行うため、push後の完了までインターネット接続とActionsの実行時間(数分程度)が必要
