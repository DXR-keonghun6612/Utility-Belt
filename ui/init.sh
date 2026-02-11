#!/bin/bash
# ==============================================================================
# 파일명: init.sh
# 설명: UI 프로세스 모듈들을 일괄 로드합니다.
# ==============================================================================

initialize_ui_processes() {
    local current_dir
    current_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # proc_*.sh 패턴의 모든 UI 프로세스 스크립트를 로드
    for script in "${current_dir}"/proc_*.sh; do
        if [[ -f "${script}" ]]; then
            # shellcheck source=/dev/null
            source "${script}"
        fi
    done
}
