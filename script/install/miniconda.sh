#!/bin/bash
# ==============================================================================
# 파일명: miniconda.sh
# 설명: Miniconda 설치 로직 (User/System 모드 지원)
# ==============================================================================

# -----------------------------------------------------------------------------
# @description Miniconda 설치 로직.
# @param $1 install_mode "user" 또는 "system" (기본값: user)
# @return 0: 성공, 1: 실패
# -----------------------------------------------------------------------------
install_miniconda_logic() {
    local install_mode="${1:-user}"
    local install_prefix=""
    local sudo_cmd=""

    if [[ "$install_mode" == "system" ]]; then
        install_prefix="/opt/miniconda3"
        # 현재 사용자가 root가 아니면 sudo 사용
        if [[ $EUID -ne 0 ]]; then
            sudo_cmd="sudo"
        fi
    else
        install_prefix="${HOME}/miniconda3"
        sudo_cmd=""
    fi

    # 이미 설치되어 있는지 확인
    if [[ -d "$install_prefix" ]]; then
        echo "[WARN] Miniconda appears to be already installed at $install_prefix."
        return 0
    fi

    # --- 1. 변수 설정 및 다운로드 ---
    local CONDA_INSTALLER="Miniconda3-latest-Linux-x86_64.sh"
    local installer_tmp_path="/tmp/${CONDA_INSTALLER}"
    
    echo "--- Downloading Miniconda installer ---"
    if ! wget https://repo.anaconda.com/miniconda/${CONDA_INSTALLER} -O "${installer_tmp_path}"; then
        echo "[ERROR] Failed to download Miniconda installer." >&2
        return 1
    fi
    
    # --- 2. 설치 실행 (Silent Mode) ---
    # -b: Batch mode (no manual intervention), -p: Installation prefix/path, -f: Force
    echo "[INFO] Installing Miniconda to $install_prefix (Mode: $install_mode)..."
    
    # 설치 명령 실행
    if ! $sudo_cmd bash "${installer_tmp_path}" -b -p "${install_prefix}"; then
        echo "[ERROR] Installation failed." >&2
        rm -f "${installer_tmp_path}"
        return 1
    fi
    
    rm -f "${installer_tmp_path}"

    # --- 3. 환경 변수 초기화 ---
    echo "[INFO] Initializing conda for bash..."
    # conda init 실행
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

    # --- 4. 설치 상태 기록 ---
    local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
    # 설정 파일 기록은 스크립트를 실행한 사용자의 권한으로 처리 (sudo 불필요)
    set_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "miniconda" "${timestamp}"
    
    echo "[SUCCESS] Miniconda installed successfully."
    return 0
}
