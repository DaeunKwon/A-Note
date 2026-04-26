# A-Note

국내 주식 매매를 **사후 복기**하고, **Google Gemini**로 초보자도 읽기 쉬운 매매 피드백(A-Note)을 제공하는 웹 앱입니다. 시세·차트·지수는 **한국투자증권(KIS) Open API**, 뉴스는 **네이버 검색 API**를 사용합니다.

상세 아키텍처·API·UI 설계는 **[design.md](./design.md)** 를 참고하세요.

---

## 주요 기능

- **주문**: 종목별 시세·차트(Chart.js), RSI 등 지표, 매수/매도 시뮬레이션(수량·가격 유효성 검사)
- **매매 내역**: 체결 기록 누적, 항목별 **A-Note(오답 노트)** — 분석 결과는 저장되어 재조회 시 동일하게 표시
- **투자 성향**: 누적 체결 기반 MBTI 스타일 프로필, 성향 변화 추적, 다음 행동 패턴 추천
- **오답 노트 2번**: 종목 관련 네이버 뉴스 + Gemini 기반 단기 해석 및 다음 행동 제안
- **잔고/보유**: 다중 종목 보유를 종목별 수량·평단으로 관리 및 표시
- **모바일 프리뷰**: `/m` 또는 `/mobile`에서 앱형 모바일 UI 미리보기 제공

---

## 기술 스택

| 구분 | 내용 |
|------|------|
| 백엔드 | Python, FastAPI, httpx, uvicorn |
| 프론트엔드 | `static/index.html` (바닐라 JS), Chart.js, 정적 UI 프리뷰 HTML |
| AI | Google Gemini (`gemini-2.5-flash`) |
| 배포 (선택) | Vercel — `api/index.py`, `vercel.json` |

---

## 사전 준비

- Python 3.10+ 권장
- [한국투자증권 Open API](https://apiportal.koreainvestment.com/) 앱키·시크릿
- [네이버 개발자센터](https://developers.naver.com/) 애플리케이션 (뉴스 검색용 Client ID/Secret)
- [Google AI Studio](https://aistudio.google.com/) 등에서 발급한 **Gemini API 키** (`GEMINI_API_KEY`)

---

## 환경 변수

프로젝트 루트에 `.env` 파일을 두고 아래 값을 채웁니다. `start.sh`/`start.ps1`는 플레이스홀더(`여기에` 등)가 남아 있으면 실행을 중단합니다.

| 변수 | 설명 |
|------|------|
| `KIS_APP_KEY` | KIS 앱키 |
| `KIS_APP_SECRET` | KIS 앱 시크릿 |
| `KIS_ACCOUNT` | 계좌번호 형식 (예: `12345678-01`) |
| `KIS_IS_VIRTUAL` | `true`: 모의투자, `false`: 실전 |
| `NAVER_CLIENT_ID` | 네이버 Client ID |
| `NAVER_CLIENT_SECRET` | 네이버 Client Secret |
| `GEMINI_API_KEY` | Gemini API 키 |

---

## 로컬 실행

### Git Bash / WSL / macOS / Linux

```bash
chmod +x start.sh
./start.sh
```

브라우저에서 **http://localhost:8000** 을 엽니다.

### Windows (PowerShell)

```powershell
.\start.ps1
```

또는 수동 실행:

```powershell
python -m pip install -r .\Requirements.txt
python -m uvicorn server:app --host 0.0.0.0 --port 8000
```

`start.ps1`은 8000 포트를 점유한 기존 서버 프로세스와 잔여 `server.py` 프로세스를 정리한 뒤 uvicorn으로 앱을 실행합니다. `server.py`를 직접 실행할 수도 있으며, Windows에서는 reload를 끄고 실행되도록 구성되어 있습니다.

---

## 프로젝트 구조 (요약)

```
A-Note/
├── server.py          # FastAPI 앱, REST·정적 파일·WebSocket
├── static/
│   ├── index.html                  # 메인 프론트엔드 UI
│   ├── mobile-app-preview.html     # /m, /mobile 모바일 앱형 프리뷰
│   └── order-tab-card-preview.html # 주문 탭 카드형 UI 프리뷰
├── api/
│   ├── index.py       # Vercel 진입점 (from server import app)
│   └── requirements.txt
├── Requirements.txt
├── start.sh           # 로컬 기동 스크립트
├── start.ps1          # Windows PowerShell 기동 스크립트
├── vercel.json        # Vercel 빌드·라우팅
├── design.md          # 설계 문서
└── README.md
```

---

## Vercel 배포

1. 저장소를 Vercel에 연결합니다.
2. 환경 변수에 위 `.env` 항목을 동일하게 설정합니다.
3. `vercel.json`이 `static/**`를 포함하도록 구성되어 있어야 메인 화면과 `/m` 모바일 프리뷰가 정상 서빙됩니다.

**참고**: 서버리스 환경에서는 **WebSocket**(`/ws/prices`)이 기대대로 동작하지 않을 수 있습니다. 시세는 HTTP 폴링 등으로 보완하는 것이 안전합니다.

---

## 라이선스 / 면책

이 프로젝트는 교육·개인 복기 목적에 가깝습니다. 투자 판단은 본인 책임이며, API 응답 지연·오류 가능성을 항상 고려하세요.
