import pandas as pd
import datetime

# 1. 시연용 가공 데이터 구성
data = [
    {
        "매매날짜": "2026-03-10",
        "종목명": "삼성전자",
        "매매유형": "매수",
        "가격": 84500,
        "수량": 10,
        "당시뉴스": "반도체 역대급 실적 전망, '8만전자' 안착하나?",
        "투자심리": "탐욕 (추격 매수)"
    },
    {
        "매매날짜": "2026-03-25",
        "종목명": "SK하이닉스",
        "매매유형": "매수",
        "가격": 182000,
        "수량": 5,
        "당시뉴스": "HBM 공급 부족 현상 심화, 목표가 상향 조정",
        "투자심리": "확신"
    },
    {
        "매매날짜": "2026-04-05",
        "종목명": "엔비디아",
        "매매유형": "매도",
        "가격": 880,
        "수량": 2,
        "당시뉴스": "미 금리 인하 기대감 후퇴, 기술주 일제히 하락",
        "투자심리": "공포 (패닉 셀링)"
    }
]

# 2. 데이터프레임 생성 및 CSV 저장
df = pd.DataFrame(data)
df.to_csv("trade_history.csv", index=False, encoding="utf-8-sig")

print("시연용 데이터 'trade_history.csv'가 생성되었습니다.")

# 3. 로드 확인 코드
def load_data():
    return pd.read_csv("trade_history.csv")

if __name__ == "__main__":
    test_df = load_data()
    print(test_df)