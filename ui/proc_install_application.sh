#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/proc_install_application.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: 추가 소프트웨어(NVIDIA, Miniconda, VSCode 등) 설치를 위한 동적 UI.
# ==============================================================================

##
# @description NVIDIA 드라이버 설치를 위한 전용 UI.
#           - 동적 메뉴에서 'NVIDIA Driver' 선택 시 호출됩니다.
#
_ui_install_nvidia_driver() {
    # 이 함수는 복잡한 드라이버 버전 선택 로직을 포함하므로 별도로 유지됩니다.
    ui_message_box "Searching for available NVIDIA drivers..." "NVIDIA Driver Installation" 5 70
    
    local driver_list_raw
    if ! driver_list_raw=$(get_available_nvidia_drivers); then
        ui_message_box "No NVIDIA drivers found for your hardware or 'ubuntu-drivers' not available." "Not Found"
        return
    fi
    
    local driver_list
    mapfile -t driver_list <<< "${driver_list_raw}"

    local dialog_options=()
    for item in "${driver_list[@]}"; do
        local driver_name recommended_text
        read -r driver_name recommended_text <<< "$item"
        dialog_options+=("${driver_name}" "${recommended_text}")
    done

    local selected_driver
    selected_driver=$(ui_create_menu "NVIDIA Driver Installation" "Select NVIDIA Driver" \
        "Use SPACE to select the driver. '(recommended)' is the best choice." 20 70 15 -- \
        "${dialog_options[@]}")

    if [[ "${selected_driver}" == "CANCEL" ]]; then
        ui_message_box "No driver was selected." "Canceled"; return
    fi

    local confirm_prompt="You have selected '${selected_driver}'.\n\nThis will automatically remove any other NVIDIA drivers and may require a system reboot. Continue?"
    if ! ui_confirm "${confirm_prompt}" "Confirm Installation"; then
        return
    fi

    clear
    if install_nvidia_driver_logic "${selected_driver}"; then
        # [Config 연동] 설치 성공 시 DRIVER_LIST에 기록
        local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
        set_config_value "${CONFIG_FILE}" "DRIVER_LIST" "nvidia-driver" "${selected_driver} (${timestamp})"
        ui_message_box "Driver '${selected_driver}' installed.\nA reboot is highly recommended." "Installation Successful"
    else
        ui_message_box "Failed to install '${selected_driver}'. Check the terminal for logs." "Installation Failed"
    fi
    read -rp $'\nCompleted. Press Enter to continue...'
}


##
# @description OpenCV 설치를 위한 전용 UI.
#
_ui_install_opencv() {
    # 1. 버전 선택
    local version
    version=$(ui_input_box "Enter OpenCV version to install:" "OpenCV Setup" "4.10.0")
    [[ -z "$version" || "$version" == "CANCEL" ]] && return 1

    # 2. CUDA 지원 여부
    local with_cuda="OFF"
    local gpu_arch=""
    
    # 01_install_package.sh의 _detect_cuda_toolkit을 활용할 수 없으므로 직접 체크하거나 
    # 로직 내부의 자동 감지 기능을 믿고 질문만 던짐
    if ui_confirm "Do you want to build OpenCV with CUDA acceleration?\n(CUDA Toolkit must be installed)" "CUDA Support"; then
        with_cuda="ON"
        
        # GPU 아키텍처 입력
        local detected_arch=""
        if command -v nvidia-smi &>/dev/null; then
            detected_arch=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader,nounits | head -n 1)
        fi
        gpu_arch=$(ui_input_box "Enter GPU Compute Capability (e.g., 8.6, 8.9):" "CUDA Arch" "${detected_arch}")
        [[ -z "$gpu_arch" ]] && gpu_arch="${detected_arch}"
    fi

    # 3. 병렬 빌드 수
    local jobs
    jobs=$(ui_input_box "Enter number of parallel build jobs:" "Build Speed" "$(nproc)")
    [[ -z "$jobs" ]] && jobs="$(nproc)"

    # 4. 설치 실행
    clear
    echo "========================================================"
    echo " Starting OpenCV ${version} Build & Installation"
    echo " CUDA: ${with_cuda} (Arch: ${gpu_arch:-N/A})"
    echo " Jobs: ${jobs}"
    echo "========================================================"
    
    if install_opencv_logic "${version}" "${with_cuda}" "${gpu_arch}" "${jobs}"; then
        ui_message_box "OpenCV ${version} installation completed successfully." "Success"
    else
        ui_message_box "OpenCV installation failed. Check terminal logs." "Error"
    fi
}


##
# @description CUDA Toolkit 관리 전용 UI.
#
_ui_install_cuda_toolkit() {
    while true; do
        local local_versions=$(_get_local_cuda_versions)
        
        # 1. 설치된 버전이 없는 경우 즉시 설치 UI로 이동
        if [[ -z "${local_versions}" ]]; then
            local target_arch=""
            if [[ $(uname -m) == "aarch64" ]]; then
                target_arch=$(ui_create_menu "CUDA Architecture" "Select ARM Variant" \
                    "Choose the repository target:" 15 70 2 \
                    "sbsa" "Server Base (Standard)" "arm64" "Generic ARM64")
                [[ "${target_arch}" == "CANCEL" ]] && return 1
            fi

            local version_list
            mapfile -t version_list < <(_get_available_cuda_versions)
            [[ ${#version_list[@]} -eq 0 ]] && { ui_message_box "No CUDA packages found." "Error"; return 1; }

            local choice
            choice=$(ui_create_menu "CUDA Installation" "Select Version" "Choose version to install:" 18 80 10 "${version_list[@]}")
            [[ "${choice}" == "CANCEL" ]] && return 1

            clear
            install_cuda_toolkit_logic "INSTALL" "${choice}" "${target_arch}"
            return $?
        fi

        # 2. 설치된 버전이 있는 경우 관리 메뉴 표시
        local current_link=""
        [[ -L "/usr/local/cuda" ]] && current_link=$(readlink -f /usr/local/cuda)

        local menu_desc="Installed versions:\n"
        for ver in $local_versions; do
            local mark=""; [[ "$current_link" == *"/cuda-${ver}" ]] && mark=" (*Active)"
            menu_desc+="  - ${ver}${mark}\n"
        done

        local action
        action=$(ui_create_menu "CUDA Version Manager" "Manage CUDA" "${menu_desc}" 20 80 6 \
            "INSTALL" "Install a NEW version" \
            "SWITCH"  "Switch active version" \
            "EXIT"    "Return")

        case "$action" in
            "INSTALL")
                local target_arch=""
                [[ $(uname -m) == "aarch64" ]] && target_arch=$(ui_create_menu "Arch" "Select" "" 10 50 2 "sbsa" "SBSA" "arm64" "ARM64")
                
                local version_list
                mapfile -t version_list < <(_get_available_cuda_versions)
                local choice
                choice=$(ui_create_menu "Install" "Select Version" "" 18 80 10 "${version_list[@]}")
                [[ "${choice}" != "CANCEL" ]] && { clear; install_cuda_toolkit_logic "INSTALL" "${choice}" "${target_arch}"; }
                ;;
            "SWITCH")
                local opts=()
                for ver in $local_versions; do opts+=("$ver" "Set as active"); done
                local choice
                choice=$(ui_create_menu "Switch" "Select Version" "" 15 70 5 "${opts[@]}")
                [[ "${choice}" != "CANCEL" ]] && install_cuda_toolkit_logic "SWITCH" "${choice}"
                ;;
            *) break ;;
        esac
    done
}


##
# @description cuDNN Library 설치 전용 UI.
#
_ui_install_cudnn_library() {
    if ! apt-cache pkgnames "libcudnn" | grep -q "."; then
        ui_message_box "NVIDIA repository is not found.\nPlease install 'CUDA Toolkit' first." "Repository Missing"
        return 1
    fi

    # 1. 현재 CUDA 버전 감지
    local cuda_major
    cuda_major=$(_get_active_cuda_major_version)

    # 2. 버전 목록 조회
    local version_list_raw
    version_list_raw=$(_get_available_cudnn_versions "${cuda_major}")
    
    if [[ -z "${version_list_raw}" ]]; then
        ui_message_box "No compatible cuDNN packages found for CUDA ${cuda_major}.\nShowing all available packages..." "Notice"
        version_list_raw=$(_get_available_cudnn_versions "unknown")
    fi

    if [[ -z "${version_list_raw}" ]]; then
        ui_message_box "No cuDNN packages found in the repository." "Error"; return 1
    fi

    local menu_options=()
    while read -r tag item; do
        menu_options+=("${tag}" "${item}")
    done <<< "${version_list_raw}"

    local prompt="Detected active CUDA major version: ${cuda_major}\n\nPlease select a compatible cuDNN version:"
    [[ "$cuda_major" == "unknown" ]] && prompt="Could not detect active CUDA version.\nPlease select a cuDNN version:"

    # 3. 버전 선택
    local choice
    choice=$(ui_create_menu "cuDNN Installation" "Select Version" "${prompt}" 18 80 10 "${menu_options[@]}")
    [[ "$choice" == "CANCEL" ]] && return 1

    # 4. 설치 실행
    clear
    if install_cudnn_library_logic "${choice}"; then
        ui_message_box "cuDNN Library installed successfully." "Success"
    else
        ui_message_box "cuDNN installation failed." "Error"
    fi
}


##
# @description '추가 소프트웨어 설치' 메인 UI 함수 (동적 체크리스트 방식).
#
ui_install_application() {
    # --- 1. 설정 및 스크립트 스캔 ---
    local install_dir="${SCRIPT_DIR}/script/install"
    
    # 스크립트 파일명 => "UI 표시 이름|설정 파일 키|설정 파일 섹션|설치 권한 유형" 매핑
    # 권한 유형: System (강제 시스템 설치), Selectable (설치 시 User/System 선택 가능)
    declare -A SCRIPT_MAP=(
        ["conda.sh"]="Conda|conda|APPLICATION_LIST|Selectable"
        ["vscode.sh"]="VS Code|code|APPLICATION_LIST|System"
        ["nvidia_driver.sh"]="NVIDIA Driver|nvidia-driver|DRIVER_LIST|System"
        ["cuda_toolkit.sh"]="CUDA Toolkit|cuda-toolkit|APPLICATION_LIST|System"
        ["cudnn_library.sh"]="cuDNN Library|cudnn-library|APPLICATION_LIST|System"
        ["docker.sh"]="Docker|docker|APPLICATION_LIST|System"
        ["ros2.sh"]="ROS 2|ros2|APPLICATION_LIST|System"
        ["opencv.sh"]="OpenCV|opencv|APPLICATION_LIST|System"
    )
    # UI 표시 이름 => 실제 실행할 함수 이름 매핑
    declare -A NAME_TO_LOGIC=(
        ["Conda"]="install_conda_logic"
        ["VS Code"]="install_vscode_logic"
        ["NVIDIA Driver"]="_ui_install_nvidia_driver"
        ["CUDA Toolkit"]="_ui_install_cuda_toolkit"
        ["cuDNN Library"]="_ui_install_cudnn_library"
        ["Docker"]="install_docker_logic"
        ["ROS 2"]="install_ros2_logic"
        ["OpenCV"]="_ui_install_opencv"
    )
    # UI 표시 이름 => 설치 확인 함수 매핑
    declare -A NAME_TO_CHECK=(
        ["Conda"]="is_installed_conda"
        ["VS Code"]="is_installed_vscode"
        ["NVIDIA Driver"]="is_installed_nvidia_driver"
        ["CUDA Toolkit"]="is_installed_cuda_toolkit"
        ["cuDNN Library"]="is_installed_cudnn_library"
        ["Docker"]="is_installed_docker"
        ["ROS 2"]="is_installed_ros2"
        ["OpenCV"]="is_installed_opencv"
    )
    # UI 표시 이름 => 스크립트 파일명 역매핑 (설치 시 정보 조회를 위해 필요)
    declare -A NAME_TO_FILENAME

    local available_scripts
    mapfile -t available_scripts < <(find "${install_dir}" -maxdepth 1 -name "*.sh" -printf "%f\n" | sort)

    # --- 2. 체크리스트 옵션 생성 ---
    local dialog_options=()
    declare -A initial_states
    
    for script_file in "${available_scripts[@]}"; do
        if [[ -z "${SCRIPT_MAP[$script_file]}" ]]; then continue; fi

        IFS='|' read -r name key section install_type <<< "${SCRIPT_MAP[$script_file]}"
        NAME_TO_FILENAME["$name"]="$script_file"

        local is_checked="off"
        local status_desc="Not Installed"

        # [개선된 로직] 설치 확인 함수 우선 사용
        local check_func="${NAME_TO_CHECK[$name]}"
        local installed=false
        local is_verified_externally=false # 상태 검증 여부

        if [[ -n "$check_func" ]] && command -v "$check_func" &>/dev/null; then
            if "$check_func"; then
                installed=true
            fi
            is_verified_externally=true
        else
            # Fallback: 기존 Config/DPKG 확인 방식
            if [[ "$section" == "DRIVER_LIST" && "$key" == "nvidia-driver" ]]; then
                if dpkg-query -W -f='${Status}' nvidia-driver-* 2>/dev/null | grep -q 'install ok installed'; then
                    installed=true
                fi
                is_verified_externally=true
            elif [[ -n "$(get_config_value "${CONFIG_FILE}" "$section" "$key")" ]]; then
                installed=true
            fi
        fi

        if [[ "$installed" == "true" ]]; then
            is_checked="on"
            status_desc="(Installed)"

            # [SPECIAL] CUDA Toolkit: Always force OFF to allow entering Management Menu
            if [[ "$name" == "CUDA Toolkit" ]]; then
                is_checked="off"
                status_desc="(Installed - Check to Manage)"
            fi
        fi
        
        # [Sync Config] 실제 설치 상태와 설정 파일 동기화
        if [[ "$is_verified_externally" == "true" ]]; then
            # [SPECIAL] CUDA Toolkit과 cuDNN Library는 버전별 개별 키를 사용하므로 범용 키 동기화 제외
            if [[ "$name" != "CUDA Toolkit" && "$name" != "cuDNN Library" ]]; then
                local current_conf_val
                current_conf_val=$(get_config_value "${CONFIG_FILE}" "$section" "$key")

                if [[ "$installed" == "true" ]]; then
                    if [[ -z "$current_conf_val" ]]; then
                        local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
                        set_config_value "${CONFIG_FILE}" "$section" "$key" "${timestamp}"
                    fi
                else
                    if [[ -n "$current_conf_val" ]]; then
                        delete_config_value "${CONFIG_FILE}" "$section" "$key"
                    fi
                fi
            fi
        fi
        
        initial_states["$name"]=$is_checked
        
        # UI 항목 이름에 설치 유형 표시
        local type_label="[System]"
        [[ "$install_type" == "Selectable" ]] && type_label="[User/System]"
        
        local display_name="${name} ${type_label}"
        dialog_options+=("${display_name}" "$status_desc" "$is_checked")
    done

    if [[ ${#dialog_options[@]} -eq 0 ]]; then
        ui_message_box "No configurable installation scripts found." "Info"; return
    fi

    # --- 3. UI 표시 및 사용자 선택 처리 ---
    local selections_str
    selections_str=$(ui_create_checklist "Additional Software Setup" "Install Software" \
        "Check items to install. [Type] indicates permission level." 20 75 15 "${dialog_options[@]}")

    if [[ "$selections_str" == "CANCEL" ]]; then return; fi

    # --- 4. 선택된 항목 순차 처리 (설치/삭제) ---
    local -a selections
    eval "selections=($selections_str)"

    local any_action_performed=false
    clear
    echo "--- Processing software setup changes ---"

    # 모든 스크립트에 대해 상태 변화 감지
    for script_file in "${available_scripts[@]}"; do
        if [[ -z "${SCRIPT_MAP[$script_file]}" ]]; then continue; fi

        IFS='|' read -r name key section install_type <<< "${SCRIPT_MAP[$script_file]}"
        
        local is_selected=false
        for sel in "${selections[@]}"; do
            if [[ "$sel" == "$name "* ]]; then
                is_selected=true
                break
            fi
        done

        local initial_state="${initial_states[$name]}"
        local logic_func="${NAME_TO_LOGIC[$name]}"
        
        # [Case 1] 신규 설치: 초기 OFF -> 현재 ON
        if [[ "$initial_state" == "off" && "$is_selected" == "true" ]]; then
            any_action_performed=true
            echo "----------------------------------------"
            echo "[ACTION] Installing: ${name}"
            
            local mode_arg=""
            local conda_type="miniconda" 

            if [[ "$name" == "Conda" ]]; then
                conda_type=$(ui_create_menu "Conda Distribution" "Select Distribution" \
                    "Which distribution do you want to install?" 15 60 5 \
                    "miniconda" "Miniconda (Lightweight, Recommended)" \
                    "anaconda" "Anaconda (Full, Large)")
                if [[ "$conda_type" == "CANCEL" ]]; then continue; fi
            fi

            if [[ "$install_type" == "Selectable" ]]; then
                mode_arg=$(ui_create_menu "Installation Mode" "Select Mode for ${name}" \
                    "How should ${name} be installed?" 15 60 5 \
                    "user" "User Mode" "system" "System Mode")
                [[ "$mode_arg" == "CANCEL" ]] && continue
            fi

            if [[ -n "$logic_func" ]] && command -v "$logic_func" &>/dev/null; then
                if [[ "$name" == "Conda" ]]; then
                    "$logic_func" "$mode_arg" "$conda_type"
                else
                    "$logic_func" "$mode_arg"
                fi
            fi

        # [Case 2] 삭제: 초기 ON -> 현재 OFF
        elif [[ "$initial_state" == "on" && "$is_selected" == "false" ]]; then
            any_action_performed=true
            echo "----------------------------------------"
            echo "[ACTION] Uninstalling: ${name}"
            local uninstall_func="${logic_func/install/uninstall}"
            if [[ -n "$uninstall_func" ]] && command -v "$uninstall_func" &>/dev/null; then
                "$uninstall_func"
                delete_config_value "${CONFIG_FILE}" "$section" "$key"
            fi
        fi
    done

    if [[ "$any_action_performed" == "true" ]]; then
        read -rp $'\nAll selected operations completed. Press Enter to continue...'
    fi
}
