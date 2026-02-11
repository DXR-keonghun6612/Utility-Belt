#!/bin/bash
# ==============================================================================
# 파일명: account.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: 시스템 계정 및 그룹의 생성, 수정, 삭제 등 핵심 로직을 담당.
# ==============================================================================

# ==============================================================================
# 초기화
# ==============================================================================

# -----------------------------------------------------------------------------
# @description 패키지 설치 유틸리티에 필요한 패키지를 확인하고 설치함.
# -----------------------------------------------------------------------------
_initialize_account_utils() {
    # ensure_packages_installed 함수를 사용하여 패키지 확인 및 설치
    # 계정 관리 및 비밀번호 해시 생성에 필요한 openssl 확인
    ensure_packages_installed "PACKAGES_LIST" "Account Management Utils" "openssl" || return $?

    log_success "Account management utility initialized successfully."
    return 0
}

# 초기화 함수 호출
_initialize_account_utils

# ==============================================================================
# 보조 함수
# ==============================================================================

##
# @description 지정된 그룹이 시스템에 존재하는지 확인.
# @param $1 group_name 확인할 그룹 이름
# @return 0: 존재함, 1: 존재하지 않음
#
is_group_exist() {
    getent group "$1" >/dev/null 2>&1
}

##
# @description 지정된 사용자가 시스템에 존재하는지 확인.
# @param $1 username 확인할 사용자 이름
# @return 0: 존재함, 1: 존재하지 않음
#
is_user_exist() {
    id -u "$1" >/dev/null 2>&1
}

# ==============================================================================
# 핵심 로직 함수
# ==============================================================================

# -----------------------------------------------------------------------------
# 그룹 관리
# -----------------------------------------------------------------------------

# ------------------------------------------------------------------------------
# @description 시스템에 새로운 그룹을 추가.
# @param
#      $1 group_name 생성할 그룹 이름
# ------------------------------------------------------------------------------
add_system_group() {
    local group_name="$1"

    if [[ -z "${group_name}" ]]; then
        log_error "Group name is required."
        return 1
    fi

    if is_group_exist "${group_name}"; then
        log_info "Group '${group_name}' already exists."
        return 0
    fi

    log_info "Creating group '${group_name}'..."
    if ${G_SUDO_PREFIX} groupadd "${group_name}"; then
        log_success "Successfully created group '${group_name}'."
    else
        log_error "Failed to create group '${group_name}'."
        return 1
    fi
}

# -----------------------------------------------------------------------------
# @description 시스템에서 기존 그룹을 삭제.
# @param
#      $1 group_name 삭제할 그룹 이름
# -----------------------------------------------------------------------------
delete_system_group() {
    local group_name="$1"

    if [[ -z "${group_name}" ]]; then
        log_error "Group name to delete is required."
        return 1
    fi

    if ! is_group_exist "${group_name}"; then
        log_info "Group '${group_name}' does not exist."
        return 0
    fi

    log_info "Deleting system group '${group_name}'..."
    if ${G_SUDO_PREFIX} groupdel "${group_name}"; then
        log_success "Group '${group_name}' successfully deleted."
    else
        log_error "Failed to delete group '${group_name}'."
        return 1
    fi
}

# -----------------------------------------------------------------------------
# @description 특정 그룹에 사용자를 추가하거나 제거.
# @param
#      $1 group_name 대상 그룹 이름
#      $2 action 수행할 동작 ("add": 추가, "remove": 제거)
#      $3 user_list 사용자 목록 (공백으로 구분된 문자열, 예: "user1 user2 user3")
# -----------------------------------------------------------------------------
manage_group_members() {
    local group_name="$1"
    local action="$2"
    local user_list_str="$3"

    # 1. 필수 인자 검증
    if [[ -z "${group_name}" ]]; then
        log_error "Group name is required."; return 1
    fi
    if ! is_group_exist "${group_name}"; then
        log_error "Group '${group_name}' does not exist."; return 1
    fi
    if [[ -z "${user_list_str}" ]]; then
        log_warn "No users specified to ${action}."; return 0
    fi

    # 2. 동작 검증
    if [[ "${action}" != "add" && "${action}" != "remove" ]]; then
        log_error "Invalid action '${action}'. Use 'add' or 'remove'."; return 1
    fi

    # 3. 사용자 목록 파싱 및 처리
    local users
    read -ra users <<< "${user_list_str}"
    
    log_info "Processing ${action} users for group '${group_name}'..."

    local success_count=0
    local fail_count=0

    for user in "${users[@]}"; do
        if ! is_user_exist "${user}"; then
            log_warn "User '${user}' does not exist. Skipping."
            ((fail_count++))
            continue
        fi

        local cmd_output
        if [[ "${action}" == "add" ]]; then
            # 이미 그룹 멤버인지 확인
            if id -nG "${user}" | grep -qw "${group_name}"; then
                log_info "  - User '${user}' is already in group '${group_name}'."
                continue
            fi
            
            # gpasswd를 사용하여 그룹에 사용자 추가
            if cmd_output=$(${G_SUDO_PREFIX} gpasswd -a "${user}" "${group_name}" 2>&1); then
                log_success "  - Added user '${user}' to group."
                ((success_count++))
            else
                log_error "  - Failed to add '${user}': ${cmd_output}"
                ((fail_count++))
            fi

        elif [[ "${action}" == "remove" ]]; then
            # 그룹 멤버가 아닌지 확인
            if ! id -nG "${user}" | grep -qw "${group_name}"; then
                log_info "  - User '${user}' is not in group '${group_name}'."
                continue
            fi

            # gpasswd를 사용하여 그룹에서 사용자 제거
            if cmd_output=$(${G_SUDO_PREFIX} gpasswd -d "${user}" "${group_name}" 2>&1); then
                log_success "  - Removed user '${user}' from group."
                ((success_count++))
            else
                log_error "  - Failed to remove '${user}': ${cmd_output}"
                ((fail_count++))
            fi
        fi
    done

    log_info "Completed. Success: ${success_count}, Failed/Skipped: ${fail_count}."
    return 0
}

# -----------------------------------------------------------------------------
# 사용자 관리
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# @description 새로운 시스템 사용자를 추가. (UID 1000 이상)
# @param
#       $1 username 생성할 사용자 이름
#       $2 primary_group (선택 사항) 사용자의 주 그룹 이름
#       $3 create_home (yes/no) 홈 디렉터리 생성 여부
#       $4 shell_access (yes/no) 원격 로그인 허용 여부
#       $5 home_base (선택 사항) 홈 디렉터리 생성 지점 (기본값: /home)
# -----------------------------------------------------------------------------
add_system_user() {
    local username="$1"
    local primary_group="$2"
    local create_home="$3"
    local shell_access="$4"
    local home_base="${5:-/home}"

    if [[ -z "${username}" ]]; then
        log_error "Username is required."; return 1
    fi
    if is_user_exist "${username}"; then
        log_info "User '${username}' already exists."; return 0
    fi

    local useradd_opts=()
    
    # 원격 로그인 허용 여부에 따라 셸을 동적으로 설정.
    if [[ "${shell_access}" == "yes" ]]; then
        useradd_opts+=("-s" "/bin/bash")
        log_info "  - Login shell: /bin/bash (remote login allowed)"
    else
        useradd_opts+=("-s" "/usr/sbin/nologin")
        log_info "  - Login shell: /usr/sbin/nologin (remote login disabled)"
    fi

    # 홈 디렉터리 생성 여부 설정
    if [[ "${create_home}" == "yes" ]]; then
        useradd_opts+=("-m" "-d" "${home_base}/${username}")
        log_info "  - Home directory: ${home_base}/${username} (will be created)"
    else
        useradd_opts+=("-M")
        log_info "  - Home directory: (will NOT be created)"
    fi

    # 주 그룹 지정. 그룹이 존재하지 않으면 경고 메시지 출력.
    if [[ -n "${primary_group}" ]]; then
        if is_group_exist "${primary_group}"; then
            useradd_opts+=("-g" "${primary_group}")
        else
            log_warn "Group '${primary_group}' does not exist. User will be created with the default group."
        fi
    fi

    log_info "Creating user '${username}'..."
    if ${G_SUDO_PREFIX} useradd "${useradd_opts[@]}" "${username}"; then
        log_success "Successfully created user '${username}'."
        
        # /home 이외의 장소에 생성된 경우 /home으로 심볼릭 링크 생성 (create_home이 yes인 경우)
        if [[ "${create_home}" == "yes" && "${home_base}" != "/home" ]]; then
            log_info "Creating symbolic link: /home/${username} -> ${home_base}/${username}"
            ${G_SUDO_PREFIX} ln -sf "${home_base}/${username}" "/home/${username}"
        fi
    else
        log_error "Failed to create user '${username}'."
        return 1
    fi
}

# -----------------------------------------------------------------------------
# @description 시스템 사용자의 비밀번호를 설정. (대화형 및 비대화형 모드 지원)
# -----------------------------------------------------------------------------

set_password_interactively() {
    local username="$1"
    local new_password="$2"
    local confirm_password="$3"
    
    local final_password=""

    # 비대화형 모드: 두 번째와 세 번째 인자가 모두 제공된 경우
    if [[ -n "${new_password}" && -n "${confirm_password}" ]]; then
        if [[ "${new_password}" == "${confirm_password}" ]]; then
            final_password="${new_password}"
            log_info "Non-interactive mode: Passwords match. Proceeding to set password."
        else
            log_warn "Non-interactive mode: Provided passwords do not match. Switching to interactive mode."
        fi
    fi

    # 대화형 모드: final_password가 아직 설정되지 않은 경우
    if [[ -z "${final_password}" ]]; then
        # 입력 루프 시작
        while true; do
            # echo와 'read -rs'를 사용하여 비밀번호를 숨겨서 입력받습니다.
            echo -n "Enter new password for '${username}': "
            if ! read -rs interactive_pass; then
                echo
                log_info "Password entry cancelled."
                return 1
            fi
            echo # 입력 후 줄바꿈

            echo -n "Re-enter password: "
            if ! read -rs interactive_confirm; then
                echo # 줄바꿈
                log_info "Password entry cancelled."
                return 1
            fi
            echo # 입력 후 줄바꿈

            if [[ -z "${interactive_pass}" ]]; then
                log_error "Password cannot be empty. Please try again."
                continue
            fi
            if [[ "${interactive_pass}" != "${interactive_confirm}" ]]; then
                log_error "Passwords do not match. Please try again."
                continue
            fi
            
            final_password="${interactive_pass}"
            break # 루프 종료
        done
    fi

    # 최종 비밀번호가 설정되었는지 확인
    if [[ -n "${final_password}" ]]; then
        log_info "Setting system password for '${username}'..."

        local password_hash
        if ! password_hash=$(openssl passwd -1 "${final_password}") || [[ -z "${password_hash}" ]]; then
            log_error "Failed to generate password hash with openssl."
            return 1
        fi

        if ${G_SUDO_PREFIX} usermod -p "${password_hash}" "${username}"; then
            log_success "Password has been set securely."
            return 0
        else
            log_error "Failed to set password using usermod."
            return 1
        fi
    else
        log_info "Password setting was cancelled."
        return 1
    fi
}

##
# @description 시스템 사용자를 삭제하고 관련 데이터(홈 디렉터리, 심볼릭 링크)를 정리.
# @param
#       $1 username 삭제할 사용자 이름
#       $2 home_base (선택 사항) 홈 디렉터리 생성 지점 (기본값: /home)
#
delete_system_user() {
    local username="$1"
    local home_base="${2:-/home}"

    if [[ -z "${username}" ]]; then
        log_error "Username to delete is required."
        return 1
    fi

    if ! is_user_exist "${username}"; then
        log_info "User '${username}' does not exist."
        return 0
    fi
    
    # --- 1. 시스템 계정 삭제 ---
    log_info "Deleting system account for '${username}'..."
    if ! ${G_SUDO_PREFIX} userdel "${username}"; then
        log_error "Failed to delete system user '${username}'. Aborting."
        return 1
    fi

    # --- 2. 홈 디렉터리 및 심볼릭 링크 삭제 ---
    if [[ "${home_base}" != "no_home" ]]; then
        # 실제 홈 디렉터리 삭제
        local real_home="${home_base}/${username}"
        if [[ -d "${real_home}" ]]; then
            log_info "Deleting real home directory (${real_home})..."
            ${G_SUDO_PREFIX} rm -rf "${real_home}"
        fi

        # /home 아래의 심볼릭 링크 삭제 (home_base가 /home이 아닌 경우에만 의미가 있으나 안전하게 항상 확인)
        local symlink_path="/home/${username}"
        if [[ -L "${symlink_path}" ]]; then
            log_info "Deleting symbolic link (${symlink_path})..."
            ${G_SUDO_PREFIX} rm -f "${symlink_path}"
        fi
    fi

    log_success "User '${username}' and related data have been processed."
    return 0
}

##
# @description 기존 시스템 사용자의 정보를 수정.
#
modify_system_user() {
    local username="$1"
    local options_str="$2"
    
    # --- 1. 입력값 유효성 검증 ---
    if [[ -z "${username}" ]]; then
        log_error "Username to modify is required."; return 1
    fi
    if ! is_user_exist "${username}"; then
        log_error "User '${username}' does not exist."; return 1
    fi
    if [[ -z "${options_str}" ]]; then
        log_info "No modification options provided."
        return 0
    fi

    # --- 2. usermod 명령어 옵션을 동적으로 생성 ---
    local usermod_opts=()
    local changes_made=false
    
    # 옵션 문자열을 세미콜론(;) 기준으로 분리하여 처리.
    IFS=';' read -ra options <<< "${options_str}"
    for option in "${options[@]}"; do
        # 등호(=)를 기준으로 키와 값을 분리.
        local key; key=$(echo "$option" | cut -d'=' -f1 | xargs)
        local value; value=$(echo "$option" | cut -d'=' -f2- | xargs)

        case "$key" in
            "group")
                if is_group_exist "${value}"; then
                    usermod_opts+=("-g" "${value}") # 새 주 그룹 설정 (-g)
                    log_info "  - Setting new primary group to '${value}'."
                    changes_made=true
                else
                    log_warn "New group '${value}' does not exist. Skipping group change."
                fi
                ;;
            "home")
                usermod_opts+=("-d" "${value}") # 새 홈 디렉터리 설정 (-d)
                log_info "  - Setting new home directory to '${value}'."
                changes_made=true
                ;;
            "move_home")
                if [[ "${value}" == "yes" ]]; then
                    usermod_opts+=("-m") # 기존 홈 디렉터리 내용 이동 (-m)
                    log_info "  - Contents of the old home directory will be moved."
                fi
                ;;
            "shell")
                usermod_opts+=("-s" "${value}") # 새 로그인 셸 설정 (-s)
                log_info "  - Setting new login shell to '${value}'."
                changes_made=true
                ;;
            *)
                log_warn "Unknown option '${key}'. Ignoring."
                ;;
        esac
    done

    # --- 3. 생성된 옵션으로 명령어 실행 ---
    if ! $changes_made; then
        log_info "No valid changes were requested for user '${username}'."
        return 0
    fi

    log_info "Modifying user '${username}'..."
    if ${G_SUDO_PREFIX} usermod "${usermod_opts[@]}" "${username}"; then
        log_success "Successfully modified user '${username}'."
    else
        log_error "Failed to modify user '${username}'."
        return 1
    fi
}

# --- 2.3. 정보 조회 ---

##
# @description 시스템에 등록된 일반 사용자 목록을 반환. (UID 1000 이상)
#
list_system_users() {
    awk -F: '$3 >= 1000 && $1 != "nobody" { print $1 }' /etc/passwd | tr '\n' ' '
}

##
# @description 특정 사용자의 상세 정보를 반환.
#
get_user_details() {
    local username="$1"
    if ! is_user_exist "${username}"; then return; fi
    
    local details; details=$(getent passwd "${username}")
    
    local primary_gid; primary_gid=$(echo "$details" | cut -d: -f4)
    local primary_group; primary_group=$(getent group "${primary_gid}" | cut -d: -f1)
    local home_dir; home_dir=$(echo "$details" | cut -d: -f6)
    local shell; shell=$(echo "$details" | cut -d: -f7)
    
    echo "${primary_group};${home_dir};${shell}"
}
