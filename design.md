# A-Note — 설계 문서 (design.md)

## 1. 제품 개요

**A-Note**는 국내 주식 매매를 **사후 복기**하고, **Gemini 기반 AI**로 초보 투자자도 이해하기 쉬운 피드백을 주는 웹 애플리케이션이다.  
시세·지수는 **한국투자증권(KIS) Open API**, 뉴스는 **네이버 검색 API**를 사용하며, 매매 분석과 뉴스 보강은 **Google Gemini**로 생성한다.

---

## 2. 아키텍처 개요

| 계층 | 역할 |
|------|------|
| **프론트엔드** | 단일 페이지 `static/index.html` (바닐라 JS + Chart.js). REST로 백엔드 호출, `localStorage`로 체결·A-Note 분석·패턴 통계 유지. 별도 정적 HTML로 모바일/주문 탭 프리뷰 제공 |
| **백엔드** | FastAPI (`server.py`): REST API, 정적 파일 서빙, 로컬에서 WebSocket 시세 스트림 |
| **배포 (Vercel)** | `api/index.py`가 `server`의 `app`을 로드. `vercel.json`으로 모든 경로를 Python 서버리스 함수로 라우팅. `static/**`는 `includeFiles`로 번들에 포함 |

```
[Browser] ──HTTPS──► [FastAPI]
                          │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
      KIS Open API   Naver News API   Gemini API
```

---

## 3. 기술 스택

- **언어**: Python 3, JavaScript (ES 모듈 없이 인라인 스크립트)
- **서버**: FastAPI, Uvicorn(로컬), `httpx`(비동기 HTTP), `python-dotenv`
- **프론트**: HTML/CSS, Chart.js, Google Fonts (Noto Sans KR, DM Mono)
- **저장소(클라이언트)**: `localStorage` 키 `anote_trade_state_v4`

---

## 4. 외부 연동

### 4.1 한국투자증권 (KIS)

- OAuth2 `client_credentials`로 액세스 토큰 발급 후 REST 호출
- `KIS_IS_VIRTUAL`: 모의투자(`openapivts…29443`) / 실전(`openapi…9443`) 베이스 URL 전환
- 주요 사용 TR: 현재가, 일봉 차트, 지수(KOSPI/KOSDAQ), WebSocket용 주기적 현재가 폴링

### 4.2 네이버 뉴스 검색

- `X-Naver-Client-Id` / `Secret` 헤더로 뉴스 JSON 검색
- 수신 후 서버에서 제목·요약 정제, 선택적 키워드 기반 감성 태그
- **Gemini 배치 보강**: 각 기사에 `summary`, `marketImpact`, `relatedSector`, `relatedStocks` 추가 (키 없거나 실패 시 스니펫 기반 폴백, 상투구 하드코딩 없음)

### 4.3 Google Gemini

- 모델: `gemini-2.5-flash` (매매 분석 `/api/analyze`, 뉴스 배치 보강, 오답 노트 2번 뉴스 해석)
- 매매 분석: JSON 스키마(점수, 분석문, 액션, 총평, 패턴 등) 준수, 실패 시 `_fallback_analysis` 룰 기반 응답
- 뉴스 해석: `responseMimeType="application/json"`와 응답 스키마를 우선 사용하고, 400 응답이면 레거시 텍스트 JSON 방식으로 재시도
- `429`/`503` 일시 실패는 짧게 재시도하며, 모델이 `newsActions`를 3개 미만으로 반환하면 복기용 기본 행동 항목으로 보정
- Gemini·네이버 뉴스·로깅 실패가 `/api/analyze` 전체 실패로 번지지 않도록 뉴스 블록은 폴백 메시지로 대체

---

## 5. API 표면 (요약)

| 메서드·경로 | 설명 |
|-------------|------|
| `GET /` | `static/index.html` 반환 |
| `GET /m`, `GET /mobile` | `static/mobile-app-preview.html` 반환 |
| `GET /api/price/{code}` | 종목 현재가 등 |
| `GET /api/chart/{code}` | 일봉(및 period 파라미터) |
| `GET /api/index` | KOSPI / KOSDAQ 지수 |
| `GET /api/news?query=…` | 네이버 뉴스 + AI 보강 필드 |
| `POST /api/analyze` | `TradeRecord` 바디 → 매매 분석 + 종목 뉴스 기반 해석 JSON |
| `GET /static/*` | 정적 자원 |
| `WS /ws/prices` | 5초 간격 다종목 시세 브로드캐스트 (**로컬 전제**; Vercel 서버리스에서는 일반적으로 사용 불가) |

**종목 목록**은 서버 `STOCKS`와 프론트 `STOCKS` 배열에 동기화되어 있으며, 대표적으로 한화투자증권(003530)이 목록 선두에 둔다.

---

## 6. 프론트엔드 설계

### 6.1 레이아웃·내비게이션

- **전체 높이**: `100vh` 그리드, 상단 글로벌 헤더 + 본문
- **하단 탭**: 주문 / 매매 내역 / 투자 성향 — 앱형 UI, 하단 고정(`position` + 콘텐츠 `margin-bottom`으로 겹침 방지)
- **좁은 화면**: 종목 탭·시장 지표·차트 헤더 등에 `scroll-x`로 가로 스크롤
- **프리뷰 페이지**: `static/mobile-app-preview.html`은 `/m`·`/mobile`에서 모바일 앱형 목업을 보여주고, `static/order-tab-card-preview.html`은 주문 탭 카드형 UI 검토용 정적 프리뷰로 유지

### 6.2 주요 기능 흐름

- **주문 탭**: 종목 선택 → 차트·지표 → 매수/매도 입력(수량·가격 유효성: 양의 정수 등)
- **매매 내역**: 누적 체결 목록, 항목 클릭 시 A-Note(오답 노트) — 저장된 `anoteAnalysis`가 있으면 재요청 없이 표시
- **A-Note 분석 맥락**: 열람 중인 체결보다 시간상 앞선 기록만 이전 매매로 세며, 같은 시각이면 `id` 순서로 정렬해 해당 체결 시점까지의 맥락을 계산
- **오답 노트 2번**: 종목 관련 네이버 뉴스를 기반으로 시장 해석 + 다음 행동 추천(참고 기사 링크 포함)
- **투자 성향**: 누적 체결 기반 MBTI 유사 프로필 + 유형별 마스코트 + 성향 변화 추적 + 행동 패턴 추천

### 6.3 API 베이스 URL

- `const API = ''` — 동일 오리진 기준. 로컬은 `http://localhost:8000`, Vercel은 배포 도메인

---

## 7. 데이터·상태 모델 (클라이언트)

`anote_trade_state_v4`와 `anote_profile_history_v1`에 대략 다음이 포함된다.

- 누적 **체결 기록**(종목, 수량, 가격, 시각 등)
- 종목별 **다중 보유 상태**(`holdings`: 수량, 평균단가)
- 거래별 **A-Note 분석 결과**(`anoteAnalysis`) — 재조회 시 불변
- **패턴 카운트**(공황 손절, 조기 익절, 장기 보유 후 손절 등) — UI에서 재계산
- 다음 분석 요청 시 전체 누적 건수가 아니라 **해당 체결 시점까지의 학습 건수**를 백엔드에 전달 (`totalTradesLearned`)
- 투자 성향 **스냅샷 히스토리**(코드/축 점수/체결 건수)로 변화 분석 렌더링

---

## 8. UI 디자인 시스템 (요약)

CSS 변수 기준 다크 테마.

| 토큰 | 용도 |
|------|------|
| `--bg`, `--bg2` … | 배경 단계 |
| `--text`, `--text2`, `--text3` | 본문·보조·약한 텍스트 |
| `--up` / `--down` | 상승·하락 색 |
| `--accent` | 브랜드·강조(파랑 계열) |
| `--mono` (DM Mono) | 가격·코드·숫자 |
| `--sans` (Noto Sans KR) | 본문 |

카드·보더는 낮은 대비의 `rgba` 테두리로 구분한다.

---

## 9. 배포·운영 고려사항

1. **환경 변수**: `.env`에 `KIS_*`, `NAVER_*`, `GEMINI_API_KEY` 등 — Vercel 대시보드에도 동일 키 설정 필요
2. **WebSocket**: 로컬 `uvicorn`에서는 `/ws/prices` 동작; **Vercel**에서는 연결 제약이 있어 시세는 `fetch` 폴링 등으로 보완하는 편이 안전
3. **정적 파일**: `STATIC_DIR` 존재 시에만 마운트·`/` 응답; `/m`·`/mobile`은 `static/mobile-app-preview.html` 존재 여부를 확인해 반환. 번들에 `static` 포함 필수
4. **Windows 로컬 실행**: `start.ps1`은 기존 8000 포트 리스너와 잔여 `server.py` 프로세스를 정리한 뒤 `python -m uvicorn server:app`으로 실행. `server.py` 직접 실행 시 Windows에서는 reload를 끔
5. **CORS**: `allow_origins=["*"]` — 필요 시 운영 도메인으로 제한 검토

---

## 10. 로컬 실행

- `start.sh`: Git Bash/WSL/macOS/Linux에서 의존성 설치 후 서버 기동
- `start.ps1`: Windows PowerShell에서 의존성 설치, 포트/잔여 프로세스 정리 후 서버 기동
- 공통 접속: `http://localhost:8000/`
- 모바일 프리뷰: `http://localhost:8000/m`

---

## 11. 확장 시 참고

- 실시간 시세: WebSocket 실패 시 **HTTP 폴링 폴백**으로 통일
- 뉴스 UI: 과거 우측 패널 제거 후 API·`buildNewsEl` 등은 유지 여부에 따라 정리 가능
- 저장소: 장기적으로 서버 DB로 옮기면 기기 간 동기화·백업에 유리

---

*문서 버전: 코드베이스 기준 스냅샷. 구현 변경 시 이 파일을 함께 갱신하는 것을 권장한다.*
