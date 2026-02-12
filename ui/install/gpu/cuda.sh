#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/gpu/cuda.sh
# 설명: CUDA Toolkit 설치 및 관리 전용 UI.
# ==============================================================================

ui_install_cuda_toolkit() {
    while true; do
        local local_versions; local_versions=$(get_local_cuda_versions)
        
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
