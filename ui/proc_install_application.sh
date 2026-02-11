#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/proc_install_application.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: 추가 소프트웨어(NVIDIA, Miniconda, VSCode 등) 설치를 위한 동적 UI.
# ==============================================================================

##
# @description NVIDIA 드라이버 설치를 위한 전용 UI.
#
_ui_install_nvidia_driver() {
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
        return
    fi

    local confirm_prompt="You have selected '${selected_driver}'.\n\nThis will automatically remove any other NVIDIA drivers and may require a system reboot. Continue?"
    if ! ui_confirm "${confirm_prompt}" "Confirm Installation"; then
        return
    fi

    clear
    install_nvidia_driver_logic "${selected_driver}"
    read -rp $'\nCompleted. Press Enter to continue...'
}


##
# @description OpenCV 설치를 위한 전용 UI.
#
_ui_install_opencv() {
    local version
    version=$(ui_input_box "Enter OpenCV version to install:" "OpenCV Setup" "4.10.0")
    [[ -z "$version" || "$version" == "CANCEL" ]] && return 1

    local with_cuda="OFF"
    local gpu_arch=""
    
    if ui_confirm "Do you want to build OpenCV with CUDA acceleration?\n(CUDA Toolkit must be installed)" "CUDA Support"; then
        with_cuda="ON"
        
        local detected_arch=""
        if command -v nvidia-smi &>/dev/null; then
            detected_arch=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader,nounits | head -n 1)
        fi
        gpu_arch=$(ui_input_box "Enter GPU Compute Capability (e.g., 8.6, 8.9):" "CUDA Arch" "${detected_arch}")
        [[ -z "$gpu_arch" ]] && gpu_arch="${detected_arch}"
    fi

    local jobs
    jobs=$(ui_input_box "Enter number of parallel build jobs:" "Build Speed" "$(nproc)")
    [[ -z "$jobs" ]] && jobs="$(nproc)"

    clear
    install_opencv_logic "${version}" "${with_cuda}" "${gpu_arch}" "${jobs}"
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

    local cuda_major
    cuda_major=$(_get_active_cuda_major_version)

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

    local choice
    choice=$(ui_create_menu "cuDNN Installation" "Select Version" "${prompt}" 18 80 10 "${menu_options[@]}")
    [[ "$choice" == "CANCEL" ]] && return 1

    clear
    install_cudnn_library_logic "${choice}"
}


##
# @description '추가 소프트웨어 설치' 메인 UI 함수 (동적 체크리스트 방식).
#
ui_install_application() {
    # --- 1. 설정 및 스크립트 스캔 ---
    local install_dir="${SCRIPT_DIR}/script/install"
    
    # UI 표시 이름 => [설정 섹션, 설치 권한 유형, 로직 함수, 체크 함수]
    declare -A APP_DATA=(
        ["Conda"]="APPLICATION_LIST|Selectable|install_conda_logic|is_installed_conda"
        ["VS Code"]="APPLICATION_LIST|System|install_vscode_logic|is_installed_vscode"
        ["NVIDIA Driver"]="DRIVER_LIST|System|_ui_install_nvidia_driver|is_installed_nvidia_driver"
        ["CUDA Toolkit"]="APPLICATION_LIST|System|_ui_install_cuda_toolkit|is_installed_cuda_toolkit"
        ["cuDNN Library"]="APPLICATION_LIST|System|_ui_install_cudnn_library|is_installed_cudnn_library"
        ["Docker"]="APPLICATION_LIST|System|install_docker_logic|is_installed_docker"
        ["ROS 2"]="APPLICATION_LIST|System|install_ros2_logic|is_installed_ros2"
        ["OpenCV"]="APPLICATION_LIST|System|_ui_install_opencv|is_installed_opencv"
    )

    local app_order=("Conda" "VS Code" "NVIDIA Driver" "CUDA Toolkit" "cuDNN Library" "Docker" "ROS 2" "OpenCV")

    # --- 2. 체크리스트 옵션 생성 ---
    local dialog_options=()
    declare -A initial_states
    
    for name in "${app_order[@]}"; do
        IFS='|' read -r section install_type logic_func check_func <<< "${APP_DATA[$name]}"

        local is_checked="off"
        local status_desc="Not Installed"

        # 백엔드 함수를 호출하여 상태 감지 및 설정 동기화
        if [[ -n "$check_func" ]] && command -v "$check_func" &>/dev/null; then
            if "$check_func"; then
                is_checked="on"
                status_desc="(Installed)"

                # [SPECIAL] CUDA Toolkit: 매니지먼트 메뉴 진입을 위해 항상 OFF로 표시
                if [[ "$name" == "CUDA Toolkit" ]]; then
                    is_checked="off"
                    status_desc="(Installed - Check to Manage)"
                fi
            fi
        fi
        
        initial_states["$name"]=$is_checked
        
        local type_label="[System]"
        [[ "$install_type" == "Selectable" ]] && type_label="[User/System]"
        dialog_options+=("${name} ${type_label}" "$status_desc" "$is_checked")
    done

    # --- 3. UI 표시 및 사용자 선택 처리 ---
    local selections_str
    selections_str=$(ui_create_checklist "Additional Software Setup" "Install Software" \
        "Check items to install. [Type] indicates permission level." 20 75 15 "${dialog_options[@]}")

    if [[ "$selections_str" == "CANCEL" ]]; then return; fi

    local -a selections
    eval "selections=($selections_str)"

    local any_action_performed=false
    clear
    echo "--- Processing software setup changes ---"

    for name in "${app_order[@]}"; do
        IFS='|' read -r section install_type logic_func check_func <<< "${APP_DATA[$name]}"
        
        local is_selected=false
        for sel in "${selections[@]}"; do
            if [[ "$sel" == "$name "* ]]; then
                is_selected=true; break
            fi
        done

        local initial_state="${initial_states[$name]}"
        
        # [Case 1] 신규 설치
        if [[ "$initial_state" == "off" && "$is_selected" == "true" ]]; then
            any_action_performed=true
            echo "----------------------------------------"
            echo "[ACTION] Installing: ${name}"
            
            local mode_arg=""
            if [[ "$name" == "Conda" ]]; then
                local conda_type
                conda_type=$(ui_create_menu "Conda Distribution" "Select Distribution" \
                    "Which distribution do you want to install?" 15 60 5 \
                    "miniconda" "Miniconda (Lightweight, Recommended)" \
                    "anaconda" "Anaconda (Full, Large)")
                [[ "$conda_type" == "CANCEL" ]] && continue

                mode_arg=$(ui_create_menu "Installation Mode" "Select Mode for ${name}" \
                    "How should ${name} be installed?" 15 60 5 \
                    "user" "User Mode" "system" "System Mode")
                [[ "$mode_arg" == "CANCEL" ]] && continue
                
                "$logic_func" "$mode_arg" "$conda_type"
            else
                if [[ "$install_type" == "Selectable" ]]; then
                    mode_arg=$(ui_create_menu "Installation Mode" "Select Mode for ${name}" \
                        "How should ${name} be installed?" 15 60 5 \
                        "user" "User Mode" "system" "System Mode")
                    [[ "$mode_arg" == "CANCEL" ]] && continue
                fi
                "$logic_func" "$mode_arg"
            fi

        # [Case 2] 삭제
        elif [[ "$initial_state" == "on" && "$is_selected" == "false" ]]; then
            any_action_performed=true
            echo "----------------------------------------"
            echo "[ACTION] Uninstalling: ${name}"
            # TODO: uninstall_..._logic 백엔드 함수 보강 필요
            local uninstall_func="${logic_func/install/uninstall}"
            if [[ -n "$uninstall_func" ]] && command -v "$uninstall_func" &>/dev/null; then
                "$uninstall_func"
            else
                echo "[WARN] Automatic uninstallation not supported for ${name}."
            fi
        fi
    done

    if [[ "$any_action_performed" == "true" ]]; then
        read -rp $'\nAll selected operations completed. Press Enter to continue...'
    fi
}
