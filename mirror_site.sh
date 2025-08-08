#!/bin/bash

# 사용법 출력 함수
usage() {
    echo "Usage: $0 <site_name> [-c] [-e]"
    echo "  site_name: Target site (dalong, bandai-hobby, gundaminfo, or gcd)"
    echo "  -c: Collect/mirror website"
    echo "  -e: Extract products only"
    echo "  Both options can be used together"
    echo ""
    echo "Sites:"
    echo "  dalong: Dalong.net (smart incremental mirroring)"
    echo "  bandai-hobby: Bandai Manual site (smart incremental mirroring + PDFs)"
    echo "  gundaminfo: Gundam Info (smart incremental mirroring)"
    echo "  gcd: Naver Cafe JSON API (paged crawling, page=1..N)"
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
    "gcd")
        hostname="apis.naver.com"
        url="https://apis.naver.com/cafe-web/cafe-boardlist-api/v1/cafes/11569626/menus/394/articles?pageSize=50&sortBy=TIME&viewType=L&page="
        output_file="${site_name}_articles.json"
        ;;
    *)
        echo "Unsupported site: $site_name"
        echo "Supported sites: dalong, bandai-hobby, gundaminfo, gcd"
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
        "gcd")
            # gcd: JSON API 페이지 순회 (page=1..N), 대량 URL 초기 등록 없이 전용 루프
            echo "gcd JSON API 수집 중..."
            ./smart_incremental_mirror.py "$url" "gcd" 300 "gcd"
            ;;
    esac
    
    echo "미러링 완료."
fi

if [ "$do_extract" = "1" ]; then
    echo "$site_name 건프라 상품명 추출 시작..."
    if [ "$site_name" = "gcd" ]; then
        # gcd: JSON 텍스트 추출 수행 (subjects)
        # 미러 디렉터리는 수집 시 지정한 출력 디렉터리인 "gcd"
        ./extract_site_products.py "gcd" "gcd_products.txt" "$site_name"
        echo "추출 완료: gcd_products.txt"
    else
        ./extract_site_products.py "$hostname" "$output_file" "$site_name"
        echo "추출 완료: $output_file"
    fi
fi
