#!/usr/bin/env python


import sys
import re
import json
import getopt
import unicodedata
import requests
import time
from pathlib import Path
from typing import Optional


MANUAL_DIR_PATH = Path("manual.bandai-hobby.net")
BASE_URL = "https://manual.bandai-hobby.net"

# 사용된 번역 키들을 추적하기 위한 전역 변수
used_translation_keys = set()


def read_translation(translation_file_path: Path) -> dict[str, str]:
    with translation_file_path.open("r", encoding="utf-8") as infile:
        translation_data = json.load(infile)
    return translation_data


def write_translation(translation_file_path: Path, translation_data: dict[str, str]) -> None:
    with translation_file_path.open("w", encoding="utf-8") as outfile:
        json.dump(translation_data, outfile, ensure_ascii=False, indent=2, sort_keys=True)


def convert_full_character_to_half(text: str) -> str:
    return unicodedata.normalize('NFKC', text)


def get_product_name_from_file(file_path: Path) -> tuple[str, str, str, str]:
    product_name = ""
    brand = ""
    scale = ""
    year = ""
    
    with file_path.open("r", encoding="utf-8") as infile:
        for line in infile:
            line = convert_full_character_to_half(line)
            
            m = re.search(r'<h2 class="el_title"><span>(?P<scale>1/\d{1,4})\s*(?P<product_name>.+)</span></h2>', line)
            if m:
                brand = ""
                scale = m.group("scale")
                scale = re.sub(r"/", "_", scale)
                product_name = m.group("product_name")
                year = ""
                continue

            m = re.search(r'<h2 class="el_title"><span>(?P<brand>SDW HEROES|Figure-rise Standard|SDガンダム EX|SDガンダム|SDBD:R|SDBF|SDBD|ADVANCE OF Z|BB戦士|HGBF|HGBC|FULL MECHANICS|HGBD:R|HGBD|HGFC|ENTRY GRADE|RE/100|HGAC|HGCE|EXPO|MGSD|HGCC|HGAW|HGUC|MGEX|RG|MG|PG|HG).*(?P<scale>1/\d{1,4})[ \u3000\xa0\s]*(?P<product_name>.+)</span></h2>', line)
            if m:
                brand = m.group("brand")
                brand = convert_full_character_to_half(brand)
                brand = re.sub(r"RE/100", "RE100", brand)
                scale = m.group("scale")
                scale = re.sub(r"/", "_", scale)
                product_name = m.group("product_name")
                year = ""
                continue
            
            m = re.search(r'<h2 class="el_title"><span>(?P<brand>SDW HEROES|Figure-rise Standard|SDガンダム EX|SDガンダム|SDBD:R|SDBF|SDBD|ADVANCE OF Z|BB戦士|HGBF|HGBC|FULL MECHANICS|HGBD:R|HGBD|HGFC|ENTRY GRADE|RE/100|HGAC|HGCE|EXPO|MGSD|HGCC|HGAW|HGUC|MGEX|RG|MG|PG|HG)[ \u3000\xa0\s]*(?P<product_name>.+)</span></h2>', line)
            if m:
                brand = m.group("brand")
                brand = convert_full_character_to_half(brand)
                brand = re.sub(r"RE/100", "RE100", brand)
                scale = ""
                product_name = m.group("product_name")
                year = ""
                continue
            
            m = re.search(r'<h2 class="el_title"><span>(?P<product_name>.+)</span></h2>', line)
            if m:
                brand = ""
                scale = ""
                product_name = m.group("product_name")
                product_name = product_name
                year = ""
                continue

            m = re.search(r'<dd class="bl_detail_box_txt">(?P<year>(19|20)\d\d)年.*</dd>', line)
            if m:
                year = m.group("year")
            
    return product_name, brand, scale, year

            
def convert_ja_to_ko(translation_data: dict[str, str], product_name: str, brand: str, scale: str) -> tuple[str, str]:
    """
    번역 시도하고 (번역결과, 상태) 튜플 반환
    상태: "success", "empty", "not_found"
    """
    # cleaning
    product_name = re.sub(r'["""]', '', product_name)
    product_name = convert_full_character_to_half(product_name)
    brand = convert_full_character_to_half(brand)

    # 각 키를 순차적으로 시도하고 사용된 키를 기록
    key = product_name + " " + brand + " " + scale
    if key in translation_data:
        result = translation_data[key]
        used_translation_keys.add(key)
        if result:
            return re.sub(r'[/"]', '', result), "success"
        else:
            return "", "empty"
    
    key = product_name + " " + brand
    if key in translation_data:
        result = translation_data[key]
        used_translation_keys.add(key)
        if result:
            return re.sub(r'[/"]', '', result), "success"
        else:
            return "", "empty"
    
    key = product_name + " " + scale
    if key in translation_data:
        result = translation_data[key]
        used_translation_keys.add(key)
        if result:
            return re.sub(r'[/"]', '', result), "success"
        else:
            return "", "empty"
    
    key = product_name
    if key in translation_data:
        result = translation_data[key]
        used_translation_keys.add(key)
        if result:
            return re.sub(r'[/"]', '', result), "success"
        else:
            return "", "empty"
    
    # 기존 방식으로 찾지 못한 경우
    return product_name, "not_found"
    

def download_pdf(product_number: str, pdf_dir_path: Path) -> bool:
    """
    제품번호에 해당하는 PDF 파일을 다운로드
    """
    url = f"{BASE_URL}/pdf/{product_number}.pdf"
    target_file = pdf_dir_path / f"{product_number}.pdf"
    
    try:
        print(f"DEBUG: PDF 다운로드 시도 - {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        with target_file.open("wb") as f:
            f.write(response.content)
        
        print(f"DEBUG: PDF 다운로드 성공 - {product_number}.pdf")
        time.sleep(0.1)  # 서버 부하 방지
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"DEBUG: PDF 다운로드 실패 - {product_number}.pdf, {e}")
        return False
    except Exception as e:
        print(f"DEBUG: PDF 다운로드 오류 - {product_number}.pdf, {e}")
        return False


def make_symbolic_link(link: Path, target: Path, pdf_dir_path: Path, product_number: str = None) -> str:
    """
    심볼릭링크 생성을 시도하고 결과를 반환
    반환값: "created", "downloaded_and_created", "already_exists", "target_missing", "failed"
    """
    if link.is_symlink():
        #print(f"DEBUG: 이미 심볼릭링크 존재 - {link.name}")
        return "already_exists"
        
    # 원본 파일이 존재하는지 체크
    if not target.exists():
        print(f"DEBUG: target 파일 없음 - {target.name}")
        
        # 제품번호가 있으면 다운로드 시도
        if product_number:
            if download_pdf(product_number, pdf_dir_path):
                # 다운로드 성공했으면 심볼릭링크 생성 시도
                try:
                    link.symlink_to(target.relative_to(pdf_dir_path))
                    print(f"{link.name} -> {target.relative_to(pdf_dir_path)} (다운로드 후 생성)")
                    return "downloaded_and_created"
                except Exception as e:
                    print(f"DEBUG: 다운로드 후 심볼릭링크 생성 실패 - {link.name}, {e}")
                    return "failed"
            else:
                return "target_missing"
        else:
            return "target_missing"
    
    try:
        link.symlink_to(target.relative_to(pdf_dir_path))
        print(f"{link.name} -> {target.relative_to(pdf_dir_path)}")
        return "created"
    except FileNotFoundError as e:
        print(f"DEBUG: 심볼릭링크 생성 실패 - {link.name} -x-> {target.name}, {e}")
        return "failed"
    except Exception as e:
        print(f"DEBUG: 심볼릭링크 생성 오류 - {link.name}, {e}")
        return "failed"

            
def print_html(product_number: str, full_korean_name: str) -> None:
    print(f"<li><a href='{BASE_URL}/pdf/{product_number}.pdf' target='_blank'>{full_korean_name}</a></li>")


def process_duplicates(product_name_number_dict: dict[str, int], product_number: int, full_korean_name: str, year: str, pdf_dir_path: Path) -> Optional[Path]:
    if full_korean_name in product_name_number_dict:
        #print(f"duplicate name: {product_name} / {brand} / {scale} -> {full_korean_name} -> {product_number} or {product_name_number_dict[full_korean_name]}")
        # add the year field to link
        full_korean_name += ((" " + year) if year else "")
        link = pdf_dir_path / (full_korean_name + ".pdf")
        #print(f"{product_number}: {link}, {link.is_symlink()} -> {target}, {target.is_file()}")
        return link

    product_name_number_dict[full_korean_name] = product_number
    return None
    
    
def main() -> int:
    detail_dir_path = MANUAL_DIR_PATH / "menus" / "detail"
    pdf_dir_path = MANUAL_DIR_PATH / "pdf"
    translation_file_path = Path("mapping") / "bandai_product_ja_ko_mapping.json"
    #print(f"{detail_dir_path=}, {pdf_dir_path=}, {translation_file_path=}")

    do_print_html = False
    
    opts, args = getopt.getopt(sys.argv[1:], "-h")
    for o, _ in opts:
        if o == "-h":
            do_print_html = True
    
    translation_data = read_translation(translation_file_path)
    if not translation_data:
        sys.stderr.write(f"can't find translation data from '{translation_file_path}'\n")
    
    # 조악한 번역 방지를 위해 TranslationOptimizer 비활성화
    optimizer = None

    if do_print_html:
        print("<ul>")
    
    # 디버깅용 카운터들
    total_html_files = 0
    valid_product_number_files = 0
    product_name_extracted = 0
    translation_success = 0
    translation_empty = 0
    translation_not_found = 0
    symlink_attempts = 0
    symlink_created = 0
    symlink_downloaded_and_created = 0
    symlink_already_exists = 0
    symlink_target_missing = 0
    symlink_creation_failed = 0
    
    product_name_number_dict = {}
    for file_path in detail_dir_path.iterdir():
        if not file_path.is_file():
            print(f"DEBUG: 파일이 아님: {file_path.name}")
            continue
        total_html_files += 1
        m = re.search(r'^(?P<product_number>\d+)\.html$', file_path.name)
        if not m:
            print(f"DEBUG: 이름 컨벤션이 맞지 않는 파일명: {file_path.name}")
            continue
        product_number = m.group("product_number")
        valid_product_number_files += 1
        product_name, brand, scale, year = get_product_name_from_file(file_path)
        #print(f"{product_number}: {product_name}, {brand}, {scale}, {year}")
        
        if product_name:
            product_name_extracted += 1
            korean, status = convert_ja_to_ko(translation_data, product_name, brand, scale)
            
            if status == "success":
                translation_success += 1
                escaped_korean_name = re.sub(r'/', ' ', korean)
                full_korean_name = escaped_korean_name + ((" " + brand) if brand else "") + ((" " + scale) if scale else "")
                #print(f"{product_number}: \"{product_name}{(" " + brand) if brand else ""}{(" " + scale) if scale else ""}\": \"{full_korean_name}\",")
                #print(f"success: {brand} {product_name} -> {full_korean_name}")
                
                link = pdf_dir_path / (full_korean_name + ".pdf")
                target = pdf_dir_path / (product_number + ".pdf")

                deduplicated_link = process_duplicates(product_name_number_dict, int(product_number), full_korean_name, year, pdf_dir_path)
                if deduplicated_link:
                    link = deduplicated_link
                
                #print(f"{product_number}: {link}, {link.is_symlink()} -> {target}, {target.is_file()}")
                    
                if do_print_html:
                    print_html(product_number, full_korean_name)
                
                symlink_attempts += 1
                result = make_symbolic_link(link, target, pdf_dir_path, product_number)
                if result == "created":
                    symlink_created += 1
                elif result == "downloaded_and_created":
                    symlink_downloaded_and_created += 1
                elif result == "already_exists":
                    symlink_already_exists += 1
                elif result == "target_missing":
                    symlink_target_missing += 1
                else:  # "failed"
                    symlink_creation_failed += 1
            elif status == "empty":
                translation_empty += 1
                print(f"translating error: {brand} / {product_name} / {product_number}")
            else:  # status == "not_found"
                translation_not_found += 1
                print(f"translating error: {brand} / {product_name} / {product_number}")
        else:
            print(f"can't get product name from web page, {file_path=}")

    if do_print_html:
        print("</ul>")
    
    # 실제 PDF 파일 갯수 계산 (심볼릭링크 제외)
    pdf_files_count = sum(1 for f in pdf_dir_path.iterdir() if f.is_file() and not f.is_symlink() and f.name.endswith('.pdf'))
    
    # 현재 존재하는 심볼릭링크 갯수 계산
    existing_symlinks_count = sum(1 for f in pdf_dir_path.iterdir() if f.is_symlink())
    
    # 심볼릭링크가 가리키는 target 파일들을 분석
    symlink_targets = {}
    for f in pdf_dir_path.iterdir():
        if f.is_symlink():
            try:
                target = f.resolve().name
                if target not in symlink_targets:
                    symlink_targets[target] = []
                symlink_targets[target].append(f.name)
            except:
                pass
    
    # 여러 심볼릭링크가 가리키는 PDF 찾기
    multiple_symlinks = {target: links for target, links in symlink_targets.items() if len(links) > 1}
    
    # 처리 단계별 통계 출력
    print(f"\n=== 처리 단계별 통계 ===")
    print(f"전체 HTML 파일: {total_html_files}개")
    print(f"유효한 제품번호 파일: {valid_product_number_files}개 (감소: {total_html_files - valid_product_number_files}개)")
    print(f"제품명 추출 성공: {product_name_extracted}개 (감소: {valid_product_number_files - product_name_extracted}개)")
    print(f"번역 성공: {translation_success}개")
    print(f"번역 실패 (빈 번역값): {translation_empty}개")
    print(f"번역 실패 (번역 데이터 없음): {translation_not_found}개")

    print(f"\n=== 심볼릭링크 처리 통계 ===")
    print(f"실제 PDF 파일: {pdf_files_count}개")
    print(f"심볼릭링크 시도: {symlink_attempts}개 (번역 성공과 일치해야 함)")
    print(f"심볼릭링크 생성 성공: {symlink_created}개")
    print(f"PDF 다운로드 후 생성: {symlink_downloaded_and_created}개")
    print(f"이미 존재하는 심볼릭링크: {symlink_already_exists}개")
    print(f"target PDF 파일 없음 (다운로드 실패): {symlink_target_missing}개")
    print(f"생성 실패 (기타 오류): {symlink_creation_failed}개")
    print(f"심볼릭링크 처리 총합: {symlink_created + symlink_downloaded_and_created + symlink_already_exists + symlink_target_missing + symlink_creation_failed}개 (시도와 일치해야 함)")
    print(f"실제 생성된 심볼릭링크: {symlink_created + symlink_downloaded_and_created}개")
    print(f"현재 존재하는 총 심볼릭링크: {existing_symlinks_count}개")
    print(f"여러 심볼릭링크가 가리키는 PDF: {len(multiple_symlinks)}개")
    print(f"중복 심볼릭링크 총 개수: {sum(len(links) - 1 for links in multiple_symlinks.values())}개")
    print(f"translating error 출력 예상: {translation_empty + translation_not_found}개")
    
    # 중복 심볼릭링크 상세 정보 출력
    if multiple_symlinks:
        print(f"\n=== 중복 심볼릭링크 상세 정보 ===")
        for target, links in sorted(multiple_symlinks.items()):
            print(f"{target} <- {len(links)}개:")
            for link in sorted(links):
                print(f"  - {link}")
    
    # 사용되지 않은 번역 아이템들 처리
    unused_keys = set(translation_data.keys()) - used_translation_keys
    if unused_keys:
        print(f"\n사용되지 않은 번역 아이템들 ({len(unused_keys)}개):")
        for key in sorted(unused_keys):
            print(f"  ! {key}")
        
        # 미사용 키들을 translation_data에서 삭제
        for key in unused_keys:
            del translation_data[key]
        
        # 업데이트된 translation_data를 파일에 저장
        write_translation(translation_file_path, translation_data)
        print(f"\n미사용 번역 아이템들을 삭제하고 '{translation_file_path}'에 저장했습니다.")
        print(f"남은 번역 아이템: {len(translation_data)}개")
    else:
        print("\n모든 번역 아이템들이 사용되었습니다.")
        
    return 0


if __name__ == "__main__":
    sys.exit(main())



