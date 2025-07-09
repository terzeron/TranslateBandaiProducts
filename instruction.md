# 건담 프라모델 일본어-한국어 번역 작업

## 목표
convert_bandai_product_ja2ko.py 실행 시 translating error가 발생하는 일본어 상품명을 한국어로 번역
실행할 명령: ./convert_bandai_product_ja2ko.py manual.bandai-hobby.net/menus/detail manual.bandai-hobby.net/pdf bandai_product_ja_ko_mapping.json

## 번역 우선순위 (배치 처리)
1. **gundaminfo_products.json 매칭** - 가장 높은 우선순위
2. **dalong_products.json 매칭** - 두 번째 우선순위
3. **bnkr_products.json 매칭** - 세 번째 우선순위
4. **Claude 건프라 전문 번역** - 단순 번역이 아니라 한국 통용 표기가 필수임

## 자동화 도구 활용
현재 디렉터리에 있는 다음 번역 도구들을 활용하여 작업 효율성을 높일 것:

### 1. 주요 번역 스크립트
- **gundam_batch_translator.py**: 자동 오류 탐지 및 일괄 번역 처리
- **batch_translator.py**: 수동 오류 목록 기반 배치 번역
- **enhanced_translator.py**: 고급 N-gram 매칭 및 우선순위 번역
- **final_translator.py**: Eclipse 건담 특수 번역 문제 해결

### 2. 번역 도구 사용법
```bash
# 1단계: 자동 오류 탐지 및 일괄 처리
python gundam_batch_translator.py

# 2단계: 추가 오류 처리 (필요시)
python batch_translator.py

# 3단계: Eclipse 건담 특수 처리
python enhanced_translator.py
python final_translator.py
```

### 3. 번역 품질 향상 전략
- **N-gram 매칭**: 부분 문자열 매칭으로 유사 제품명 찾기
- **유사도 점수**: 문자열 유사도 기반 최적 매칭
- **컨텍스트 인식**: 브랜드, 스케일, 연도 정보 활용
- **다중 소스 참조**: 여러 데이터베이스 교차 검증

## 처리 방식
- 모든 참조 파일을 초기에 한 번만 로딩
- 오류 발생 항목들을 배치로 처리
- 매칭 품질: 단어 일치도 + 유사도 점수 기준
- 대체 표기: 다른 번역이 있을 경우 괄호 병기 (예: 스트라이크 루즈(루지) B팩)
- 히라가나, 카타카나가 한국어 번역문에 노출되지 않도록 꼼꼼하게 번역할 것
- **자동화 도구 우선 활용**: 수동 번역 전에 기존 번역 스크립트로 최대한 자동 처리

## 번역 가이드라인
### 건담 전문 용어 표준화
- 모빌슈트명: 일관된 한국어 표기 사용
- 캐릭터명: 일본 발음 기준 한국어 표기

## 참고 자료 활용법
- 브랜드명 표기: HG, RG, MG, PG, RE/100 등은 그대로 유지
- 스케일 표기: 1/144, 1/100 등은 그대로 유지
- 기체명 번역: 참고 자료의 한국어 표기법 따름
- 신뢰도: 고품질 참고 자료 우선 참조

### 품질 검증 기준
- 기존 번역과의 일관성 확인
- 한국 건프라 커뮤니티 통용 표기 우선
- 브랜드 정보 및 스케일 정보 보존
- 특수 문자 및 기호 적절한 처리

## 출력
- translating error가 발생했던 미번역 항목의 번역 결과를 bandai_product_ja_ko_mapping.json에 추가하되 기존 번역 항목은 수정하지 말 것
- 백업 파일 생성: bandai_product_ja_ko_mapping.json.YYMMDD
- 번역 처리 로그 및 품질 점수 기록
- 자동화 도구 실행 결과 보고


