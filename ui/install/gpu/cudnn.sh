#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/gpu/cudnn.sh
# 설명: cuDNN Library 설치 전용 UI.
# ==============================================================================

ui_install_cudnn_library() {
    if ! apt-cache pkgnames "libcudnn" | grep -q "."; then
        ui_message_box "NVIDIA repository is not found.\nPlease install 'CUDA Toolkit' first." "Repository Missing"
        return 1
    fi

    local cuda_major; cuda_major=$(get_active_cuda_major_version)
    local version_list_raw; version_list_raw=$(get_available_cudnn_versions "${cuda_major}")
    
    if [[ -z "${version_list_raw}" ]]; then
        ui_message_box "No compatible cuDNN packages found for CUDA ${cuda_major}.\nShowing all available packages..." "Notice"
        version_list_raw=$(get_available_cudnn_versions "unknown")
    fi

    if [[ -z "${version_list_raw}" ]]; then
        ui_message_box "No cuDNN packages found in the repository." "Error"; return 1
    fi

    local menu_options=()
    while read -r line; do
        # 라인 형식: "pkg=ver cuDNN_vX.Y.Z [for CUDA XX]"
        local target_choice=$(echo "$line" | awk '{print $1}')
        local display_text=$(echo "$line" | cut -d' ' -f2-)
        
        # 단순 버전 번호 추출 (X.Y.Z)
        local ver_num=$(echo "$display_text" | grep -oP "cuDNN_v\K[0-9.]+")
        
        menu_options+=("${ver_num}" "${display_text}")
    done <<< "${version_list_raw}"

    local prompt="Detected active CUDA major version: ${cuda_major}\n\nPlease select a cuDNN version to install:"
    [[ "$cuda_major" == "unknown" ]] && prompt="Could not detect active CUDA version.\nPlease select a cuDNN version:"

    local choice
    choice=$(ui_create_menu "cuDNN Installation" "Select Version" "${prompt}" 18 80 10 "${menu_options[@]}")
    [[ "$choice" == "CANCEL" || -z "$choice" ]] && return 1

    clear
    log_info "Starting installation for cuDNN v${choice}..."
    install_cudnn_library "${choice}"
    
    read -rp $'
Press Enter to continue...'
}
