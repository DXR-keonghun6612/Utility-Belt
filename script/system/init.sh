#!/bin/bash
# ==============================================================================
# 파일명: init.sh
# 설명: 시스템 관련 백엔드 모듈들을 일괄 로드합니다.
# ==============================================================================

initialize_system_modules() {
    local current_dir
    current_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # 02_*.sh 패턴의 모든 시스템 스크립트를 로드
    for script in "${current_dir}"/02_*.sh; do
        if [[ -f "${script}" ]]; then
            # shellcheck source=/dev/null
            source "${script}"
        fi
    done
}
