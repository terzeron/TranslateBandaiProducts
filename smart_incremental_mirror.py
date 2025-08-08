#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import hashlib
import sqlite3
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse
from typing import Dict, Set, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SmartFileManager:
    """스마트 파일 관리 시스템"""
    
    def __init__(self, base_dir: str, db_path: str = "smart_mirror.db"):
        self.base_dir = Path(base_dir)
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """데이터베이스 초기화"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    url TEXT PRIMARY KEY,
                    file_path TEXT,
                    content_hash TEXT,
                    last_modified TEXT,
                    etag TEXT,
                    size INTEGER,
                    download_time REAL,
                    access_count INTEGER DEFAULT 0,
                    last_access REAL,
                    file_type TEXT DEFAULT 'html'
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS url_patterns (
                    pattern TEXT PRIMARY KEY,
                    last_check REAL,
                    status TEXT,
                    priority INTEGER DEFAULT 1
                )
            """)
            
            # 인덱스 생성
            conn.execute("CREATE INDEX IF NOT EXISTS idx_download_time ON files(download_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_last_access ON files(last_access)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_type ON files(file_type)")
    
    def get_file_info(self, url: str) -> Optional[Dict[str, str]]:
        """파일 정보 조회"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT file_path, content_hash, last_modified, etag, size, 
                       download_time, access_count, last_access, file_type
                FROM files WHERE url = ?
            """, (url,))
            
            result = cursor.fetchone()
            if result:
                return {
                    'file_path': str(result[0]) if result[0] else '',
                    'content_hash': str(result[1]) if result[1] else '',
                    'last_modified': str(result[2]) if result[2] else '',
                    'etag': str(result[3]) if result[3] else '',
                    'size': str(result[4]) if result[4] else '0',
                    'download_time': str(result[5]) if result[5] else '0',
                    'access_count': str(result[6]) if result[6] else '0',
                    'last_access': str(result[7]) if result[7] else '0',
                    'file_type': str(result[8]) if result[8] else 'html'
                }
        return None
    
    def save_file_info(self, url: str, file_path: str, content_hash: str, 
                      last_modified: Optional[str] = None, etag: Optional[str] = None, size: int = 0, file_type: str = 'html'):
        """파일 정보 저장"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO files 
                (url, file_path, content_hash, last_modified, etag, size, download_time, access_count, last_access, file_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT access_count FROM files WHERE url = ?), 0) + 1, ?, ?)
            """, (url, file_path, content_hash, last_modified, etag, size, time.time(), url, time.time(), file_type))
    
    def should_update_file(self, url: str, response_headers: Dict[str, str]) -> bool:
        """파일 업데이트 필요 여부 판단"""
        file_info = self.get_file_info(url)
        if not file_info:
            return True
        
        # 파일이 실제로 존재하는지 확인
        if not Path(file_info['file_path']).exists():
            return True
        
        # ETag 기반 확인
        if file_info.get('etag') and response_headers.get('etag'):
            return file_info['etag'] != response_headers['etag']
        
        # Last-Modified 기반 확인
        if file_info.get('last_modified') and response_headers.get('last-modified'):
            return file_info['last_modified'] != response_headers['last-modified']
        
        # 파일 크기 비교
        content_length = response_headers.get('content-length')
        if content_length and file_info.get('size'):
            return int(content_length) != int(file_info['size'])
        
        # 파일 타입별 재검사 주기
        file_type = file_info.get('file_type', 'html')
        age_hours = (time.time() - float(file_info['download_time'])) / 3600
        
        if file_type == 'pdf':
            return age_hours > 168  # PDF는 1주일
        elif file_type == 'html':
            return age_hours > 24   # HTML은 24시간
        else:
            return age_hours > 72   # 기타는 3일
    
    def get_outdated_files(self, hours: int = 168) -> List[str]:  # 1주일
        """오래된 파일 목록 반환"""
        cutoff_time = time.time() - (hours * 3600)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT url FROM files WHERE download_time < ? AND access_count < 5",
                (cutoff_time,)
            )
            return [row[0] for row in cursor.fetchall()]
    
    def cleanup_orphaned_files(self):
        """고아 파일 정리"""
        cleaned_count = 0
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT url, file_path FROM files")
            for url, file_path in cursor.fetchall():
                if not Path(file_path).exists():
                    conn.execute("DELETE FROM files WHERE url = ?", (url,))
                    cleaned_count += 1
        
        logger.info(f"정리된 고아 레코드: {cleaned_count}개")
        return cleaned_count

class SiteConfig:
    """사이트별 설정 클래스"""
    
    @staticmethod
    def get_config(site_name: str) -> Dict:
        """사이트별 설정 반환"""
        configs = {
            'dalong': {
                'priority_patterns': [
                    (r'/photo/.*\.htm', 3),  # 사진 페이지 우선
                    (r'/review/.*\.htm', 3), # 리뷰 페이지 우선
                    (r'/list/.*\.htm', 2),   # 목록 페이지
                    (r'/.*\.htm', 1),        # 일반 페이지
                ],
                'link_keywords': ['photo', 'review', 'list', 'gundam', 'mobile'],
                'file_extensions': ['.htm', '.html'],
                'max_depth': 4
            },
            'bandai-hobby': {
                'priority_patterns': [
                    (r'/menus/detail/.*\.html', 3), # 상세 페이지 우선
                    (r'/pdf/.*\.pdf', 3),           # PDF 파일 우선
                    (r'/menus/.*\.html', 2),        # 메뉴 페이지
                    (r'/.*\.html', 1),              # 일반 페이지
                ],
                'link_keywords': ['menus', 'detail', 'pdf', 'manual'],
                'file_extensions': ['.html', '.pdf'],
                'max_depth': 3
            },
            'gundaminfo': {
                'priority_patterns': [
                    (r'/about-gundam/series-pages/.*/product/', 3), # 제품 페이지 우선
                    (r'/about-gundam/series-pages/.*/mecha/', 3),   # 메카 페이지 우선
                    (r'/news/gunpla\.html', 2),                     # 뉴스 페이지
                    (r'/about-gundam/.*\.html', 1),                 # 일반 페이지
                ],
                'link_keywords': ['gundam', 'gunpla', 'mecha', 'product', 'series'],
                'file_extensions': ['.html', '.htm', '.php'],
                'max_depth': 4
            }
            ,
            'gcd': {
                # JSON API 기반 수집 (페이지네이션)
                'priority_patterns': [],
                'link_keywords': [],
                'file_extensions': ['.json'],
                'max_depth': 1,
                'max_pages': 300
            }
        }
        
        return configs.get(site_name, {})  

class SmartIncrementalMirror:
    """스마트 증분 미러링 시스템"""
    
    def __init__(self, base_url: str, output_dir: str, site_name: str):
        self.base_url = base_url.rstrip('/')
        self.output_dir = Path(output_dir)
        self.site_name = site_name
        self.config = SiteConfig.get_config(site_name)
        self.file_manager = SmartFileManager(output_dir, f"smart_mirror_{site_name}.db")
        self.session = self.create_session()
        self.downloaded_count = 0
        self.skipped_count = 0
        self.error_count = 0
        
        # 사이트별 우선순위 패턴
        self.priority_patterns = self.config['priority_patterns']
    
    def create_session(self) -> requests.Session:
        """최적화된 requests 세션 생성"""
        session = requests.Session()
        
        # 재시도 전략 - 더 빠른 재시도
        retry_strategy = Retry(
            total=1,  # 재시도 횟수 줄임
            backoff_factor=1,  # 백오프 시간 단축
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 헤더 설정
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
        })
        
        return session
    
    def get_url_priority(self, url: str) -> int:
        """URL 우선순위 계산"""
        for pattern, priority in self.priority_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return priority
        return 1  # 기본 우선순위
    
    def normalize_url(self, url: str) -> str:
        """URL 정규화"""
        parsed = urlparse(url)
        # 쿼리 파라미터 정렬
        query_parts = sorted(parsed.query.split('&')) if parsed.query else []
        normalized_query = '&'.join(query_parts)
        
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}{'?' + normalized_query if normalized_query else ''}"
    
    def get_file_path(self, url: str, file_type: str = 'html') -> Path:
        """URL에서 파일 경로 생성 (파일 타입에 따라 확장자 결정)"""
        parsed = urlparse(url)
        
        # 경로 생성
        path_parts = [part for part in parsed.path.split('/') if part]
        if not path_parts:
            path_parts = ['index']
        
        # 쿼리를 파일명에 포함 (해시 사용)
        if parsed.query:
            query_hash = hashlib.md5(parsed.query.encode()).hexdigest()[:8]
            path_parts[-1] += f"_{query_hash}"
        
        # 확장자 추가
        file_path = '/'.join(path_parts)
        if file_type == 'pdf':
            if not file_path.endswith('.pdf'):
                file_path += '.pdf'
        elif file_type == 'json':
            if not file_path.endswith('.json'):
                file_path += '.json'
        else:
            if not file_path.endswith('.html'):
                file_path += '.html'
        
        return self.output_dir / file_path
    
    def check_if_update_needed(self, url: str) -> tuple[bool, Dict[str, str]]:
        """HEAD 요청으로 업데이트 필요 여부 확인"""
        try:
            response = self.session.head(url, timeout=15)  # 타임아웃 단축
            if response.status_code == 200:
                headers = {
                    'etag': response.headers.get('etag', ''),
                    'last-modified': response.headers.get('last-modified', ''),
                    'content-length': response.headers.get('content-length', ''),
                }
                
                needs_update = self.file_manager.should_update_file(url, headers)
                return needs_update, headers
            
        except Exception as e:
            logger.warning(f"HEAD 요청 실패 {url}: {e}")
        
        # HEAD 요청 실패 시 안전하게 업데이트 필요로 간주
        return True, {}
 
    def get_file_type(self, url: str) -> str:
        """URL에서 파일 타입 추출"""
        if url.endswith('.pdf'):
            return 'pdf'
        elif url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
            return 'image'
        elif url.endswith(('.css', '.js')):
            return 'static'
        else:
            return 'html'

    def download_file(self, url: str, file_type: str = 'html') -> bool:
        """파일 다운로드 (HTML/PDF/기타 지원)"""
        normalized_url = self.normalize_url(url)
        
        # 업데이트 필요 여부 확인
        needs_update, headers = self.check_if_update_needed(normalized_url)
        
        if not needs_update:
            self.skipped_count += 1
            if self.skipped_count % 50 == 0:  # 더 자주 진행상황 출력
                logger.info(f"건너뛴 파일: {self.skipped_count}개")
            return False
        
        try:
            # 실제 다운로드
            response = self.session.get(normalized_url, timeout=30)  # 타임아웃 단축
            response.raise_for_status()
            
            # 파일 저장 (타입에 따른 확장자)
            file_path = self.get_file_path(normalized_url, file_type)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if file_type == 'pdf':
                # PDF는 바이너리 모드로 저장
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                content_hash = hashlib.md5(response.content).hexdigest()
                file_size = len(response.content)
            else:
                # HTML/텍스트는 UTF-8로 저장
                content = response.text
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                content_hash = hashlib.md5(content.encode()).hexdigest()
                file_size = len(content.encode())
            
            # 메타데이터 저장
            self.file_manager.save_file_info(
                normalized_url,
                str(file_path),
                content_hash,
                response.headers.get('last-modified'),
                response.headers.get('etag'),
                file_size,
                file_type
            )
            
            self.downloaded_count += 1
            if self.downloaded_count % 20 == 0:  # 더 자주 진행상황 출력
                logger.info(f"다운로드: {self.downloaded_count}개, 건너뛰기: {self.skipped_count}개")
            
            return True
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"다운로드 실패 {normalized_url}: {e}")
            return False
    
    def extract_links(self, content: str, base_url: str) -> Set[str]:
        """링크 추출 (사이트별 키워드 사용)"""
        links = set()
        href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
        
        for match in href_pattern.finditer(content):
            href = match.group(1)
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue
            
            full_url = urljoin(base_url, href)
            
            # 사이트별 키워드로 필터링
            if (full_url.startswith(self.base_url) and 
                any(keyword in full_url.lower() for keyword in self.config['link_keywords'])):
                links.add(full_url)
        
        return links

    def save_korean_keywords(self, url: str, keywords: Set[str]):
        """한글 키워드를 파일로 저장"""
        if not keywords:
            return
            
        keywords_file = self.output_dir / "korean_keywords.txt"
        with open(keywords_file, 'a', encoding='utf-8') as f:
            f.write(f"\n=== {url} ===\n")
            f.write(f"키워드 수: {len(keywords)}\n")
            f.write(f"키워드: {', '.join(sorted(keywords))}\n")
            f.write("-" * 50 + "\n")

    def extract_korean_keywords(self, content: str) -> Set[str]:
        """HTML 내용에서 한글 키워드 추출 (개선된 버전)"""
        korean_keywords = set()
        
        # 한글 패턴 (단어 단위)
        korean_word_pattern = re.compile(r'[가-힣]{2,}')
        
        # 1. title 태그에서 한글 추출
        title_pattern = re.compile(r'<title[^>]*>(.*?)</title>', re.IGNORECASE | re.DOTALL)
        title_matches = title_pattern.findall(content)
        for title in title_matches:
            # HTML 엔티티 디코딩
            title_clean = re.sub(r'&[^;]+;', ' ', title)
            title_clean = re.sub(r'<[^>]+>', ' ', title_clean)
            for match in korean_word_pattern.finditer(title_clean):
                word = match.group().strip()
                if len(word) >= 2:
                    korean_keywords.add(word)
        
        # 2. 링크 텍스트에서 한글 추출
        link_text_pattern = re.compile(r'<a[^>]*>(.*?)</a>', re.IGNORECASE | re.DOTALL)
        link_matches = link_text_pattern.findall(content)
        for link_text in link_matches:
            # HTML 태그 제거
            link_clean = re.sub(r'<[^>]+>', ' ', link_text)
            link_clean = re.sub(r'&[^;]+;', ' ', link_clean)
            for match in korean_word_pattern.finditer(link_clean):
                word = match.group().strip()
                if len(word) >= 2:
                    korean_keywords.add(word)
        
        # 3. 메타 태그에서 한글 추출 (keywords, description)
        meta_patterns = [
            r'<meta[^>]*name=["\']keywords["\'][^>]*content=["\']([^"\']+)["\']',
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']',
            r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']',
            r'<meta[^>]*property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']'
        ]
        
        for pattern in meta_patterns:
            meta_matches = re.findall(pattern, content, re.IGNORECASE)
            for meta_content in meta_matches:
                meta_clean = re.sub(r'&[^;]+;', ' ', meta_content)
                for match in korean_word_pattern.finditer(meta_clean):
                    word = match.group().strip()
                    if len(word) >= 2:
                        korean_keywords.add(word)
        
        # 4. h1, h2, h3 태그에서 한글 추출
        heading_pattern = re.compile(r'<h[1-6][^>]*>(.*?)</h[1-6]>', re.IGNORECASE | re.DOTALL)
        heading_matches = heading_pattern.findall(content)
        for heading in heading_matches:
            heading_clean = re.sub(r'<[^>]+>', ' ', heading)
            heading_clean = re.sub(r'&[^;]+;', ' ', heading_clean)
            for match in korean_word_pattern.finditer(heading_clean):
                word = match.group().strip()
                if len(word) >= 2:
                    korean_keywords.add(word)
        
        # 5. 일반 텍스트에서 한글 추출 (HTML 태그 제거 후)
        content_clean = re.sub(r'<[^>]+>', ' ', content)
        content_clean = re.sub(r'&[^;]+;', ' ', content_clean)
        content_clean = re.sub(r'\s+', ' ', content_clean)  # 연속된 공백 제거
        
        for match in korean_word_pattern.finditer(content_clean):
            word = match.group().strip()
            if len(word) >= 2:
                korean_keywords.add(word)
        
        return korean_keywords

    def get_initial_urls(self) -> List[str]:
        """사이트별 초기 URL 목록"""
        if self.site_name == 'dalong':
            return self._get_dalong_urls()
        elif self.site_name == 'bandai-hobby':
            return self._get_bandai_urls()
        elif self.site_name == 'gundaminfo':
            return self._get_gundaminfo_urls()
        elif self.site_name == 'gcd':
            # JSON API는 스트리밍 방식으로 순회하므로 초기 URL 큐를 크게 만들지 않음
            return [self.base_url]
        else:
            return [self.base_url]

    def _get_dalong_urls(self) -> List[str]:
        """Dalong.net 초기 URL 목록"""
        return [
            f"{self.base_url}/index.htm",
            f"{self.base_url}/photo/index.htm",
            f"{self.base_url}/review/index.htm",
            f"{self.base_url}/list/index.htm",
        ]

    def _get_bandai_urls(self) -> List[str]:
        """Bandai Manual 초기 URL 목록"""
        return [
            f"{self.base_url}/index.html",
            f"{self.base_url}/menus/index.html",
        ]

    def _get_gundaminfo_urls(self) -> List[str]:
        """Gundam Info 초기 URL 목록"""
        return [
            f"{self.base_url}/news/gunpla.html",
            f"{self.base_url}/about-gundam/series-pages/gquuuuuux/mecha/",
            f"{self.base_url}/about-gundam/series-pages/gquuuuuux/goods/",
            f"{self.base_url}/about-gundam/series-pages/seedfreedom/mecha/",
            f"{self.base_url}/about-gundam/series-pages/seedfreedom/product/",
        ]

    def mirror_site(self, max_pages: int = 10000):
        """스마트 증분 미러링 실행"""
        # JSON API 기반의 gcd는 전용 경로로 처리 (대량 URL 초기 등록 회피)
        if self.site_name == 'gcd':
            return self._mirror_gcd_api(max_pages)

        logger.info("스마트 증분 미러링 시작")
        logger.info(f"최대 페이지 수: {max_pages}")
        
        start_time = time.time()
        
        # 초기 정리
        self.file_manager.cleanup_orphaned_files()
        
        urls_to_visit = self.get_initial_urls()
        visited_urls = set()
        processed_count = 0
        
        while urls_to_visit and processed_count < max_pages:
            # 우선순위가 높은 URL부터 처리
            current_url = urls_to_visit.pop(0)
            
            if current_url in visited_urls:
                continue
            
            visited_urls.add(current_url)
            processed_count += 1
            
            logger.info(f"처리 중 [{processed_count}/{max_pages}]: {current_url}")
            
            # 페이지 다운로드
            success = self.download_file(current_url)
            
            if success:
                # 새로운 링크 추출
                try:
                    file_path = self.get_file_path(current_url)
                    if file_path.exists():
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        new_links = self.extract_links(content, current_url)
                        
                        # 한글 키워드 추출 (gundaminfo 사이트의 경우)
                        if self.site_name == 'gundaminfo':
                            korean_keywords = self.extract_korean_keywords(content)
                            if korean_keywords:
                                logger.info(f"한글 키워드 추출: {len(korean_keywords)}개 - {list(korean_keywords)[:10]}")
                                self.save_korean_keywords(current_url, korean_keywords) # 키워드 저장
                        
                        # 우선순위 기반으로 새 링크 삽입
                        for link in new_links:
                            if link not in visited_urls and link not in urls_to_visit:
                                priority = self.get_url_priority(link)
                                # 우선순위에 따라 적절한 위치에 삽입
                                insert_pos = 0
                                for i, existing_url in enumerate(urls_to_visit):
                                    if self.get_url_priority(existing_url) < priority:
                                        break
                                    insert_pos = i + 1
                                
                                urls_to_visit.insert(insert_pos, link)
                                
                                # 최대 대기 목록 크기 제한
                                if len(urls_to_visit) > max_pages * 2:
                                    urls_to_visit = urls_to_visit[:max_pages * 2]
                
                except Exception as e:
                    logger.error(f"링크 추출 오류 {current_url}: {e}")
            
            # 진행 상황 주기적 출력
            if processed_count % 100 == 0:
                elapsed = time.time() - start_time
                rate = processed_count / elapsed if elapsed > 0 else 0
                logger.info(f"진행: {processed_count}/{max_pages}, "
                          f"다운로드: {self.downloaded_count}, "
                          f"건너뛰기: {self.skipped_count}, "
                          f"오류: {self.error_count}, "
                          f"속도: {rate:.1f} urls/sec")
            
            # 요청 간격 (서버 부하 방지) - 동적 대기 시간
            if success:
                time.sleep(0.3)  # 성공 시 짧은 대기
            else:
                time.sleep(1.0)  # 실패 시 긴 대기
        
        # 최종 통계
        elapsed = time.time() - start_time
        
        # 한글 키워드 통계 (gundaminfo 사이트의 경우)
        if self.site_name == 'gundaminfo':
            keywords_file = self.output_dir / "korean_keywords.txt"
            if keywords_file.exists():
                with open(keywords_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    korean_word_count = len(re.findall(r'[가-힣]{2,}', content))
                    logger.info(f"총 추출된 한글 단어 수: {korean_word_count}개")
        
        logger.info(f"\n=== 미러링 완료 ===")
        logger.info(f"총 처리 URL: {processed_count}")
        logger.info(f"새로 다운로드: {self.downloaded_count}")
        logger.info(f"건너뛴 파일: {self.skipped_count}")
        logger.info(f"오류 발생: {self.error_count}")
        logger.info(f"총 소요 시간: {elapsed:.1f}초")
        logger.info(f"평균 속도: {processed_count/elapsed:.1f} urls/sec")
        logger.info(f"실제 다운로드 비율: {self.downloaded_count/processed_count*100:.1f}%")

    def _mirror_gcd_api(self, max_pages: int = 300):
        """gcd(JSON API) 전용 수집: page=1..N 순회, 파일은 .json으로 저장"""
        logger.info("gcd(JSON API) 수집 시작")
        pages_to_fetch = min(max_pages, self.config.get('max_pages', 300))
        start_time = time.time()
        processed_pages = 0
        self.file_manager.cleanup_orphaned_files()

        for page_index in range(1, pages_to_fetch + 1):
            page_url = f"{self.base_url}{page_index}"
            logger.info(f"처리 중 페이지: {page_index}/{pages_to_fetch} - {page_url}")
            success = self.download_file(page_url, file_type='json')
            processed_pages += 1

            # 진행 상황 출력 간격
            if processed_pages % 50 == 0:
                elapsed_mid = time.time() - start_time
                rate = processed_pages / elapsed_mid if elapsed_mid > 0 else 0
                logger.info(f"진행: {processed_pages}/{pages_to_fetch}, 다운로드: {self.downloaded_count}, 건너뛰기: {self.skipped_count}, 오류: {self.error_count}, 속도: {rate:.1f} req/sec")

            # 서버 부담 완화
            time.sleep(0.2 if success else 0.8)

        elapsed = time.time() - start_time
        logger.info("\n=== gcd 수집 완료 ===")
        logger.info(f"총 요청 수: {processed_pages}")
        logger.info(f"새로 다운로드: {self.downloaded_count}")
        logger.info(f"건너뛴 파일: {self.skipped_count}")
        logger.info(f"오류 발생: {self.error_count}")
        logger.info(f"총 소요 시간: {elapsed:.1f}초, 평균 속도: {processed_pages/elapsed:.1f} req/sec")

def main():
    """메인 함수"""
    if len(sys.argv) < 3:
        print("Usage: python3 smart_incremental_mirror.py <base_url> <output_dir> [max_pages] [site_name]")
        print("  site_name: dalong, bandai-hobby, gundaminfo")
        sys.exit(1)
    
    base_url = sys.argv[1]
    output_dir = sys.argv[2]
    max_pages = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
    site_name = sys.argv[4]
    # 미러링 시스템 초기화
    mirror = SmartIncrementalMirror(base_url, output_dir, site_name)
    
    # 미러링 실행
    try:
        mirror.mirror_site(max_pages)
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"미러링 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()