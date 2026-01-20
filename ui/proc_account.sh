#!/bin/bash
# ==============================================================================
# 파일명: proc_account.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: account.sh의 기능을 활용하여 계정 및 그룹 관리를 위한 모든 사용자 인터페이스를 제공.
# 필요: dialog, account.sh (백엔드 로직)
# ==============================================================================

# ==============================================================================
# --- UI 헬퍼 함수 ---
# ==============================================================================

_ui_show_completion_message() {
    ui_message_box "Operation completed." "Success" 8 60
    sleep 1
}

_ui_show_cancel_message() {
    ui_message_box "Operation canceled." "Cancelled" 8 60
}

##
# @description 'dialog' UI를 통해 비밀번호 입력을 받고, 지정된 백엔드 함수를 호출합니다.
#
ui_handle_password_change() {
    local target_user="$1"
    local purpose="$2"
    local backend_func="$3"

    while true; do
        local password
        password=$(ui_password_box "Enter new ${purpose} password for '${target_user}':" "Password Change")
        if [[ $? -ne 0 ]]; then return 2; fi # 취소

        local password_confirm
        password_confirm=$(ui_password_box "Re-enter ${purpose} password:" "Password Change")
        if [[ $? -ne 0 ]]; then return 2; fi # 취소

        if [[ "${password}" == "${password_confirm}" ]]; then
            if [[ -z "${password}" ]]; then
                ui_message_box "Password cannot be empty. Please try again." "Error" 8 60
                continue
            fi

            if "${backend_func}" "${target_user}" "${password}" "${password_confirm}"; then
                return 0 # 성공
            else
                ui_message_box "An error occurred while running the backend task." "Error" 8 60
                return 1 # 실패
            fi
        else
            ui_message_box "Passwords do not match. Please try again." "Error" 8 60
        fi
    done
}

# ==============================================================================
# --- 그룹 관리 UI ---
# ==============================================================================

ui_add_group() {
    local group_name
    group_name=$(ui_input_box "Enter the name of the group to add:" "Add Group" "" 8 60)
    
    if [[ $? -ne 0 || -z "$group_name" ]]; then
        _ui_show_cancel_message; return
    fi
    
    clear
    add_system_group "$group_name"
    _ui_show_completion_message
}

ui_modify_group_members() {
    local group_list=()
    while read -r group; do
        group_list+=("$group" "")
    done < <(awk -F: '$3 >= 1000 && $1 != "nogroup" {print $1}' /etc/group)

    if [[ ${#group_list[@]} -eq 0 ]]; then
        ui_message_box "No available groups to modify." "Error" 8 60; return
    fi

    local selected_group
    selected_group=$(ui_create_menu "Group Management" "Modify Group Members" "Select a group to modify:" 15 50 10 "${group_list[@]}")

    if [[ "$selected_group" == "CANCEL" ]]; then
        _ui_show_cancel_message; return
    fi

    local all_users_str; all_users_str=$(list_system_users)
    read -ra all_users <<< "$all_users_str"

    if [[ ${#all_users[@]} -eq 0 ]]; then
        ui_message_box "No standard users found in the system." "Error" 8 50; return
    fi

    local current_members_str
    current_members_str=$(getent group "$selected_group" | cut -d: -f4 | tr ',' ' ')
    
    declare -A current_members_map
    for member in $current_members_str; do
        current_members_map["$member"]=1
    done

    local checklist_options=()
    for user in "${all_users[@]}"; do
        local status="off"
        if [[ -n "${current_members_map[$user]}" ]]; then
            status="on"
        fi
        checklist_options+=("$user" "" "$status")
    done

    local selected_users_str
    selected_users_str=$(ui_create_checklist "Group Management" "Modify Members of '$selected_group'" \
        "Select users to be in the group (Space to select/deselect):" 20 60 15 \
        "${checklist_options[@]}")
    
    if [[ "$selected_users_str" == "CANCEL" ]]; then
        _ui_show_cancel_message; return
    fi
    
    selected_users_str="${selected_users_str//\"/}"
    read -ra selected_users <<< "$selected_users_str"
    
    declare -A selected_members_map
    for user in "${selected_users[@]}"; do
        selected_members_map["$user"]=1
    done

    local users_to_add=()
    local users_to_remove=()

    for user in "${selected_users[@]}"; do
        if [[ -z "${current_members_map[$user]}" ]]; then
            users_to_add+=("$user")
        fi
    done

    for user in "${all_users[@]}"; do
        if [[ -n "${current_members_map[$user]}" && -z "${selected_members_map[$user]}" ]]; then
            users_to_remove+=("$user")
        fi
    done

    if [[ ${#users_to_add[@]} -eq 0 && ${#users_to_remove[@]} -eq 0 ]]; then
        ui_message_box "No changes made to group members." "Info" 8 60; return
    fi

    local summary="Target Group: ${selected_group}\n"
    if [[ ${#users_to_add[@]} -gt 0 ]]; then
        summary+="\n[Adding]: ${users_to_add[*]}"
    fi
    if [[ ${#users_to_remove[@]} -gt 0 ]]; then
        summary+="\n[Removing]: ${users_to_remove[*]}"
    fi

    if ui_confirm "${summary}\n\nProceed with these changes?" "Confirm Changes" 15 60; then
        clear
        echo "--- Updating members for group '$selected_group' ---"
        if [[ ${#users_to_add[@]} -gt 0 ]]; then
            manage_group_members "$selected_group" "add" "${users_to_add[*]}"
        fi
        if [[ ${#users_to_remove[@]} -gt 0 ]]; then
            manage_group_members "$selected_group" "remove" "${users_to_remove[*]}"
        fi
        _ui_show_completion_message
    else
        _ui_show_cancel_message
    fi
}

ui_delete_group() {
    local group_list=()
    while read -r group; do
        group_list+=("$group" "")
    done < <(awk -F: '$3 >= 1000 && $1 != "nogroup" {print $1}' /etc/group)

    if [[ ${#group_list[@]} -eq 0 ]]; then
        ui_message_box "No available groups to delete." "Error" 8 60; return
    fi

    local selected_group
    selected_group=$(ui_create_menu "Group Management" "Delete Group" "Select a group to delete:" 15 50 10 "${group_list[@]}")
    
    if [[ "$selected_group" == "CANCEL" ]]; then
        _ui_show_cancel_message; return
    fi
    
    if ui_confirm "Are you sure you want to delete the group '${selected_group}'?" "Delete Group" 8 60; then
        clear
        delete_system_group "$selected_group"
        _ui_show_completion_message
    else
        _ui_show_cancel_message
    fi
}

# ==============================================================================
# --- 사용자 계정 관리 UI ---
# ==============================================================================

ui_add_user() {
    local home_base="$1"
    
    local values
    values=$(ui_create_form "Add New User" "Enter New User Information" "" 16 60 0 \
        "Username:"                   1 1 "" 1 30 35 0 \
        "Primary Group:"              2 1 "" 2 30 35 0 \
        "Allow Remote Login (yes/no):" 3 1 "no" 3 30 35 0)

    if [[ $? -ne 0 ]]; then
        _ui_show_cancel_message; return
    fi

    local username group_name shell_access
    {
        read -r username
        read -r group_name
        read -r shell_access
    } <<< "$values"
    shell_access=$(echo "$shell_access" | tr '[:upper:]' '[:lower:]')

    if [[ -z "$username" || -z "$group_name" ]]; then
        ui_message_box "Error: Username and Primary Group are required." "Error" 8 50; return
    fi
    
    clear
    echo "--- Starting Add User operation [User: ${username}, Group: ${group_name}] ---"
    
    add_system_group "$group_name"
    
    if ! add_system_user "$username" "$group_name" "no" "$shell_access"; then
        read -rp $'/\nUser creation failed. Press Enter to continue.../'
        return
    fi

    if ! ui_handle_password_change "${username}" "System" "set_password_interactively"; then
        echo "[Warning] System password setup was cancelled or failed. Rolling back..."
        delete_system_user "${username}" "no_home"
        read -rp $'/\nOperation has been rolled back. Press Enter to continue.../'
        return
    fi
    ui_message_box "System password has been updated." "Info" 5 60; sleep 1

    ui_handle_password_change "${username}" "Samba" "add_samba_user_interactively"
    local samba_status=$?
    case $samba_status in
        0) 
            ui_message_box "Samba user has been configured." "Info" 5 60; sleep 1 ;;
        1) 
            echo "[Warning] Samba user setup failed. Rolling back..."
            delete_system_user "${username}" "no_home"
            read -rp $'/\nOperation has been rolled back. Press Enter to continue.../'
            return ;;
        2) 
            ui_message_box "Samba password setup skipped." "Info" 5 60; sleep 1 ;;
    esac

    local user_home_dir="${home_base}/${username}"
    echo "Creating home directory (${user_home_dir}) and setting permissions..."
    sudo mkdir -p "${user_home_dir}"
    sudo chown -R "${username}:${group_name}" "${user_home_dir}"
    
    if [[ ! -L "/home/${username}" ]]; then
        sudo ln -s "${user_home_dir}" "/home/${username}"
        echo "Symbolic link /home/${username} created successfully."
    fi
    
    echo "--- All operations complete ---"
    _ui_show_completion_message
}

ui_delete_user() {
    local home_base="$1"
    
    local user_list=()
    while read -r user; do
        user_list+=("$user" "")
    done < <(awk -F: '$3 >= 1000 && $1 != "nobody" {print $1}' /etc/passwd)

    if [[ ${#user_list[@]} -eq 0 ]]; then
        ui_message_box "There are no available users to delete." "Error" 8 60; return
    fi

    local username
    username=$(ui_create_menu "User Management" "Delete User" "Select a user to delete:" 15 50 10 "${user_list[@]}")
    
    if [[ "$username" == "CANCEL" ]]; then
        _ui_show_cancel_message; return
    fi

    if ui_confirm "Are you sure you want to delete user '${username}' and all related data?" "Confirm Deletion" 10 50; then
        clear
        echo "--- Starting Delete User operation [Target: ${username}] ---"
        delete_samba_user "${username}"
        delete_system_user "${username}" "${home_base}"
        echo "--- All operations complete ---"
        _ui_show_completion_message
    else
        _ui_show_cancel_message
    fi
}

ui_modify_user() {
    local users_raw; users_raw=$(list_system_users)
    if [[ -z "$users_raw" ]]; then
        ui_message_box "No standard users found to modify." "Error" 8 50; return
    fi
    
    local radiolist_options=(); read -r -a users_array <<< "$users_raw"
    for user in "${users_array[@]}"; do radiolist_options+=("$user" "" "off"); done
    
    # ui_create_selection "radiolist" 사용
    local target_user
    target_user=$(ui_create_selection "radiolist" "Step 1: Select User" "Select a user to modify:" "Select a user to modify:" 20 70 15 "${radiolist_options[@]}")
    
    if [[ "$target_user" == "CANCEL" || -z "$target_user" ]]; then
        _ui_show_cancel_message; return
    fi

    local details; details=$(get_user_details "${target_user}")
    local current_group; current_group=$(echo "$details" | cut -d';' -f1)
    local current_home; current_home=$(echo "$details" | cut -d';' -f2)
    local current_shell; current_shell=$(echo "$details" | cut -d';' -f3)

    local values
    values=$(ui_create_form "Step 2: Edit Information for '${target_user}'" "Modify User" "Leave a field empty to keep the current value." 20 70 0 \
        "New Primary Group:"  1 1 "${current_group}" 1 25 30 0 \
        "New Home Directory:" 2 1 "${current_home}"  2 25 60 0 \
        "New Login Shell:"    3 1 "${current_shell}"  3 25 60 0)
    
    if [[ $? -ne 0 ]]; then
        _ui_show_cancel_message; return
    fi

    local new_group new_home new_shell
    {
        read -r new_group
        read -r new_home
        read -r new_shell
    } <<< "$values"

    local password_changed=false
    if ui_confirm "Do you also want to change the password for '${target_user}'?" "Step 3: Change Password" 8 60; then
        if ui_handle_password_change "${target_user}" "System" "set_password_interactively"; then
            password_changed=true
        fi
    fi

    local options_str=""; local changes_summary="Proposed changes for '${target_user}':\n"; local other_changes_made=false
    if [[ -n "$new_group" && "$new_group" != "$current_group" ]]; then
        options_str+="group=${new_group};"; changes_summary+="\n- Group: ${current_group} -> ${new_group}"; other_changes_made=true
    fi
    
    if [[ -n "$new_home" && "$new_home" != "$current_home" ]]; then
        options_str+="home=${new_home};"; changes_summary+="\n- Home: ${current_home} -> ${new_home}"; other_changes_made=true
        if ui_confirm "Do you want to move contents from the old home directory to the new one?" "Move Home?" 8 60;
            then
            options_str+="move_home=yes;"; changes_summary+="\n  (Contents will be moved)"
        fi
    fi
    if [[ -n "$new_shell" && "$new_shell" != "$current_shell" ]]; then
        options_str+="shell=${new_shell};"; changes_summary+="\n- Shell: ${current_shell} -> ${new_shell}"; other_changes_made=true
    fi

    if ! $other_changes_made && ! $password_changed; then
        ui_message_box "No changes were made." "Info" 8 60
        return
    fi
    
    if $other_changes_made; then
        if ui_confirm "${changes_summary}\n\nApply these changes?" "Final Confirmation" 20 70;
            then
            clear
            modify_system_user "${target_user}" "${options_str}"
        else
            _ui_show_cancel_message; return
        fi
    fi

    _ui_show_completion_message
}

# ==============================================================================
# --- 메인 UI ---
# ==============================================================================

ui_account_management() {
    local home_base="$1"
    while true; do
        local choice=$(ui_create_menu \
            "Main Menu > Account Management" \
            "Account and Group Management" \
            "" \
            "20" "60" "15" \
            "ADD_USER"  "Add User" \
            "MOD_USER"  "Modify User" \
            "DEL_USER"  "Delete User" \
            "---"       "------------------" \
            "ADD_GROUP" "Add Group" \
            "MOD_GROUP" "Modify Group Members" \
            "DEL_GROUP" "Delete Group" \
            "---"       "------------------" \
            "BACK"      "Return to Main Menu")

        case "$choice" in
            ADD_USER)   ui_add_user "${home_base}" ;; 
            MOD_USER)   ui_modify_user ;; 
            DEL_USER)   ui_delete_user "${home_base}" ;; 
            ADD_GROUP)  ui_add_group ;; 
            MOD_GROUP)  ui_modify_group_members ;; 
            DEL_GROUP)  ui_delete_group ;; 
            BACK | CANCEL) break ;; 
            *) ui_message_box "Invalid option: ${choice}" "Error" 6 60 ;; 
        esac
    done
}
