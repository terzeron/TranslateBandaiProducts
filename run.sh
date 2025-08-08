#!/bin/bash

# 건프라 사이트 미러링 및 상품명 추출 통합 스크립트

echo "건프라 사이트 데이터 수집 시작..."

# gcd(JSON API) 데이터 수집
echo
echo "=== gcd(JSON API) 데이터 수집 ==="
./mirror_site.sh gcd -c -e > gcd.log 2>&1

# Gundaminfo 데이터 수집
echo
echo "=== Gundaminfo 데이터 추출 ==="
./mirror_site.sh gundaminfo -c -e > gundaminfo.log 2>&1 

# Dalong.net 데이터 수집  
echo
echo "=== Dalong.net 데이터 수집 ==="
./mirror_site.sh dalong -c -e > dalong.log 2>&1

# Bandai Manual 데이터 수집
echo
echo "=== Bandai Manual 데이터 수집 ==="
./mirror_site.sh bandai-hobby -c > bandai-hobby.log 2>&1

#echo
#echo "=== 번역 참고 자료 추출 ==="
#python gemini_agent.py < instruction.md
if ./convert_bandai_product_ja2ko.py | grep "translating error:" > /dev/null; then
    (cat instruction.md; ./convert_bandai_product_ja2ko.py | grep "translating error:") | ~/.claude/local/claude -p
fi

echo
echo "=== Bandai Manual 결과 조회 및 HTML 저장 ==="
./convert_bandai_product_ja2ko.py 
./convert_bandai_product_ja2ko.py -h > ~/public_html/xml/bandai.html
