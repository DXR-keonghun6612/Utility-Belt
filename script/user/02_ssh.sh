#!/bin/bash
# ==============================================================================
# 파일명: utils/ssh.sh
# 설명: SSH 키 생성, 등록, 클라이언트 패키지 생성과 관련된 모든 핵심 로직(백엔드) 함수를 포함.
# ==============================================================================

_initialize_ssh_utils() {
    local ssh_packages=()
    local pkg_type
    
    # 01_install_package.sh의 get_package_manager_type 사용
    if command -v get_package_manager_type &> /dev/null; then
        pkg_type=$(get_package_manager_type)
    else
        # 폴백: 직접 감지 시도 (독립 실행 대비)
        if command -v dpkg &>/dev/null; then pkg_type="dpkg"
        elif command -v rpm &>/dev/null; then pkg_type="rpm"
        elif command -v pacman &>/dev/null; then pkg_type="pacman"
        fi
    fi

    case "$pkg_type" in
        "dpkg")
            ssh_packages=("openssh-server" "openssh-client")
            ;;
        "rpm")
            # RHEL/CentOS 계열은 openssh-server와 openssh-clients로 분리됨
            ssh_packages=("openssh-server" "openssh-clients")
            ;;
        "pacman")
            # Arch Linux 계열은 openssh 하나에 모두 포함됨
            ssh_packages=("openssh")
            ;;
        *)
            log_warn "Unsupported package manager. Skipping automatic package check for SSH."
            return 0
            ;;
    esac

    # ensure_packages_installed 함수를 사용하여 패키지 확인 및 설치
    # openssl은 대부분 기본 설치되어 있으나 명시적으로 확인해도 무방함
    ensure_packages_installed "PACKAGES_LIST" "${ssh_packages[@]}" || return $?

    if [[ "${G_IS_ROOT}" == "true" ]]; then
        if [[ "${G_IS_SUDO}" == "true" ]]; then
            log_info "Running with sudo privileges (Original user: ${G_ACTUAL_USER})."
        else
            log_info "Running as root user."
        fi
    fi

    log_success "SSH utility initialized successfully."
    return 0
}

_initialize_ssh_utils

# =============
# 내부 함수
# =============
##
# @description [개선됨] 개인키를 Linux 클라이언트용으로 패키징합니다.
# @param $1 key_filename 패키징할 개인키의 전체 경로
# @param $2 output_dir 최종 .tar.gz 패키지 파일을 저장할 디렉토리
# @return 0 on success, 1 on failure
#
_package_key_for_linux() {
    local key_filename="$1"
    local output_dir="$2"

    # FINAL: key_filename으로 private_key_path를 내부에서 직접 생성
    local private_key_path="${HOME}/.ssh/${key_filename}"
    local package_path="${output_dir}/client_package_linux_${key_filename}.tar.gz"

    local work_dir; work_dir=$(mktemp -d) || { log_error "Failed to create temp dir."; return 1; }
    trap 'rm -rf "${work_dir}"' RETURN

    cp "${private_key_path}" "${work_dir}/${key_filename}"

    # ... (cat EOF ... ) 로직은 변경 없음 ...
    cat > "${work_dir}/install_key.sh" << EOF
#!/bin/bash
echo "Installing SSH private key for server access..."
mkdir -p "\$HOME/.ssh"
chmod 700 "\$HOME/.ssh"
SCRIPT_DIR=\$(cd -- "\$(dirname -- "\${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cp "\${SCRIPT_DIR}/${key_filename}" "\$HOME/.ssh/${key_filename}"
chmod 600 "\$HOME/.ssh/${key_filename}"
echo ""
echo "✅ Success! Key installed at \$HOME/.ssh/${key_filename}"
echo "You can now connect using: ssh -i \$HOME/.ssh/${key_filename} ${USER}@<SERVER_IP>"
EOF

    chmod +x "${work_dir}/install_key.sh"
    tar -czf "${package_path}" -C "${work_dir}" .
    
    log_info "Linux client package created at ${package_path}"
    return 0
}

##
# @description [개선됨] 개인키를 Windows 클라이언트용으로 패키징합니다.
# @param $1 private_key_path 패키징할 개인키의 전체 경로
# @param $2 output_dir 최종 .zip 패키지 파일을 저장할 디렉토리
# @return 0 on success, 1 on failure
#
_package_key_for_windows() {
    local key_filename="$1"
    local output_dir="$2"

    local private_key_path="${HOME}/.ssh/${key_filename}"
    local package_path="${output_dir}/client_package_windows_${key_filename}.zip"


    local work_dir; work_dir=$(mktemp -d) || { log_error "Failed to create temp dir."; return 1; }
    trap 'rm -rf "${work_dir}"' RETURN

    cp "${private_key_path}" "${work_dir}/${key_filename}"

    # ... (cat EOF ... ) 로직은 변경 없음 ...
    cat > "${work_dir}/install_key.bat" << EOF
@echo off
echo Installing SSH private key for server access...
if not exist "%USERPROFILE%\\.ssh" ( mkdir "%USERPROFILE%\\.ssh" )
copy "%~dp0${key_filename}" "%USERPROFILE%\\.ssh\\${key_filename}" > NUL
echo.
echo Success! Key installed at %USERPROFILE%\\.ssh\\${key_filename}
echo You can now connect using: ssh -i %USERPROFILE%\\.ssh\\${key_filename} ${USER}@<SERVER_IP>
pause
EOF

    (cd "${work_dir}" && zip -r "${package_path}" ./*)

    log_info "Windows client package created at ${package_path}"
    return 0
}

# =============
# 주요 함수
# =============

##
# @description 현재 사용자의 ~/.ssh 디렉토리에 SSH 키를 비대화형으로 생성하고,
#              공개키는 authorized_keys에 자동 등록 후 삭제합니다.
# @param $1 key_filename 저장할 개인키의 파일 이름 (경로 제외, 예: "id_deploy")
# @param $2 key_type 키 타입 (e.g., "ed25519", "rsa")
# @param $3 key_bits RSA 키 비트 수 (RSA 타입일 때만 유효)
# @param $4 comment 키에 포함될 코멘트 (주로 이메일)
# @return 0 on success, 1 on failure
#
backend_generate_ssh_key() {
    local key_filename="$1"
    local key_type="$2"
    local key_bits="$3"
    local comment="$4"

    # --- 1. 경로 및 파일 유효성 검사 ---
    if [[ -z "${key_filename}" ]]; then
        log_error "SSH key filename cannot be empty."
        return 1
    fi

    # 현재 사용자의 .ssh 디렉토리 경로를 설정하고, 없으면 생성합니다.
    local ssh_dir="${HOME}/.ssh"
    mkdir -p "${ssh_dir}"
    chmod 700 "${ssh_dir}"

    local private_key_path="${ssh_dir}/${key_filename}"
    local public_key_path="${private_key_path}.pub"

    if [[ -f "${private_key_path}" ]]; then
        log_error "Private key file already exists: ${private_key_path}"
        return 1
    fi

    # --- 2. SSH 키 생성 ---
    local ssh_keygen_cmd_array=("ssh-keygen" "-t" "${key_type}" "-f" "${private_key_path}" "-C" "${comment}" "-N" "''")
    if [[ "${key_type}" == "rsa" ]]; then
        ssh_keygen_cmd_array+=("-b" "${key_bits}")
    fi

    log_info "Generating SSH key at ${private_key_path}..."
    if ! "${ssh_keygen_cmd_array[@]}"; then
        log_error "Failed to generate SSH key."
        return 1
    fi

    # --- 3. 공개키를 authorized_keys에 등록 ---
    local authorized_keys_path="${ssh_dir}/authorized_keys"
    touch "${authorized_keys_path}"
    chmod 600 "${authorized_keys_path}"
    
    # 생성된 공개키 내용을 읽어와 authorized_keys 파일에 추가합니다.
    local pub_key_content; pub_key_content=$(cat "${public_key_path}")
    echo "${pub_key_content}" >> "${authorized_keys_path}"
    log_info "Public key has been added to ${authorized_keys_path}."

    # --- 4. 공개키(.pub) 파일 삭제 ---
    rm -f "${public_key_path}"
    log_info "Public key file (${public_key_path}) has been removed."

    # --- 5. 소유권 복구 (sudo 실행 시) ---
    if [[ "${G_IS_SUDO}" == "true" ]]; then
        log_info "Restoring ownership to ${G_ACTUAL_USER}..."
        chown -R "${G_ACTUAL_USER}:${G_ACTUAL_GROUP}" "${ssh_dir}"
    fi

    log_success "SSH private key is ready at ${private_key_path}"
    return 0
}

##
# @description SSH 키 생성, 서버 등록, 다중 클라이언트 OS 패키징까지 전 과정을 자동화합니다.
# @param $1 key_filename 생성할 키의 파일 이름 (예: "id_deploy_server1")
# @param $2 key_type 키 타입
# @param $3 key_bits RSA 비트 수
# @param $4 comment 키 코멘트
# @param $5 output_dir 생성된 패키지들을 저장할 디렉토리
# @param $6... target_os_list 대상 OS 목록 (배열로 전달)
# @return 0 on success, 1 on failure
#
generate_and_package_client_keys() {
    local key_filename="$1"
    local key_type="$2"
    local key_bits="$3"
    local comment="$4"
    local output_dir="$5"
    shift 5
    local target_os_list=("$@")
    
    log_info "Step 1: Generating and registering SSH key"
    if ! backend_generate_ssh_key "${key_filename}" "${key_type}" "${key_bits}" "${comment}"; then
        log_error "Failed to generate the base SSH key. Aborting."
        return 1
    fi

    mkdir -p "${output_dir}"

    log_info "Step 2: Creating client packages for specified OS list"
    for os in "${target_os_list[@]}"; do
        log_info "Processing package for ${os}..."

        case "${os}" in
            "linux")
                # FINAL: 이제 private_key_path 대신 key_filename을 전달
                if ! _package_key_for_linux "${key_filename}" "${output_dir}"; then
                    log_error "Failed to create package for ${os}."
                    return 1
                fi
                ;;
            "windows")
                # FINAL: 이제 private_key_path 대신 key_filename을 전달
                if ! _package_key_for_windows "${key_filename}" "${output_dir}"; then
                    log_error "Failed to create package for ${os}."
                    return 1
                fi
                ;;
            *)
                log_warn "Skipping unsupported OS type: ${os}"
                continue
                ;;
        esac
    done

    log_success "All client packages have been successfully created in: ${output_dir}"
    return 0
}