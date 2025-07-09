#!/bin/bash

# 건프라 사이트 미러링 및 상품명 추출 통합 스크립트

echo "건프라 사이트 데이터 수집 시작..."

# BNKR Mall 데이터 수집
echo
echo "=== BNKR Mall 데이터 추출 ==="
./mirror_site.sh bnkrmall -e

# Gundaminfo 데이터 수집
echo
echo "=== Gundaminfo 데이터 추출 ==="
./mirror_site.sh gundaminfo -c -e

# Dalong.net 데이터 수집  
echo
echo "=== Dalong.net 데이터 수집 ==="
./mirror_site.sh dalong -c -e

# Bandai Manual 데이터 수집
echo
echo "=== Bandai Manual 데이터 수집 ==="
./mirror_site.sh bandai-hobby -c -e

echo
echo "=== 번역 참고 자료 추출 ==="
cat instruction.md | ~/.claude/local/claude --dangerously-skip-permissions -p --file bnkrmall_products.json --file gundaminfo_products.json --file dalong_products.json

echo
echo "=== Bandai Manual 결과 조회 및 HTML 저장 ==="
./convert_bandai_product_ja2ko.py manual.bandai-hobby.net/menus/detail manual.bandai-hobby.net/pdf bandai_product_ja_ko_mapping.json
./convert_bandai_product_ja2ko.py -h manual.bandai-hobby.net/menus/detail manual.bandai-hobby.net/pdf bandai_product_ja_ko_mapping.json > ~/public_html/xml/bandai.html
