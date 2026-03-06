# 실거래 분석 홈페이지 MVP

아파트 매매/전월세 데이터를 data.go.kr OpenAPI에서 수집해서  
`전국 / 시군구 / 법정동 / 단지별` 메뉴형 대시보드를 정적 사이트로 제공하는 프로젝트입니다.

## 현재 구성

- 데이터 소스
  - `RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev`
  - `RTMSDataSvcAptRent/getRTMSDataSvcAptRent`
- 샘플 수집 범위: 서울 + 인천 (`config/lawd_codes_seoul_incheon.csv`)
- 기본 수집 기간: 최근 12개월 (KST 기준)
- 화면
  - `1. 전국`: 최근 3개년 월별 그래프 + 시도별 최근 3개월 표
  - `2. 시군구`: 전월대비 증가율 Top 20 + 전체 시군구 표
  - `3. 법정동`: 전월대비 증가율 Top 20 + 전체 법정동 표
  - `4. 단지별`: 전월대비 증가율 Top 20 + 전체 단지 표

## 빠른 실행 (로컬)

1. 환경변수 설정 (PowerShell)

```powershell
$env:DATA_GO_KR_SERVICE_KEY='여기에_서비스키'
```

2. 수집 + 집계

```powershell
.\scripts\update_dashboard.ps1 -Months 12
```

3. 로컬 웹 확인

```powershell
cd docs
python -m http.server 8080
```

브라우저: `http://localhost:8080`

## GitHub Actions 자동화

워크플로: `.github/workflows/update-dashboard.yml`

- 매일 `06:26 KST` 실행
- 수집 -> 집계 -> `docs/data/dashboard.json` 업데이트 커밋
- 수동 실행(`workflow_dispatch`) 가능

### 필수 Secret

- `DATA_GO_KR_SERVICE_KEY`

### 선택 Secret (텔레그램 요약)

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## GitHub Pages 배포

1. 저장소 Settings > Pages
2. Source: `Deploy from a branch`
3. Branch: `main` / folder: `/docs`

## 원격 저장소 초기화(선택)

```powershell
.\scripts\init_git_and_push.ps1 -RemoteUrl "https://github.com/사용자명/저장소명.git"
```

## 다음 확장 포인트

- 수집 범위를 전국 255 시군구로 확대
- 단지 상세(기간별 실거래 원장) JSON/API 분리
- 청약/경매/거시지표 수집기 추가
