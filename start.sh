#!/bin/bash
echo "======================================"
echo "  A-Note 서버 시작"
echo "======================================"
 
# 패키지 설치
pip install -r requirements.txt --break-system-packages -q
 
# .env 파일 확인
if grep -q "여기에" .env; then
  echo ""
  echo "⚠️  .env 파일에 API 키를 입력해주세요!"
  echo "   - KIS_APP_KEY"
  echo "   - KIS_APP_SECRET"
  echo "   - KIS_ACCOUNT"
  echo "   - NAVER_CLIENT_ID"
  echo "   - NAVER_CLIENT_SECRET"
  echo "   - GEMINI_API_KEY"
  echo ""
  echo "입력 후 다시 실행하세요."
  exit 1
fi
 
echo ""
echo "서버 시작: http://localhost:8000"
echo "브라우저에서 위 주소를 열어주세요."
echo ""
python server.py