# 실거래 분석 홈페이지 MVP (무료/GitHub 중심)

아파트 **매매(상세)** + **전세** 데이터를 data.go.kr OpenAPI에서 수집해서,  
지역 비교 지표(JSON)를 만들고 `GitHub Pages`로 공개하는 프로젝트입니다.

## 현재 포함 범위

- 데이터 소스
  - `RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev` (아파트 매매 상세)
  - `RTMSDataSvcAptRent/getRTMSDataSvcAptRent` (아파트 전세/월세)
- 수집 지역: 서울 25개 구 (`config/lawd_codes_seoul.csv`)
- 기본 수집 기간: 최근 2개월 (KST 기준)
- 지표
  - 지역별 매매 건수
  - 지역별 전세 건수(월세 0 기준)
  - 매매 중앙값 / 전세 중앙값
  - 전세가율(전세 중앙값 / 매매 중앙값)

## 로컬에서 실행

1. 환경변수 설정 (PowerShell)

```powershell
$env:DATA_GO_KR_SERVICE_KEY='여기에_서비스키'
```

2. 데이터 수집 + 지표 생성

```powershell
python scripts/fetch_rtms.py --months 2 --output .tmp/raw_rtms.json
python scripts/build_dashboard_data.py --input .tmp/raw_rtms.json --output docs/data/dashboard.json
```

또는 한 번에 실행:

```powershell
.\scripts\update_dashboard.ps1 -Months 2
```

3. 로컬 확인

`docs/index.html` 파일을 브라우저로 열거나, 간단한 정적 서버로 확인합니다.

## GitHub Actions 자동화

워크플로 파일: `.github/workflows/update-dashboard.yml`

- 매일 `06:26 KST` 스케줄 실행
- 수집 → 지표 생성 → `docs/data/dashboard.json` 커밋/푸시
- 수동 실행(`workflow_dispatch`)도 가능

### 필수 GitHub Secret

저장소 설정 > Secrets and variables > Actions > New repository secret

- 이름: `DATA_GO_KR_SERVICE_KEY`
- 값: data.go.kr 서비스키

### 선택 GitHub Secret (텔레그램 자동 공유)

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

둘 다 설정하면, 매일 업데이트 후 텔레그램으로 요약 메시지를 자동 발송합니다.

## GitHub Pages 배포

1. 저장소 Settings > Pages
2. Source: `Deploy from a branch`
3. Branch: `main` / folder: `/docs`
4. 저장 후 1~2분 뒤 사이트 오픈

## Git 초기화/푸시 (선택)

원격 저장소 URL이 있을 때 한 번에 실행:

```powershell
.\scripts\init_git_and_push.ps1 -RemoteUrl "https://github.com/사용자명/저장소명.git"
```

## 확장 포인트

- 지역 확장: `config/lawd_codes_seoul.csv`에 코드 추가
- 수집 기간 확장: `--months 3` 이상
- 아파트 외 유형 추가: 별도 API endpoint를 `fetch_rtms.py`에 같은 패턴으로 추가
