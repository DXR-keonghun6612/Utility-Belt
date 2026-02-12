#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/gpu/cudnn.sh
# 설명: cuDNN Library 설치 전용 UI.
# ==============================================================================

ui_install_cudnn_library() {
    if ! apt-cache pkgnames "libcudnn" | grep -q "."; then
        ui_message_box "NVIDIA repository is not found.
Please install 'CUDA Toolkit' first." "Repository Missing"
        return 1
    fi

    local cuda_major; cuda_major=$(_get_active_cuda_major_version)

    local version_list_raw; version_list_raw=$(_get_available_cudnn_versions "${cuda_major}")
    
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
