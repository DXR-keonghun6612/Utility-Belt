#!/bin/bash
# ==============================================================================
# 파일명: samba.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: Samba 서비스 제어, 공유 및 사용자 관리 등 모든 핵심 로직을 담당.
# ==============================================================================


# ==============================================================================
# 초기화
# ==============================================================================

# -----------------------------------------------------------------------------
# @description 패키지 설치 유틸리티에 필요한 패키지를 확인하고 설치함.
# -----------------------------------------------------------------------------
_initialize_samba_utils() {
    # ensure_packages_installed 함수를 사용하여 패키지 확인 및 설치
    ensure_packages_installed "PACKAGES_LIST" "Network Management Utils" "samba" || return $?
    
    log_success "Samba management utility initialized successfully."
    return 0
}

# 초기화 함수 호출
_initialize_samba_utils


# ==============================================================================
# 서비스 관리
# ==============================================================================

##
# @description smb.conf 설정 파일의 구문이 유효한지 검사.
#
check_samba_config() {
    log_info "Checking Samba configuration syntax..."
    if testparm -s; then
        log_info "Configuration syntax is OK."
        return 0
    else
        log_error "Samba configuration check failed. Please review the errors above."
        return 1
    fi
}

##
# @description Samba (smbd) 서비스의 현재 상태를 가져옴.
#
get_samba_status() {
    log_info "Getting Samba service status..."
    systemctl status smbd
}

##
# @description Samba 설정을 확인한 후 안전하게 서비스를 재시작.
#
restart_samba() {
    if ! check_samba_config; then
        return 1
    fi
    
    log_info "Restarting Samba service..."
    if systemctl restart smbd; then
        log_success "Samba service restarted successfully."
    else
        log_error "Failed to restart Samba service."
        return 1
    fi
}

# ==============================================================================
# 공유 프로필 관리
# ==============================================================================

##
# @description smb.conf에서 모든 공유 프로필과 그 활성화 상태를 읽어옴.
# @return stdout "share1 on share2 off ..." 형태의 문자열
#
get_samba_shares() {
    local smb_conf="/etc/samba/smb.conf"
    if [[ ! -f "${smb_conf}" ]]; then return; fi

    awk '
        /^\s*#*\s*\[.*\]/ && !/\[(global)\]/ {
            name = $0;
            gsub(/^.*\[|].*$/, "", name);
            status = ($0 ~ /^\s*#/) ? "off" : "on";
            printf "%s %s ", name, status;
        }
    ' "${smb_conf}" | xargs
}

##
# @description 지정된 공유 프로필을 활성화/비활성화 (주석 처리/해제).
# @param $1 share_name 대상 공유 이름
# @param $2 state "enable" 또는 "disable"
#
toggle_samba_share_status() {
    local share_name="$1"
    local state="$2"
    local smb_conf="/etc/samba/smb.conf"

    if [[ -z "$share_name" || -z "$state" ]]; then
        log_error "Share name and state ('enable' or 'disable') are required."
        return 1
    fi

    log_info "Setting share '[${share_name}]' to '${state}'..."
    
    # 1. 원본 파일을 백업.
    cp "${smb_conf}" "${smb_conf}.bak_$(date +%F-%T)"

    # 2. profile_engine.sh의 범용 섹션 토글 함수를 호출.
    if toggle_config_section "${smb_conf}" "${share_name}" "${state}"; then
        log_success "Successfully changed state for '[${share_name}]'."
    else
        log_error "Failed to change state for '[${share_name}]'."
        return 1
    fi
}

##
# @description 지정된 이름의 공유 프로필을 smb.conf에서 완전히 제거.
# @param $1 share_name 제거할 공유 이름
# @param $2 silent_mode "silent"일 경우 메시지 출력 안 함
#
delete_samba_share() {
    local share_name="$1"
    local smb_conf="/etc/samba/smb.conf"

    # 1. 제거할 공유가 실제로 존재하는지 확인.
    if ! get_samba_shares | grep -q "\b${share_name}\b"; then
        log_info "Share '[${share_name}]' does not exist."
        return 0
    fi
    
    log_info "Removing share profile '[${share_name}]'..."
    
    # 2. 만약을 대비해 원본 파일을 백업.
    cp "${smb_conf}" "${smb_conf}.bak_$(date +%F-%T)"
    
    # 3. profile_engine.sh의 범용 섹션 삭제 함수를 호출.
    if delete_config_section "${smb_conf}" "${share_name}"; then
        log_success "Successfully removed share profile '[${share_name}]'."
    else
        log_error "Failed to remove share profile '[${share_name}]'."
        return 1
    fi
}

##
# @description 새로운 Samba 공유 프로필을 smb.conf 파일 끝에 추가.
# @param $1 share_name 생성할 공유 이름
# @param $2 options_str "path=/srv/share;valid users=user1" 형태의 옵션 문자열
#
add_samba_share() {
    local share_name="$1"
    local options_str="$2"
    local smb_conf="/etc/samba/smb.conf"

    # 1. 필수 인자(공유 이름, 옵션 문자열)가 모두 있는지 확인.
    if [[ -z "$share_name" || -z "$options_str" ]]; then
        log_error "Share name and options are required."
        return 1
    fi
    # 'path='는 Samba 공유의 필수 옵션이므로 반드시 포함되어 있는지 확인.
    if ! echo "${options_str}" | grep -q "path="; then
        log_error "The 'path=' setting is required in the options string."
        return 1
    fi

    # 2. profile_engine.sh의 섹션 추가 함수를 호출 (섹션이 없을 경우에만 추가).
    add_config_section "${smb_conf}" "${share_name}"
    
    # 3. 옵션 문자열을 profile_engine.sh 함수가 사용할 배열 형식으로 변환.
    local key_value_pairs=()
    local share_path=""
    local force_user=""
    local force_group=""

    IFS=';' read -ra options <<< "${options_str}"
    for option in "${options[@]}"; do
        key=$(echo "$option" | cut -d'=' -f1 | xargs)
        value=$(echo "$option" | cut -d'=' -f2- | xargs)
        key_value_pairs+=("${key}" "${value}")

        # 경로 및 권한 설정값 추출
        if [[ "${key}" == "path" ]]; then share_path="${value}"; fi
        if [[ "${key}" == "force user" ]]; then force_user="${value}"; fi
        if [[ "${key}" == "force group" ]]; then force_group="${value}"; fi
    done
    
    # 4. profile_engine.sh의 키-값 설정 함수를 호출하여 모든 옵션을 한 번에 기록.
    log_info "Setting options for share '[${share_name}]'..."
    if ! set_config_value "${smb_conf}" "${share_name}" "${key_value_pairs[@]}"; then
        log_error "Failed to set configuration for share '[${share_name}]'."
        return 1
    fi

    # 5. 디렉토리 생성 및 소유권 설정
    if [[ -n "${share_path}" ]]; then
        if [[ ! -d "${share_path}" ]]; then
            log_info "Creating shared directory: ${share_path}"
            mkdir -p "${share_path}"
        fi

        local chown_target=""
        [[ -n "${force_user}" ]] && chown_target="${force_user}"
        [[ -n "${force_group}" ]] && chown_target="${chown_target}:${force_group}"

        # 옵션에 사용자/그룹 설정이 없고 sudo로 실행된 경우, 원래 사용자를 소유자로 설정
        if [[ -z "${chown_target}" && "${G_IS_SUDO}" == "true" ]]; then
            chown_target="${G_ACTUAL_USER}:${G_ACTUAL_GROUP}"
            log_info "No 'force user/group' specified. Defaulting ownership to '${chown_target}'."
        fi

        if [[ -n "${chown_target}" ]]; then
            log_info "Applying ownership '${chown_target}' to '${share_path}'..."
            if chown "${chown_target}" "${share_path}"; then
                log_success "Ownership updated."
            else
                log_warn "Failed to change ownership of '${share_path}' to '${chown_target}'."
            fi
        fi
    fi

    log_success "Successfully configured share '[${share_name}]'."
}

# ==============================================================================
# 사용자 관리
# ==============================================================================

##
# @description 등록된 모든 Samba 사용자 목록을 보여줌.
#
list_samba_users() {
    log_info "Listing all Samba users..."
    pdbedit -L | awk -F: '{print " - " $1}'
}

##
# @description 대화형/비대화형으로 Samba 사용자를 추가하고 비밀번호를 설정합니다. (순수 TUI)
#
add_samba_user_interactively() {
    local username="$1"
    local password="$2"
    local password_confirm="$3"
    
    local final_password=""

    if [[ -z "${username}" ]]; then
        log_error "Username cannot be empty."; return 1
    fi
    if ! is_user_exist "${username}"; then
        log_error "System account '${username}' does not exist. Please create it first."
        return 1
    fi

    # 비대화형 모드
    if [[ -n "${password}" && -n "${password_confirm}" ]]; then
        if [[ "${password}" != "${password_confirm}" ]]; then
            log_warn "Provided passwords do not match. Switching to interactive mode."
        else
            final_password="${password}"
        fi
    fi

    # 대화형 모드
    if [[ -z "${final_password}" ]]; then
        log_info "Starting interactive password setup for Samba user '${username}'."
        while true; do
            read -r -s -p "Enter new Samba password: " interactive_pass; echo
            read -r -s -p "Re-enter Samba password: " interactive_confirm; echo
            
            if [[ -z "${interactive_pass}" ]]; then
                log_error "Password cannot be empty. Please try again."; continue
            fi
            if [[ "${interactive_pass}" != "${interactive_confirm}" ]]; then
                log_error "Passwords do not match. Please try again."; continue
            fi
            
            final_password="${interactive_pass}"
            break
        done
    fi

    # Samba 사용자 추가
    if [[ -n "${final_password}" ]]; then
        log_info "Adding Samba user '${username}'..."
        
        if printf "%s\n%s\n" "${final_password}" "${final_password}" | smbpasswd -a -s "${username}"; then
            log_success "Successfully added Samba user '${username}'."
        else
            log_error "Failed to add Samba user '${username}'."
            return 1
        fi
    else
        log_error "No valid password was provided. Aborting."
        return 1
    fi
}

##
# @description Samba 사용자를 삭제.
#
delete_samba_user() {
    local username="$1"
    if [[ -z "${username}" ]]; then
        log_error "Username is required."
        return 1
    fi
    
    if ! pdbedit -L | grep -q "^${username}:"; then
        log_info "Samba user '${username}' does not exist."
        return 0
    fi
    
    log_info "Deleting Samba user '${username}'..."
    if pdbedit -x -u "${username}"; then
        log_success "Successfully deleted Samba user '${username}'."
    else
        log_error "Failed to delete Samba user '${username}'."
        return 1
    fi
}
