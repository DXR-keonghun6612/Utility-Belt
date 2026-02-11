#!/bin/bash
# ==============================================================================
# 파일명: proc_ssh.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: SSH 키 생성 및 클라이언트 패키징 관리를 위한 UI 스크립트
# ==============================================================================

# ==============================================================================
# SSH Key Generation & Packaging UI
# ==============================================================================
ui_ssh_key_generation() {
    # Step 1: Input Form (Filename, Comment)
    local result
    result=$(ui_create_form "SSH Management" "SSH Key Generation" "Enter SSH Key Details" \
        12 60 2 \
        "Key Filename:" 1 1 "" 1 15 40 50 \
        "Comment:"      2 1 "" 2 15 40 50)
    
    if [[ $? -ne 0 ]]; then return; fi
    
    local lines
    mapfile -t lines <<< "${result}"
    local key_name="${lines[0]}"
    local comment="${lines[1]}"
    
    # 유효성 검사
    if [[ -z "${key_name}" ]]; then
        ui_message_box "Key filename is required." "Error"
        return
    fi

    # Step 2: Select Target OS (Checklist)
    local os_selection
    os_selection=$(ui_create_checklist "SSH Key Generation" "Target OS" "Select target OS for client packages:" \
        "15" "60" "5" \
        "linux" "Linux Client" "ON" \
        "windows" "Windows Client" "ON")
    
    if [[ "${os_selection}" == "CANCEL" || -z "${os_selection}" ]]; then
        return
    fi

    # Step 3: Confirm and Execute
    if ui_confirm "Generate SSH key '${key_name}' and packages for: ${os_selection}?" "Confirm"; then
        eval "local os_array=(${os_selection})"
        local output_dir="${HOME}/ssh_packages"
        
        # 키 생성 및 패키징 실행 (backend 함수)
        if generate_and_package_client_keys "${key_name}" "ed25519" "" "${comment}" "${output_dir}" "${os_array[@]}"; then
             ui_message_box "SSH key and packages created successfully in:\n${output_dir}" "Success" 10 70
        else
             ui_message_box "Failed to create SSH keys. Check logs for details." "Error"
        fi
    fi
}

# ==============================================================================
# Main SSH Menu
# ==============================================================================
ui_ssh_management_menu() {
    while true; do
        local choice
        choice=$(ui_create_menu "SSH Management" "SSH Settings" "Select a task:" \
            "15" "60" "5" \
            "1" "Generate New SSH Key & Package" \
            "0" "Back to Main Menu")

        case "${choice}" in
            1) ui_ssh_key_generation ;; 
            0 | CANCEL) break ;; 
        esac
    done
}