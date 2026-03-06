param(
  [int]$Months = 2,
  [string]$LawdCodesFile = "config/lawd_codes_seoul.csv"
)

if (-not $env:DATA_GO_KR_SERVICE_KEY) {
  Write-Error "DATA_GO_KR_SERVICE_KEY 환경변수를 먼저 설정하세요."
  exit 1
}

New-Item -ItemType Directory -Force -Path .tmp | Out-Null

python scripts/fetch_rtms.py `
  --months $Months `
  --lawd-codes-file $LawdCodesFile `
  --output .tmp/raw_rtms.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python scripts/build_dashboard_data.py `
  --input .tmp/raw_rtms.json `
  --output docs/data/dashboard.json
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "완료: docs/data/dashboard.json 갱신"
