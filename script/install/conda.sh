#!/bin/bash
# ==============================================================================
# 파일명: conda.sh
# 설명: Conda (Anaconda/Miniconda) 설치 로직 (User/System 모드 지원)
# ==============================================================================

# -----------------------------------------------------------------------------
# @description Conda (Anaconda/Miniconda) 설치 여부 확인
# @return 0: 설치됨, 1: 설치 안 됨
# -----------------------------------------------------------------------------
is_installed_conda() {
    # 1. PATH에 conda가 있는지 확인
    if command -v conda &> /dev/null; then
        return 0
    fi

    # 2. 알려진 기본 설치 경로 목록 정의
    local check_dirs=(
        "${HOME}/miniconda3"
        "${HOME}/anaconda3"
        "/opt/miniconda3"
        "/opt/anaconda3"
    )
    
    # 3. sudo로 실행된 경우, 원본 사용자의 홈 디렉토리 추가
    if [[ -n "${SUDO_USER}" ]]; then
        local sudo_user_home
        sudo_user_home=$(getent passwd "${SUDO_USER}" | cut -d: -f6)
        if [[ -n "${sudo_user_home}" ]]; then
            check_dirs+=("${sudo_user_home}/miniconda3")
            check_dirs+=("${sudo_user_home}/anaconda3")
        fi
    fi

    # 4. 각 경로별로 bin/conda 바이너리가 존재하는지 확인
    for dir in "${check_dirs[@]}"; do
        if [[ -f "$dir/bin/conda" ]]; then
            return 0
        fi
    done
    
    # 5. 마지막 수단: which 명령어 확인
    if which conda &> /dev/null; then
        return 0
    fi

    return 1
}

# -----------------------------------------------------------------------------
# @description 최신 Anaconda 버전을 확인합니다.
# @return stdout 최신 버전 파일명
# -----------------------------------------------------------------------------
_get_latest_anaconda_filename() {
    local archive_url="https://repo.anaconda.com/archive/"
    local latest_file=""
    
    # wget을 사용하여 아카이브 페이지를 가져오고, grep/sort로 최신 버전 파싱
    # 패턴: Anaconda3-YYYY.MM-Linux-x86_64.sh 또는 Anaconda3-YYYY.MM-build-Linux-x86_64.sh
    latest_file=$(wget -qO - "${archive_url}" | \
        grep -o 'Anaconda3-[0-9]\{4\}\.[0-9]\{2\}\(-[0-9]\+\)\?-Linux-x86_64.sh' | \
        sort -V | tail -n 1)
        
    echo "${latest_file}"
}

# -----------------------------------------------------------------------------
# @description Conda 설치 로직.
# @param  install_mode "user" 또는 "system" (기본값: user)
# @param $2 conda_type "miniconda" 또는 "anaconda" (기본값: miniconda)
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
install_conda_logic() {
    local install_mode="${1:-user}"
    local conda_type="${2:-miniconda}" # miniconda or anaconda
    local install_prefix=""
    local sudo_cmd=""
    local installer_url=""
    local installer_file=""
    local target_dir_name=""

    # --- 0. 필수 의존성 확인 ---
    ensure_packages_installed "SYSTEM_TOOLS" "Conda Dependencies" "wget" || return 1

    # --- 1. 타입별 설정 ---
    if [[ "${conda_type}" == "anaconda" ]]; then
        echo "[INFO] Detecting latest Anaconda version..."
        installer_file=$(_get_latest_anaconda_filename)
        
        # 감지 실패 시 최신 버전 하드코딩 (Fallback)
        if [[ -z "${installer_file}" ]]; then
            echo "[WARN] Failed to detect latest Anaconda version. Using fallback version."
            installer_file="Anaconda3-2025.12-1-Linux-x86_64.sh"
        else
            echo "[INFO] Latest Anaconda version detected: ${installer_file}"
        fi
        
        installer_url="https://repo.anaconda.com/archive/${installer_file}"
        target_dir_name="anaconda3"
    else
        installer_file="Miniconda3-latest-Linux-x86_64.sh"
        installer_url="https://repo.anaconda.com/miniconda/${installer_file}"
        target_dir_name="miniconda3"
    fi

    # --- 2. 설치 모드별 설정 ---
    if [[ "$install_mode" == "system" ]]; then
        install_prefix="/opt/${target_dir_name}"
        if [[ $EUID -ne 0 ]]; then
            sudo_cmd="sudo"
        fi
    else
        install_prefix="${HOME}/${target_dir_name}"
        sudo_cmd=""
    fi

    # 이미 설치되어 있는지 확인
    if [[ -d "$install_prefix" ]]; then
        echo "[WARN] ${conda_type} appears to be already installed at $install_prefix."
        return 0
    fi

    # --- 3. 다운로드 ---
    local installer_tmp_path="/tmp/${installer_file}"
    echo "--- Downloading ${conda_type} installer ---"
    if ! wget "${installer_url}" -O "${installer_tmp_path}"; then
        echo "[ERROR] Failed to download ${conda_type} installer." >&2
        return 1
    fi
    
    # --- 4. 설치 실행 (Silent Mode) ---
    echo "[INFO] Installing ${conda_type} to $install_prefix (Mode: $install_mode)..."
    if ! $sudo_cmd bash "${installer_tmp_path}" -b -p "${install_prefix}"; then
        echo "[ERROR] Installation failed." >&2
        rm -f "${installer_tmp_path}"
        return 1
    fi
    rm -f "${installer_tmp_path}"

    # --- 5. 환경 변수 초기화 ---
    echo "[INFO] Initializing conda for bash..."
    local conda_bin="${install_prefix}/bin/conda"
    
    if [[ "$install_mode" == "system" ]]; then
        # 시스템 전역 설정: /etc/profile.d/conda.sh 생성
        $sudo_cmd ln -sf "${install_prefix}/etc/profile.d/conda.sh" /etc/profile.d/conda.sh
        echo "[INFO] System-wide configuration added to /etc/profile.d/conda.sh"
    else
        # 사용자 설정: ~/.bashrc 수정
        if [[ -x "$conda_bin" ]]; then
            "$conda_bin" init bash
        fi
    fi

    # --- 6. 설치 상태 기록 ---
    local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
    set_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "conda" "${timestamp}"
    
    echo "[SUCCESS] ${conda_type} installed successfully."
    return 0
}