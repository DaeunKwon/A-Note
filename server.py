"""
A-Note 백엔드 서버
FastAPI + KIS API + 네이버 뉴스 API + Google Gemini AI
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = FastAPI(title="A-Note API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 환경변수 ──────────────────────────────────────────
KIS_APP_KEY      = os.getenv("KIS_APP_KEY", "")
KIS_APP_SECRET   = os.getenv("KIS_APP_SECRET", "")
KIS_ACCOUNT      = os.getenv("KIS_ACCOUNT", "")          # 예: 12345678-01
KIS_IS_VIRTUAL   = os.getenv("KIS_IS_VIRTUAL", "true").lower() == "true"
NAVER_CLIENT_ID  = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")

KIS_BASE = "https://openapivts.koreainvestment.com:29443" if KIS_IS_VIRTUAL \
           else "https://openapi.koreainvestment.com:9443"

# ── KIS 토큰 캐시 ─────────────────────────────────────
_kis_token: dict = {"token": None, "expires": 0}

async def get_kis_token() -> str:
    now = time.time()
    if _kis_token["token"] and now < _kis_token["expires"]:
        return _kis_token["token"]
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{KIS_BASE}/oauth2/tokenP",
            json={"grant_type": "client_credentials",
                  "appkey": KIS_APP_KEY,
                  "appsecret": KIS_APP_SECRET},
            timeout=10
        )
        data = r.json()
        _kis_token["token"]   = data["access_token"]
        _kis_token["expires"] = now + int(data.get("expires_in", 86400)) - 60
        return _kis_token["token"]

async def kis_get(path: str, params: dict, tr_id: str) -> dict:
    token = await get_kis_token()
    headers = {
        "authorization": f"Bearer {token}",
        "appkey":        KIS_APP_KEY,
        "appsecret":     KIS_APP_SECRET,
        "tr_id":         tr_id,
        "custtype":      "P",
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{KIS_BASE}{path}", params=params,
                             headers=headers, timeout=10)
        return r.json()

# ── 종목 코드 목록 ────────────────────────────────────
STOCKS = {
    "003530": "한화투자증권",
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "051910": "LG화학",
    "035720": "카카오",
}

# ════════════════════════════════════════════════════
# REST 엔드포인트
# ════════════════════════════════════════════════════

# ── 현재가 조회 ───────────────────────────────────────
@app.get("/api/price/{code}")
async def get_price(code: str):
    try:
        data = await kis_get(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code},
            "FHKST01010100"
        )
        o = data["output"]
        return {
            "code":      code,
            "name":      STOCKS.get(code, code),
            "price":     int(o["stck_prpr"]),
            "change":    int(o["prdy_vrss"]),
            "changePct": float(o["prdy_ctrt"]),
            "volume":    int(o["acml_vol"]),
            "high":      int(o["stck_hgpr"]),
            "low":       int(o["stck_lwpr"]),
            "open":      int(o["stck_oprc"]),
            "high52":    int(o["stck_dryy_hgpr"]),
            "low52":     int(o["stck_dryy_lwpr"]),
            "per":       o.get("per", "N/A"),
            "marketCap": o.get("hts_avls", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 차트 데이터 (일봉) ────────────────────────────────
@app.get("/api/chart/{code}")
async def get_chart(code: str, period: str = "D"):
    try:
        today = datetime.now().strftime("%Y%m%d")
        data = await kis_get(
            "/uapi/domestic-stock/v1/quotations/inquire-daily-price",
            {
                "fid_cond_mrkt_div_code": "J",
                "fid_input_iscd":         code,
                "fid_org_adj_prc":        "0",
                "fid_period_div_code":    period,  # D/W/M
            },
            "FHKST01010400"
        )
        candles = []
        for row in reversed(data.get("output", [])):
            candles.append({
                "date":   row["stck_bsop_date"],
                "open":   int(row["stck_oprc"]),
                "high":   int(row["stck_hgpr"]),
                "low":    int(row["stck_lwpr"]),
                "close":  int(row["stck_clpr"]),
                "volume": int(row["acml_vol"]),
            })
        return {"code": code, "candles": candles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 지수 조회 (KOSPI/KOSDAQ) ──────────────────────────
@app.get("/api/index")
async def get_index():
    try:
        async def fetch(code, tr):
            d = await kis_get(
                "/uapi/domestic-stock/v1/quotations/inquire-index-price",
                {"fid_cond_mrkt_div_code": "U", "fid_input_iscd": code},
                tr
            )
            o = d["output"]
            return {
                "price":     float(o["bstp_nmix_prpr"]),
                "change":    float(o["bstp_nmix_prdy_vrss"]),
                "changePct": float(o["bstp_nmix_prdy_ctrt"]),
            }
        kospi  = await fetch("0001", "FHPUP02100000")
        kosdaq = await fetch("1001", "FHPUP02100000")
        return {"kospi": kospi, "kosdaq": kosdaq}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 뉴스 AI 보강 (요약 + 시장 영향 + 관련 분야·종목) ─────────────────
def _fallback_news_enrich(it: dict) -> None:
    """Gemini 미사용/실패 시: 요약만 원문 기반, 시장 영향은 비움(상투구 하드코딩 없음)."""
    desc = (it.get("description") or "").strip()
    if len(desc) > 200:
        desc = desc[:200] + "…"
    it["summary"] = desc if desc else (it.get("title") or "")[:150]
    it["marketImpact"] = ""
    it["relatedSector"] = ""
    it["relatedStocks"] = []


def _strip_prefix(s: str, prefixes: tuple) -> str:
    """모델이 라벨 접두어를 붙였을 때 제거."""
    t = (s or "").strip()
    for p in prefixes:
        if t.startswith(p):
            return t[len(p) :].strip()
    return t


def _strip_news_json_text(raw: str) -> str:
    raw = raw.strip()
    if "```" in raw:
        raw = raw.split("```", 1)[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


async def _enrich_news_batch_gemini(batch: List[dict]) -> None:
    """batch 항목에 summary, marketImpact, relatedSector, relatedStocks 채움."""
    if not batch:
        return
    if not GEMINI_API_KEY:
        for it in batch:
            _fallback_news_enrich(it)
        return

    payload_in = []
    for it in batch:
        t = (it.get("title") or "")[:220]
        d = (it.get("description") or "")[:280]
        payload_in.append({"title": t, "snippet": d})

    prompt = f"""당신은 한국 주식 시장 전문가입니다. 아래 뉴스마다 **JSON 배열만** 출력하세요. 마크다운·설명·머리말 금지.

## 출력 형식 (각 뉴스당 객체)
- "summary": 뉴스가 말하는 사실·핵심만 한국어 **한 문장**. 끝맺음은 '~다.' '~이다.' 등 자연스럽게. "요약:" 같은 접두어 넣지 말 것. 220자 이내.
- "marketImpact": **이 뉴스 내용에만** 기반한 국내 주식시장(코스피·코스닥) 관점 분석 **한 문장**. 원자재·환율·금리·특정 업종·관련 종목 기대 움직임을 구체적으로. "요약:" "시장 영향:" 접두어 넣지 말 것. 200자 이내.

## 좋은 예시 (전쟁·유가 류 뉴스일 때 스타일만 참고, 내용은 입력 뉴스에 맞출 것)
- summary 예: "미국과 이란 간의 전쟁이 심화되고 있다."
- marketImpact 예: "국내 기름값이 폭등할 것으로 예상되어 석유 관련주가 상승할 것으로 예상됩니다."

## 절대 금지
- 모든 기사에 같은 문장을 반복하는 상투구 (예: '단기 변동성에 영향을 줄 수 있습니다', '수급·심리에 영향을 줄 수 있습니다'만 단독으로 쓰기 등)
- 입력과 무관한 일반론만 나열하기
- summary와 marketImpact에 동일 문장 복붙

- "relatedSector": 관련 업종·테마 짧게(예: 석유·정유, 반도체). 없으면 "".
- "relatedStocks": 국내 상장 종목명 0~4개 배열(이 뉴스와 연결되는 경우만).

입력 {len(payload_in)}개 → 출력 배열 길이 동일·순서 동일.

입력:
{json.dumps(payload_in, ensure_ascii=False)}
"""

    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.45,
                        "maxOutputTokens": 4096,
                    },
                },
                timeout=45,
            )
        r.raise_for_status()
        result = r.json()
        raw = result["candidates"][0]["content"]["parts"][0]["text"]
        arr = json.loads(_strip_news_json_text(raw))
        if not isinstance(arr, list) or len(arr) != len(batch):
            raise ValueError("bad array shape")
        for it, ex in zip(batch, arr):
            if not isinstance(ex, dict):
                _fallback_news_enrich(it)
                continue
            desc_fb = (it.get("description") or "").strip()
            if len(desc_fb) > 200:
                desc_fb = desc_fb[:200] + "…"
            sm = _strip_prefix((ex.get("summary") or "").strip(), ("요약:", "요약 :"))
            it["summary"] = sm or desc_fb or ((it.get("title") or "")[:120])
            it["marketImpact"] = _strip_prefix(
                (ex.get("marketImpact") or "").strip(),
                ("시장 영향:", "시장영향:", "시장 영향 :"),
            )
            rs = ex.get("relatedSector")
            it["relatedSector"] = rs.strip() if isinstance(rs, str) else ""
            rst = ex.get("relatedStocks")
            if isinstance(rst, list):
                it["relatedStocks"] = [str(x).strip() for x in rst if str(x).strip()][:4]
            else:
                it["relatedStocks"] = []
    except Exception:
        for it in batch:
            _fallback_news_enrich(it)


async def enrich_news_items(items: List[dict]) -> None:
    """뉴스 목록에 AI 요약·시장 영향 필드 추가 (배치 호출)."""
    batch_size = 10
    for i in range(0, len(items), batch_size):
        await _enrich_news_batch_gemini(items[i : i + batch_size])


# ── 뉴스 조회 ─────────────────────────────────────────
@app.get("/api/news")
async def get_news(query: str = "주식 증시 코스피"):
    try:
        headers = {
            "X-Naver-Client-Id":     NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
        }
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://openapi.naver.com/v1/search/news.json",
                params={"query": query, "display": 12,
                        "sort": "date"},
                headers=headers, timeout=10
            )
            data = r.json()

        items = []
        for item in data.get("items", []):
            # HTML 태그 제거
            title = item["title"].replace("<b>","").replace("</b>","") \
                                 .replace("&amp;","&").replace("&quot;",'"')
            desc  = item["description"].replace("<b>","").replace("</b>","") \
                                       .replace("&amp;","&").replace("&quot;",'"')
            # 감성 분류 (간단 키워드 기반)
            neg_kw = ["하락","급락","손실","악재","우려","위기","감소","침체","폭락"]
            pos_kw = ["상승","급등","호재","기대","성장","증가","돌파","신고가","회복"]
            sentiment = "neutral"
            for k in neg_kw:
                if k in title: sentiment = "negative"; break
            if sentiment == "neutral":
                for k in pos_kw:
                    if k in title: sentiment = "positive"; break

            items.append({
                "title":       title,
                "description": desc,
                "link":        item["link"],
                "pubDate":     item["pubDate"],
                "sentiment":   sentiment,
            })

        await enrich_news_items(items)
        return {"items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── AI 분석 (Gemini) ──────────────────────────────────
class TradeRecord(BaseModel):
    stockName:  str
    stockCode:  str
    tradeType:  str          # "buy" | "sell"
    price:      int
    qty:        int
    avgPrice:   Optional[int] = None
    pnl:        Optional[int] = None
    rsi:        Optional[float] = None
    kospiChg:   Optional[float] = None
    volRatio:   Optional[float] = None
    tradeTime:  str
    # 과거 패턴 통계
    panicCutCount:  int = 0
    earlyExitCount: int = 0
    holdLossCount:  int = 0
    # 누적 매매 건수(학습·맥락용)
    totalTradesLearned: int = 0

@app.post("/api/analyze")
async def analyze_trade(trade: TradeRecord):
    try:
        pnl_pct = None
        if trade.avgPrice and trade.avgPrice > 0:
            pnl_pct = round((trade.price - trade.avgPrice) / trade.avgPrice * 100, 2)

        learned = trade.totalTradesLearned
        prompt = f"""
당신은 개인 투자자의 매매를 사후 분석하는 AI 투자 코치입니다.
투자자 '김한화' 님의 매매를 분석합니다. 아래 JSON 형식으로만 응답하세요.

## 말투·난이도 (필수)
- 주식을 막 시작한 사람도 이해할 수 있게 짧은 문장과 쉬운 말을 쓰세요.
- 전문 용어(RSI, PER, 손절, 익절, 물타기 등)를 쓸 때는 괄호로 한 줄 풀이를 붙이세요.
- 예: "RSI(최근 가격이 얼마나 올랐는지 나타내는 지표)" 처럼 설명을 덧붙이세요.

## 누적 학습 맥락
- 앱에 저장된 김한화 님의 매매 기록은 총 {learned}건입니다. 이번 분석은 그 기록과 아래 패턴 통계를 함께 참고하세요.

## 이번 매매 정보
- 종목: {trade.stockName} ({trade.stockCode})
- 매매 유형: {"매수" if trade.tradeType == "buy" else "매도"}
- 체결가: {trade.price:,}원
- 수량: {trade.qty}주
- 평균 매수가: {f"{trade.avgPrice:,}원" if trade.avgPrice else "해당없음"}
- 손익: {f"{trade.pnl:+,}원 ({pnl_pct:+.1f}%)" if trade.pnl is not None and pnl_pct is not None else "해당없음"}
- 체결 시각: {trade.tradeTime}

## 당시 시장 지표
- RSI: {trade.rsi if trade.rsi else "N/A"}
- 코스피 등락: {f"{trade.kospiChg:+.2f}%" if trade.kospiChg else "N/A"}
- 거래량 비율: {f"{trade.volRatio:.1f}x" if trade.volRatio else "N/A"}

## 김한화 님의 과거 매매 패턴 (앱이 집계한 누적)
- 공황성 손절(작은 손실에 급히 판 경우) 추정: {trade.panicCutCount}회
- 조기 익절(수익이 조금 났을 때 너무 빨리 판 경우) 추정: {trade.earlyExitCount}회
- 큰 손실까지 끌고 갔다가 손절한 경우 추정: {trade.holdLossCount}회

## 응답 형식 (JSON만 출력, 다른 텍스트 금지)
{{
  "scores": {{
    "timing": 0~100 사이 정수,
    "riskManagement": 0~100 사이 정수,
    "marketContext": 0~100 사이 정수
  }},
  "analysis": "이번 매매를 쉬운 말로 3~4문장 분석 (수치 포함)",
  "actions": [
    {{"title": "다음에 실천할 일 (짧은 제목)", "desc": "초보자도 이해할 구체적 설명"}},
    {{"title": "다음에 실천할 일 (짧은 제목)", "desc": "초보자도 이해할 구체적 설명"}},
    {{"title": "다음에 실천할 일 (짧은 제목)", "desc": "초보자도 이해할 구체적 설명"}}
  ],
  "verdict": "한 줄 총평 (김한화 님에게 말하듯, 쉬운 말)",
  "pattern": "감지된 패턴명 또는 null",
  "patternCount": 해당 패턴 누적 횟수 정수
}}
"""
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.4,
                        "maxOutputTokens": 1024,
                    }
                },
                timeout=30
            )
            result = r.json()

        raw = result["candidates"][0]["content"]["parts"][0]["text"]
        # JSON 블록 추출
        raw = raw.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    except Exception as e:
        # Gemini 실패 시 fallback 분석
        return _fallback_analysis(trade, pnl_pct)


def _fallback_analysis(trade: TradeRecord, pnl_pct):
    """Gemini API 실패 시 룰 기반 분석"""
    is_loss = trade.pnl is not None and trade.pnl < 0
    is_buy  = trade.tradeType == "buy"
    rsi     = trade.rsi or 50

    timing = 75 if rsi < 45 else 45
    risk   = 60 if not is_loss else 35
    ctx    = 65 if (trade.kospiChg or 0) > 0 else 42

    if is_buy:
        rsi_note = "낮을수록 '너무 많이 떨어져서 반등할 수 있다'는 쪽에 가깝다는 뜻입니다" if rsi < 45 else "중간쯤이라 추가로 오를지 내릴지 더 지켜볼 구간입니다"
        analysis = (
            f"{trade.stockName}을(를) 사실 때 RSI(최근 가격 움직임 지표)는 {rsi:.1f}였어요. {rsi_note}. "
            f"코스피(국내 주식 시장 대표 지수)는 당시 {trade.kospiChg:+.2f}% 흐름이었습니다."
            if trade.kospiChg is not None
            else f"{trade.stockName} 매수 시점 RSI는 {rsi:.1f}였고, {rsi_note}."
        )
        actions = [
            {"title": "손절가(감당 가능한 하한) 정하기", "desc": f"매수가 {trade.price:,}원보다 5% 아래인 약 {int(trade.price*0.95):,}원에서 미리 팔겠다고 정해두면 공포에 팔 확률이 줄어요."},
            {"title": "목표가(기대 수익 구간) 정하기", "desc": f"예를 들어 {int(trade.price*1.09):,}~{int(trade.price*1.10):,}원 근처에서 일부만 팔고 나머지는 추세를 본다고 정할 수 있어요."},
            {"title": "하루 한 번만 시장만 보기", "desc": "코스피 방향과 뉴스만 짧게 확인하고, 잦은 매매는 피하는 습관이 좋아요."},
        ]
        verdict = "매수 후에는 '어디까지 떨어지면 팔지, 어디까지 오르면 나눠 팔지'만 미리 써두면 마음이 훨씬 편해져요."
        pattern = None
        pattern_count = 0
    elif is_loss:
        loss_pct = abs(pnl_pct) if pnl_pct else 5
        pattern = "공황 손절" if loss_pct < 7 else "장기보유 후 대손절"
        pattern_count = trade.panicCutCount if loss_pct < 7 else trade.holdLossCount
        analysis = (
            f"{trade.stockName}을(를) 평균 매수가보다 약 {pnl_pct:+.1f}% 낮은 가격에 팔아 손실을 확정했어요. "
            f"그때 RSI는 {rsi:.1f}였는데, '아직 회복 여지가 있었는지' 차트를 다시 보면 도움이 돼요."
        )
        actions = [
            {"title": f"'{pattern}'이 반복되는지 보기", "desc": f"비슷한 손절이 지금까지 약 {pattern_count}번 있었어요. 다음엔 매수 직후 손절 가격을 메모앱에 적어두세요."},
            {"title": "자동 매도 주문 알아보기", "desc": "증권앱에서 '내가 정한 가격에 자동 매도' 기능이 있는지 확인해 보세요. 감정이 아니라 규칙으로 팔게 됩니다."},
            {"title": "손절 후 3일만 따라보기", "desc": "팔고 난 뒤 주가가 어떻게 움직였는지 적어두면 같은 실수를 줄이기 쉬워요."},
        ]
        verdict = f"김한화 님, 손실을 줄이려면 '얼마에 팔지'를 사기 전에 정하는 연습부터 해보세요."
    else:
        gain = pnl_pct or 3
        pattern = "조기 익절" if gain < 6 else None
        pattern_count = trade.earlyExitCount
        analysis = (
            f"{trade.stockName}을(를) 평균 매수가보다 약 +{gain:.1f}% 높은 가격에 팔아 수익을 냈어요. "
            f"그 시점 RSI는 {rsi:.1f}로, 주가 상승 '기운'이 아직 남아 있었을 수 있어요."
        )
        actions = [
            {"title": "나눠서 파는 연습", "desc": "한 번에 다 팔지 않고, 예를 들어 5% 올랐을 때 일부, 10%에서 또 일부처럼 나누면 아쉬움이 줄어요."},
            {"title": "남은 물량은 추세 보며", "desc": "첫 목표가에서 절반만 팔고, 나머지는 '이동평균선이 꺾이면 판다'처럼 규칙을 정해보세요."},
            {"title": "만족한 만큼만 챙기기", "desc": f"이번에 약 {trade.pnl:+,}원을 확보했으면 그만큼은 확실한 성과로 인정해도 좋아요."},
        ]
        verdict = "수익을 냈다는 것만으로도 좋아요. 다음엔 '조금 남겨서 더 갈지'만 규칙으로 정해보세요."

    return {
        "scores": {"timing": timing, "riskManagement": risk, "marketContext": ctx},
        "analysis": analysis,
        "actions": actions,
        "verdict": verdict,
        "pattern": pattern,
        "patternCount": pattern_count,
    }


# ── 정적 파일 (프론트엔드) ───────────────────────────
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
async def root():
    if not STATIC_DIR.exists():
        raise HTTPException(
            status_code=500,
            detail="static directory not found in deployment bundle",
        )
    return FileResponse(str(STATIC_DIR / "index.html"))


# ── 웹소켓: 실시간 시세 스트림 ───────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
    async def connect(self, ws: WebSocket):
        await ws.accept(); self.active.append(ws)
    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)
    async def broadcast(self, data: dict):
        dead = []
        for ws in self.active:
            try: await ws.send_json(data)
            except: dead.append(ws)
        for ws in dead: self.active.remove(ws)

manager = ConnectionManager()

@app.websocket("/ws/prices")
async def ws_prices(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            prices = {}
            for code in STOCKS:
                try:
                    d = await kis_get(
                        "/uapi/domestic-stock/v1/quotations/inquire-price",
                        {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code},
                        "FHKST01010100"
                    )
                    o = d["output"]
                    prices[code] = {
                        "price":     int(o["stck_prpr"]),
                        "changePct": float(o["prdy_ctrt"]),
                    }
                except:
                    pass
            await websocket.send_json({"type": "prices", "data": prices})
            await asyncio.sleep(5)   # 5초마다 갱신
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)