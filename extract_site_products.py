#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
import json
from pathlib import Path
from html.parser import HTMLParser
import unicodedata

class ProductExtractor(HTMLParser):
    def __init__(self, site_name="bnkrmall.co.kr"):
        super().__init__()
        self.products = []
        self.current_text = ""
        self.in_title = False
        self.in_product_name = False
        self.current_tag = ""
        self.site_name = site_name
        
        # 범용 특수 파싱 변수들
        self.in_special_field = False
        self.special_field_type = ""
        self.current_class = ""

        
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag == 'title':
            self.in_title = True
        
        # 범용적인 클래스/ID 기반 파싱
        for attr_name, attr_value in attrs:
            if attr_name == 'class' and attr_value:
                self.current_class = attr_value.lower()
                # 다양한 사이트의 구조화된 정보 클래스들을 체크
                special_classes = {
                    'codename': 'codename',
                    'fullname': 'fullname', 
                    'productname': 'product_name',
                    'product-name': 'product_name',
                    'item-name': 'item_name',
                    'goods-name': 'goods_name',
                    'model-name': 'model_name',
                    'kit-name': 'kit_name'
                }
                
                for class_pattern, field_type in special_classes.items():
                    if class_pattern in attr_value.lower():
                        self.in_special_field = True
                        self.special_field_type = field_type
                        break
                
            # 상품명이 들어갈 가능성이 있는 클래스나 ID 체크
            if attr_name in ['class', 'id'] and attr_value:
                if any(keyword in attr_value.lower() for keyword in ['product', 'item', 'goods', 'name', 'title', 'model', 'kit']):
                    self.in_product_name = True

    
    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if self.in_product_name:
            self.in_product_name = False
        if self.in_special_field:
            self.in_special_field = False
            self.special_field_type = ""
        self.current_tag = ""
        self.current_class = ""

    
    def handle_data(self, data):
        cleaned_data = self.clean_text(data)
        if cleaned_data and len(cleaned_data) > 5:
            # 우선순위: 1) 특수 필드, 2) 타이틀, 3) 상품명 클래스, 4) 일반
            if self.in_special_field and cleaned_data.strip():
                # 구조화된 필드는 키워드 체크 없이 수집 (더 신뢰도 높음)
                self.products.append({
                    'text': cleaned_data,
                    'source': self.special_field_type,
                    'tag': self.current_tag,
                    'confidence': 'high'
                })
            elif self.in_title and self.is_potential_gunpla(cleaned_data):
                self.products.append({
                    'text': cleaned_data,
                    'source': 'title',
                    'tag': self.current_tag,
                    'confidence': 'medium'
                })
            elif self.in_product_name and self.is_potential_gunpla(cleaned_data):
                self.products.append({
                    'text': cleaned_data,
                    'source': 'product_name',
                    'tag': self.current_tag,
                    'confidence': 'medium'
                })
            elif self.is_potential_gunpla(cleaned_data):
                self.products.append({
                    'text': cleaned_data,
                    'source': 'general',
                    'tag': self.current_tag,
                    'confidence': 'low'
                })
 
   
    def clean_text(self, text):
        # HTML 엔티티 정리
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&apos;', "'")
        
        # 유니코드 정규화
        text = unicodedata.normalize('NFKC', text)
        
        # 불필요한 문자 제거
        text = re.sub(r'[\r\n\t]+', ' ', text)  # 개행문자를 공백으로
        text = re.sub(r'\s+', ' ', text)       # 연속 공백을 하나로
        
        # 앞뒤 공백 및 특수문자 제거
        text = text.strip(' \t\n\r\f\v｜|[]()<>{}"\'')
        
        return text
    
    def extract_product_name(self, text):
        """설명문에서 상품명만 추출"""
        # 상품명 패턴들 (브랜드 + 스케일 + 모델명)
        product_patterns = [
            r'(HG|RG|MG|PG|RE/?100)\s+1/\d+\s+[^\s]+[^\.\!\?]*',
            r'1/\d+\s+(HG|RG|MG|PG|RE/?100)\s+[^\s]+[^\.\!\?]*',
            r'(HG|RG|MG|PG|RE/?100)[^\d]*1/\d+[^\.\!\?]*',
        ]
        
        for pattern in product_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted = match.group(0).strip()
                # 문장 끝 표시나 설명문 제거
                extracted = re.sub(r'[\.\!\?].*$', '', extracted)
                extracted = re.sub(r'(입니다|됩니다|했습니다|있습니다).*$', '', extracted)
                if len(extracted) < 80:  # 토큰 절약을 위해 80자 제한
                    return extracted
        
        # 브랜드명이 포함된 짧은 텍스트
        if re.search(r'(HG|RG|MG|PG|RE)\s', text, re.IGNORECASE) and len(text) <= 50:
            # 설명문 제거
            text = re.sub(r'(와|과|과 함께|와 함께).*$', '', text)
            text = re.sub(r'(입니다|됩니다|했습니다|있습니다).*$', '', text)
            return text.strip()
        
        return text
    
    def should_include_as_reference(self, text):
        """번역 참고 자료로 포함할 가치가 있는 텍스트인지 판단"""
        # 너무 긴 텍스트는 제외 (토큰 절약)
        if len(text) > 80:
            return False
        
        # 완전한 한국어 상품명이 있는 텍스트를 우선 선택 (참고 자료용)
        korean_gunpla = re.match(r'^[가-힣\s\d/\-\(\)HG|RG|MG|PG|RE]+$', text)
        if korean_gunpla and re.search(r'(HG|RG|MG|PG|RE)', text):
            return True
        
        # 브랜드 + 스케일 + 한국어 모델명 조합 (좋은 참고 자료)
        has_brand = bool(re.search(r'(HG|RG|MG|PG|RE)', text))
        has_scale = bool(re.search(r'1/\d+', text))
        has_korean_model = bool(re.search(r'[가-힣]', text))
        
        if has_brand and has_scale and has_korean_model:
            return True
        
        # 일본어가 포함되어도 한국어가 같이 있으면 참고 자료로 유용
        has_japanese = bool(re.search(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]', text))
        if has_japanese and has_korean_model and has_brand:
            return True
        
        return False

    def is_potential_gunpla(self, text):
        # 기본 필터링: 길이 체크 (토큰 절약을 위해 더 엄격하게)
        if len(text) < 8 or len(text) > 80:  # 150 -> 80으로 단축
            return False
            
        # 불필요한 텍스트 필터링 (쿠키, 저작권, 네비게이션 등)
        exclude_patterns = [
            r'cookie', r'copyright', r'privacy', r'terms',
            r'navigation', r'menu', r'search', r'login',
            r'카트', r'장바구니', r'회원', r'로그인',
            r'주문', r'결제', r'배송', r'문의',
            r'\d{4}-\d{2}-\d{2}',  # 날짜 형식
            r'^[\d\s\-\.]+$',     # 숫자와 구두점만
            r'^[가-힣]{1,2}$',     # 한글 1-2글자만
            r'다운로드', r'업로드', r'페이지', r'사이트',
            r'링크', r'클릭', r'버튼', r'메뉴',
            r'상품 설명', r'제품 설명', r'상세 정보'
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        # 사이트별 키워드 설정 (더 엄격하게)
        if self.site_name == "dalong.net":
            # Dalong.net은 일본어 키워드 위주
            primary_keywords = ['ガンダム', 'ガンプラ', 'プラモデル']
            secondary_keywords = ['HG', 'RG', 'MG', 'PG', 'RE/100']
            model_keywords = [
                'フリーダム', 'ストライク', 'バルバトス', 'ユニコーン', 'エクシア',
                'ウイングガンダム', 'デスティニー', 'インパルス', 'ジャスティス'
            ]
        elif self.site_name == "manual.bandai-hobby.net":
            # Bandai Manual은 일본어 키워드 위주 (공식 사이트)
            primary_keywords = ['ガンダム', 'ガンプラ', 'プラモデル']
            secondary_keywords = ['HG', 'RG', 'MG', 'PG', 'RE/100']
            model_keywords = [
                'フリーダム', 'ストライク', 'バルバトス', 'ユニコーン', 'エクシア',
                'ウイングガンダム', 'デスティニー', 'インパルス', 'ジャスティス',
                'ストライクルージュ', 'スカイグラスパー', 'ルージュ', 'グラスパー'
            ]
        elif self.site_name == "gundam-wiki":
            # Gundam Wiki: 영어/일본어/한국어 모두 포함
            primary_keywords = [
                'ガンダム', 'Gundam', '건담',
                'Mobile Suit', 'モビルスーツ', '모빌슈트',
                'ガンプラ', 'Gunpla', '건프라'
            ]
            secondary_keywords = ['HG', 'RG', 'MG', 'PG', 'RE/100', 'RE']
            model_keywords = [
                # 일본어
                'フリーダム', 'ストライク', 'バルバトス', 'ユニコーン', 'エクシア',
                'ザク', 'ジム', 'シャア', 'キュベレイ', 'ノイエジール',
                # 영어
                'Freedom', 'Strike', 'Barbatos', 'Unicorn', 'Exia',
                'Zaku', 'GM', 'Char', 'Qubeley', 'Neue Ziel',
                # 한국어
                '프리덤', '스트라이크', '바르바토스', '유니콘', '엑시아',
                '자쿠', '짐', '샤아', '큐베레이', '노이에질'
            ]
        elif self.site_name == "kr.gundam.info":
            # Gundam Info 한국 사이트: 한국어 중심, 공식 사이트
            primary_keywords = [
                '건담', '건프라', '프라모델', '모빌슈트',
                'ガンダム', 'ガンプラ', 'プラモデル', 'モビルスーツ',
                'Gundam', 'Gunpla', 'Mobile Suit'
            ]
            secondary_keywords = ['HG', 'RG', 'MG', 'PG', 'RE', 'RE/100']
            model_keywords = [
                # 한국어
                '프리덤', '스트라이크', '바르바토스', '유니콘', '엑시아',
                '윙건담', '데스티니', '임펄스', '저스티스', '세라비',
                '자쿠', '짐', '샤아', '큐베레이', '노이에질', '지온',
                # 일본어
                'フリーダム', 'ストライク', 'バルバトス', 'ユニコーン', 'エクシア',
                'ウイングガンダム', 'デスティニー', 'インパルス', 'ジャスティス',
                'ザク', 'ジム', 'シャア', 'キュベレイ', 'ノイエジール',
                # 영어
                'Freedom', 'Strike', 'Barbatos', 'Unicorn', 'Exia',
                'Wing Gundam', 'Destiny', 'Impulse', 'Justice',
                'Zaku', 'GM', 'Char', 'Qubeley', 'Neue Ziel'
            ]
        else:
            # BNKR Mall은 한국어 키워드 위주
            primary_keywords = ['건담', '건프라', '프라모델', 'ガンダム', 'ガンプラ']
            secondary_keywords = ['HG', 'RG', 'MG', 'PG', 'RE']
            model_keywords = [
                '프리덤', '스트라이크', '바르바토스', '유니콘', '엑시아',
                '윙건담', '데스티니', '임펄스', '저스티스', '세라비'
            ]
        
        text_lower = text.lower()
        
        # 1순위: 기본 키워드 체크
        has_primary = any(keyword.lower() in text_lower for keyword in primary_keywords)
        
        # 2순위: 스케일 + 브랜드 조합
        has_scale = re.search(r'1/(?:144|100|60|48)', text)
        has_brand = any(keyword.lower() in text_lower for keyword in secondary_keywords)
        
        # 3순위: 모델명 키워드
        has_model = any(keyword.lower() in text_lower for keyword in model_keywords)
        
        # 점수 기반 판정
        score = 0
        if has_primary: score += 3
        if has_scale and has_brand: score += 2
        elif has_scale or has_brand: score += 1  
        if has_model: score += 1
        
        # 추가 보너스: 정확한 건프라 패턴
        if re.search(r'(HG|RG|MG|PG|RE)\s+1/\d+', text, re.IGNORECASE):
            score += 2
            
        return score >= 2


def extract_products_from_html(html_file, site_name):
    """HTML 파일에서 건프라 상품 정보 추출"""
    try:
        with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        extractor = ProductExtractor(site_name)
        extractor.feed(content)
        
        return extractor.products
    except Exception as e:
        print(f"Error processing {html_file}: {e}")
        return []


def process_mirror_directory(mirror_dir, site_name):
    """미러링된 디렉토리에서 모든 HTML 파일 처리"""
    all_products = []
    
    # 범용적으로 .html과 .htm 파일들을 모두 포함
    html_files = list(Path(mirror_dir).rglob("*.html")) + list(Path(mirror_dir).rglob("*.htm"))
    
    print(f"Processing {len(html_files)} HTML files...")
    
    for html_file in html_files:
        products = extract_products_from_html(html_file, site_name)
        for product in products:
            product['file'] = str(html_file)
        all_products.extend(products)
    
    return all_products


def save_semi_structured_data(products, output_file, site_name):
    """추출된 상품 정보를 Claude CLI 번역 참고 자료로 최적화된 형태로 저장 (토큰 절약)"""
    # 중복 제거 및 정리
    unique_products = {}
    extractor = ProductExtractor(site_name)
    
    for product in products:
        original_text = product['text']
        
        # 상품명 추출 및 정제
        refined_text = extractor.extract_product_name(original_text)
        
        # 참고 자료 가치 판단
        if not extractor.should_include_as_reference(refined_text):
            continue
        
        # 최종 길이 제한 (토큰 절약)
        if len(refined_text) > 80:
            continue
            
        if refined_text not in unique_products:
            product['text'] = refined_text  # 정제된 텍스트로 교체
            unique_products[refined_text] = product
        else:
            # 더 좋은 소스로 업데이트
            source_priority = {
                'codename': 10, 'fullname': 9, 'product_name': 8, 'item_name': 7, 
                'goods_name': 6, 'model_name': 5, 'kit_name': 4,
                'title': 3, 'general': 1
            }
            current_priority = source_priority.get(product['source'], 0)
            existing_priority = source_priority.get(unique_products[refined_text]['source'], 0)
            
            if current_priority > existing_priority:
                product['text'] = refined_text
                unique_products[refined_text] = product
    
    # 품질 점수로 정렬 (높은 점수부터)
    sorted_products = sorted(unique_products.values(), 
                           key=lambda x: x.get('quality_score', 0), reverse=True)
    
    # 토큰 절약을 위한 압축된 참고 자료 JSON 구조 생성
    reference_data = {
        "meta": {
            "site": site_name,
            "date": os.popen('date +"%Y-%m-%d"').read().strip(),
            "total": len(sorted_products),
            "version": "2.1",
            "purpose": "gunpla_reference"  # 번역 참고 자료임을 명시
        },
        "usage": {  # instructions -> usage로 변경
            "description": "Claude 번역 시 참고용 한국어 건프라 상품명",
            "how_to_use": [
                "일본어 건프라 상품명 번역 시 이 데이터를 참고",
                "브랜드명(HG,RG,MG,PG,RE/100) 표기법 참조",
                "한국어 기체명 표기법 참조",
                "스케일 표기법 참조"
            ]
        },
        "references": []  # products -> references로 변경
    }
    
    # 품질별 그룹화 (참고 자료로서 가치가 높은 것만)
    high_quality_refs = []
    medium_quality_refs = []
    reference_items = []
    
    for product in sorted_products:
        # 참고 자료에 필요한 핵심 정보만 추출
        ref_data = {
            "id": len(reference_items) + 1,
            "korean_name": product['text'],  # text -> korean_name으로 명확화
            "quality": product.get('quality_score', 0),
            "reliable": product.get('is_high_quality', False)
        }
        
        # 참고 정보 추가 (압축된 형태)
        text = product['text']
        info = []
        
        # 브랜드 정보 추출
        brand_match = re.search(r'\b(HG|RG|MG|PG|RE/?100)\b', text, re.IGNORECASE)
        if brand_match:
            info.append(f"brand:{brand_match.group(1)}")
        
        # 스케일 정보 추출
        scale_match = re.search(r'1/(\d+)', text)
        if scale_match:
            info.append(f"scale:1/{scale_match.group(1)}")
        
        # 기체 타입 추출 (참고용)
        model_types = []
        for model in ['스트라이크', '프리덤', '유니콘', '엑시아', '바르바토스', '자쿠', '짐']:
            if model in text:
                model_types.append(model)
        
        if model_types:
            info.append(f"models:{','.join(model_types)}")
        
        if info:
            ref_data["info"] = info
        
        # 품질별 분류
        if product.get('is_high_quality', False):
            high_quality_refs.append(ref_data)
        elif product.get('quality_score', 0) >= 2:
            medium_quality_refs.append(ref_data)
        
        reference_items.append(ref_data)
    
    # 토큰 절약을 위해 상위 품질 참고 자료만 포함
    max_references = 1000  # 최대 1000개로 제한
    if len(reference_items) > max_references:
        reference_items = reference_items[:max_references]
        print(f"토큰 절약을 위해 상위 {max_references}개 참고 자료만 포함")
    
    reference_data["references"] = reference_items
    
    # 참고 자료 품질 정보
    reference_data["quality_info"] = {
        "high_quality": len(high_quality_refs),
        "medium_quality": len(medium_quality_refs),
        "total_references": len(reference_items)
    }
    
    # JSON 형태로 저장 (압축된 형태)
    json_output = output_file.replace('.txt', '.json')
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump(reference_data, f, ensure_ascii=False, indent=1, separators=(',', ':'))
    
    # 텍스트 형태로도 저장 (참고 자료 목록)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# {site_name} 건프라 상품명 참고 자료\n")
        f.write(f"# 날짜: {reference_data['meta']['date']}\n")
        f.write(f"# 총 {len(reference_items)}개 참고 자료 (토큰 절약)\n")
        f.write(f"# 용도: Claude 번역 시 한국어 표기법 참고\n\n")
        
        # 고품질 참고 자료 우선 출력
        f.write("## 고품질 참고 자료 (신뢰도 높음)\n")
        for ref in high_quality_refs:
            f.write(f"{ref['korean_name']}\n")
        
        if medium_quality_refs:
            f.write(f"\n## 중간품질 참고 자료 ({len(medium_quality_refs)}개)\n")
            for ref in medium_quality_refs[:200]:  # 최대 200개만
                f.write(f"{ref['korean_name']}\n")
    
    # 토큰 사용량 추정
    total_chars = sum(len(r['korean_name']) for r in reference_items)
    estimated_tokens = total_chars // 3  # 대략적인 토큰 추정
    
    print(f"Reference data saved to:")
    print(f"  - {output_file} (text format)")
    print(f"  - {json_output} (reference JSON)")
    print(f"  - Total references: {len(reference_items)} (제한됨)")
    print(f"  - High quality: {len(high_quality_refs)}")
    print(f"  - Medium quality: {len(medium_quality_refs)}")
    print(f"  - Estimated tokens: ~{estimated_tokens:,}")
    print(f"  - Average length: {total_chars/len(reference_items):.1f} chars")
    

def validate_and_filter_products(products):
    """추출된 제품 데이터의 품질 검증 및 필터링"""
    validated_products = []
    
    for product in products:
        text = product['text']
        
        # 품질 점수 계산
        quality_score = 0
        
        # 1. 브랜드 + 스케일 + 모델명 패턴 (최고 점수)
        if re.search(r'(HG|RG|MG|PG|RE)\s+1/\d+\s+\S+', text, re.IGNORECASE):
            quality_score += 5
        
        # 2. 스케일 정보 있음
        if re.search(r'1/(?:144|100|60|48)', text):
            quality_score += 2
            
        # 3. 브랜드 정보 있음
        if re.search(r'\b(HG|RG|MG|PG|RE)\b', text, re.IGNORECASE):
            quality_score += 2
            
        # 4. 건프라 관련 키워드
        gunpla_terms = ['건담', '건프라', '프라모델', '모빌슈트']
        if any(term in text for term in gunpla_terms):
            quality_score += 1
            
        # 5. 구체적인 모델명 키워드
        model_terms = ['스트라이크', '유니콘', '엑시아', '프리덤', '발바토스', '자쿠', '짐', '샤아', '큐베레이', '노이에질', '지온', '아무로', '데스티니', '임펄스', '저스티스', '세라비']
        if any(term in text for term in model_terms):
            quality_score += 1
            
        # 품질 점수 추가
        product['quality_score'] = quality_score
        product['is_high_quality'] = quality_score >= 3
        
        # 최소 품질 기준 통과 시 추가
        if quality_score >= 1:
            validated_products.append(product)
    
    return validated_products


def main():
    if len(sys.argv) != 4:
        print("Usage: python3 extract_site_products.py <mirror_directory> <output_file> <site_name>")
        sys.exit(1)
    
    mirror_dir = sys.argv[1]
    output_file = sys.argv[2]
    site_name = sys.argv[3]
    
    if not os.path.exists(mirror_dir):
        print(f"Error: Mirror directory '{mirror_dir}' does not exist")
        sys.exit(1)
    
    print(f"Extracting Gunpla products from {site_name}: {mirror_dir}")
    
    # HTML 파일에서 상품 정보 추출
    products = process_mirror_directory(mirror_dir, site_name)
    
    if not products:
        print("No Gunpla products found")
        sys.exit(1)
    
    print(f"Raw products extracted: {len(products)}")
    
    # 품질 검증 및 필터링
    validated_products = validate_and_filter_products(products)
    
    print(f"Products after validation: {len(validated_products)}")
    high_quality_count = sum(1 for p in validated_products if p.get('is_high_quality', False))
    print(f"High quality products: {high_quality_count}")
    
    # Semi-structured 데이터로 저장
    save_semi_structured_data(validated_products, output_file, site_name)
    
    print("Extraction completed successfully!")


if __name__ == "__main__":
    main()