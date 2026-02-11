#!/bin/bash
# ==============================================================================
# 파일명: storage.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi (Refactored by Gemini)
# 설명: 'server.conf'에 정의된 프로필을 기반으로 모든 스토리지 작업을 자동화.
# 의존성: install_package.sh (sync_package 함수 제공), base/profile_engine.sh (설정 관리)
# ==============================================================================

# Bash 확장 패턴 매칭 활성화
shopt -s extglob

# ==============================================================================
# 초기화
# ==============================================================================

_initialize_storage_utils() {
    # ensure_packages_installed 함수를 사용하여 패키지 확인 및 설치
    ensure_packages_installed "PACKAGES_LIST" "Storage Management Utils" "lvm2" "parted" "xfsprogs" "cifs-utils" || return $?
    log_success "Storage management utility initialized successfully."
    return 0
}

_initialize_storage_utils

# ==============================================================================
# --- 2. 저수준 보조 함수 (Low-Level Helpers) ---
# ==============================================================================

##
# @description UUID=... 또는 PTUUID=... 또는 경로를 받아 실제 장치 경로를 반환
resolve_device_path() {
    local input_path="$1"
    local resolved_path=""

    if [[ "$input_path" == UUID=* ]]; then
        resolved_path=$(blkid -U "${input_path#UUID=}")
    elif [[ "$input_path" == PTUUID=* ]]; then
        resolved_path=$(blkid -t PTUUID="${input_path#PTUUID=}" -o device | head -n 1)
    fi

    if [[ -n "$resolved_path" ]]; then
        echo "$resolved_path"
        return 0
    fi

    if [[ "$input_path" == UUID=* || "$input_path" == PTUUID=* ]]; then
        return 1
    fi

    echo "$input_path"
    return 0
}

##
# @description 입력된 장치 목록을 해석하여 실제 경로와 영구적 ID 목록을 생성
resolve_and_collect_devices() {
    local input_string="$1"
    
    G_RESOLVED_DEVICES=()
    local persistent_ids_arr=()
    G_NEEDS_UPDATE=false

    read -r -a input_array <<< "$input_string"
    
    for dev_input in "${input_array[@]}"; do
        local resolved_dev
        resolved_dev=$(resolve_device_path "$dev_input") || {
            log_error "Could not resolve device: $dev_input"
            return 1
        }
        G_RESOLVED_DEVICES+=("$resolved_dev")

        if [[ "$dev_input" == UUID=* || "$dev_input" == PTUUID=* ]]; then
            persistent_ids_arr+=("$dev_input")
        else
            local dev_ptuuid
            dev_ptuuid=$(blkid -s PTUUID -o value "$resolved_dev" 2>/dev/null)
            if [[ -n "$dev_ptuuid" ]]; then
                persistent_ids_arr+=("PTUUID=${dev_ptuuid}")
                G_NEEDS_UPDATE=true
            else
                persistent_ids_arr+=("$dev_input")
            fi
        fi
    done
    
    G_PERSISTENT_IDS="${persistent_ids_arr[*]}"
    return 0
}

##
# @description 설정 파일의 값을 업데이트 (Self-Healing)
update_profile_config() {
    local conf_file="$1"
    local profile_name="$2"
    local key="$3"
    local value="$4"
    
    if [[ -n "$conf_file" && -n "$value" ]]; then
        log_info "[Self-Healing] Updating '$key' for profile '${profile_name}'..."
        if command -v set_config_value &>/dev/null; then
            set_config_value "$conf_file" "$profile_name" "$key" "$value"
        else
            log_warn "set_config_value command not found. Skipping config update."
        fi
    fi
}

validate_disk_device() {
    local disk_device="$1"
    [[ ! -b "$disk_device" ]] && return 1
    local disk_type; disk_type=$(lsblk -dno TYPE "${disk_device}" 2>/dev/null)
    [[ "${disk_type}" != "disk" ]] && return 1
    return 0
}

get_device_uuid() {
    local device="$1"
    local uuid; uuid=$(blkid -s UUID -o value "${device}" 2>/dev/null)
    [[ -n "$uuid" ]] && echo "$uuid" && return 0
    return 1
}

_parse_definition_string() {
    local def_string="$1"
    local target_array_name="$2"
    
    # 세미콜론(;)을 줄바꿈으로 변환하여 정밀 파서(parse_config_to_array)에 전달
    echo "${def_string}" | tr ';' '\n' | parse_config_to_array "${target_array_name}"
}

format_device() {
    local device="$1"; local fs_type="${2:-ext4}"
    if [[ -z "$device" ]]; then log_error "Device path required."; return 1; fi

    local current_fs; current_fs=$(blkid -s TYPE -o value "${device}" 2>/dev/null)
    if [[ "$current_fs" == "$fs_type" ]]; then
        log_info "Device '${device}' is already formatted with ${fs_type}."
        return 0
    fi

    log_info "Formatting '${device}' with '${fs_type}'..."
    local output
    case "$fs_type" in
        "ext4") 
            if ! output=$(${G_SUDO_PREFIX} mkfs.ext4 -F "${device}" 2>&1); then
                log_error "Format failed for '${device}'. Reason: ${output}"
                return 1
            fi
            ;;
        "xfs")  
            if ! output=$(${G_SUDO_PREFIX} mkfs.xfs -f "${device}" 2>&1); then
                log_error "Format failed for '${device}'. Reason: ${output}"
                return 1
            fi
            ;;
        *) 
            log_error "Unsupported filesystem: ${fs_type}"
            return 1 
            ;;
    esac
    
    log_success "Format complete."
}

manage_fstab_entry() {
    local device="$1"; local mount_point="$2"; local fs_type="$3"; local options="${4:-defaults}"
    
    if grep -q " ${mount_point} " /etc/fstab; then
        log_info "Removing existing fstab entry for '${mount_point}'."
        ${G_SUDO_PREFIX} sed -i.bak "\_ ${mount_point} _d" /etc/fstab
    fi

    [[ ! -d "${mount_point}" ]] && ${G_SUDO_PREFIX} mkdir -p "${mount_point}"

    local fstab_device="${device}"
    if [[ "$fs_type" != "cifs" ]]; then
        local uuid
        if uuid=$(get_device_uuid "${device}"); then
            fstab_device="UUID=${uuid}"
            log_info "Resolved '${device}' to '${fstab_device}' for persistence."
        else
            log_warn "Could not resolve UUID for '${device}'. Using device path."
        fi
    fi

    local fstab_entry="${fstab_device} ${mount_point} ${fs_type} ${options} 0 0"
    log_info "Adding to /etc/fstab: ${fstab_entry}"
    echo "${fstab_entry}" | ${G_SUDO_PREFIX} tee -a /etc/fstab > /dev/null
}

apply_mounts() {
    log_info "Reloading daemon and mounting all filesystems..."
    if ${G_SUDO_PREFIX} systemctl daemon-reload && ${G_SUDO_PREFIX} mount -a; then
        log_success "All mounts applied successfully."
    else
        log_error "Mount failed. Check fstab or device status."
        return 1
    fi
}

create_pv() {
    local devices=("$@")
    if [[ ${#devices[@]} -eq 0 ]]; then return 0; fi

    for device in "${devices[@]}"; do
        if ! ${G_SUDO_PREFIX} pvs "${device}" &>/dev/null; then
            log_info "Creating PV on '${device}'..."
            if ! output=$(${G_SUDO_PREFIX} pvcreate "${device}" 2>&1); then
                log_error "Failed to create PV on '${device}'. Reason: ${output}"
                return 1
            fi
        fi
    done
}

manage_vg() {
    local vg_name="$1"; shift; local desired_devices=("$@")
    if [[ ${#desired_devices[@]} -eq 0 ]]; then return 1; fi

    if ! ${G_SUDO_PREFIX} vgs "${vg_name}" &>/dev/null; then
        log_info "Creating new VG '${vg_name}'..."
        if ! output=$(${G_SUDO_PREFIX} vgcreate "${vg_name}" "${desired_devices[@]}" 2>&1); then
            log_error "Failed to create VG '${vg_name}'. Reason: ${output}"
            return 1
        fi
        return 0
    fi

    local current_pvs; current_pvs=$(${G_SUDO_PREFIX} pvs --noheadings -o pv_name,vg_name | awk -v vg="${vg_name}" '$2 == vg {print $1}')
    for device in "${desired_devices[@]}"; do
        if ! echo "${current_pvs}" | grep -q -w "${device}"; then
            log_info "Extending VG '${vg_name}' with '${device}'..."
            if ! output=$(${G_SUDO_PREFIX} vgextend "${vg_name}" "${device}" 2>&1); then
                log_error "Failed to extend VG. Reason: ${output}"
                return 1
            fi
        fi
    done
}

create_lv() {
    local lv_name="$1"; local vg_name="$2"; local size="$3"; local type="$4"; shift 4; local devices=("$@")
    local lv_path="/dev/${vg_name}/${lv_name}"
    if [[ -e "${lv_path}" ]]; then return 0; fi

    local cmd=(lvcreate -y -n "${lv_name}")
    [[ "${size}" == *"%"* ]] && cmd+=(-l "${size}") || cmd+=(-L "${size}")
    [[ -n "${type}" ]] && cmd+=(--type "${type}")
    cmd+=("${vg_name}")
    [[ ${#devices[@]} -gt 0 ]] && cmd+=("${devices[@]}")
    
    log_info "Creating LV '${lv_name}'..."
    if ! output=$(${G_SUDO_PREFIX} "${cmd[@]}" 2>&1); then
        log_error "Failed to create LV '${lv_name}'. Reason: ${output}"
        return 1
    fi
}

create_and_format_lvm_lv() {
    local lv_name="$1"; local vg_name="$2"; local size="$3"; local type="$4"; local fs_type="$5"
    shift 5
    local devices=("$@")
    create_lv "$lv_name" "$vg_name" "$size" "$type" "${devices[@]}" || return 1
    format_device "/dev/${vg_name}/${lv_name}" "$fs_type" || return 1
}

create_and_get_partition() {
    local disk_device="$1"
    if ! validate_disk_device "$disk_device"; then return 1; fi

    local part_device="${disk_device}1"
    [[ "$disk_device" == *nvme* ]] && part_device="${disk_device}p1"

    if [[ -b "$part_device" ]]; then
        log_info "Partition '${part_device}' already exists."
        echo "$part_device"
        return 0
    fi

    log_info "Creating partition on '${disk_device}'."
    if ! output=$(${G_SUDO_PREFIX} parted -s -a optimal "${disk_device}" -- mklabel gpt mkpart primary 0% 100% 2>&1); then
        log_error "Partition creation failed. Reason: ${output}"
        return 1
    fi
    ${G_SUDO_PREFIX} partprobe "${disk_device}" && ${G_SUDO_PREFIX} udevadm settle
    
    [[ -b "$part_device" ]] && echo "$part_device" && return 0
    return 1
}

create_and_mount_direct_partitions() {
    local source_disk="$1"; local fs_type="$2"
    shift 2
    local part_definitions=("$@")

    local existing_parts_count; existing_parts_count=$(lsblk -ln -o TYPE "${source_disk}" | grep -c "part")
    if [[ "${existing_parts_count}" -eq 0 ]]; then
        log_info "Creating partitions on '${source_disk}'."
        local cmd=(parted -s -a optimal "${source_disk}" -- mklabel gpt)
        local start_percent=0
        for def in "${part_definitions[@]}"; do
            local size_str; size_str=${def#*size=}
            size_str=${size_str%%;*}
            local size_val
            [[ "$size_str" == *% ]] && size_val=${size_str%%%*} || size_val=$(echo "$size_str" | tr -dc '0-9')
            local end_percent=$((start_percent + size_val))
            [[ "$end_percent" -gt 100 ]] && end_percent=100
            cmd+=("mkpart" "primary" "${fs_type}" "${start_percent}%" "${end_percent}%")
            start_percent=$end_percent
        done
        if ! output=$(${G_SUDO_PREFIX} "${cmd[@]}" 2>&1); then
            log_error "Partitioning failed. Reason: ${output}"
            return 1
        fi
        ${G_SUDO_PREFIX} partprobe "${source_disk}" && ${G_SUDO_PREFIX} udevadm settle
    else
        log_info "Partitions already exist on '${source_disk}'. Skipping creation."
    fi

    local counter=1
    for def in "${part_definitions[@]}"; do
        local mount_point; mount_point=${def#*mount=}
        mount_point=${mount_point%%;*}
        
        if [[ -z "${mount_point}" || "${mount_point}" == "none" ]]; then
            counter=$((counter + 1))
            continue
        fi
        
        local target_device="${source_disk}${counter}"
        [[ ! -b "$target_device" ]] && target_device="${source_disk}p${counter}"
        
        if [[ ! -b "$target_device" ]]; then
            log_error "Partition device '${target_device}' not found."
            return 1
        fi
        
        format_device "$target_device" "$fs_type" || return 1
        manage_fstab_entry "$target_device" "$mount_point" "$fs_type" || return 1
        counter=$((counter + 1))
    done
    apply_mounts || return 1
}

# ==============================================================================
# --- 3. 고수준 프로필 실행기 (High-Level Profile Executors) ---
# ==============================================================================

apply_cifs_profile() {
    local profile_name="$1"; declare -n profile_data_ref="$2"
    local remote_server="${profile_data_ref[REMOTE_SERVER]}"
    local remote_path="${profile_data_ref[REMOTE_PATH]}"
    local mount_point="${profile_data_ref[MOUNT_POINT]}"
    local options="${profile_data_ref[OPTIONS]:-defaults}"
    local cifs_credential="${profile_data_ref[CIFS_CREDENTIAL]}"

    if [[ -z "$remote_server" || -z "$remote_path" || -z "$mount_point" || -z "$cifs_credential" ]]; then
        log_error "Missing CIFS parameters."; return 1
    fi
    if [[ ! -f "$cifs_credential" ]]; then log_error "Credential file not found."; return 1; fi

    local source="//${remote_server}/${remote_path}"
    local opts="credentials=${cifs_credential},${options}"
    
    if findmnt --source "${source}" --target "${mount_point}" &>/dev/null; then
        log_info "CIFS share already mounted."
        return 0
    fi
    
    manage_fstab_entry "${source}" "${mount_point}" "cifs" "${opts}" && apply_mounts
}

apply_direct_profile() {
    local profile_name="$1"; declare -n profile_data_ref="$2"
    local fs_type="${profile_data_ref[FSTYPE]:-ext4}"
    local conf_file="${profile_data_ref[_CONF_FILE]}"

    resolve_and_collect_devices "${profile_data_ref[SOURCE_DISK]}" || return 1
    local source_disk="${G_RESOLVED_DEVICES[0]}"
    
    if ! validate_disk_device "$source_disk"; then
        log_error "Invalid disk: ${source_disk}"; return 1
    fi

    local -a parts=()
    for key in "${!profile_data_ref[@]}"; do
        [[ "$key" == "DEFINE_PARTITION_"* ]] && parts+=("${profile_data_ref[$key]}")
    done
    if [[ ${#parts[@]} -eq 0 ]]; then log_error "No partitions defined."; return 1; fi

    create_and_mount_direct_partitions "$source_disk" "$fs_type" "${parts[@]}" || return 1

    if [[ "$G_NEEDS_UPDATE" == "true" ]]; then
        update_profile_config "$conf_file" "$profile_name" "SOURCE_DISK" "${G_PERSISTENT_IDS}"
    fi
    return 0
}

apply_lvm_profile() {
    local profile_name="$1"; declare -n profile_data_ref="$2"
    local fs_type="${profile_data_ref[FSTYPE]:-ext4}"
    local vg_name="${profile_data_ref[VG_NAME]}"
    local conf_file="${profile_data_ref[_CONF_FILE]}"
    
    if [[ -z "$vg_name" ]]; then log_error "VG_NAME missing."; return 1; fi

    resolve_and_collect_devices "${profile_data_ref[VG_DEVICES]}" || return 1
    local -a vg_devices=("${G_RESOLVED_DEVICES[@]}")
    local persistent_ids="${G_PERSISTENT_IDS}"
    local needs_vg_update="${G_NEEDS_UPDATE}"

    create_pv "${vg_devices[@]}" || return 1
    manage_vg "${vg_name}" "${vg_devices[@]}" || return 1

    local -a lv_defs=()
    for key in "${!profile_data_ref[@]}"; do
        [[ "$key" == "DEFINE_LV_"* ]] && lv_defs+=("${key}=${profile_data_ref[$key]}")
    done
    
    for def in "${lv_defs[@]}"; do
        local lv_name; lv_name=${def#*DEFINE_LV_}; lv_name=${lv_name%%=*}
        declare -A params; _parse_definition_string "${def#*=}" "params"
        
        local -a devs=()
        if [[ -n "${params[devices]}" ]]; then
            read -r -a d_arr <<< "${params[devices]}"
            for d in "${d_arr[@]}"; do
                if [[ "$d" == LV:* ]]; then
                    local dep="/dev/${vg_name}/${d#LV:}"
                    [[ ! -e "$dep" ]] && log_error "LV dependency '$dep' missing." && return 1
                    devs+=("$dep")
                else
                    devs+=("$d")
                fi
            done
        fi
        create_and_format_lvm_lv "$lv_name" "$vg_name" "${params[size]}" "${params[type]}" "$fs_type" "${devs[@]}" || return 1
    done

    if [[ -n "${profile_data_ref[CACHE_TARGET]}" && -n "${profile_data_ref[CACHE_DEVICE]}" ]]; then
        local target="${profile_data_ref[CACHE_TARGET]}"
        resolve_and_collect_devices "${profile_data_ref[CACHE_DEVICE]}" || return 1
        local cache_dev="${G_RESOLVED_DEVICES[0]}"
        
        local cache_pv; cache_pv=$(create_and_get_partition "$cache_dev") || return 1
        local target_path="/dev/${vg_name}/${target}"
        
        if [[ $(lvs -o attr --noheadings "$target_path" 2>/dev/null | xargs) != C* ]]; then
            log_info "Attaching cache to '$target'..."
            if ! pvs --noheadings -o vg_name "$cache_pv" 2>/dev/null | grep -q "$vg_name"; then
                create_pv "$cache_pv" && vgextend "$vg_name" "$cache_pv" || return 1
            fi
            local pool="${target}_cachepool"
            create_lv "$pool" "$vg_name" "100%FREE" "" "$cache_pv" || return 1
            ${G_SUDO_PREFIX} lvconvert -y --type cache --cachepool "/dev/${vg_name}/${pool}" "$target_path" || return 1
        fi
        
        if [[ "$G_NEEDS_UPDATE" == "true" ]]; then
            update_profile_config "$conf_file" "$profile_name" "CACHE_DEVICE" "${G_PERSISTENT_IDS}"
        fi
    fi

    if [[ -n "${profile_data_ref[MOUNT_TARGET]}" && -n "${profile_data_ref[MOUNT_POINT]}" ]]; then
        local final_dev="/dev/${vg_name}/${profile_data_ref[MOUNT_TARGET]}"
        [[ ! -e "$final_dev" ]] && log_error "Mount target missing." && return 1
        manage_fstab_entry "$final_dev" "${profile_data_ref[MOUNT_POINT]}" "$fs_type" || return 1
        apply_mounts || return 1
    fi

    if [[ "$needs_vg_update" == "true" ]]; then
        update_profile_config "$conf_file" "$profile_name" "VG_DEVICES" "${persistent_ids}"
    fi
    return 0
}

unmount_storage_profile() {
    local profile_name="$1"; declare -n profile_data_ref="$2"
    local mount_point="${profile_data_ref[MOUNT_POINT]}"
    
    if [[ -z "$mount_point" && "${profile_data_ref[PROFILE_TYPE]}" == "direct" ]]; then
         local part_def="${profile_data_ref[DEFINE_PARTITION_1]}"
         local temp; temp=${part_def#*mount=}; mount_point=${temp%%;*}
    fi
    
    if [[ -z "$mount_point" || "$mount_point" == "none" ]]; then
        log_warn "No mount point to unmount for '${profile_name}'."
        return 0
    fi

    if findmnt -rno TARGET "${mount_point}" >/dev/null; then
        ${G_SUDO_PREFIX} umount "${mount_point}" || return 1
        log_success "Unmounted '${mount_point}'."
    fi
    
    if grep -q " ${mount_point} " /etc/fstab; then
        ${G_SUDO_PREFIX} sed -i.bak "\_ ${mount_point} _d" /etc/fstab
        ${G_SUDO_PREFIX} systemctl daemon-reload
    fi
    return 0
}

apply_storage_profile() {
    local profile_name="$1"; declare -n profile_data_ref="$2"
    local type="${profile_data_ref[PROFILE_TYPE]}"
    
    case "$type" in
        "direct") apply_direct_profile "$profile_name" "$2" ;;
        "lvm")    apply_lvm_profile "$profile_name" "$2" ;;
        "cifs")   apply_cifs_profile "$profile_name" "$2" ;;
        *) log_error "Unknown type: $type"; return 1 ;;
    esac
}

apply_all_storage_profiles() {
    local conf_file="$1"; shift; local profiles=("$@")
    [[ ! -f "$conf_file" ]] && log_error "Config not found." && return 1
    [[ ${#profiles[@]} -eq 0 ]] && return 0

    for profile in "${profiles[@]}"; do
        log_info "--------------------------------------------------"
        log_info "Processing: [${profile}]"
        declare -A p_data
        parse_config_to_array "p_data" < <(get_config_section "${conf_file}" "${profile}")
        p_data["_CONF_FILE"]="$conf_file"
        
        [[ ${#p_data[@]} -eq 0 ]] && continue
        apply_storage_profile "${profile}" "p_data" || return 1
    done
    log_info "--------------------------------------------------"
}
