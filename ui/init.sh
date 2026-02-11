#!/bin/bash
# ==============================================================================
# 파일명: init.sh
# 설명: UI 프로세스 모듈들을 일괄 로드합니다.
# ==============================================================================

initialize_ui_processes() {
    local current_dir
    current_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # 서브디렉토리 내의 모든 .sh 파일을 재귀적으로 찾아 로드
    while read -r script; do
        if [[ -f "${script}" && "${script}" != "${current_dir}/init.sh" ]]; then
            # shellcheck source=/dev/null
            source "${script}"
        fi
    done < <(find "${current_dir}" -mindepth 2 -name "*.sh")
}
