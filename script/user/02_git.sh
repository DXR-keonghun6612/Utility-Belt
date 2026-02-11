#!/bin/bash

_initialize_git_utils() {
    ensure_packages_installed "PACKAGES_LIST" "git" || return $?
    log_success "Git utility initialized successfully."
    return 0
}

_initialize_git_utils

# ------------------------------------------------------------------------------
# @description Git 설정을 관리(읽기/쓰기)합니다.
#              value 인자가 있으면 쓰기, 없으면 읽기 모드로 동작합니다.
# @param $1 key (설정 키)
# @param $2 [scope] (옵션: --global, --system, --local. 기본값: --global)
# @param $3 [value] (옵션: 설정할 값. 이 값이 있으면 쓰기 모드가 됨)
# @return 읽기 성공 시 0, 쓰기 성공 시 0, 실패 시 1.
# ------------------------------------------------------------------------------
manage_git_config() {
    local key="$1"
    local scope="${2:---global}"
    local value="$3" # 세 번째 인자를 값으로 받음

    local git_cmd_array=()

    # 권한 확인 로직
    if [[ "${scope}" == "--system" && "${G_IS_ROOT}" == "false" ]]; then
        log_error "System-wide git config requires root privileges."
        return 1
    fi

    git_cmd_array+=("git" "config" "${scope}")

    # --- 읽기/쓰기/삭제/목록 분기 ---
    if [[ -z "${key}" ]]; then
        # 목록 모드
        git_cmd_array+=("--list")
    elif [[ "${value}" == "__DELETE__" ]]; then
        # 삭제 모드
        git_cmd_array+=("--unset" "${key}")
    elif [[ -n "${value}" ]]; then
        # 쓰기 모드
        git_cmd_array+=("${key}" "${value}")
    else
        # 읽기 모드
        git_cmd_array+=("${key}")
    fi
    
    # 최종 구성된 명령어를 실행
    "${git_cmd_array[@]}"
    
    return $?
}

# 읽기 전용 래퍼
get_git_config() {
    manage_git_config "$1" "$2"
}

# 쓰기 전용 래퍼
set_git_config() {
    # 쓰기 함수는 key, scope, value가 모두 필요
    if [[ "$#" -lt 3 ]]; then
        log_error "Usage: set_git_config <key> <scope> <value>"
        return 1
    fi
    manage_git_config "$1" "$2" "$3"
}

# ------------------------------------------------------------------------------
# @description Git Credential Helper(store)를 설정하고 토큰을 저장합니다.
# @param $1 username
# @param $2 token
# @param $3 [host] (기본값: github.com)
# ------------------------------------------------------------------------------
update_git_token() {
    local username="$1"
    local token="$2"
    local host="${3:-github.com}"
    
    # 1. Credential helper 설정 (global)
    git config --global credential.helper store
    
    # 2. .git-credentials 파일 업데이트
    local cred_file="${HOME}/.git-credentials"
    
    # 해당 호스트에 대한 기존 항목 제거 (중복 방지)
    if [[ -f "$cred_file" ]]; then
        # sed를 사용하여 해당 호스트(@host)가 포함된 줄 삭제
        sed -i "\#@${host}#d" "$cred_file"
    fi
    
    # 새 자격 증명 추가 (URL 인코딩이 필요할 수 있으나, 일반적인 토큰에는 필요 없음)
    # umask 077을 사용하여 파일이 새로 생성될 경우 600 권한을 갖도록 함
    (
        umask 077
        cat <<EOF >> "$cred_file"
https://${username}:${token}@${host}
EOF
    )
    
    log_info "Git credentials updated for ${host}"
    return 0
}