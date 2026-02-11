#!/bin/bash
# ==============================================================================
# 파일명: proc_samba.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: samba.sh의 기능을 활용하여 Samba 서비스, 공유, 사용자 관리를 위한 모든 사용자 인터페이스를 제공.
# 필요: dialog, samba.sh, base/config.sh, 02_dialog.sh (헬퍼 함수)
# ==============================================================================

# ==============================================================================
# --- UI 헬퍼 함수 ---
# ==============================================================================

_ui_show_completion_message() {
    read -rp $'/
Completed. Press Enter to continue.../'
}

_ui_show_cancel_message() {
    ui_message_box "Operation canceled." "Cancelled" 5 30
    sleep 1
}

# ==============================================================================
# --- Samba 공유 프로필 관리 내부 헬퍼 함수 ---
# ==============================================================================

_get_share_text_options_from_form() {
    local title="$1"; shift
    local initial_share_name="$1"; shift
    local initial_values=($@)

    local form_output
    # ui_create_continuous_form 사용: backtitle, title, prompt, height, width, form_height, fields...
    if ! form_output=$(ui_create_continuous_form "Samba Share Wizard" "${title}" "" 22 70 12 \
        "Share Name:"      1 1 "${initial_share_name}"  1 25 30 0 \
        "Share Path:"      2 1 "${initial_values[0]}" 2 25 40 0 \
        "Comment:"         3 1 "${initial_values[1]}" 3 25 40 0 \
        "Valid Users:"     4 1 "${initial_values[2]}" 4 25 40 0 \
        "Admin Users:"     5 1 "${initial_values[3]}" 5 25 40 0 \
        "Force User:"      6 1 "${initial_values[4]}" 6 25 40 0 \
        "Force Group:"     7 1 "${initial_values[5]}" 7 25 40 0 \
        "Create Mask:"     8 1 "${initial_values[6]:-0664}" 8 25 10 0 \
        "Directory Mask:"  9 1 "${initial_values[7]:-0775}" 9 25 10 0);
    then
        return 1
    fi

    declare -g share_name="$(echo "$form_output" | sed -n '1p' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')" \
               share_path="$(echo "$form_output" | sed -n '2p' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')" \
               comment="$(echo "$form_output" | sed -n '3p' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')" \
               valid_users="$(echo "$form_output" | sed -n '4p' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')" \
               admin_users="$(echo "$form_output" | sed -n '5p' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')" \
               force_user="$(echo "$form_output" | sed -n '6p' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')" \
               force_group="$(echo "$form_output" | sed -n '7p' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')" \
               create_mask="$(echo "$form_output" | sed -n '8p' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')" \
               directory_mask="$(echo "$form_output" | sed -n '9p' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    return 0
}

_get_share_boolean_options_from_dialogs() {
    declare -g new_writable new_browseable new_guest_ok
    local current_writable="${1:-no}" current_browseable="${2:-yes}" current_guest_ok="${3:-no}"
    local opts=()

    # --defaultno 등의 옵션 사용을 위해 dialog 직접 호출 유지 또는 래퍼 확장 필요.
    # 현재는 직접 호출 유지.
    opts=()
    [[ "${current_writable}" != "yes" ]] && opts=("--defaultno")
    if dialog "${opts[@]}" --title "Permissions" --yesno "Allow users to write to this share?" 8 60; then new_writable="yes"; else new_writable="no"; fi

    opts=()
    [[ "${current_browseable}" != "yes" ]] && opts=("--defaultno")
    if dialog "${opts[@]}" --title "Visibility" --yesno "Make this share visible?" 8 60; then new_browseable="yes"; else new_browseable="no"; fi

    opts=()
    [[ "${current_guest_ok}" != "yes" ]] && opts=("--defaultno")
    if dialog "${opts[@]}" --title "Guest Access" --yesno "Allow guest (public) access?" 8 60; then new_guest_ok="yes"; else new_guest_ok="no"; fi
}

_build_samba_options_string() {
    local mode="$1"
    local options_str="path=${share_path}"

    [[ -n "${comment}" ]] && options_str+";comment=${comment}"

    [[ "${new_writable}" == "yes" ]] && options_str+";writable=yes" || options_str+";writable=no"
    [[ "${new_browseable}" == "yes" ]] && options_str+";browseable=yes" || options_str+";browseable=no"

    if [[ "${mode}" == "modify" || -n "${valid_users}" ]]; then
        options_str+";valid users=${valid_users}"
    fi
    if [[ "${mode}" == "modify" || -n "${admin_users}" ]]; then
        options_str+";admin users=${admin_users}"
    fi
    if [[ "${mode}" == "modify" || -n "${force_user}" ]]; then
        options_str+";force user=${force_user}"
    fi
    if [[ "${mode}" == "modify" || -n "${force_group}" ]]; then
        options_str+";force group=${force_group}"
    fi

    [[ -n "${create_mask}" ]] && options_str+";create mask=${create_mask}"
    [[ -n "${directory_mask}" ]] && options_str+";directory mask=${directory_mask}"

    [[ "${new_guest_ok}" == "yes" ]] && options_str+";guest ok=yes"
    
    echo "${options_str}"
}

_ensure_share_directory_exists() {
    if [[ -d "${share_path}" ]]; then return 0; fi
    if ! ui_confirm "Directory '${share_path}' does not exist. Create it now?" "Directory Creation"; then return 1; fi
    
    clear; echo "Creating directory: ${share_path}"
    if ${G_SUDO_PREFIX} mkdir -p "${share_path}"; then
        echo "Directory created successfully."
        if [[ -n "${valid_users}" ]]; then
            echo "Attempting to set ownership for '${share_path}'..."
            if [[ "${valid_users}" =~ ^@ ]]; then
                local group_name="${valid_users#@}"
                if is_group_exist "${group_name}"; then 
                    ${G_SUDO_PREFIX} chown "root:${group_name}" "${share_path}"
                    ${G_SUDO_PREFIX} chmod 775 "${share_path}"
                fi
            elif is_user_exist "${valid_users}"; then
                ${G_SUDO_PREFIX} chown "${valid_users}:${valid_users}" "${share_path}"
                ${G_SUDO_PREFIX} chmod 755 "${share_path}"
            fi
        fi
        read -rp "Press Enter to continue..."
    else
        ui_message_box "Error: Failed to create directory." "Error" 8 60; return 2
    fi
    return 0
}

_confirm_and_apply_share() {
    local mode="$1"
    local title="Final Confirmation"
    local question="Create the following share?"
    if [[ "$mode" == "modify" ]]; then question="Apply these changes for [${share_name}]?"; fi

    local summary="${question}\n\n"
    summary+="- Path: ${share_path}\n"
    [[ -n "${comment}" ]] && summary+="- Comment: ${comment}\n"
    summary+="---\n"
    summary+="- Writable: ${new_writable}\n- Browseable: ${new_browseable}\n- Guest OK: ${new_guest_ok}\n"
    summary+="---\n"
    
    if [[ "${mode}" == "modify" || -n "${valid_users}" ]]; then
        summary+="- Valid Users: ${valid_users}\n"
    fi
    if [[ "${mode}" == "modify" || -n "${admin_users}" ]]; then
        summary+="- Admin Users: ${admin_users}\n"
    fi
    if [[ "${mode}" == "modify" || -n "${force_user}" ]]; then
        summary+="- Force User: ${force_user}\n"
    fi
    if [[ "${mode}" == "modify" || -n "${force_group}" ]]; then
        summary+="- Force Group: ${force_group}\n"
    fi

    [[ -n "${create_mask}" ]] && summary+="- Create Mask: ${create_mask}\n"
    [[ -n "${directory_mask}" ]] && summary+="- Directory Mask: ${directory_mask}\n"

    if ui_confirm "${summary}" "${title}" 20 70;
    then
        local options_str=$(_build_samba_options_string "$mode")
        clear; add_samba_share "${share_name}" "${options_str}" && restart_samba
        _ui_show_completion_message
    else
        _ui_show_cancel_message
    fi
}

# ==============================================================================
# --- 메인 UI ---
# ==============================================================================
ui_samba_management() {
    while true; do
        local choice
        choice=$(ui_create_menu "Samba Management Utility" "Samba Management" "Select an option:" "20" "60" "12" \
            "MANAGE_SHARES" "Manage Share Profiles (Enable/Disable)" \
            "ADD_SHARE" "Add New Share Profile" \
            "MOD_SHARE" "Modify Share Profile" \
            "DEL_SHARE" "Delete Share Profile" \
            "---" "---------------------------------" \
            "LIST_USERS" "List Samba Users" \
            "ADD_USER" "Add New Samba User" \
            "DEL_USER" "Delete Samba User" \
            "---" "---------------------------------" \
            "BACK" "Return to Main Menu")
        case "${choice}" in
            MANAGE_SHARES) ui_manage_samba_shares ;; ADD_SHARE) ui_add_samba_share ;; MOD_SHARE) ui_modify_samba_share ;; 
            DEL_SHARE) ui_delete_samba_share ;; 
            LIST_USERS) ui_list_samba_users ;;
            ADD_USER) ui_add_samba_user ;;
            DEL_USER) ui_delete_samba_user ;;
            BACK | CANCEL) clear; break ;; 
            *) ui_message_box "Invalid option: ${choice}" "Error" 6 40 ;; 
        esac
    done
}

# ==============================================================================
# --- 공유 관리 UI ---
# ==============================================================================

ui_manage_samba_shares() {
    local initial_shares_raw; initial_shares_raw=$(get_samba_shares)
    if [[ -z "$initial_shares_raw" ]]; then ui_message_box "No configurable share profiles found." "Info"; return; fi
    
    local checklist_options=() initial_enabled_shares=()
    local shares_array=(${initial_shares_raw})
    
    for (( i=0; i<${#shares_array[@]}; i+=2 )); do
        local name="${shares_array[i]}"
        local status="${shares_array[i+1]}"
        checklist_options+=("$name" "" "$status")
        
        if [[ "$status" == "on" ]]; then
            initial_enabled_shares+=("$name")
        fi
    done

    local final_enabled_shares_str
    final_enabled_shares_str=$(ui_create_checklist "" "Manage Samba Shares" "(Press Space to toggle)" 20 70 15 "${checklist_options[@]}")
    if [[ "$final_enabled_shares_str" == "CANCEL" ]]; then _ui_show_cancel_message; return; fi
    
    local final_enabled_shares; read -r -a final_enabled_shares <<< "$final_enabled_shares_str"
    local changes_made=false
    
    for share in "${initial_enabled_shares[@]}"; do
        if ! [[ " ${final_enabled_shares[*]} " =~ " ${share} " ]]; then
            echo "Disabling share: [${share}]"; toggle_samba_share_status "${share}" "disable"; changes_made=true
        fi
    done
    
    for share in "${final_enabled_shares[@]}"; do
        if ! [[ " ${initial_enabled_shares[*]} " =~ " ${share} " ]]; then
            echo "Enabling share: [${share}]"; toggle_samba_share_status "${share}" "enable"; changes_made=true
        fi
    done

    if $changes_made;
    then
        clear
        dialog --infobox "Applying changes and restarting Samba..." 5 50
        if restart_samba; then ui_message_box "Samba shares updated successfully." "Success"; 
        else ui_message_box "Error: Failed to restart Samba." "Error"; fi
    else
        dialog --infobox "No changes were made." 5 30; sleep 1
    fi
    _ui_show_completion_message
}

ui_add_samba_share() {
    if ! _get_share_text_options_from_form "Step 1: Add Share Details"; then _ui_show_cancel_message; return; fi
    if [[ -z "${share_name}" || -z "${share_path}" ]]; then ui_message_box "'Share Name' and 'Share Path' are required." "Error"; return; fi
    if [[ ! "${share_path}" =~ ^/ ]]; then ui_message_box "'Share Path' must be an absolute path." "Error"; return; fi
    
    _get_share_boolean_options_from_dialogs
    if ! _ensure_share_directory_exists; then _ui_show_cancel_message; return; fi
    _confirm_and_apply_share "add"
}

ui_modify_samba_share() {
    local shares_raw; shares_raw=$(get_samba_shares)
    if [[ -z "$shares_raw" ]]; then ui_message_box "No configurable share profiles found to modify." "Info"; return; fi
    
    local radiolist_options=()
    read -r -a shares_array <<< "$shares_raw"
    for (( i=0; i<${#shares_array[@]}; i+=2 )); do radiolist_options+=("${shares_array[i]}" "" "off"); done

    local share_to_modify
    share_to_modify=$(ui_create_selection "radiolist" "Samba" "Select a share profile to MODIFY" "Select share:" 20 70 15 "${radiolist_options[@]}")
    
    if [[ "$share_to_modify" == "CANCEL" || -z "$share_to_modify" ]]; then
        _ui_show_cancel_message; return
    fi

    local current_settings
    current_settings=$(get_config_section "/etc/samba/smb.conf" "${share_to_modify}")
    
    declare -A current_values_map
    parse_config_to_array current_values_map <<< "${current_settings}"
    
    if [[ "${current_values_map["read only"]}" == "yes" ]]; then current_values_map["writable"]="no"; fi

    if ! _get_share_text_options_from_form "Modify Share Details: [${share_to_modify}]" "${share_to_modify}" \
        "${current_values_map[path]}" "${current_values_map[comment]}" "${current_values_map[valid users]}" \
        "${current_values_map[admin users]}" "${current_values_map[force user]}" "${current_values_map[force group]}" \
        "${current_values_map[create mask]}" "${current_values_map[directory mask]}"; then _ui_show_cancel_message; return; fi

    _get_share_boolean_options_from_dialogs 
        "${current_values_map[writable]:-yes}" "${current_values_map[browseable]:-yes}" "${current_values_map[guest ok]:-no}"
    
    _confirm_and_apply_share "modify"
}

ui_delete_samba_share() {
    local shares_raw; shares_raw=$(get_samba_shares)
    if [[ -z "$shares_raw" ]]; then ui_message_box "No configurable share profiles found to delete." "Info"; return; fi
    
    local radiolist_options=()
    read -r -a shares_array <<< "$shares_raw"
    for (( i=0; i<${#shares_array[@]}; i+=2 )); do radiolist_options+=("${shares_array[i]}" "" "off"); done

    local share_to_delete
    share_to_delete=$(ui_create_selection "radiolist" "Samba" "Select a share profile to DELETE" "Select share:" 20 70 15 "${radiolist_options[@]}")
    
    if [[ "$share_to_delete" == "CANCEL" || -z "$share_to_delete" ]]; then
        _ui_show_cancel_message; return
    fi

    if ui_confirm "Are you sure you want to PERMANENTLY DELETE the share '[${share_to_delete}]'?" "Confirm Deletion" 10 60;
    then
        clear; delete_samba_share "${share_to_delete}" && restart_samba
        _ui_show_completion_message
    else
        _ui_show_cancel_message
    fi
}

ui_list_samba_users() {
    local user_list; user_list=$(list_samba_users)
    if [[ -z "$user_list" ]]; then ui_message_box "No Samba users found." "Info"; return; fi
    
    local tmp_file; tmp_file=$(mktemp)
    echo "${user_list}" > "${tmp_file}"
    ui_show_textbox "${tmp_file}" "Samba User List" 20 70
    rm -f "${tmp_file}"
}

ui_add_samba_user() {
    local system_users_raw samba_users_raw available_users_raw
    local radiolist_options=()

    system_users_raw=$(awk -F: '$3 >= 1000 && $3 < 60000 {print $1}' /etc/passwd | sort)
    
    if command -v pdbedit &> /dev/null; then
        samba_users_raw=$(pdbedit -L | cut -d: -f1 | sort)
    else
        samba_users_raw=""
    fi
    
    available_users_raw=$(comm -23 <(echo "$system_users_raw") <(echo "$samba_users_raw"))
    
    if [[ -z "$available_users_raw" ]]; then
        ui_message_box "No eligible system users found to add to Samba.\n(Only system users with UID >= 1000 not already in Samba are shown)." "Info"
        return
    fi
    
    while read -r user; do
        if [[ -n "$user" ]]; then
            radiolist_options+=("$user" "" "off")
        fi
    done <<< "$available_users_raw"
    
    local username
    username=$(ui_create_selection "radiolist" "Samba" "Select a system user to add to Samba" "Select user:" 20 70 15 "${radiolist_options[@]}")
    
    if [[ "$username" == "CANCEL" || -z "$username" ]]; then
        _ui_show_cancel_message; return
    fi
    
    local password password_confirm
    password=$(ui_password_box "Enter new Samba password for '${username}':" "Samba Password")
    if [[ $? -ne 0 ]]; then return; fi
    
    password_confirm=$(ui_password_box "Confirm Samba password:" "Samba Password")
    if [[ $? -ne 0 ]]; then return; fi
    
    if [[ "$password" != "$password_confirm" ]]; then
        ui_message_box "Passwords do not match." "Error"; return
    fi
    
    clear
    if add_samba_user_interactively "$username" "$password" "$password_confirm"; then
        ui_message_box "Samba user '${username}' added successfully." "Success"
    else
        ui_message_box "Failed to add Samba user. Please check the terminal output for details." "Error"
    fi
    _ui_show_completion_message
}

ui_delete_samba_user() {
    local user_list_raw; user_list_raw=$(list_samba_users)
    if [[ -z "$user_list_raw" ]]; then ui_message_box "No Samba users found to delete." "Info"; return; fi
    
    local radiolist_options=()
    while IFS= read -r line; do
        local user=$(echo "$line" | sed 's/^ - //')
        if [[ -n "$user" ]]; then radiolist_options+=("$user" "" "off"); fi
    done <<< "$user_list_raw"

    local user_to_delete
    user_to_delete=$(ui_create_selection "radiolist" "Samba" "Select a Samba user to DELETE" "Select user:" 20 70 15 "${radiolist_options[@]}")
    
    if [[ "$user_to_delete" == "CANCEL" || -z "$user_to_delete" ]]; then
        _ui_show_cancel_message; return
    fi

    if ui_confirm "Are you sure you want to PERMANENTLY DELETE Samba user '${user_to_delete}'?" "Confirm Deletion"; then
        clear
        if delete_samba_user "${user_to_delete}"; then
            ui_message_box "Samba user '${user_to_delete}' deleted successfully." "Success"
        else
            ui_message_box "Failed to delete Samba user." "Error"
        fi
        _ui_show_completion_message
    else
        _ui_show_cancel_message
    fi
}