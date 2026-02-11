#!/bin/bash
# ==============================================================================
# 파일명: init.sh
# 설명: 사용자 관련 유틸리티 모듈들을 일괄 로드합니다.
# ==============================================================================

initialize_user_modules() {
    local current_dir
    current_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # 02_*.sh 패턴의 모든 사용자 스크립트를 로드
    for script in "${current_dir}"/02_*.sh; do
        if [[ -f "${script}" ]]; then
            # shellcheck source=/dev/null
            source "${script}"
        fi
    done
}
