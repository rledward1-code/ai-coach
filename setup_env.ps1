# setup_env.ps1
Write-Host "--- AI Coach 環境修復與初始化 ---" -ForegroundColor Cyan

# 1. 確保沒有 Python 在佔用該資料夾
Write-Host "1. 正在停止任何運行中的 Streamlit 或 Python 進程..."
Stop-Process -Name "python" -ErrorAction SilentlyContinue

# 2. 移除舊環境 (PowerShell 語法)
if (Test-Path venv) {
    Write-Host "2. 正在移除舊的虛擬環境 (這可能需要一點時間)..."
    # 等待一秒確保 process 釋放
    Start-Sleep -s 1
    Remove-Item -Recurse -Force venv
}

# 3. 建立新的虛擬環境
Write-Host "3. 正在建立全新的虛擬環境 (python -m venv venv)..."
python -m venv venv

# 4. 安裝依賴 (直接使用 python 模組方式呼叫，避免 Launcher 報錯)
Write-Host "4. 正在安裝零件 (這會確保路徑正確)..."
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "--- 修復完成！請執行 .\start_app.bat 啟動教練 ---" -ForegroundColor Green
