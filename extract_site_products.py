#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
from pathlib import Path
from html.parser import HTMLParser
import unicodedata
import json

# chardet가 없을 경우를 대비한 fallback
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False

class ProductExtractor(HTMLParser):
    def __init__(self, site_name: str):
        super().__init__()
        self.products = []
        self.current_text = ""
        self.in_title = False
        self.in_product_name = False
        self.in_link = False  # a 태그 추적
        self.in_heading = False  # h1-h6 태그 추적
        self.in_strong = False  # strong, b 태그 추적
        self.in_em = False  # em, i 태그 추적
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
        elif tag == 'a':
            self.in_link = True
        elif tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self.in_heading = True
        elif tag in ['strong', 'b']:
            self.in_strong = True
        elif tag in ['em', 'i']:
            self.in_em = True
        elif tag in ['span', 'div', 'p', 'td', 'th', 'li', 'dt', 'dd']:
            # 더 많은 태그에서 제목으로 인식
            for attr_name, attr_value in attrs:
                if attr_name == 'class' and attr_value:
                    title_keywords = ['title', 'name', 'heading', 'caption', 'label', 'header', 'product', 'item', 'model', 'kit']
                    if any(keyword in attr_value.lower() for keyword in title_keywords):
                        self.in_product_name = True
                        break
        elif tag == 'meta':
            # meta 태그에서 제목 추출
            meta_name = None
            meta_content = None
            for attr_name, attr_value in attrs:
                if attr_name == 'name':
                    meta_name = attr_value
                elif attr_name == 'content':
                    meta_content = attr_value
            
            if meta_name and meta_content and 'title' in meta_name.lower():
                if len(meta_content) > 3 and len(meta_content) < 200:
                    self.products.append({
                        'text': meta_content,
                        'source': 'meta_title',
                        'tag': 'meta',
                        'confidence': 'high'
                    })
        
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
                    'kit-name': 'kit_name',
                    'title': 'title_class',
                    'name': 'name_class',
                    'heading': 'heading_class',
                    'caption': 'caption_class',
                    'label': 'label_class',
                    'text': 'text_class',
                    'header': 'header_class',
                    'subtitle': 'subtitle_class',
                    'brand': 'brand_class',
                    'series': 'series_class',
                    'version': 'version_class',
                    'type': 'type_class',
                    'category': 'category_class'
                }
                
                for class_pattern, field_type in special_classes.items():
                    if class_pattern in attr_value.lower():
                        self.in_special_field = True
                        self.special_field_type = field_type
                        break
                
            # 상품명이 들어갈 가능성이 있는 클래스나 ID 체크
            if attr_name in ['class', 'id'] and attr_value:
                title_keywords = ['product', 'item', 'goods', 'name', 'title', 'model', 'kit', 'review', 'gundam', 'gunpla', 'mobile', 'suit']
                if any(keyword in attr_value.lower() for keyword in title_keywords):
                    self.in_product_name = True

    
    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        elif tag == 'a':
            self.in_link = False
        elif tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self.in_heading = False
        elif tag in ['strong', 'b']:
            self.in_strong = False
        elif tag in ['em', 'i']:
            self.in_em = False
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
            # title 태그에서 모든 텍스트를 빠짐없이 추출 (건프라 키워드 체크 완화)
            if self.in_title and cleaned_data.strip():
                self.products.append({
                    'text': cleaned_data,
                    'source': 'title',
                    'tag': self.current_tag,
                    'confidence': 'high'
                })
            # a 태그 텍스트도 title로 인식 (네비게이션 링크나 상품 링크)
            elif self.in_link and cleaned_data.strip():
                # a 태그는 건프라 키워드 체크를 완화 (더 많은 링크 텍스트 수집)
                if len(cleaned_data) > 3 and len(cleaned_data) < 200:  # 길이 제한만 적용
                    self.products.append({
                        'text': cleaned_data,
                        'source': 'link_title',  # a 태그에서 추출된 title
                        'tag': self.current_tag,
                        'confidence': 'high'
                    })
            # 제목 태그들 (h1-h6)에서 추출
            elif self.in_heading and cleaned_data.strip():
                if len(cleaned_data) > 3 and len(cleaned_data) < 150:
                    self.products.append({
                        'text': cleaned_data,
                        'source': 'heading_title',
                        'tag': self.current_tag,
                        'confidence': 'high'
                    })
            # 강조 태그들 (strong, b, em, i)에서 추출
            elif (self.in_strong or self.in_em) and cleaned_data.strip():
                if len(cleaned_data) > 3 and len(cleaned_data) < 100:
                    self.products.append({
                        'text': cleaned_data,
                        'source': 'emphasized_title',
                        'tag': self.current_tag,
                        'confidence': 'medium'
                    })
            # 우선순위: 1) 특수 필드, 2) 상품명 클래스, 3) 일반
            elif self.in_special_field and cleaned_data.strip():
                # 구조화된 필드는 키워드 체크 없이 수집 (더 신뢰도 높음)
                self.products.append({
                    'text': cleaned_data,
                    'source': self.special_field_type,
                    'tag': self.current_tag,
                    'confidence': 'high'
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
        
        # 인코딩이 깨진 텍스트 필터링 강화
        if len(text) > 0:
            # 1. null 문자나 제어 문자 제거
            text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
            
            # 2. 깨진 문자 비율 계산 (의미있는 문자 외의 특수문자)
            broken_chars = len(re.findall(r'[^\w\s가-힣\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf\-\(\)\[\]\.\,\:\;\'\"\/]', text))
            total_chars = len(text)
            broken_ratio = broken_chars / total_chars if total_chars > 0 else 0
            
            # 3. 깨진 문자가 25% 이상이면 제거 (더 엄격하게)
            if broken_ratio > 0.25:
                return ""
            
            # 4. 연속된 특수문자 체크
            if re.search(r'[^\w\s가-힣\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]{5,}', text):
                return ""
            
            # 5. 의미있는 텍스트가 너무 짧으면 제거
            meaningful_chars = len(re.findall(r'[\w가-힣\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]', text))
            if meaningful_chars < 3:
                return ""
        
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
        # 인코딩 문제를 방지하기 위해 더 엄격한 검증
        if re.search(r'(HG|RG|MG|PG|RE)', text):
            # 한국어 문자가 실제로 의미있는 단어를 구성하는지 확인
            korean_words = re.findall(r'[가-힣]{2,}', text)
            if korean_words and len(korean_words) >= 1:
                # 의미있는 한국어 단어가 있는 경우만 포함
                return True
        
        # 브랜드 + 스케일 + 한국어 모델명 조합 (좋은 참고 자료)
        has_brand = bool(re.search(r'(HG|RG|MG|PG|RE)', text))
        has_scale = bool(re.search(r'1/\d+', text))
        
        # 한국어 모델명 검증 강화
        korean_words = re.findall(r'[가-힣]{2,}', text)
        has_korean_model = len(korean_words) >= 1
        
        if has_brand and has_scale and has_korean_model:
            return True
        
        # 일본어가 포함되어도 한국어가 같이 있으면 참고 자료로 유용
        has_japanese = bool(re.search(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]', text))
        if has_japanese and has_korean_model and has_brand:
            return True
        
        return False

    def is_potential_gunpla(self, text):
        # 기본 필터링: 길이 체크 (사이트별 조정)
        # 다른 사이트는 완화
        if len(text) < 3 or len(text) > 150:
            return False
            
        # 불필요한 텍스트 필터링 (더 완화)
        exclude_patterns = [
            r'cookie', r'copyright', r'privacy', r'terms',
            r'navigation', r'menu', r'search', r'login',
            r'카트', r'장바구니', r'회원', r'로그인',
            r'주문', r'결제', r'배송', r'문의',
            r'\d{4}-\d{2}-\d{2}',  # 날짜 형식
            r'^[\d\s\-\.]+$',     # 숫자와 구두점만
            r'^[가-힣]{1,2}$',     # 한글 1-2글자만
            r'다운로드', r'업로드', r'페이지', r'사이트',
            r'링크', r'클릭', r'버튼', r'메뉴'
            # '상품 설명', '제품 설명', '상세 정보' 제거 (더 많은 텍스트 포함)
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return False
        
        # 사이트별 키워드 설정 (더 엄격하게)
        if self.site_name == "dalong.net":
            # Dalong.net은 일본어 키워드 위주 (더 많은 키워드 추가)
            primary_keywords = ['ガンダム', 'ガンプラ', 'プラモデル', 'モビルスーツ', 'MS']
            secondary_keywords = ['HG', 'RG', 'MG', 'PG', 'RE/100', 'RE', 'HGUC', 'HGBF', 'HGAW']
            model_keywords = [
                'フリーダム', 'ストライク', 'バルバトス', 'ユニコーン', 'エクシア',
                'ウイングガンダム', 'デスティニー', 'インパルス', 'ジャスティス',
                'ザク', 'ジム', 'シャア', 'キュベレイ', 'ノイエジール',
                'アストレイ', 'ブリッツ', 'イージス', 'プロビデンス',
                'ターンエー', 'ターンX', 'ガンダムX', 'ガンダムDX'
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
            # 기본값: 정의되지 않은 사이트에 대한 기본 키워드
            primary_keywords = ['ガンダム', 'Gundam', '건담', 'ガンプラ', 'Gunpla', '건프라']
            secondary_keywords = ['HG', 'RG', 'MG', 'PG', 'RE']
            model_keywords = [
                'Freedom', 'Strike', 'Barbatos', 'Unicorn', 'Exia',
                'Wing Gundam', 'Destiny', 'Impulse', 'Justice',
                'Zaku', 'GM', 'Char', 'Qubeley', 'Neue Ziel'
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
            
        return score >= 1  # 더 낮은 점수 기준으로 더 많은 텍스트 포함


def extract_title_from_filename(file_path):
    """파일명에서 제목 추출"""
    filename = Path(file_path).stem  # 확장자 제거
    filename = filename.replace('_', ' ').replace('-', ' ')
    
    # 의미있는 파일명인지 확인
    if len(filename) > 3 and len(filename) < 100:
        # 건프라 관련 키워드가 있으면 제목으로 인식
        gunpla_keywords = ['gundam', 'gunpla', 'mg', 'hg', 'rg', 'pg', 'seed', 'strike', 'freedom', 'unicorn', 'exia', 'barbatos']
        if any(keyword in filename.lower() for keyword in gunpla_keywords):
            return filename
    return None


def detect_encoding_from_meta(content):
    """HTML 메타 태그에서 인코딩 정보 추출"""
    # charset 메타 태그 패턴들
    charset_patterns = [
        r'<meta[^>]*charset=["\']?([^"\'>]+)["\']?',
        r'<meta[^>]*http-equiv=["\']?content-type["\']?[^>]*content=["\']?[^"\']*charset=([^"\'>]+)["\']?',
        r'<meta[^>]*content=["\']?[^"\']*charset=([^"\'>]+)["\']?[^>]*http-equiv=["\']?content-type["\']?'
    ]
    
    for pattern in charset_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            encoding = match.group(1).strip()
            # 일반적인 인코딩명 정규화
            encoding = encoding.lower()
            if encoding in ['utf-8', 'utf8']:
                return 'utf-8'
            elif encoding in ['euc-kr', 'euckr']:
                return 'euc-kr'
            elif encoding in ['cp949', 'ms949']:
                return 'cp949'
            elif encoding in ['iso-8859-1', 'latin1']:
                return 'iso-8859-1'
            elif encoding in ['shift_jis', 'shift-jis', 'sjis']:
                return 'shift_jis'
            else:
                return encoding
    
    return None

def is_binary_file(file_path, sample_size=1024):
    """파일이 바이너리인지 확인"""
    try:
        with open(file_path, 'rb') as f:
            sample = f.read(sample_size)
        
        # null 바이트가 있으면 바이너리
        if b'\x00' in sample:
            return True
        
        # 텍스트로 디코딩 시도
        try:
            sample.decode('utf-8')
            return False
        except UnicodeDecodeError:
            # UTF-8로 디코딩 실패 시 다른 인코딩 시도
            try:
                sample.decode('cp949')
                return False
            except UnicodeDecodeError:
                return True
    except Exception:
        return True

def extract_products_from_html(html_file, site_name):
    """HTML 파일에서 건프라 상품 정보 추출"""
    try:
        # 바이너리 파일 체크
        if is_binary_file(html_file):
            print(f"Skipping binary file: {html_file}")
            return []
        
        # 파일 크기 체크 (너무 큰 파일 제외)
        file_size = Path(html_file).stat().st_size
        if file_size > 10 * 1024 * 1024:  # 10MB 이상
            print(f"Skipping large file ({file_size/1024/1024:.1f}MB): {html_file}")
            return []
        
        # 먼저 바이너리로 읽어서 메타 태그 확인
        with open(html_file, 'rb') as f:
            raw_content = f.read()
        
        # 파일이 비어있는지 체크
        if len(raw_content) == 0:
            return []
        
        # 처음 10KB만 읽어서 메타 태그 확인 (성능 최적화)
        head_content = raw_content[:10240].decode('utf-8', errors='ignore')
        detected_encoding = detect_encoding_from_meta(head_content)
        
        # 인코딩이 감지되지 않으면 chardet로 추정 (가능한 경우)
        if not detected_encoding and HAS_CHARDET:
            try:
                result = chardet.detect(raw_content)
                detected_encoding = result['encoding']
                # chardet 신뢰도 체크
                if result.get('confidence', 0) < 0.7:
                    detected_encoding = None
            except:
                pass
        
        # 기본값으로 utf-8 사용
        if not detected_encoding:
            detected_encoding = 'utf-8'
        
        # 감지된 인코딩으로 디코딩
        try:
            content = raw_content.decode(detected_encoding)
        except (UnicodeDecodeError, LookupError):
            # 실패하면 다른 인코딩들 시도
            for fallback_encoding in ['utf-8', 'cp949', 'euc-kr', 'iso-8859-1']:
                try:
                    content = raw_content.decode(fallback_encoding, errors='ignore')
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                # 모든 인코딩 실패 시 UTF-8로 강제
                content = raw_content.decode('utf-8', errors='ignore')
        
        # 디코딩된 내용이 너무 짧으면 제외
        if len(content.strip()) < 100:
            return []
        
        extractor = ProductExtractor(site_name)
        extractor.feed(content)
        
        # 파일명에서도 제목 추출
        filename_title = extract_title_from_filename(html_file)
        if filename_title:
            extractor.products.append({
                'text': filename_title,
                'source': 'filename_title',
                'tag': 'filename',
                'confidence': 'medium'
            })
        
        return extractor.products
    except Exception as e:
        print(f"Error processing {html_file}: {e}")
        return []


def process_mirror_directory(mirror_dir, site_name):
    """미러링된 디렉토리에서 모든 HTML 파일 처리"""
    all_products = []
    
    # 범용적으로 .html과 .htm 파일들을 모두 포함
    html_files = list(Path(mirror_dir).rglob("*.html")) + list(Path(mirror_dir).rglob("*.htm"))
    
    print(f"Found {len(html_files)} HTML files...")
    
    processed_count = 0
    skipped_count = 0
    
    for html_file in html_files:
        try:
            products = extract_products_from_html(html_file, site_name)
            if products:
                for product in products:
                    product['file'] = str(html_file)
                all_products.extend(products)
                processed_count += 1
            else:
                skipped_count += 1
        except Exception as e:
            print(f"Error processing {html_file}: {e}")
            skipped_count += 1
    
    print(f"Processed: {processed_count}, Skipped: {skipped_count}")
    return all_products


def process_gcd_directory(mirror_dir: str) -> list[str]:
    """gcd(JSON API) 미러 디렉터리에서 subject 목록 추출 (.result.articleList[].item.subject)"""
    subjects: list[str] = []
    json_files = list(Path(mirror_dir).rglob("*.json"))
    print(f"Found {len(json_files)} JSON files...")
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            result = data.get('result') if isinstance(data, dict) else None
            if not result:
                continue
            article_list = result.get('articleList', [])
            for entry in article_list:
                if not isinstance(entry, dict):
                    continue
                item = entry.get('item', {})
                subject = item.get('subject')
                if isinstance(subject, str):
                    cleaned = ProductExtractor('gcd').clean_text(subject)
                    if cleaned and 3 <= len(cleaned) <= 200:
                        subjects.append(cleaned)
        except Exception as e:
            print(f"Error processing JSON {json_file}: {e}")
            continue
    return subjects


def save_gcd_subjects(subjects: list[str], output_file: str) -> None:
    """gcd 추출 결과를 텍스트 파일로 저장"""
    # 중복 제거 (공백 정규화 + 소문자 기준)
    normalized_map: dict[str, str] = {}
    for s in subjects:
        normalized = re.sub(r'\s+', ' ', s.strip().lower())
        if normalized not in normalized_map:
            normalized_map[normalized] = s.strip()
    unique_subjects = list(normalized_map.values())
    unique_subjects.sort()

    current_date = os.popen('date +"%Y-%m-%d"').read().strip()
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# gcd 기사 제목 추출 결과\n")
        f.write(f"# 날짜: {current_date}\n")
        f.write(f"# 총 {len(unique_subjects)}개 추출 (JSON path: .result.articleList[].item.subject)\n\n")
        seen_lines = set()
        for subj in unique_subjects:
            key = re.sub(r'\s+', ' ', subj.strip().lower())
            if key in seen_lines:
                continue
            seen_lines.add(key)
            f.write(f"{subj}\n")


def save_semi_structured_data(products, output_file, site_name):
    """추출된 상품 정보를 title 태그 중심으로 저장 (토큰 절약)"""
    # title 관련 태그들에서 추출된 것들을 우선 수집
    title_products = [p for p in products if p['source'] in ['title', 'link_title', 'heading_title', 'emphasized_title', 'meta_title', 'filename_title']]
    other_products = [p for p in products if p['source'] not in ['title', 'link_title', 'heading_title', 'emphasized_title', 'meta_title', 'filename_title']]
    
    # title만 추출할 것인지 확인하기 위한 옵션
    # 사이트별 최적화
    if site_name == "dalong.net":
        TITLE_ONLY = False  # dalong.net은 title이 부족하므로 다른 필드도 포함
    else:
        TITLE_ONLY = True   # 기본값
    
    unique_products = {}
    extractor = ProductExtractor(site_name)
    
    # title 태그 데이터는 모두 포함 (중복 제거 강화)
    for product in title_products:
        text = product['text'].strip()
        # 더 엄격한 중복 제거 (대소문자 무시, 공백 정규화)
        normalized_text = re.sub(r'\s+', ' ', text.lower()).strip()
        if len(text) > 5 and normalized_text not in unique_products:
            unique_products[normalized_text] = product
    
    # TITLE_ONLY가 False일 때만 나머지 제품들 처리
    if not TITLE_ONLY:
        for product in other_products:
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
                    'title': 8, 'general': 1  # title 우선순위 높임
                }
                current_priority = source_priority.get(product['source'], 0)
                existing_priority = source_priority.get(unique_products[refined_text]['source'], 0)
                
                if current_priority > existing_priority:
                    product['text'] = refined_text
                    unique_products[refined_text] = product
    
    # 품질 점수로 정렬 (높은 점수부터)
    sorted_products = sorted(unique_products.values(), 
                           key=lambda x: x.get('quality_score', 0), reverse=True)
    
    # 최대 개수 제한 (사이트별 조정)
    max_references = 2000  # 다른 사이트는 2000개
    
    if len(sorted_products) > max_references:
        sorted_products = sorted_products[:max_references]
        print(f"토큰 절약을 위해 상위 {max_references}개 참고 자료만 포함")
    
    # 품질별 분류
    high_quality_products = [p for p in sorted_products if p.get('is_high_quality', False)]
    medium_quality_products = [p for p in sorted_products if p.get('quality_score', 0) >= 2 and not p.get('is_high_quality', False)]
    
    # 메타 정보
    current_date = os.popen('date +"%Y-%m-%d"').read().strip()
    
    # 텍스트 형태로 저장
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# {site_name} 상품명 추출 결과\n")
        f.write(f"# 날짜: {current_date}\n")
        f.write(f"# 총 {len(sorted_products)}개 추출 (title 태그 우선)\n")
        f.write(f"# 용도: 모든 title 필드 텍스트 수집\n\n")

        title_products_filtered = [p for p in sorted_products if p['source'] in ['title', 'link_title', 'heading_title', 'emphasized_title', 'meta_title', 'filename_title']]
        other_products_filtered = [p for p in sorted_products if p['source'] not in ['title', 'link_title', 'heading_title', 'emphasized_title', 'meta_title', 'filename_title']]

        def normalize_line(text: str) -> str:
            return re.sub(r'\s+', ' ', text.strip().lower())

        seen_lines = set()

        if TITLE_ONLY:
            f.write(f"## Title 관련 태그에서 추출 ({len(title_products_filtered)}개)\n")
            for product in title_products_filtered:
                line = product['text']
                key = normalize_line(line)
                if key in seen_lines:
                    continue
                seen_lines.add(key)
                f.write(f"{line}\n")
        else:
            f.write(f"## Title 관련 태그에서 추출 ({len(title_products_filtered)}개)\n")
            for product in title_products_filtered:
                line = product['text']
                key = normalize_line(line)
                if key in seen_lines:
                    continue
                seen_lines.add(key)
                f.write(f"{line}\n")

            if other_products_filtered:
                f.write(f"\n## 기타 필드에서 추출 ({len(other_products_filtered)}개)\n")
                for product in other_products_filtered[:200]:
                    line = product['text']
                    key = normalize_line(line)
                    if key in seen_lines:
                        continue
                    seen_lines.add(key)
                    f.write(f"{line}\n")
    
    # 토큰 사용량 추정
    total_chars = sum(len(p['text']) for p in sorted_products)
    estimated_tokens = total_chars // 3  # 대략적인 토큰 추정
    
    # title 추출 통계 계산
    title_count = len(title_products_filtered)
    other_count = len(other_products_filtered)
    
    print(f"Extraction results saved to:")
    print(f"  - {output_file} (text format only)")
    print(f"  - Total references: {len(sorted_products)}")
    print(f"  - From title tags: {title_count}")
    print(f"  - From other sources: {other_count}")
    print(f"  - Estimated tokens: ~{estimated_tokens:,}")
    if sorted_products:
        print(f"  - Average length: {total_chars/len(sorted_products):.1f} chars")
    

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
    
    print(f"Extracting products from {site_name}: {mirror_dir}")
    
    # gcd(JSON API) 전용 처리
    if site_name == "gcd":
        subjects = process_gcd_directory(mirror_dir)
        if not subjects:
            print("No subjects found from JSON")
            sys.exit(1)
        save_gcd_subjects(subjects, output_file)
        print(f"Extraction completed successfully! Total subjects: {len(subjects)}")
        return
    
    # HTML 파일에서 상품 정보 추출 (기존 사이트)
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