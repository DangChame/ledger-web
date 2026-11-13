# 2주마다: JSON(원본)에서 엑셀에 아직 안 옮긴 칸을 OneDrive 엑셀에 쓰고, 지운 dirty 표시를 GitHub에 올림
Set-Location (Split-Path $PSScriptRoot -Parent)
$log = "$HOME\.config\ledger\daily.log"
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
"==== 엑셀 반영 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -Append -Encoding utf8 $log
python tools\push_excel.py 2>&1 | Out-File -Append -Encoding utf8 $log
powershell -NoProfile -ExecutionPolicy Bypass -File tools\publish.ps1 2>&1 | Out-File -Append -Encoding utf8 $log
