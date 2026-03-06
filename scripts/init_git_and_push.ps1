param(
  [Parameter(Mandatory = $true)]
  [string]$RemoteUrl
)

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Error "git 이 설치되어 있어야 합니다."
  exit 1
}

if (-not (Test-Path ".git")) {
  git init
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

git branch -M main
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git add .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
  git commit -m "chore: bootstrap real-estate dashboard mvp"
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$hasOrigin = git remote | Select-String -Pattern "^origin$" -Quiet
if (-not $hasOrigin) {
  git remote add origin $RemoteUrl
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

git push -u origin main
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "완료: origin/main 으로 푸시되었습니다."
