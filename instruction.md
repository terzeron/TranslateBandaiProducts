# 건담 프라모델 일본어-한국어 번역 작업

## 핵심 작업 지침
- **절대로 새로운 스크립트를 작성하지 말 것**
- **기존 도구만 사용할 것**
- **단계별로 효율적으로 진행할 것**

## 목표
convert_bandai_product_ja2ko.py 실행 시 translating error가 발생하는 일본어 상품명을 한국어로 번역
실행할 명령: `./convert_bandai_product_ja2ko.py manual.bandai-hobby.net/menus/detail manual.bandai-hobby.net/pdf bandai_product_ja_ko_mapping.json`

## 작업 순서 (반드시 이 순서로 진행)

### 1단계: 다음 파일의 한국어 텍스트를 참고해서 번역할 것
* bandai-hobby_products.json
* bnkrmall_products.json
* dalong_products.json
* gundaminfo_products.json

### 2단계: 결과 확인
각 도구 실행 후:
- `./convert_bandai_product_ja2ko.py manual.bandai-hobby.net/menus/detail manual.bandai-hobby.net/pdf bandai_product_ja_ko_mapping.json` 실행
- 남은 오류 개수 확인
- 진행 상황 보고

## 번역 규칙
- 브랜드명: HG, RG, MG, PG, RE/100 등 그대로 유지
- 스케일: 1/144, 1/100 등 그대로 유지
- 기체명: 한국 건프라 커뮤니티 통용 표기 우선
- 히라가나, 카타카나 완전 제거
- 대체 표기가 있을 경우 괄호 병기 (예: 스트라이크 루즈(루지) B팩)

## 출력 요구사항
- bandai_product_ja_ko_mapping.json에 추가 (기존 항목 수정 금지)
- 백업 파일 생성: bandai_product_ja_ko_mapping.json.YYMMDD
- 간단한 처리 결과 보고. 특히 신규 번역된 항목 모두 나열할 것

## 금지 사항
- 기존 스크립트 수정 금지
- 불필요한 파일 생성 금지
- 긴 설명이나 분석 금지
- 부득이하게 새로운 Python 스크립트를 작성해야 한다면 최소화해서 작성하고, 반드시 용도를 설명할 것

## 시간 절약을 위한 핵심 포인트
1. 기존 도구를 순서대로 실행
2. 각 단계 후 결과만 간단히 보고
3. 자동화로 해결되지 않는 경우만 수동 번역
4. 빠른 진행과 효율성 우선
