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
    # 키를 clean_text로 정규화하여 HTML에서 추출한 상품명과 매칭되도록 함
    return {clean_text(k): v for k, v in translation_data.items()}


def write_translation(translation_file_path: Path, translation_data: dict[str, str]) -> None:
    with translation_file_path.open("w", encoding="utf-8") as outfile:
        json.dump(translation_data, outfile, ensure_ascii=False, indent=2, sort_keys=True)


def convert_full_character_to_half(text: str) -> str:
    return unicodedata.normalize('NFKC', text)


def clean_text(text: str) -> str:
    text = re.sub(r'[“”"]', '\'', text)
    return convert_full_character_to_half(text)


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

            m = re.search(r'<h2 class="el_title"><span>(?P<brand>30MM|30MS|30MF|SDW HEROES|Figure-rise Standard|SDガンダム EX|SDガンダム|SDBD:R|SDBF|SDBD|ADVANCE OF Z|BB戦士|HGBF|HGBC|FULL MECHANICS|HGBD:R|HGBD|HGFC|ENTRY GRADE|RE/?100|HGAC|HGCE|EXPO|MGSD|HGCC|HGAW|HGUC|MGEX|RG|MG|PG|HG).*(?P<scale>1/\d{1,4})[ \u3000\xa0\s]*(?P<product_name>.+)</span></h2>', line)
            if m:
                brand = m.group("brand")
                brand = clean_text(brand)
                brand = re.sub(r"RE/100", "RE100", brand)
                scale = m.group("scale")
                scale = re.sub(r"/", "_", scale)
                product_name = m.group("product_name")
                year = ""
                continue

            m = re.search(r'<h2 class="el_title"><span>(?P<brand>30MM|30MS|30MF|SDW HEROES|Figure-rise Standard|SDガンダム EX|SDガンダム|SDBD:R|SDBF|SDBD|ADVANCE OF Z|BB戦士|HGBF|HGBC|FULL MECHANICS|HGBD:R|HGBD|HGFC|ENTRY GRADE|RE/?100|HGAC|HGCE|EXPO|MGSD|HGCC|HGAW|HGUC|MGEX|RG|MG|PG|HG)[ \u3000\xa0\s]*(?P<product_name>.+)</span></h2>', line)
            if m:
                brand = m.group("brand")
                brand = clean_text(brand)
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
    product_name = clean_text(product_name)
    brand = clean_text(brand)

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


def download_pdf(product_number: int, pdf_dir_path: Path) -> bool:
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


def make_symbolic_link(link: Path, target: Path, pdf_dir_path: Path, product_number: int = None) -> str:
    """
    심볼릭링크 생성을 시도하고 결과를 반환
    반환값: "created", "downloaded_and_created", "already_exists", "target_missing", "failed"
    """
    if link.is_symlink():
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


def print_html(product_number: int, full_korean_name: str, korean_name: str, brand: str, scale: str) -> None:
    print(f"<li data-name='{korean_name}' data-brand='{brand}' data-scale='{scale}'>"
          f"<a href='{BASE_URL}/pdf/{product_number}.pdf' target='_blank'>{full_korean_name}</a></li>")


def process_duplicates(product_name_number_dict: dict[str, int], product_number: int, full_korean_name: str, year: str, pdf_dir_path: Path) -> Optional[Path]:
    if full_korean_name in product_name_number_dict:
        # add the year field to link
        full_korean_name += ((" " + year) if year else "")
        link = pdf_dir_path / (full_korean_name + ".pdf")
        return link

    product_name_number_dict[full_korean_name] = product_number
    return None


class Stats:
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


def process_product_page_files(detail_dir_path: Path, pdf_dir_path: Path, translation_data: dict[str, str], do_print_html: bool) -> Stats:
    st = Stats()

    product_name_number_dict = {}
    list_to_print: list[tuple[int, str, str, str, str]] = []
    for file_path in detail_dir_path.iterdir():
        if not file_path.is_file():
            print(f"DEBUG: 파일이 아님: {file_path.name}")
            continue
        st.total_html_files += 1
        m = re.search(r'^(?P<product_number>\d+)\.html$', file_path.name)
        if not m:
            print(f"DEBUG: 이름 컨벤션이 맞지 않는 파일명: {file_path.name}")
            continue
        product_number = int(m.group("product_number"))
        st.valid_product_number_files += 1
        product_name, brand, scale, year = get_product_name_from_file(file_path)

        if product_name:
            st.product_name_extracted += 1
            korean, status = convert_ja_to_ko(translation_data, product_name, brand, scale)

            if status == "success":
                st.translation_success += 1
                escaped_korean_name = re.sub(r'/', ' ', korean)
                full_korean_name = escaped_korean_name + ((" " + brand) if brand else "") + ((" " + scale) if scale else "")

                link = pdf_dir_path / (full_korean_name + ".pdf")
                target = pdf_dir_path / (str(product_number) + ".pdf")

                deduplicated_link = process_duplicates(product_name_number_dict, product_number, full_korean_name, year, pdf_dir_path)
                if deduplicated_link:
                    link = deduplicated_link

                list_to_print.append((product_number, full_korean_name, escaped_korean_name, brand, scale))

                st.symlink_attempts += 1
                result = make_symbolic_link(link, target, pdf_dir_path, product_number)
                if result == "created":
                    st.symlink_created += 1
                elif result == "downloaded_and_created":
                    st.symlink_downloaded_and_created += 1
                elif result == "already_exists":
                    st.symlink_already_exists += 1
                elif result == "target_missing":
                    st.symlink_target_missing += 1
                else:  # "failed"
                    st.symlink_creation_failed += 1
            elif status == "empty":
                st.translation_empty += 1
                print(f"translating error: {product_name} / {brand} / {scale} / {product_number}")
            else:  # status == "not_found"
                st.translation_not_found += 1
                print(f"translating error: {product_name} / {brand} / {scale} / {product_number}")
        else:
            print(f"can't get product name from web page, {file_path=}")


    if do_print_html:
        for product_number, full_korean_name, korean_name, brand, scale in sorted(list_to_print, key=lambda x: x[1]):
            print_html(product_number, full_korean_name, korean_name, brand, scale)

    return st


def main() -> int:
    detail_dir_path = MANUAL_DIR_PATH / "menus" / "detail"
    pdf_dir_path = MANUAL_DIR_PATH / "pdf"
    translation_file_path = Path("mapping") / "bandai_product_ja_ko_mapping.json"

    do_print_html = False

    opts, args = getopt.getopt(sys.argv[1:], "-h")
    for o, _ in opts:
        if o == "-h":
            do_print_html = True

    translation_data = read_translation(translation_file_path)
    if not translation_data:
        sys.stderr.write(f"can't find translation data from '{translation_file_path}'\n")

    if do_print_html:
        print("""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>반다이 프라모델 목록</title>
<style>
  body { font-family: 'Malgun Gothic', sans-serif; margin: 20px; background: #f5f5f5; }
  .search-box { background: #fff; padding: 16px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.12); margin-bottom: 20px; }
  .search-box label { display: inline-block; margin-right: 8px; font-weight: bold; }
  .search-box input, .search-box select { padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; margin-right: 16px; }
  .search-box input[type=text] { width: 200px; }
  .search-box input[type=number] { width: 60px; }
  .search-box button { padding: 6px 16px; border: 1px solid #1a73e8; border-radius: 4px; background: #1a73e8; color: #fff; cursor: pointer; font-size: 14px; }
  .search-box button:hover { background: #1557b0; }
  .options { margin-top: 8px; font-size: 0.9em; color: #555; }
  #count { margin-bottom: 8px; color: #666; }
  ul { list-style: disc; padding-left: 20px; }
  li { padding: 2px 0; }
  li a { color: #1a0dab; text-decoration: none; }
  li a:hover { text-decoration: underline; }
  li.hidden { display: none; }
  mark { background: #fff176; padding: 0; }
</style>
</head>
<body>
<h1>반다이 프라모델 목록</h1>
<div class="search-box">
  <div>
    <label for="searchName">제품명:</label>
    <input type="text" id="searchName" placeholder="제품명 검색...">
    <label for="searchBrand">등급:</label>
    <input type="text" id="searchBrand" placeholder="예: HG, MG, RG...">
    <label for="searchScale">스케일:</label>
    <input type="text" id="searchScale" placeholder="예: 1_144">
    <button id="searchBtn">검색</button>
  </div>
  <div class="options">
    <label><input type="checkbox" id="fuzzyToggle" checked> 오타 허용 (퍼지 검색)</label>
    <label style="margin-left:16px;">허용 거리: <input type="number" id="fuzzyThreshold" value="1" min="0" max="5" style="width:50px;"></label>
  </div>
</div>
<div id="count"></div>
<ul id="productList">""")

    # 상품 페이지 파일 처리
    st = process_product_page_files(detail_dir_path, pdf_dir_path, translation_data, do_print_html)

    if do_print_html:
        print(r"""</ul>
<script>
(function() {
  // Levenshtein distance 계산
  function levenshtein(a, b) {
    var m = a.length, n = b.length;
    if (m === 0) return n;
    if (n === 0) return m;
    var dp = [];
    for (var i = 0; i <= m; i++) dp[i] = [i];
    for (var j = 0; j <= n; j++) dp[0][j] = j;
    for (i = 1; i <= m; i++) {
      for (j = 1; j <= n; j++) {
        var cost = a[i-1] === b[j-1] ? 0 : 1;
        dp[i][j] = Math.min(dp[i-1][j] + 1, dp[i][j-1] + 1, dp[i-1][j-1] + cost);
      }
    }
    return dp[m][n];
  }

  // 부분 문자열 퍼지 매칭: 공백 제거 후 슬라이딩 윈도우로 최소 편집 거리 계산
  function fuzzyContains(target, query, threshold) {
    target = target.toLowerCase();
    query = query.toLowerCase();
    if (query.length === 0) return true;
    if (target.indexOf(query) !== -1 || removeSpaces(target).indexOf(removeSpaces(query)) !== -1) return true;
    // 공백 제거 버전으로 퍼지 매칭
    var t = removeSpaces(target);
    var q = removeSpaces(query);
    if (q.length > t.length) return levenshtein(t, q) <= threshold;
    var minDist = Infinity;
    for (var i = 0; i <= t.length - q.length; i++) {
      var sub = t.substring(i, i + q.length);
      var d = levenshtein(sub, q);
      if (d < minDist) minDist = d;
      if (minDist === 0) return true;
    }
    return minDist <= threshold;
  }

  // 공백 제거 유틸
  function removeSpaces(s) { return s.replace(/\s+/g, ''); }

  // 정확한 부분 문자열 매칭 (공백 무시)
  function exactContains(target, query) {
    var t = target.toLowerCase(), q = query.toLowerCase();
    return t.indexOf(q) !== -1 || removeSpaces(t).indexOf(removeSpaces(q)) !== -1;
  }

  var items = document.querySelectorAll('#productList li');
  var nameInput = document.getElementById('searchName');
  var brandInput = document.getElementById('searchBrand');
  var scaleInput = document.getElementById('searchScale');
  var fuzzyToggle = document.getElementById('fuzzyToggle');
  var fuzzyThreshold = document.getElementById('fuzzyThreshold');
  var searchBtn = document.getElementById('searchBtn');
  var countEl = document.getElementById('count');

  function doFilter() {
    var qName = nameInput.value.trim();
    var qBrand = brandInput.value.trim();
    var qScale = scaleInput.value.trim();
    var useFuzzy = fuzzyToggle.checked;
    var threshold = parseInt(fuzzyThreshold.value) || 2;
    var matchFn = useFuzzy
      ? function(t, q) { return fuzzyContains(t, q, threshold); }
      : exactContains;

    var shown = 0;
    for (var i = 0; i < items.length; i++) {
      var li = items[i];
      var name = li.getAttribute('data-name') || '';
      var brand = li.getAttribute('data-brand') || '';
      var scale = li.getAttribute('data-scale') || '';

      var match = true;
      if (qName && !matchFn(name, qName)) match = false;
      if (qBrand && !exactContains(brand, qBrand)) match = false;
      if (qScale && !exactContains(scale, qScale)) match = false;

      if (match) {
        li.classList.remove('hidden');
        shown++;
      } else {
        li.classList.add('hidden');
      }
    }
    countEl.textContent = shown + '개 / 전체 ' + items.length + '개';
  }

  searchBtn.addEventListener('click', doFilter);
  nameInput.addEventListener('keydown', function(e) { if (e.key === 'Enter') doFilter(); });
  brandInput.addEventListener('keydown', function(e) { if (e.key === 'Enter') doFilter(); });
  scaleInput.addEventListener('keydown', function(e) { if (e.key === 'Enter') doFilter(); });

  // 초기 카운트 표시
  countEl.textContent = items.length + '개 / 전체 ' + items.length + '개';
})();
</script>
</body>
</html>""")

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
            except Exception as e:
                print(f"DEBUG: 심볼릭링크 타겟 파일 오류 - {f.name}, {e}")

    # 여러 심볼릭링크가 가리키는 PDF 찾기
    multiple_symlinks = {target: links for target, links in symlink_targets.items() if len(links) > 1}

    if not do_print_html:
        # 처리 단계별 통계 출력
        print("\n=== 처리 단계별 통계 ===")
        print(f"전체 HTML 파일: {st.total_html_files}개")
        print(f"유효한 제품번호 파일: {st.valid_product_number_files}개 (감소: {st.total_html_files - st.valid_product_number_files}개)")
        print(f"제품명 추출 성공: {st.product_name_extracted}개 (감소: {st.valid_product_number_files - st.product_name_extracted}개)")
        print(f"번역 성공: {st.translation_success}개")
        print(f"번역 실패 (빈 번역값): {st.translation_empty}개")
        print(f"번역 실패 (번역 데이터 없음): {st.translation_not_found}개")
        
        print("\n=== 심볼릭링크 처리 통계 ===")
        print(f"실제 PDF 파일: {pdf_files_count}개")
        print(f"심볼릭링크 시도: {st.symlink_attempts}개 (번역 성공과 일치해야 함)")
        print(f"심볼릭링크 생성 성공: {st.symlink_created}개")
        print(f"PDF 다운로드 후 생성: {st.symlink_downloaded_and_created}개")
        print(f"이미 존재하는 심볼릭링크: {st.symlink_already_exists}개")
        print(f"target PDF 파일 없음 (다운로드 실패): {st.symlink_target_missing}개")
        print(f"생성 실패 (기타 오류): {st.symlink_creation_failed}개")
        print(f"심볼릭링크 처리 총합: {st.symlink_created + st.symlink_downloaded_and_created + st.symlink_already_exists + st.symlink_target_missing + st.symlink_creation_failed}개 (시도와 일치해야 함)")
        print(f"실제 생성된 심볼릭링크: {st.symlink_created + st.symlink_downloaded_and_created}개")
        print(f"현재 존재하는 총 심볼릭링크: {existing_symlinks_count}개")
        print(f"여러 심볼릭링크가 가리키는 PDF: {len(multiple_symlinks)}개")
        print(f"중복 심볼릭링크 총 개수: {sum(len(links) - 1 for links in multiple_symlinks.values())}개")
        print(f"translating error 출력 예상: {st.translation_empty + st.translation_not_found}개")

    return 0


if __name__ == "__main__":
    sys.exit(main())



