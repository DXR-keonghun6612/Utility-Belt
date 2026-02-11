#!/bin/bash
# ==============================================================================
# 파일명: proc_git.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: Git 사용자 설정 및 인증 토큰 관리를 위한 UI 스크립트
# ==============================================================================

# ==============================================================================
# Git Configuration Form (Name & Email)
# ==============================================================================
ui_git_config_form() {
    local current_name; current_name=$(get_git_config "user.name")
    local current_email; current_email=$(get_git_config "user.email")

    # ui_create_form 사용
    local result
    result=$(ui_create_form "User Configuration > Git" "Git User Configuration" "Edit Git User Settings" \
        12 60 2 \
        "User Name:"  1 1 "${current_name}"  1 15 40 50 \
        "User Email:" 2 1 "${current_email}" 2 15 40 50)
    
    if [[ $? -eq 0 ]]; then
        local lines
        mapfile -t lines <<< "${result}"
        
        local new_name="${lines[0]}"
        local new_email="${lines[1]}"

        # 변경사항 적용 (빈 값도 그대로 설정하여 덮어쓰기)
        set_git_config "user.name" "--global" "${new_name}"
        set_git_config "user.email" "--global" "${new_email}"
        
        ui_message_box "Git configuration updated.\nName: ${new_name}\nEmail: ${new_email}" "Success"
    fi
}

# ==============================================================================
# Git Credential (Token) Configuration
# ==============================================================================
ui_git_credential_config() {
    local username
    username=$(get_git_config "user.name")
    
    # 1. Ask for Username
    username=$(ui_input_box "Enter GitHub Username:" "Git Credential Setup" "${username}")
    if [[ $? -ne 0 || -z "${username}" ]]; then return; fi

    # 2. Ask for Token
    local token
    token=$(ui_password_box "Enter Personal Access Token (PAT):" "Git Credential Setup")
    if [[ $? -ne 0 || -z "${token}" ]]; then return; fi

    # 3. Ask for Host
    local host
    host=$(ui_input_box "Enter Git Host (Default: github.com):" "Git Credential Setup" "github.com")
    if [[ $? -ne 0 ]]; then return; fi
    [[ -z "${host}" ]] && host="github.com"

    # 4. Save
    update_git_token "${username}" "${token}" "${host}"
    ui_message_box "Git credentials updated for ${host}." "Success"
}

# ==============================================================================
# Main Git Menu
# ==============================================================================
ui_git_management_menu() {
    while true; do
        local choice
        choice=$(ui_create_menu "Git Management" "Git Settings" "Select a task:" \
            "15" "60" "5" \
            "1" "Configure User & Email" \
            "2" "Update Auth Token" \
            "0" "Back to Main Menu")

        case "${choice}" in
            1) ui_git_config_form ;;
            2) ui_git_credential_config ;;
            0 | CANCEL) break ;;
        esac
    done
}