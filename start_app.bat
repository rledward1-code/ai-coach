@echo off
chcp 65001 >nul
title AI Coach 啟動器

:: 關鍵修正：切換到該 .bat 檔所在的資料夾路徑
cd /d "%~dp0"

echo ========================================================
echo 🏃‍♂️ 正在啟動 AI Coach 數據診斷中心...
echo 當前執行目錄: %cd%
echo ========================================================

:: 1. 檢查 Python
python --version >nul 2>&1
if "%errorlevel%" neq "0" (
    echo [錯誤] 找不到 Python！
    pause
    exit /b
)

:: 使用電腦名稱建立專屬虛擬環境，避免兩台電腦同步時互蓋
set VENV_DIR=venv_%COMPUTERNAME%

:: 2. 建立/啟動虛擬環境
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [系統] 首次執行或換電腦，正在建立專屬虛擬環境 [%VENV_DIR%] ...
    python -m venv "%VENV_DIR%"
)

:: 3. 安裝零件 (確保 requirements.txt 在同一層)
if exist "requirements.txt" (
    echo [系統] 正在安裝必要套件...
    "%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
    "%VENV_DIR%\Scripts\python.exe" -m pip install -r requirements.txt
) else (
    echo [警告] 找不到 requirements.txt，將跳過安裝步驟。
)

:: 4. 啟動
echo.
echo [成功] 準備完成，正在喚醒路格與佩絲教練...
echo ========================================================
"%VENV_DIR%\Scripts\python.exe" -m streamlit run app.py

pause