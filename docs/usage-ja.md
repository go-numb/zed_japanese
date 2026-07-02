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

`No spectre-mitigated libs were found` と言われる場合は Spectre-mitigated libs が
入っていない。Visual Studio Installer の Individual components で
`MSVC v143 - VS 2022 C++ x64/x86 Spectre-mitigated libs` を追加する。

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

事前チェック:

```powershell
git --version
docker --version
rustc --version
cargo --version
Get-Command cmake
where link
Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\Lib" -Recurse -Filter kernel32.lib -ErrorAction SilentlyContinue | Select-Object -First 1
```

`where link` は `link.exe` の場所を見るための確認。何も出ない場合は MSVC C++
toolchain が不足している。

`kernel32.lib` が出ない場合は Windows SDK libraries が不足している。

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

ここでは、実際に詰まりやすい順に症状、原因、対処をまとめる。

### まず `git pull`

wrapper 側は初期実装から何度か修正している。Docker image、Docker 引数渡し、
CMake 検出、Windows SDK 事前チェックで詰まる場合は、まず最新版へ更新する。

```powershell
cd path\to\zed_japanese
git pull
```

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

### `Missing Windows build dependencies: CMake`

CMake が未インストール、または PowerShell の PATH に入っていない。

対処:

```powershell
winget install -e --id Kitware.CMake
```

インストール後、新しい PowerShell を開く。

確認:

```powershell
Get-Command cmake
Test-Path "C:\Program Files\CMake\bin\cmake.exe"
```

最新版 wrapper は一般的な CMake install path を自動で PATH に追加する。
それでも失敗する場合は `git pull` してから再実行する。

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

### `No spectre-mitigated libs were found`

MSVC の Spectre-mitigated libraries が不足している。

対応:

1. Visual Studio Installer を開く。
2. Visual Studio / Build Tools の `Modify` を選ぶ。
3. `Individual components` を開く。
4. `Spectre` で検索する。
5. `MSVC v143 - VS 2022 C++ x64/x86 Spectre-mitigated libs` を追加する。
6. PowerShell を開き直して再実行する。

確認例:

```powershell
Get-ChildItem "C:\Program Files\Microsoft Visual Studio\2022" -Recurse -Filter libcpmt.lib -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -match "\\lib\\spectre\\x64\\" } |
  Select-Object -First 5
```

### Visual Studio Installer の場所が分からない

スタートメニューで `Visual Studio Installer` と入力して開く。

PowerShell から開く場合:

```powershell
Start-Process "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\setup.exe"
```

開いたら `Visual Studio Build Tools 2022` または `Visual Studio Community 2022`
の `Modify` を選ぶ。

### `Cloning into '/work/.cache/zed-upstream'...` で長い

初回 clone は大きいので時間がかかる。別 PowerShell で確認:

```powershell
docker ps
Get-ChildItem .\.cache\zed-upstream -Force
```

10 分以上まったく変化がなければ `Ctrl+C` で止めて再実行する。

### `! [rejected] nightly -> nightly (would clobber existing tag)`

Zed upstream の tag がローカル cache の tag と衝突している。最新版では
`git fetch --tags` を使わないため発生しにくい。

対処:

```powershell
git pull
powershell -ExecutionPolicy Bypass -File .\scripts\zed_japanese.ps1 -Command update
```

それでも直らない場合は、Zed source cache を消して取り直す。

```powershell
Remove-Item -Recurse -Force .\.cache\zed-upstream
powershell -ExecutionPolicy Bypass -File .\scripts\zed_japanese.ps1 -Command update
```

### `cargo build --release` が長い

初回 build はかなり長い。`Compiling ...` が流れていれば正常。

完了すると、通常は次のような表示に進む。

```text
installed: C:\Users\...\AppData\Local\Programs\Zed\Zed.exe
backup: C:\Users\...\AppData\Local\Programs\Zed\.zed-japanese-backups\...
```

途中で失敗した場合は、最後の 30 から 50 行を確認する。

### Windows の `Zed.exe` に Linux build を置こうとして拒否される

WSL で build すると Linux 向け成果物になる。Windows 版を作る場合は Windows 側
PowerShell で実行する。

## よくある更新パターン

公式 Zed が更新された後、日本語化が戻った場合:

```powershell
cd path\to\zed_japanese
git pull
powershell -ExecutionPolicy Bypass -File .\scripts\zed_japanese.ps1 -Command update
```

翻訳 patch だけ確認したい場合:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\zed_japanese.ps1 -Command prepare
```

build 済み成果物だけ install したい場合:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\zed_japanese.ps1 -Command install
```
