# Zed 日本語化ビルド インストール手順

## 対象

Windows 11 で公式 Zed を使っていて、Python がなく Docker Desktop がある環境。

この手順では、公式 Zed と同じ commit のソースを取得し、日本語化 patch を当てて
Windows 側で build する。完成した `Zed.exe` は公式インストール先へ overlay する。

## 方針

- 公式 Zed のインストールを基準にする。
- app identity は変えない。
- 既存の settings、extensions、履歴、LSP cache は公式 Zed と共有する。
- 公式 `Zed.exe` は overlay 前にバックアップする。
- Zed 更新後は同じ手順を再実行する。
- DLL injection や UI hook は使わない。

## 1. 公式 Zed をインストール

未インストールの場合:

```powershell
winget install -e --id ZedIndustries.Zed
```

すでに入っている場合はそのままでよい。

通常の overlay install には公式 Zed の `Zed.exe` path が必要。公式 Zed を入れずに
日本語化版だけを install する運用はまだ対象外。

## 2. 必要ツールを入れる

Python は不要。Docker image 内の Python を使う。

ホスト Windows 側に必要:

- Git
- Docker Desktop
- Rust / cargo
- Visual Studio Build Tools または Visual Studio
- Desktop development with C++
- MSVC x64/x86 build tools
- MSVC Spectre-mitigated libs
- Windows 10/11 SDK
- CMake

Rust:

```powershell
winget install -e --id Rustlang.Rustup
```

Visual Studio Build Tools:

```powershell
winget install -e --id Microsoft.VisualStudio.2022.BuildTools
```

Visual Studio Installer が開いたら、`Desktop development with C++` と上記の MSVC /
SDK / CMake 関連コンポーネントを入れる。

VS Code は別製品なので、Zed の Windows build には不足。

`kernel32.lib` がないと言われる場合は Windows SDK libraries が入っていない。
Visual Studio Installer で Windows 10/11 SDK を追加する。

CMake が不足している場合は standalone CMake を入れるのが早い。

```powershell
winget install -e --id Kitware.CMake
```

インストール後、新しい PowerShell を開き直してから再実行する。

確認:

```powershell
Get-Command cmake
Test-Path "C:\Program Files\CMake\bin\cmake.exe"
```

## 3. Repository を取得

```powershell
git clone https://github.com/go-numb/zed_japanese.git
cd zed_japanese
```

既に clone 済みの場合:

```powershell
git pull
```

## 4. 日本語化 build と overlay

通常はこれだけ:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\zed_japanese.ps1 -Command update
```

内部で実行すること:

1. 公式 Zed の version / commit / `Zed.exe` path を検出する。
2. Docker image `zed-japanese-tool:latest` がなければ build する。
3. Docker 内で upstream Zed を `.cache\zed-upstream` に clone / fetch する。
4. 公式 Zed と同じ commit に checkout する。
5. `translations\ja-JP.json` の翻訳を適用する。
6. Windows ホスト側で `cargo build --release` する。
7. 公式 `Zed.exe` を `.zed-japanese-backups` へ退避する。
8. 日本語化した `Zed.exe` を公式インストール先へコピーする。

初回は Zed 本体 repo の clone と Rust build が長い。`Cloning into
'/work/.cache/zed-upstream'...` で数分止まって見えることがある。

## 5. 実行

通常どおり Zed を起動する。

```powershell
zed
```

またはスタートメニュー / 既存ショートカットから起動する。app identity を変えて
いないため、既存の設定や extension は同じものを使う。

## 更新手順

公式 Zed が更新された後:

```powershell
cd path\to\zed_japanese
git pull
powershell -ExecutionPolicy Bypass -File .\scripts\zed_japanese.ps1 -Command update
```

公式 update によって日本語化 `Zed.exe` が上書きされた場合も、この手順で再適用する。

## Zed 未インストールで checkout/patch だけ試す

公式 Zed なしでは overlay install はできない。source checkout と patch の検証だけなら
version と commit を明示する。

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\zed_japanese.ps1 -Command prepare `
  -ZedVersion 1.9.0 `
  -ZedCommit ced90fc636c4ede05402befc38a63bae7fd741bd
```

## Side-by-side で試す

通常は公式 overlay を使う。別ディレクトリに置きたい場合:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\zed_japanese.ps1 -Command update `
  -SideBySide `
  -Dest "C:\Apps\Zed Japanese"
```

この場合は起動方法や user data の扱いが公式 overlay と異なる可能性があるため、
常用は公式 overlay を推奨する。

## 復旧

もっとも簡単な復旧:

```powershell
winget install -e --id ZedIndustries.Zed
```

バックアップから戻す場合は、Zed を閉じてから
`%LOCALAPPDATA%\Programs\Zed\.zed-japanese-backups` の `.bak` を `Zed.exe` に戻す。

## トラブルシュート

### `No such image: zed-japanese-tool:latest`

古い wrapper では image 未作成時に止まることがあった。最新版へ更新する。

```powershell
git pull
```

最新版では image がなければ自動で `docker build` する。

### `the following arguments are required: command`

古い wrapper の Docker 引数渡しの問題。最新版へ更新する。

```powershell
git pull
```

### `VS Code is a different product, and is not sufficient`

Visual Studio / Visual Studio Build Tools の C++ toolchain が不足している。

入れるもの:

- Desktop development with C++
- MSVC x64/x86 build tools
- MSVC Spectre-mitigated libs
- Windows 10/11 SDK
- CMake

CMake だけ不足している場合:

```powershell
winget install -e --id Kitware.CMake
```

インストール済みなのに見つからない場合は、新しい PowerShell を開き直す。
それでもだめなら確認:

```powershell
Get-Command cmake
Test-Path "C:\Program Files\CMake\bin\cmake.exe"
```

インストール後、通常 PowerShell でうまくいかない場合は
`Developer PowerShell for VS 2022` から同じコマンドを実行する。

### `LINK : fatal error LNK1181: cannot open input file 'kernel32.lib'`

MSVC linker は見つかっているが、Windows SDK の library path が不足している。

確認:

```powershell
where link
echo $env:LIB
Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\Lib" -Recurse -Filter kernel32.lib -ErrorAction SilentlyContinue | Select-Object -First 5
```

対応:

1. Visual Studio Installer を開く。
2. Visual Studio / Build Tools の `Modify` を選ぶ。
3. `Individual components` で Windows 10/11 SDK を追加する。
4. PowerShell を開き直して再実行する。

通常 PowerShell でだめな場合は `Developer PowerShell for VS 2022` から実行する。

### `Cloning into '/work/.cache/zed-upstream'...` で長い

初回 clone は大きいので時間がかかる。別 PowerShell で確認:

```powershell
docker ps
Get-ChildItem .\.cache\zed-upstream -Force
```

10 分以上まったく変化がなければ `Ctrl+C` で止めて再実行する。

### Windows の `Zed.exe` に Linux build を置こうとして拒否される

WSL で build すると Linux 向け成果物になる。Windows 版を作る場合は Windows 側
PowerShell で実行する。
