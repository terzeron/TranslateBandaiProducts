#!/usr/bin/env python


import sys
import re
import json
import getopt
import unicodedata
from pathlib import Path
from typing import Optional


def read_translation(translation_file_path: Path) -> dict[str, str]:
    with translation_file_path.open("r", encoding="utf-8") as infile:
        translation_data = json.load(infile)
    return translation_data


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

            
def convert_ja_to_ko(translation_data: dict[str, str], product_name: str, brand: str, scale: str) -> str:
    # cleaning
    product_name = re.sub(r'[“”"]', '', product_name)
    product_name = convert_full_character_to_half(product_name)
    brand = convert_full_character_to_half(brand)

    result = translation_data.get(product_name + " " + brand + " " + scale, "")
    if result:
        return re.sub(r'[/"]', '', result)
    result = translation_data.get(product_name + " " + brand, "")
    if result:
        return re.sub(r'[/"]', '', result)
    result = translation_data.get(product_name + " " + scale, "")
    if result:
        return re.sub(r'[/"]', '', result)
    result = translation_data.get(product_name, "")
    if result:
        return re.sub(r'[/"]', '', result)
    
    # 기존 방식으로 찾지 못한 경우 원문 유지 (조악한 번역 방지)
    print(f"translating error: {product_name}")
    return product_name  # 원문 그대로 반환
    

def make_symbolic_link(link: Path, target: Path, pdf_dir_path: Path) -> None:
    if not link.is_symlink():
        try:
            link.symlink_to(target.relative_to(pdf_dir_path))
            print(f"{link.name} -> {target.relative_to(pdf_dir_path)}")
        except FileNotFoundError as e:
            print(f"linking error: {link.name} -x-> {target.name}, {e}")

            
def print_html(product_number: str, full_korean_name: str) -> None:
    print(f"<li><a href='https://manual.bandai-hobby.net/pdf/{product_number}.pdf' target='_blank'>{full_korean_name}</a></li>")


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
    do_print_html = False
    
    opts, args = getopt.getopt(sys.argv[1:], "-h")
    for o, _ in opts:
        if o == "-h":
            do_print_html = True
    
    detail_dir_path = Path(args[0])
    pdf_dir_path = Path(args[1])
    translation_file_path = Path(args[2])
    #print(f"{detail_dir_path=}, {pdf_dir_path=}, {translation_file_path=}")

    translation_data = read_translation(translation_file_path)
    if not translation_data:
        sys.stderr.write(f"can't find translation data from '{translation_file_path}'\n")
    
    # 조악한 번역 방지를 위해 TranslationOptimizer 비활성화
    optimizer = None

    if do_print_html:
        print("<ul>")
        
    product_name_number_dict = {}
    for file_path in detail_dir_path.iterdir():
        product_number = file_path.name
        if not re.search(r'^\d+$', product_number):
            continue
        product_name, brand, scale, year = get_product_name_from_file(file_path)
        #print(f"{product_number}: {product_name}, {brand}, {scale}, {year}")
        
        if product_name:
            korean = convert_ja_to_ko(translation_data, product_name, brand, scale)
            if korean:
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
                    
                make_symbolic_link(link, target, pdf_dir_path)
                    
                #else:
                    #print(product_number, product_name, full_korean_name)
            else:
                print(f"translating error: {brand} / {product_name} / {product_number}")
        else:
            print(f"can't get product name from web page, {file_path=}")

    if do_print_html:
        print("</ul>")
        
    return 0


if __name__ == "__main__":
    sys.exit(main())



