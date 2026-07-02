# Zed 日本語化ビルド運用メモ

## 目標

Zed の軽さと更新頻度を維持しながら、自分の環境で日本語化ビルドを使う。

このツールは Zed 本体を永続 fork しない。公式 stable の更新を先に受け取り、
その時点でインストールされている Zed の commit に対して日本語化を再適用する。

## 基本方針

- 公式 Zed はそのまま残す。
- 公式 Zed の実行ファイルを直接書き換えない。
- DLL injection や UI hook は使わない。
- 日本語化はビルド時にソースへ適用する。
- 日本語化ビルドは side-by-side で別ディレクトリに置く。
- Zed 更新後は `update --install` を再実行する。

## 通常の流れ

公式 Zed をいつも通り更新したあと、次を実行する。

```sh
python3 scripts/zed_japanese.py update --install
```

内部では次の順に動く。

1. `zed --version` から公式 Zed の version と commit を取得する。
2. `.cache/zed-upstream` に upstream Zed を取得する。
3. 公式 Zed と同じ commit に checkout する。
4. `translations/ja-JP.json` の翻訳を適用する。
5. `cargo build --release` でビルドする。
6. 成果物を side-by-side のローカルディレクトリへコピーする。

## 状態確認

```sh
python3 scripts/zed_japanese.py status
```

確認できるもの:

- 検出した Zed version / commit
- upstream source が同じ commit を向いているか
- 翻訳エントリ数
- 最後の install manifest の有無
- WSL 上で動いているか

## Windows と WSL

WSL から Windows 版 Zed を検出することはできる。

ただし WSL で `cargo build` すると Linux 向けビルドになる。Windows 版の
日本語化 Zed を作る場合は、Windows 側の Rust / Python 環境でこのツールを
実行する。

## インストール先

デフォルト:

- Windows Python: `%LOCALAPPDATA%\Programs\Zed Japanese`
- Linux/macOS/WSL Python: `~/.local/zed-japanese`

任意の場所に置く場合:

```sh
python3 scripts/zed_japanese.py install --dest ~/apps/zed-japanese
```

既存の同名ファイルがある場合は `.bak` を付けて退避してからコピーする。

## 更新運用

おすすめの運用:

1. 公式 Zed を通常どおり更新する。
2. `python3 scripts/zed_japanese.py status` で commit が変わったか見る。
3. `python3 scripts/zed_japanese.py update --install` を実行する。
4. 日本語化ビルドを起動して表示を確認する。

翻訳キーが見つからない場合は失敗扱いにしない。Zed 側で文言や配置が変わる
ことは通常の更新で起こるため、未検出項目を見ながら翻訳辞書やパッチ対象を
少しずつ更新する。

## まだやらないこと

- 公式 Zed のインストール先を直接上書きすること。
- 署名済み installer を偽装すること。
- 起動中の Zed に DLL を注入すること。
- 自動更新の経路を公式 Zed と混ぜること。

