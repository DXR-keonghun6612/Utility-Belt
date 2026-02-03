#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/proc_storage.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: storage.sh의 기능을 활용한 스토리지 관리 UI.
# ==============================================================================

# ==============================================================================
# --- UI 헬퍼 및 프로필 생성 ---
# ==============================================================================

_ui_select_storage_device() {
    local mode="$1" # "SINGLE" or "MULTI"
    local title="$2"
    local msg="$3"

    local devices=()
    # NAME, SIZE, MODEL, PTUUID(디스크 식별자) 조회
    while read -r name size model ptuuid; do
        local dev_path="/dev/${name}"
        local display_name="[${dev_path}] ${size} ${model}"
        
        # 저장할 값 결정 (PTUUID가 있으면 우선 사용)
        local value="${dev_path}"
        if [[ -n "$ptuuid" ]]; then
            value="PTUUID=${ptuuid}"
            display_name+=" (ID: ${ptuuid:0:8}...)"
        fi

        if [[ "$mode" == "MULTI" ]]; then
            devices+=("${value}" "${display_name}" "OFF")
        else
            devices+=("${value}" "${display_name}")
        fi
    done < <(lsblk -dno NAME,SIZE,MODEL,PTUUID | grep -vE "^(loop|sr|ram)")

    if [[ ${#devices[@]} -eq 0 ]]; then
        ui_message_box "No suitable physical devices found." "Error"
        return 1
    fi

    local selection
    if [[ "$mode" == "MULTI" ]]; then
        selection=$(ui_create_checklist "$title" "$msg" \
            "Select with Space, Confirm with Enter" 20 80 10 "${devices[@]}")
    else
        selection=$(ui_create_menu "$title" "$msg" \
            "Select a device" 20 80 10 -- "${devices[@]}")
    fi

    if [[ "$selection" == "CANCEL" || -z "$selection" ]]; then
        return 1
    fi

    echo "$selection"
    return 0
}

_ui_manage_cifs_credentials() {
    local cred_file="$1"
    
    # 1. Username & Domain (Combined Form)
    local form_output
    form_output=$(ui_create_form "Create Credential File" "Enter credentials for ${cred_file}" "" 12 60 0 \
        "Username:" 1 1 "" 1 15 30 0 \
        "Domain:"   2 1 "WORKGROUP" 2 15 30 0)
    
    if [[ $? -ne 0 ]]; then return 1; fi

    local username domain
    { read -r username; read -r domain; } <<< "${form_output}"

    if [[ -z "$username" ]]; then
        ui_message_box "Username is required." "Error"; return 1
    fi
    # 도메인이 비어있으면 기본값 설정
    [[ -z "$domain" ]] && domain="WORKGROUP"

    # 2. Password (Masked Input)
    local password
    password=$(ui_password_box "Enter Password:" "Create Credential File")
    if [[ $? -ne 0 || -z "$password" ]]; then return 1; fi

    # 3. Write to file securely with umask 077
    (
        umask 077
        cat <<EOF > "${cred_file}"
username=${username}
password=${password}
domain=${domain}
EOF
    )
    
    ui_message_box "Credential file created successfully:\n${cred_file}" "Success"
}

_ui_form_create_direct_profile() {
    local profile_name="$1"
    local conf_file="$2"
    
    # 1. Select Disk (Single)
    local source_disk
    source_disk=$(_ui_select_storage_device "SINGLE" "Select Source Disk" \
        "Select the disk to format and mount for [${profile_name}]")
    if [[ $? -ne 0 ]]; then return 1; fi

    # 2. Input Mount Point
    local mount_point
    mount_point=$(ui_input_box "Enter Mount Point (e.g., /mnt/data):" "Direct Profile Settings" "")
    if [[ $? -ne 0 || -z "$mount_point" ]]; then 
        ui_message_box "Mount Point is required." "Error"; return 1 
    fi

    add_config_section "${conf_file}" "${profile_name}"

    local -a config_pairs=(
        "PROFILE_TYPE" "direct"
        "SOURCE_DISK" "${source_disk}"
        "DEFINE_PARTITION_1" "size=100%;mount=${mount_point}"
    )

    if set_config_value "${conf_file}" "${profile_name}" "${config_pairs[@]}"; then
        ui_message_box "Profile [${profile_name}] created successfully." "Success"
    else
        ui_message_box "Failed to write profile [${profile_name}] to config file." "Error"
    fi
}

_ui_form_create_cifs_profile() {
    local profile_name="$1"
    local conf_file="$2"
    
    local form_output
    form_output=$(ui_create_form "Create CIFS Profile" "[${profile_name}]" "" 18 70 0 \
        "Remote Server (IP/Hostname):" 1 1 "" 1 30 40 0 \
        "Remote Path (Share Name):"    2 1 "" 2 30 40 0 \
        "Mount Point (Local Path):"    3 1 "" 3 30 40 0)
        
    if [[ $? -ne 0 ]]; then return 1; fi

    local remote_server remote_path mount_point
    { read -r remote_server; read -r remote_path; read -r mount_point; } <<< "${form_output}"
    
    if [[ -z "$remote_server" || -z "$remote_path" || -z "$mount_point" ]]; then
        ui_message_box "All fields are required." "Error"; return 1
    fi
    
    # [기능 추가] Credential 저장 위치 선택
    local loc_choice
    loc_choice=$(ui_create_menu "Credential Location" "Where to save credentials?" \
        "Select storage location for security." 15 60 5 \
        "USER" "User Home (~/.credentials/)" \
        "ROOT" "Root Home (/root/.credentials/)")
    
    if [[ "$loc_choice" == "CANCEL" ]]; then return 1; fi

    local cred_dir
    if [[ "$loc_choice" == "USER" ]]; then
        cred_dir="${HOME}/.credentials"
    else
        cred_dir="/root/.credentials"
        # Root 경로 선택 시 권한 체크 (쓰기 가능 여부 확인은 생성 시점에)
        if [[ "${G_IS_ROOT}" != "true" && -z "${G_SUDO_PREFIX}" ]]; then
            ui_message_box "Root privileges are required to save to /root." "Permission Error"; return 1
        fi
    fi

    # 디렉토리 생성 (필요 시 sudo 사용)
    if [[ ! -d "${cred_dir}" ]]; then
        if [[ "$loc_choice" == "USER" ]]; then
            mkdir -p "${cred_dir}"
        else
            ${G_SUDO_PREFIX} mkdir -p "${cred_dir}"
        fi
    fi
    
    # Credential 파일 경로 및 생성
    local cred_file="${cred_dir}/cifs_${profile_name}"
    
    # _ui_manage_cifs_credentials 함수는 현재 사용자 권한으로 파일을 씁니다.
    # Root 경로인 경우 임시 파일에 쓰고 이동하는 방식이 필요하지만, 
    # 현재 함수 구조상 내부에서 직접 쓰기 때문에 권한 문제가 발생할 수 있습니다.
    # 이를 해결하기 위해 _ui_manage_cifs_credentials 호출 전/후 처리가 복잡해지므로,
    # 해당 함수에 파일 경로만 넘기고, 파일 쓰기 권한은 그 함수 내부나 호출부에서 처리해야 합니다.
    # 하지만 _ui_manage_cifs_credentials는 단순 cat redirection을 사용하므로,
    # 여기서는 임시 파일 패턴을 사용하겠습니다.
    
    local temp_cred
    temp_cred=$(mktemp)
    
    if ! _ui_manage_cifs_credentials "${temp_cred}"; then 
        rm -f "${temp_cred}"; return 1 
    fi

    # 파일 이동 및 권한 설정
    if [[ "$loc_choice" == "USER" ]]; then
        mv "${temp_cred}" "${cred_file}"
        chmod 600 "${cred_file}"
    else
        # sudo를 사용하여 이동 및 권한 설정
        ${G_SUDO_PREFIX} mv "${temp_cred}" "${cred_file}"
        ${G_SUDO_PREFIX} chown root:root "${cred_file}"
        ${G_SUDO_PREFIX} chmod 600 "${cred_file}"
    fi

    add_config_section "${conf_file}" "${profile_name}"

    local uid; uid=$(id -u "${G_ACTUAL_USER}")
    local gid; gid=$(id -g "${G_ACTUAL_USER}")
    
    local -a config_pairs=(
        "PROFILE_TYPE" "cifs"
        "REMOTE_SERVER" "${remote_server}"
        "REMOTE_PATH" "${remote_path}"
        "MOUNT_POINT" "${mount_point}"
        "OPTIONS" "defaults,uid=${uid},gid=${gid},iocharset=utf8"
        "CIFS_CREDENTIAL" "${cred_file}"
    )
    
    if set_config_value "${conf_file}" "${profile_name}" "${config_pairs[@]}"; then
        ui_message_box "Profile [${profile_name}] created successfully." "Success"
    else
        ui_message_box "Failed to write profile [${profile_name}] to config file." "Error"
    fi
}

_ui_form_create_lvm_profile() {
    local profile_name="$1"
    local conf_file="$2"
    
    # 1. VG Name Input
    local vg_name="vg_${profile_name}"
    vg_name=$(ui_input_box "Enter Volume Group Name:" "LVM Configuration" "${vg_name}")
    if [[ $? -ne 0 || -z "$vg_name" ]]; then return 1; fi

    # 2. PV Selection (Multi)
    local selected_devices_str
    selected_devices_str=$(_ui_select_storage_device "MULTI" "Select Physical Volumes (PV)" \
        "Select devices to include in Volume Group '${vg_name}'")
    if [[ $? -ne 0 ]]; then return 1; fi

    local vg_devices="${selected_devices_str//\"/}"

    # 3. LV Configuration (Form)
    local form_output
    form_output=$(ui_create_form "Create Logical Volume" "Configure Logical Volume for [${profile_name}]" "" 16 70 0 \
        "LV Name:"        1 1 "lv_data"    1 20 30 0 \
        "LV Size:"        2 1 "100%FREE"   2 20 30 0 \
        "Filesystem:"     3 1 "ext4"       3 20 30 0 \
        "Mount Point:"    4 1 "/mnt/data"  4 20 30 0)
    
    if [[ $? -ne 0 ]]; then return 1; fi

    local lv_name lv_size fstype mount_point
    { read -r lv_name; read -r lv_size; read -r fstype; read -r mount_point; } <<< "${form_output}"
    
    if [[ -z "$lv_name" || -z "$lv_size" || -z "$fstype" || -z "$mount_point" ]]; then
        ui_message_box "All fields are required." "Error"; return 1
    fi

    # 4. Write to Config
    add_config_section "${conf_file}" "${profile_name}"

    local -a config_pairs=(
        "PROFILE_TYPE" "lvm"
        "VG_NAME" "${vg_name}"
        "VG_DEVICES" "${vg_devices}"
        "DEFINE_LV_${lv_name}" "size=${lv_size}"
        "MOUNT_TARGET" "${lv_name}"
        "MOUNT_POINT" "${mount_point}"
        "FSTYPE" "${fstype}"
    )

    if set_config_value "${conf_file}" "${profile_name}" "${config_pairs[@]}"; then
        ui_message_box "Profile [${profile_name}] created successfully." "Success"
    else
        ui_message_box "Failed to write profile [${profile_name}] to config file." "Error"
    fi
}

# ==============================================================================
# --- 프로필 관리 UI ---
# ==============================================================================

_ui_create_profile() {
    local conf_file="$1"
    
    local profile_name
    profile_name=$(ui_input_box "Enter new profile name:" "Create Profile" "STORAGE_PROFILE_" 8 60)
    if [[ $? -ne 0 || -z "$profile_name" ]]; then ui_message_box "Canceled." "Info"; return; fi

    if grep -q -F "[${profile_name}]" "${conf_file}"; then
        ui_message_box "Profile name '${profile_name}' already exists." "Error"; return
    fi
    
    local type_choice
    type_choice=$(ui_create_menu "Select Profile Type" "Select a type for [${profile_name}]" "" 15 60 5 -- \
        "direct" "Single Partition on a Full Disk" \
        "cifs"   "Samba/CIFS Remote Share" \
        "lvm"    "LVM Stack (Manual Edit Recommended)")

    case "$type_choice" in
        "direct") _ui_form_create_direct_profile "$profile_name" "$conf_file" ;; 
        "cifs")   _ui_form_create_cifs_profile "$profile_name" "$conf_file" ;; 
        "lvm")    _ui_form_create_lvm_profile "$profile_name" "$conf_file" ;; 
        "CANCEL") ui_message_box "Canceled." "Info" ;; 
    esac
}

_ui_delete_profile() {
    local conf_file="$1"
    
    local profile_list=()
    mapfile -t profile_list < <(get_profile_list "${conf_file}" "STORAGE_PROFILE_")
    if [[ ${#profile_list[@]} -eq 0 ]]; then
        ui_message_box "There are no profiles to delete." "No Profiles"; return; fi

    local dialog_options=(); for profile in "${profile_list[@]}"; do dialog_options+=("$profile" ""); done

    local choice
    choice=$(ui_create_menu "Delete Profile" "Select a profile to delete" "" 20 60 15 -- "${dialog_options[@]}")
    if [[ "${choice}" == "CANCEL" ]]; then ui_message_box "Canceled." "Info"; return; fi

    if ! ui_confirm "Are you sure you want to delete profile [${choice}] from the config file?" "Confirm Deletion"; then
        return; fi
    
    if delete_config_section "${conf_file}" "${choice}"; then
        ui_message_box "Profile [${choice}] has been deleted from config." "Success"
    else
        ui_message_box "Failed to delete profile [${choice}]." "Error"
    fi
}

_ui_apply_profiles() {
    local conf_file="$1"

    local profile_list=()
    mapfile -t profile_list < <(get_profile_list "${conf_file}" "STORAGE_PROFILE_")
    if [[ ${#profile_list[@]} -eq 0 ]]; then
        ui_message_box "There are no profiles to apply." "No Profiles"; return; fi

    local dialog_options=()
    for profile in "${profile_list[@]}"; do
        declare -A temp_profile_data
        parse_config_to_array "temp_profile_data" < <(get_config_section "${conf_file}" "${profile}")
        
        local mount_point="${temp_profile_data[MOUNT_POINT]}"
        if [[ -z "$mount_point" && "${temp_profile_data[PROFILE_TYPE]}" == "direct" ]]; then
             local part_def="${temp_profile_data[DEFINE_PARTITION_1]}"
             local temp_mp=${part_def#*mount=}
             mount_point=${temp_mp%%;*}
        fi

        local status="OFF"
        if [[ -n "$mount_point" ]] && findmnt -rno TARGET "${mount_point}" >/dev/null; then
            status="ON"
        fi
        
        dialog_options+=("$profile" "${mount_point:-No Mount Point}" "$status")
    done

    local selected_profiles_str
    selected_profiles_str=$(ui_create_checklist "Apply/Unmount Profiles" "Manage Storage Profiles" \
        "Check to APPLY (Mount), Uncheck to REMOVE (Unmount):" 20 75 15 "${dialog_options[@]}")
    
    if [[ "${selected_profiles_str}" == "CANCEL" ]]; then 
        ui_message_box "Canceled." "Info"; return; 
    fi

    local selected_profiles_arr=($selected_profiles_str)

    if ui_confirm "Proceed with the changes?\n(Selected will be mounted, Unselected will be unmounted)" "Confirm Changes" 10 60; then
        clear
        echo "Processing changes..."
        
        for profile in "${profile_list[@]}"; do
            local is_selected=false
            for selected in "${selected_profiles_arr[@]}"; do
                if [[ "$profile" == "$selected" ]]; then
                    is_selected=true
                    break
                fi
            done

            declare -A profile_data
            parse_config_to_array "profile_data" < <(get_config_section "${conf_file}" "${profile}")
            # [메타 데이터 추가] Self-Healing 기능을 위해 설정 파일 경로 저장
            profile_data["_CONF_FILE"]="$conf_file"

            if [[ "$is_selected" == "true" ]]; then
                echo "[ACTION] Applying profile: $profile"
                apply_storage_profile "$profile" "profile_data"
            else
                echo "[ACTION] Unmounting profile: $profile"
                unmount_storage_profile "$profile" "profile_data"
            fi
        done
        
        read -rp "Completed. Press Enter to continue..."
    fi
}

# ==============================================================================
# --- 상태 조회 및 메인 메뉴 ---
# ==============================================================================

_ui_view_storage_status() {
    local REPORT_FILE; REPORT_FILE=$(mktemp)
    trap 'rm -f "$REPORT_FILE"' RETURN

    {
        printf "■ System Storage Status Report (Generated: %s)\n" "$(date)"
        printf "=======================================================\n\n"
        printf "■ Block Device Overview (lsblk)\n"
        lsblk -o NAME,SIZE,FSTYPE,TYPE,MOUNTPOINT
        printf "\n\n"
        printf "■ Filesystem Usage (df -hT)\n"
        df -hT | sed 's/Mounted on/Mounted_On/'
        printf "\n\n"
        if command -v pvs &> /dev/null && [[ -n "$(pvs -o pv_name --noheadings 2>/dev/null)" ]]; then
            printf "■ LVM Status\n-------------------------------------------------------\n"
            printf ">> Physical Volumes (PVs)\n"; pvs
            printf "\n>> Volume Groups (VGs)\n"; vgs
            printf "\n>> Logical Volumes (LVs)\n"; lvs
        fi
    } > "${REPORT_FILE}"

    ui_show_textbox "${REPORT_FILE}" "Current Storage Status" 30 100
}

ui_storage_management() {
    local conf_file="$1"
    
    while true; do
        local choice=$(ui_create_menu "Storage Management" "Main Menu" "Select an option" 20 70 15 -- \
            "VIEW_STATUS"    "View Current Storage Status" \
            "APPLY_PROFILES" "Select and Apply Profiles" \
            "---"            "-----------------------------" \
            "CREATE_PROFILE" "Create New Storage Profile" \
            "DELETE_PROFILE" "Delete Existing Storage Profile" \
            "EDIT_CONFIG"    "Edit Configuration File (Advanced)" \
            "---"            "-----------------------------" \
            "BACK"           "Return to Main Menu")

        case "$choice" in
            VIEW_STATUS)    _ui_view_storage_status ;; 
            APPLY_PROFILES) _ui_apply_profiles "${conf_file}" ;; 
            CREATE_PROFILE) _ui_create_profile "${conf_file}" ;; 
            DELETE_PROFILE) _ui_delete_profile "${conf_file}" ;; 
            EDIT_CONFIG)
                local editor=${EDITOR:-nano}
                clear; ${editor} "${conf_file}"
                ;; 
            BACK | CANCEL)  break ;; 
        esac
    done
}
