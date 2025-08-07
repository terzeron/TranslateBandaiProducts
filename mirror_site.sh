#!/bin/bash

# 사용법 출력 함수
usage() {
    echo "Usage: $0 <site_name> [-c] [-e]"
    echo "  site_name: Target site (dalong, bandai-hobby, or gundam-wiki)"
    echo "  -c: Collect/mirror website"
    echo "  -e: Extract products only"
    echo "  Both options can be used together"
    echo ""
    echo "Sites:"
    echo "  dalong: Dalong.net (static mirroring)"
    echo "  bandai-hobby: Bandai Manual site (static mirroring + PDFs)"
    echo "  gundam-wiki: Gundam Wiki sites (Fandom + Namu Wiki)"
    exit 1
}

# 사이트 이름 확인
if [ $# -lt 1 ]; then
    usage
fi

site_name="$1"
shift

do_collect=0
do_extract=0

# 옵션 파싱
while [ $# -gt 0 ]; do
    case "$1" in
        -c)
            do_collect=1
            ;;
        -e)
            do_extract=1
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
    shift
done

# 기본값: 둘 다 없으면 추출만 실행
if [ $do_collect -eq 0 ] && [ $do_extract -eq 0 ]; then
    do_extract=1
fi

# 사이트별 설정
case "$site_name" in
    "dalong")
        hostname="www.dalong.net"
        url="http://$hostname"
        output_file="${site_name}_products.txt"
        ;;
    "bandai-hobby")
        hostname="manual.bandai-hobby.net"
        url="https://$hostname"
        output_file="${site_name}_products.txt"
        ;;
    "gundaminfo")
        hostname="kr.gundam.info"
        url="https://kr.gundam.info"
        output_file="${site_name}_products.txt"
        ;;
    *)
        echo "Unsupported site: $site_name"
        echo "Supported sites: dalong, bandai-hobby, gundaminfo"
        exit 1
        ;;
esac

if [ "$do_collect" = "1" ]; then
    echo "$site_name 건프라 페이지 미러링 시작..."
    
    case "$site_name" in
        "dalong")
            # Dalong.net: 스마트 증분 미러링 (우선순위 기반 + 효율적 변경 감지)
            echo "Dalong.net 스마트 증분 미러링 중..."
            ./smart_incremental_mirror.py "$url" "$hostname" 10000 "dalong"
            ;;
        "bandai-hobby")
            # Bandai Manual: 스마트 증분 미러링 필수 (복잡한 캐싱 + PDF 관리)
            echo "Bandai Manual 스마트 증분 미러링 중..."
            ./smart_incremental_mirror.py "$url" "$hostname" 10000 "bandai-hobby"
            ;;
        "gundaminfo")
            # Gundam Info: 스마트 증분 미러링 필수 (동적 콘텐츠 + 우선순위 기반 수집)
            echo "Gundam Info 스마트 증분 미러링 중..."
            ./smart_incremental_mirror.py "$url" "$hostname" 10000 "gundaminfo"
            ;;
    esac
    
    echo "미러링 완료."
fi

if [ "$do_extract" = "1" ]; then
    echo "$site_name 건프라 상품명 추출 시작..."
    ./extract_site_products.py "$hostname" "$output_file" "$site_name"
    echo "추출 완료: $output_file"
fi
