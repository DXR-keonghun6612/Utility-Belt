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
_initialize_samba_utils() {
    # ensure_packages_installed 함수를 사용하여 패키지 확인 및 설치
    ensure_packages_installed "PACKAGES_LIST" "Network Management Utils" "samba" || return $?
    
    echo "[INFO] Samba management utility initialized successfully." >&2

    # --- 3. 최초 설치 시 후속 작업 수행 ---
    # 위에서 확인한 '최초 설치' 플래그가 true일 경우에만 기본 공유 정리 실행
    if [[ "${is_first_install}" == "true" ]]; then
        echo "--- Performing initial cleanup of default Samba shares... ---"
        # delete_samba_share 함수는 별도로 구현되어 있어야 함
        if command -v delete_samba_share &> /dev/null; then
            delete_samba_share "printers" "silent"
            delete_samba_share "print$" "silent"
            echo "--- Cleanup complete ---"
        else
            echo "[Warning] 'delete_samba_share' function not found. Skipping cleanup." >&2
        fi
    fi
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
    echo "Checking Samba configuration syntax..."
    # testparm -s: 오류가 없으면 아무것도 출력하지 않고 성공(0)을 반환.
    if testparm -s; then
        echo "Configuration syntax is OK."
        return 0
    else
        echo "[ERROR] Samba configuration check failed. Please review the errors above." >&2
        return 1
    fi
}

##
# @description Samba (smbd) 서비스의 현재 상태를 가져옴.
#
get_samba_status() {
    echo "Getting Samba service status..."
    systemctl status smbd
}

##
# @description Samba 설정을 확인한 후 안전하게 서비스를 재시작.
#
restart_samba() {
    # 재시작 전, 설정 파일의 유효성을 먼저 검사.
    if ! check_samba_config; then
        return 1
    fi
    
    echo "[INFO] Restarting Samba service..."
    # systemd가 의존성을 관리하므로 smb 서비스만 재시작.
    if systemctl restart smbd; then
        echo "[SUCCESS] Samba service restarted successfully."
    else
        echo "[ERROR] Failed to restart Samba service." >&2
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

    # awk를 사용하여 파일을 한 번만 읽어 [global]을 제외한 모든 섹션의 이름과 주석 여부(on/off)를 추출.
    awk '
        /^\s*#*\s*\[.*\]/ && !/\[(global)\]/ {
            name = $0;
            gsub(/^.*\[|].*$/, "", name);
            status = ($0 ~ /^\s*#/) ? "off" : "on";
            printf "%s %s ", name, status;
        }
    ' "${smb_conf}" | xargs # xargs로 마지막 불필요한 공백을 제거.
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
        echo "[ERROR] Share name and state ('enable' or 'disable') are required." >&2
        return 1
    fi

    echo "[INFO] Setting share '[${share_name}]' to '${state}'..."
    
    # 1. 원본 파일을 백업.
    cp "${smb_conf}" "${smb_conf}.bak_$(date +%F-%T)"

    # 2. conf.sh의 범용 섹션 토글 함수를 호출.
    if toggle_config_section "${smb_conf}" "${share_name}" "${state}"; then
        echo "[SUCCESS] Successfully changed state for '[${share_name}]'."
    else
        echo "[ERROR] Failed to change state for '[${share_name}]'." >&2
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
        echo "[INFO] Share '[${share_name}]' does not exist."
        return 0
    fi
    
    echo "[INFO] Removing share profile '[${share_name}]'..."
    
    # 2. 만약을 대비해 원본 파일을 백업.
    cp "${smb_conf}" "${smb_conf}.bak_$(date +%F-%T)"
    
    # 3. conf.sh의 범용 섹션 삭제 함수를 호출.
    if delete_config_section "${smb_conf}" "${share_name}"; then
        echo "[SUCCESS] Successfully removed share profile '[${share_name}]'."
    else
        echo "[ERROR] Failed to remove share profile '[${share_name}]'." >&2
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
        echo "[ERROR] Share name and options are required." >&2
        return 1
    fi
    # 'path='는 Samba 공유의 필수 옵션이므로 반드시 포함되어 있는지 확인.
    if ! echo "${options_str}" | grep -q "path="; then
        echo "[ERROR] The 'path=' setting is required in the options string." >&2
        return 1
    fi

    # 2. conf.sh의 섹션 추가 함수를 호출 (섹션이 없을 경우에만 추가).
    add_config_section "${smb_conf}" "${share_name}"
    
    # 3. 옵션 문자열을 conf.sh 함수가 사용할 배열 형식으로 변환.
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
    
    # 4. conf.sh의 키-값 설정 함수를 호출하여 모든 옵션을 한 번에 기록.
    echo "[INFO] Setting options for share '[${share_name}]'..."
    if ! set_config_value "${smb_conf}" "${share_name}" "${key_value_pairs[@]}"; then
        echo "[ERROR] Failed to set configuration for share '[${share_name}]'." >&2
        return 1
    fi

    # 5. 디렉토리 생성 및 소유권 설정
    if [[ -n "${share_path}" ]]; then
        # 디렉토리가 없으면 생성
        if [[ ! -d "${share_path}" ]]; then
            echo "[INFO] Creating shared directory: ${share_path}"
            mkdir -p "${share_path}"
            # 기본 권한 설정 (공유 폴더 용도에 맞게 775 또는 777 등 필요에 따라 조정 가능하나, 여기서는 기본 umask 따름)
            # 필요 시: chmod 775 "${share_path}" 
        fi

        # 소유권 변경 대상 문자열 구성 (예: user:group 또는 user 또는 :group)
        local chown_target=""
        if [[ -n "${force_user}" ]]; then
            chown_target="${force_user}"
        fi
        if [[ -n "${force_group}" ]]; then
            chown_target="${chown_target}:${force_group}"
        fi

        # 옵션에 사용자/그룹 설정이 없고 sudo로 실행된 경우, 원래 사용자를 소유자로 설정
        if [[ -z "${chown_target}" && "${G_IS_SUDO}" == "true" ]]; then
            chown_target="${G_ACTUAL_USER}:${G_ACTUAL_GROUP}"
            echo "[INFO] No 'force user/group' specified. Defaulting ownership to '${chown_target}'."
        fi

        # 소유권 변경 실행
        if [[ -n "${chown_target}" ]]; then
            echo "[INFO] Applying ownership '${chown_target}' to '${share_path}'..."
            if chown "${chown_target}" "${share_path}"; then
                echo "[SUCCESS] Ownership updated."
            else
                echo "[WARN] Failed to change ownership of '${share_path}' to '${chown_target}'." >&2
            fi
        fi
    fi

    echo "[SUCCESS] Successfully configured share '[${share_name}]'."
}

# ==============================================================================
# 사용자 관리
# ==============================================================================

##
# @description 등록된 모든 Samba 사용자 목록을 보여줌.
#
list_samba_users() {
    echo "[INFO] Listing all Samba users..."
    # pdbedit -L: Samba 사용자 데이터베이스 목록을 출력.
    # awk -F: '{print " - " $1}': 콜론으로 구분된 출력에서 첫 번째 필드(사용자 이름)만 추출.
    pdbedit -L | awk -F: '{print " - " $1}'
}

##
# @description 대화형/비대화형으로 Samba 사용자를 추가하고 비밀번호를 설정합니다. (순수 TUI)
# @param $1 username 추가할 사용자 이름
# @param $2 password (선택 사항) 설정할 Samba 비밀번호
# @param $3 password_confirm (선택 사항) 확인용 비밀번호
# @return 0 on success, 1 on failure
#
add_samba_user_interactively() {
    # 인자를 지역 변수에 저장.
    local username="$1"
    local password="$2"
    local password_confirm="$3"
    
    # 최종 비밀번호를 저장할 변수 초기화.
    local final_password=""

    # 필수 조건 확인
    # 사용자 이름 유효성 검증.
    if [[ -z "${username}" ]]; then
        echo "[ERROR] Username cannot be empty." >&2; return 1
    fi
    # 시스템에 해당 계정이 존재하는지 확인.
    if ! is_user_exist "${username}"; then
        echo "[ERROR] System account '${username}' does not exist. Please create it first." >&2
        return 1
    fi

    # 비대화형 모드
    # 인자로 비밀번호가 모두 제공되었는지 확인.
    if [[ -n "${password}" && -n "${password_confirm}" ]]; then
        # 제공된 두 비밀번호의 일치 여부 확인.
        if [[ "${password}" != "${password_confirm}" ]]; then
            echo "[WARN] Provided passwords do not match. Switching to interactive mode." >&2
        else
            # 일치하면 최종 비밀번호로 확정.
            final_password="${password}"
        fi
    fi

    # 대화형 모드
    # 최종 비밀번호가 아직 설정되지 않은 경우 실행.
    if [[ -z "${final_password}" ]]; then
        echo "[INFO] Starting interactive password setup for Samba user '${username}'."
        # 비밀번호가 일치할 때까지 반복.
        while true; do
            # 비밀번호를 숨겨서 입력받음.
            read -r -s -p "Enter new Samba password: " interactive_pass; echo
            read -r -s -p "Re-enter Samba password: " interactive_confirm; echo
            
            # 빈 비밀번호 입력 방지.
            if [[ -z "${interactive_pass}" ]]; then
                echo "[ERROR] Password cannot be empty. Please try again." >&2; continue
            fi
            # 두 비밀번호가 일치하는지 확인.
            if [[ "${interactive_pass}" != "${interactive_confirm}" ]]; then
                echo "[ERROR] Passwords do not match. Please try again." >&2; continue
            fi
            
            # 검증 완료 후 최종 비밀번호로 확정하고 루프 탈출.
            final_password="${interactive_pass}"
            break
        done
    fi

    # Samba 사용자 추가
    # 최종 비밀번호가 설정되었는지 확인.
    if [[ -n "${final_password}" ]]; then
        echo "[INFO] Adding Samba user '${username}'..."
        
        # smbpasswd -a -s: 표준 입력으로 비밀번호를 받아 사용자 추가 (-s: silent/stdin)
        # printf를 사용하여 비밀번호와 확인 비밀번호(동일)를 줄바꿈으로 구분하여 전달
        if printf "%s\n%s\n" "${final_password}" "${final_password}" | smbpasswd -a -s "${username}"; then
            echo "[SUCCESS] Successfully added Samba user '${username}'."
        else
            echo "[ERROR] Failed to add Samba user '${username}'." >&2; return 1
        fi
    else
        echo "[ERROR] No valid password was provided. Aborting." >&2
        return 1
    fi
}

##
# @description Samba 사용자를 삭제.
# @param $1 username 삭제할 사용자 이름
#
delete_samba_user() {
    local username="$1"
    if [[ -z "${username}" ]]; then
        echo "[ERROR] Username is required." >&2
        return 1
    fi
    
    # pdbedit 목록에 사용자가 있는지 먼저 확인.
    if ! pdbedit -L | grep -q "^${username}:"; then
        echo "[INFO] Samba user '${username}' does not exist."
        return 0
    fi
    
    echo "[INFO] Deleting Samba user '${username}'..."
    # 사용자 추가(pdbedit -a)와의 일관성을 위해 pdbedit -x 사용.
    if pdbedit -x -u "${username}"; then
        echo "[SUCCESS] Successfully deleted Samba user '${username}'."
    else
        echo "[ERROR] Failed to delete Samba user '${username}'." >&2
        return 1
    fi
}