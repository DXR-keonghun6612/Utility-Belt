#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/proc_install_gpu_stack.sh
# 최종 수정일: 2026-02-11
# 설명: NVIDIA 드라이버, CUDA Toolkit, cuDNN 라이브러리 설치를 위한 전용 UI.
# ==============================================================================

##
# @description GPU 스택 설치 메인 메뉴.
#
ui_install_gpu_stack() {
    while true; do
        local choice
        choice=$(ui_create_menu "GPU Stack Installation" "NVIDIA GPU Stack" "Select a component to manage:" 
            20 70 10 
            "DRIVER"  "Install NVIDIA Driver" 
            "CUDA"    "Install/Manage CUDA Toolkit" 
            "CUDNN"   "Install cuDNN Library" 
            "BACK"    "Return to Previous Menu")

        case "${choice}" in
            "DRIVER") _ui_install_nvidia_driver ;;
            "CUDA")   _ui_install_cuda_toolkit ;;
            "CUDNN")  _ui_install_cudnn_library ;;
            "BACK" | "CANCEL") break ;;
        esac
    done
}

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
    selected_driver=$(ui_create_menu "NVIDIA Driver Installation" "Select NVIDIA Driver" 
        "Use SPACE to select the driver. '(recommended)' is the best choice." 20 70 15 -- 
        "${dialog_options[@]}")

    if [[ "${selected_driver}" == "CANCEL" ]]; then
        return
    fi

    local confirm_prompt="You have selected '${selected_driver}'.

This will automatically remove any other NVIDIA drivers and may require a system reboot. Continue?"
    if ! ui_confirm "${confirm_prompt}" "Confirm Installation"; then
        return
    fi

    clear
    install_nvidia_driver_logic "${selected_driver}"
    read -rp $'
Completed. Press Enter to continue...'
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
                target_arch=$(ui_create_menu "CUDA Architecture" "Select ARM Variant" 
                    "Choose the repository target:" 15 70 2 
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

        local menu_desc="Installed versions:
"
        for ver in $local_versions; do
            local mark=""; [[ "$current_link" == *"/cuda-${ver}" ]] && mark=" (*Active)"
            menu_desc+="  - ${ver}${mark}
"
        done

        local action
        action=$(ui_create_menu "CUDA Version Manager" "Manage CUDA" "${menu_desc}" 20 80 6 
            "INSTALL" "Install a NEW version" 
            "SWITCH"  "Switch active version" 
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
        ui_message_box "NVIDIA repository is not found.
Please install 'CUDA Toolkit' first." "Repository Missing"
        return 1
    fi

    local cuda_major
    cuda_major=$(_get_active_cuda_major_version)

    local version_list_raw
    version_list_raw=$(_get_available_cudnn_versions "${cuda_major}")
    
    if [[ -z "${version_list_raw}" ]]; then
        ui_message_box "No compatible cuDNN packages found for CUDA ${cuda_major}.
Showing all available packages..." "Notice"
        version_list_raw=$(_get_available_cudnn_versions "unknown")
    fi

    if [[ -z "${version_list_raw}" ]]; then
        ui_message_box "No cuDNN packages found in the repository." "Error"; return 1
    fi

    local menu_options=()
    while read -r tag item; do
        menu_options+=("${tag}" "${item}")
    done <<< "${version_list_raw}"

    local prompt="Detected active CUDA major version: ${cuda_major}

Please select a compatible cuDNN version:"
    [[ "$cuda_major" == "unknown" ]] && prompt="Could not detect active CUDA version.
Please select a cuDNN version:"

    local choice
    choice=$(ui_create_menu "cuDNN Installation" "Select Version" "${prompt}" 18 80 10 "${menu_options[@]}")
    [[ "$choice" == "CANCEL" ]] && return 1

    clear
    install_cudnn_library_logic "${choice}"
}
