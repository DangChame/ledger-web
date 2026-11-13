# data/*.json(가계부 원본)이 바뀌었으면 커밋해서 GitHub에 올림 → Pages 사이트에 반영
Set-Location (Split-Path $PSScriptRoot -Parent)
git add data
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
  git commit -q -m "data: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
  git push -q origin main
  if ($LASTEXITCODE -eq 0) { "올림: $(git log --oneline -1)" } else { "push 실패 (다음 실행 때 다시)" }
} else {
  "바뀐 것 없음"
}
