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
#           - 'sudo' 명령어가 없고 root 권한도 없는 경우, 설치를 시도하지 않음.
#           - 'sudo' 명령어가 있거나 root 권한이 있는 경우, 설치를 시도.
#           - 설치가 실패하면 오류 메시지를 출력하고 종료.
# @return
#          0: 성공
#          1: 패키지 정보 업데이트 실패
#          2: 패키지 설치 실패
#          3: 설치 함수 호출 인자 오류
#          4: 설정 파일 오류
#          5: 권한 부족 해당 패키지 사용 불가
# -----------------------------------------------------------------------------
_initialize_account_utils() {
    # ensure_packages_installed 함수를 사용하여 패키지 확인 및 설치
    # 계정 관리 및 비밀번호 해시 생성에 필요한 openssl 확인
    ensure_packages_installed "PACKAGES_LIST" "Account Management Utils" "openssl" || return $?

    echo "[INFO] Account management utility initialized successfully." >&2
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
        echo "[ERROR] Group name is required." >&2
        return 1
    fi

    if is_group_exist "${group_name}"; then
        echo "[INFO] Group '${group_name}' already exists."
        return 0
    fi

    echo "[INFO] Creating group '${group_name}'..."
    if ${G_SUDO_PREFIX} groupadd "${group_name}"; then
        echo "[SUCCESS] Successfully created group '${group_name}'."
    else
        echo "[ERROR] Failed to create group '${group_name}'." >&2
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
        echo "[ERROR] Group name to delete is required." >&2
        return 1
    fi

    if ! is_group_exist "${group_name}"; then
        echo "[INFO] Group '${group_name}' does not exist."
        return 0
    fi

    echo "[INFO] Deleting system group '${group_name}'..."
    if ${G_SUDO_PREFIX} groupdel "${group_name}"; then
        echo "[SUCCESS] Group '${group_name}' successfully deleted."
    else
        echo "[ERROR] Failed to delete group '${group_name}'." >&2
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
        echo "[ERROR] Group name is required." >&2; return 1
    fi
    if ! is_group_exist "${group_name}"; then
        echo "[ERROR] Group '${group_name}' does not exist." >&2; return 1
    fi
    if [[ -z "${user_list_str}" ]]; then
        echo "[WARN] No users specified to ${action}." >&2; return 0
    fi

    # 2. 동작 검증
    if [[ "${action}" != "add" && "${action}" != "remove" ]]; then
        echo "[ERROR] Invalid action '${action}'. Use 'add' or 'remove'." >&2; return 1
    fi

    # 3. 사용자 목록 파싱 및 처리
    local users
    read -ra users <<< "${user_list_str}"
    
    echo "[INFO] Processing ${action} users for group '${group_name}'..."

    local success_count=0
    local fail_count=0

    for user in "${users[@]}"; do
        if ! is_user_exist "${user}"; then
            echo "[WARN] User '${user}' does not exist. Skipping."
            ((fail_count++))
            continue
        fi

        local cmd_output
        if [[ "${action}" == "add" ]]; then
            # 이미 그룹 멤버인지 확인
            if id -nG "${user}" | grep -qw "${group_name}"; then
                echo "  - [SKIP] User '${user}' is already in group '${group_name}'."
                continue
            fi
            
            # gpasswd를 사용하여 그룹에 사용자 추가
            if cmd_output=$(${G_SUDO_PREFIX} gpasswd -a "${user}" "${group_name}" 2>&1); then
                echo "  - [SUCCESS] Added user '${user}' to group."
                ((success_count++))
            else
                echo "  - [ERROR] Failed to add '${user}': ${cmd_output}"
                ((fail_count++))
            fi

        elif [[ "${action}" == "remove" ]]; then
            # 그룹 멤버가 아닌지 확인
            if ! id -nG "${user}" | grep -qw "${group_name}"; then
                echo "  - [SKIP] User '${user}' is not in group '${group_name}'."
                continue
            fi

            # gpasswd를 사용하여 그룹에서 사용자 제거
            if cmd_output=$(${G_SUDO_PREFIX} gpasswd -d "${user}" "${group_name}" 2>&1); then
                echo "  - [SUCCESS] Removed user '${user}' from group."
                ((success_count++))
            else
                echo "  - [ERROR] Failed to remove '${user}': ${cmd_output}"
                ((fail_count++))
            fi
        fi
    done

    echo "[INFO] Completed. Success: ${success_count}, Failed/Skipped: ${fail_count}."
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
# -----------------------------------------------------------------------------
add_system_user() {
    local username="$1"
    local primary_group="$2"
    local create_home="$3"
    local shell_access="$4"

    if [[ -z "${username}" ]]; then
        echo "[ERROR] Username is required." >&2; return 1
    fi
    if is_user_exist "${username}"; then
        echo "[INFO] User '${username}' already exists."; return 0
    fi

    local useradd_opts=()
    
    # 원격 로그인 허용 여부에 따라 셸을 동적으로 설정.
    if [[ "${shell_access}" == "yes" ]]; then
        useradd_opts+=("-s" "/bin/bash")
        echo "  - Login shell: /bin/bash (remote login allowed)"
    else
        useradd_opts+=("-s" "/usr/sbin/nologin")
        echo "  - Login shell: /usr/sbin/nologin (remote login disabled)"
    fi

    # 홈 디렉터리 생성 여부 설정 (-m: 생성, -M: 생성 안 함).
    [[ "${create_home}" == "yes" ]] && useradd_opts+=("-m") || useradd_opts+=("-M")

    # 주 그룹 지정. 그룹이 존재하지 않으면 경고 메시지 출력.
    if [[ -n "${primary_group}" ]]; then
        if is_group_exist "${primary_group}"; then
            useradd_opts+=("-g" "${primary_group}")
        else
            echo "[WARN] Group '${primary_group}' does not exist. User will be created with the default group."
        fi
    fi

    echo "[INFO] Creating user '${username}'..."
    if ${G_SUDO_PREFIX} useradd "${useradd_opts[@]}" "${username}"; then
        echo "[SUCCESS] Successfully created user '${username}'."
    else
        echo "[ERROR] Failed to create user '${username}'." >&2
        return 1
    fi
}

# -----------------------------------------------------------------------------
# @description 시스템 사용자의 비밀번호를 설정. (대화형 및 비대화형 모드 지원)
# @param
#       $1 username 비밀번호를 설정할 사용자 이름
#       $2 new_password (선택 사항) 새 비밀번호 (비대화형 모드용)
#       $3 confirm_password (선택 사항) 새 비밀번호 확인 (비대화형 모드용)
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
            echo "[INFO] Non-interactive mode: Passwords match. Proceeding to set password."
        else
            echo "[WARN] Non-interactive mode: Provided passwords do not match. Switching to interactive mode."
        fi
    fi

    # 대화형 모드: final_password가 아직 설정되지 않은 경우
    if [[ -z "${final_password}" ]]; then
        # 입력 루프 시작
        while true; do
            # echo와 'read -s'를 사용하여 비밀번호를 숨겨서 입력받습니다.
            echo -n "Enter new password for '${username}': "
            read -s interactive_pass
            # 사용자가 입력을 취소(Ctrl+D)했는지 확인합니다.
            if [[ $? -ne 0 ]]; then
                echo
                echo "[INFO] Password entry cancelled."
                return 1
            fi
            echo # 입력 후 줄바꿈

            echo -n "Re-enter password: "
            read -s interactive_confirm
            if [[ $? -ne 0 ]]; then
                echo # 줄바꿈
                echo "Password entry cancelled."
                return 1
            fi
            echo # 입력 후 줄바꿈

            if [[ -z "${interactive_pass}" ]]; then
                echo "[ERROR] Password cannot be empty. Please try again." >&2
                continue
            fi
            if [[ "${interactive_pass}" != "${interactive_confirm}" ]]; then
                echo "[ERROR] Passwords do not match. Please try again." >&2
                continue
            fi
            
            final_password="${interactive_pass}"
            break # 루프 종료
        done
    fi

    # 최종 비밀번호가 설정되었는지 확인
    if [[ -n "${final_password}" ]]; then
        echo "[INFO] Setting system password for '${username}'..."

        local password_hash
        password_hash=$(openssl passwd -1 "${final_password}")
        if [[ $? -ne 0 || -z "${password_hash}" ]]; then
            echo "[ERROR] Failed to generate password hash with openssl." >&2
            return 1
        fi

        if ${G_SUDO_PREFIX} usermod -p "${password_hash}" "${username}"; then
            echo "[SUCCESS] Password has been set securely."
            return 0
        else
            echo "[ERROR] Failed to set password using usermod." >&2
            return 1
        fi
    else
        echo "[INFO] Password setting was cancelled."
        return 1
    fi
}

##
# @description 시스템 사용자를 삭제하고 관련 데이터(홈 디렉터리, 심볼릭 링크)를 정리.
# @param $1 username 삭제할 사용자 이름
# @param $2 user_home_base 사용자의 실제 홈 디렉터리가 위치한 기본 경로.
#                         "no_home"으로 지정 시 홈 디렉터리 삭제를 건너뜀.
#
delete_system_user() {
    local username="$1"
    local user_home_base="$2"

    if [[ -z "${username}" ]]; then
        echo "[ERROR] Username to delete is required." >&2
        return 1
    fi

    if ! is_user_exist "${username}"; then
        echo "[INFO] User '${username}' does not exist."
        return 0
    fi
    
    # --- 1. 시스템 계정 삭제 ---
    echo "[INFO] Deleting system account for '${username}'..."
    if ! ${G_SUDO_PREFIX} userdel "${username}"; then
        echo "[ERROR] Failed to delete system user '${username}'. Aborting." >&2
        return 1
    fi

    # --- 2. 실제 홈 디렉터리 삭제 (선택 사항) ---
    if [[ -n "${user_home_base}" && "${user_home_base}" != "no_home" ]]; then
        local user_home_dir="${user_home_base}/${username}"
        if [[ -d "${user_home_dir}" ]]; then
            echo "[INFO] Deleting real home directory (${user_home_dir})..."
            ${G_SUDO_PREFIX} rm -rf "${user_home_dir}"
        fi
    fi

    # --- 3. /home 아래의 심볼릭 링크 삭제 ---
    local symlink_path="/home/${username}"
    if [[ -L "${symlink_path}" ]]; then
        echo "[INFO] Deleting symbolic link (${symlink_path})..."
        ${G_SUDO_PREFIX} rm -f "${symlink_path}"
    fi

    echo "[SUCCESS] User '${username}' and related data have been processed."
    return 0
}

##
# @description 기존 시스템 사용자의 정보를 수정.
# @param $1 username 수정할 사용자 이름 (필수)
# @param $2 options 수정 옵션을 담은 문자열 (예: "group=newgroup;home=/new/home;move_home=yes")
#
modify_system_user() {
    local username="$1"
    local options_str="$2"
    
    # --- 1. 입력값 유효성 검증 ---
    if [[ -z "${username}" ]]; then
        echo "[ERROR] Username to modify is required." >&2; return 1
    fi
    if ! is_user_exist "${username}"; then
        echo "[ERROR] User '${username}' does not exist." >&2; return 1
    fi
    if [[ -z "${options_str}" ]]; then
        echo "[INFO] No modification options provided."
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
                    echo "  - Setting new primary group to '${value}'."
                    changes_made=true
                else
                    echo "[WARN] New group '${value}' does not exist. Skipping group change."
                fi
                ;;
            "home")
                usermod_opts+=("-d" "${value}") # 새 홈 디렉터리 설정 (-d)
                echo "  - Setting new home directory to '${value}'."
                changes_made=true
                ;;
            "move_home")
                if [[ "${value}" == "yes" ]]; then
                    usermod_opts+=("-m") # 기존 홈 디렉터리 내용 이동 (-m)
                    echo "  - Contents of the old home directory will be moved."
                fi
                ;;
            "shell")
                usermod_opts+=("-s" "${value}") # 새 로그인 셸 설정 (-s)
                echo "  - Setting new login shell to '${value}'."
                changes_made=true
                ;;
            *)
                echo "[WARN] Unknown option '${key}'. Ignoring."
                ;;
        esac
    done

    # --- 3. 생성된 옵션으로 명령어 실행 ---
    if ! $changes_made; then
        echo "[INFO] No valid changes were requested for user '${username}'."
        return 0
    fi

    echo "[INFO] Modifying user '${username}'..."
    if ${G_SUDO_PREFIX} usermod "${usermod_opts[@]}" "${username}"; then
        echo "[SUCCESS] Successfully modified user '${username}'."
    else
        echo "[ERROR] Failed to modify user '${username}'." >&2
        return 1
    fi
}

# --- 2.3. 정보 조회 ---

##
# @description 시스템에 등록된 일반 사용자 목록을 반환. (UID 1000 이상)
# @return stdout "user1 user2 ..." 형태의 공백으로 구분된 문자열
#
list_system_users() {
    # /etc/passwd 파일을 콜론(:)으로 구분하여 UID($3)가 1000 이상인 사용자($1)만 필터링.
    awk -F: '$3 >= 1000 && $1 != "nobody" { print $1 }' /etc/passwd | tr '\n' ' '
}

##
# @description 특정 사용자의 상세 정보를 반환.
# @param $1 username 정보를 조회할 사용자 이름
# @return stdout "주그룹;홈디렉터리;로그인셸" 형태의 세미콜론으로 구분된 문자열
#
get_user_details() {
    local username="$1"
    if ! is_user_exist "${username}"; then return; fi
    
    # getent passwd: /etc/passwd와 다른 소스(LDAP 등)까지 포함하여 사용자 정보를 가져옴.
    local details; details=$(getent passwd "${username}")
    
    local primary_gid; primary_gid=$(echo "$details" | cut -d: -f4)
    local primary_group; primary_group=$(getent group "${primary_gid}" | cut -d: -f1)
    local home_dir; home_dir=$(echo "$details" | cut -d: -f6)
    local shell; shell=$(echo "$details" | cut -d: -f7)
    
    echo "${primary_group};${home_dir};${shell}"
}
