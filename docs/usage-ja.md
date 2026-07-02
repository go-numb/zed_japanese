# Zed 日本語化ビルド運用メモ

## 目標

Zed の軽さと更新頻度を維持しながら、自分の環境で日本語化ビルドを使う。

このツールは Zed 本体を永続 fork しない。公式 stable の更新を先に受け取り、
その時点でインストールされている Zed の commit に対して日本語化を再適用する。

## 基本方針

- 公式 Zed のインストールを基準にする。
- DLL injection や UI hook は使わない。
- 日本語化はビルド時にソースへ適用する。
- 日本語化した `Zed.exe` は公式インストール先へ overlay する。
- overlay 前に公式 `Zed.exe` をバックアップする。
- app identity は変えず、設定・拡張・履歴・キャッシュを公式 Zed と共有する。
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
6. 公式 `Zed.exe` を `.zed-japanese-backups` に退避する。
7. 日本語化した `Zed.exe` を公式インストール先へコピーする。

この方式だと、Zed の user data path は変わらない。既存の extension、履歴、
settings、LSP キャッシュなどは公式 Zed と同じものを使う。

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
- 公式 `Zed.exe` として検出された path

## Windows と WSL

WSL から Windows 版 Zed を検出することはできる。

ただし WSL で `cargo build` すると Linux 向けビルドになる。Windows 版の
日本語化 Zed を作る場合は、Windows 側の Rust / Python 環境でこのツールを
実行する。Windows の `Zed.exe` に Linux ビルドを overlay することは拒否する。

## インストール先

デフォルトは公式 Zed への overlay:

- `zed --version` が示す公式 `Zed.exe`
- 例: `%LOCALAPPDATA%\Programs\Zed\Zed.exe`

バックアップ先:

- 例: `%LOCALAPPDATA%\Programs\Zed\.zed-japanese-backups\...`

side-by-side で試したい場合:

```sh
python3 scripts/zed_japanese.py install --mode side-by-side --dest ~/apps/zed-japanese
```

通常運用では side-by-side より公式 overlay を使う。app identity が変わらない
ため、extension や履歴の扱いが自然になる。

## 更新運用

おすすめの運用:

1. 公式 Zed を通常どおり更新する。
2. `python3 scripts/zed_japanese.py status` で commit が変わったか見る。
3. `python3 scripts/zed_japanese.py update --install` を実行する。
4. 通常どおり Zed を起動して表示を確認する。

翻訳キーが見つからない場合は失敗扱いにしない。Zed 側で文言や配置が変わる
ことは通常の更新で起こるため、未検出項目を見ながら翻訳辞書やパッチ対象を
少しずつ更新する。

## まだやらないこと

- 署名済み installer を偽装すること。
- 起動中の Zed に DLL を注入すること。
- app identity や user data directory を `Zed Japanese` に変えること。
- Linux ビルドを Windows の `Zed.exe` として配置すること。

## 復旧

もっとも簡単な復旧方法は、公式 Zed を再インストールすること。

バックアップから戻す場合は、公式 Zed を閉じてから
`.zed-japanese-backups` 内の該当 `.bak` を `Zed.exe` に戻す。
