# 엑셀(OneDrive) → data/*.json 변환 후 바뀐 게 있으면 GitHub에 올린다. Claude 호출 없음(토큰 0).
# 새벽 자동 수집(account-book\windows\run_daily.ps1) 끝에서 호출. 수동: powershell -File tools\sync.ps1
param(
  [string]$Since = "26-08",
  [string]$LedgerRepo = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "account-book")
)
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
$web = Split-Path $PSScriptRoot -Parent
$tmp = Join-Path $env:TEMP ("ledger_sync_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force $tmp | Out-Null
try {
  $xlsx = Join-Path $tmp "ledger.xlsx"
  Push-Location $LedgerRepo
  try { python ledger.py download $xlsx | Out-Null } finally { Pop-Location }
  if (-not (Test-Path $xlsx)) { throw "엑셀 다운로드 실패" }
  python -I (Join-Path $PSScriptRoot "import_xlsx.py") $xlsx --out (Join-Path $web "data") --since $Since
  if ($LASTEXITCODE -ne 0) { throw "변환 실패" }
  Push-Location $web
  try {
    git add data
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) { "웹 데이터: 바뀐 것 없음"; return }
    git commit -q -m ("data: sync " + (Get-Date -Format "yyyy-MM-dd HH:mm"))
    git push -q origin main
    if ($LASTEXITCODE -ne 0) { throw "git push 실패" }
    "웹 데이터: 올림 " + (git log -1 --format=%h)
  } finally { Pop-Location }
} finally {
  Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
