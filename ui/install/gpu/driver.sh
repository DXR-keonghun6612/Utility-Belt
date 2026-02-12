#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/gpu/driver.sh
# 설명: NVIDIA 드라이버 설치를 위한 전용 UI.
# ==============================================================================

ui_install_nvidia_driver() {
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
        # 드라이버 이름과 추천 문구 분리
        local driver_name=$(echo "$item" | awk '{print $1}')
        local recommended_text=$(echo "$item" | cut -d' ' -f2-)
        dialog_options+=("${driver_name}" "${recommended_text}")
    done

    local selected_driver
    selected_driver=$(ui_create_menu "NVIDIA Driver Installation" "Select NVIDIA Driver" \
        "Use UP/DOWN to navigate and ENTER to select the driver.\n'(recommended)' is the best choice." 20 70 15 \
        "${dialog_options[@]}")

    if [[ "${selected_driver}" == "CANCEL" || -z "${selected_driver}" ]]; then
        return
    fi

    local confirm_prompt="You have selected '${selected_driver}'.\n\nThis will automatically remove any other NVIDIA drivers and may require a system reboot. Continue?"
    if ! ui_confirm "${confirm_prompt}" "Confirm Installation"; then
        return
    fi

    clear
    install_nvidia_driver_logic "${selected_driver}"
    read -rp $'
Completed. Press Enter to continue...'
}
