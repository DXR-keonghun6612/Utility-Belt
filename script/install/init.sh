#!/bin/bash
# ==============================================================================
# 파일명: init.sh
# 설명: 설치 관련 로직 모듈들을 일괄 로드합니다.
# ==============================================================================

initialize_install_modules() {
    local current_dir
    current_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # .sh 확장자를 가진 모든 설치 스크립트를 로드 (단, 자기 자신은 제외)
    for script in "${current_dir}"/*.sh; do
        if [[ -f "${script}" && "${script}" != "${current_dir}/init.sh" ]]; then
            # shellcheck source=/dev/null
            source "${script}"
        fi
    done
}
