#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/proc_install_application.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: 추가 소프트웨어(NVIDIA, Miniconda, VSCode 등) 설치를 위한 동적 UI.
# ==============================================================================

##
# @description NVIDIA 드라이버 설치를 위한 전용 UI.
#           - 동적 메뉴에서 'NVIDIA Driver' 선택 시 호출됩니다.
#
_ui_install_nvidia_driver() {
    # 이 함수는 복잡한 드라이버 버전 선택 로직을 포함하므로 별도로 유지됩니다.
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
        local driver_name recommended_text
        read -r driver_name recommended_text <<< "$item"
        dialog_options+=("${driver_name}" "${recommended_text}")
    done

    local selected_driver
    selected_driver=$(ui_create_menu "NVIDIA Driver Installation" "Select NVIDIA Driver" \
        "Use SPACE to select the driver. '(recommended)' is the best choice." 20 70 15 -- \
        "${dialog_options[@]}")

    if [[ "${selected_driver}" == "CANCEL" ]]; then
        ui_message_box "No driver was selected." "Canceled"; return
    fi

    local confirm_prompt="You have selected '${selected_driver}'.\n\nThis will automatically remove any other NVIDIA drivers and may require a system reboot. Continue?"
    if ! ui_confirm "${confirm_prompt}" "Confirm Installation"; then
        return
    fi

    clear
    if install_nvidia_driver_logic "${selected_driver}"; then
        ui_message_box "Driver '${selected_driver}' installed.\nA reboot is highly recommended." "Installation Successful"
    else
        ui_message_box "Failed to install '${selected_driver}'. Check the terminal for logs." "Installation Failed"
    fi
    read -rp $'\nCompleted. Press Enter to continue...'
}


##
# @description '추가 소프트웨어 설치' 메인 UI 함수 (동적 체크리스트 방식).
#
ui_install_application() {
    # --- 1. 설정 및 스크립트 스캔 ---
    local install_dir="${SCRIPT_DIR}/script/install/ubuntu"
    
    # 스크립트 파일명 => "UI 표시 이름|설정 파일 키|설정 파일 섹션|설치 권한 유형" 매핑
    # 권한 유형: System (강제 시스템 설치), Selectable (설치 시 User/System 선택 가능)
    declare -A SCRIPT_MAP=(
        ["miniconda.sh"]="Miniconda|miniconda|APPLICATION_LIST|Selectable"
        ["vscode.sh"]="VS Code|code|APPLICATION_LIST|System"
        ["nvidia_driver.sh"]="NVIDIA Driver|nvidia-driver|DRIVER_LIST|System"
    )
    # UI 표시 이름 => 실제 실행할 함수 이름 매핑
    declare -A NAME_TO_LOGIC=(
        ["Miniconda"]="install_miniconda_logic"
        ["VS Code"]="install_vscode_logic"
        ["NVIDIA Driver"]="_ui_install_nvidia_driver"
    )
    # UI 표시 이름 => 스크립트 파일명 역매핑 (설치 시 정보 조회를 위해 필요)
    declare -A NAME_TO_FILENAME

    local available_scripts
    mapfile -t available_scripts < <(find "${install_dir}" -maxdepth 1 -name "*.sh" -printf "%f\n" | sort)

    # --- 2. 체크리스트 옵션 생성 ---
    local dialog_options=()
    declare -A initial_states
    
    for script_file in "${available_scripts[@]}"; do
        if [[ -z "${SCRIPT_MAP[$script_file]}" ]]; then continue; fi

        IFS='|' read -r name key section install_type <<< "${SCRIPT_MAP[$script_file]}"
        NAME_TO_FILENAME["$name"]="$script_file"

        local is_checked="off"
        local status_desc="Not Installed"

        # 설치 상태 확인
        if [[ "$section" == "DRIVER_LIST" && "$key" == "nvidia-driver" ]]; then
            if dpkg-query -W -f='${Status}' nvidia-driver-* 2>/dev/null | grep -q 'install ok installed'; then
                is_checked="on"; status_desc="(Installed)"
            fi
        elif [[ -n "$(get_config_value "${CONFIG_FILE}" "$section" "$key")" ]]; then
            is_checked="on"; status_desc="(Installed)"
        fi
        
        initial_states["$name"]=$is_checked
        
        # UI 항목 이름에 설치 유형 표시
        local type_label="[System]"
        [[ "$install_type" == "Selectable" ]] && type_label="[User/System]"
        
        local display_name="${name} ${type_label}"
        dialog_options+=("${display_name}" "$status_desc" "$is_checked")
    done

    if [[ ${#dialog_options[@]} -eq 0 ]]; then
        ui_message_box "No configurable installation scripts found." "Info"; return
    fi

    # --- 3. UI 표시 및 사용자 선택 처리 ---
    local selections_str
    selections_str=$(ui_create_checklist "Additional Software Setup" "Install Software" \
        "Check items to install. [Type] indicates permission level." 20 75 15 "${dialog_options[@]}")

    if [[ "$selections_str" == "CANCEL" ]]; then return; fi

    # --- 4. 선택된 항목 순차 설치 실행 ---
    local -a selections
    eval "selections=($selections_str)"

    if [[ ${#selections[@]} -eq 0 ]]; then
        ui_message_box "No items were selected for installation." "Info"; return
    fi

    clear
    echo "--- Starting selected installations ---"

    for selection_display in "${selections[@]}"; do
        # "Name [Type]" 형식에서 "Name" 추출 (마지막 공백 이후 제거)
        local selection="${selection_display% \[*\]}"
        
        # 이미 설치된 항목은 건너뜀
        if [[ "${initial_states[$selection]}" == "on" ]]; then
            echo "[INFO] '${selection}' is already installed. Skipping."
            continue
        fi
        
        local logic_func="${NAME_TO_LOGIC[$selection]}"
        local script_file="${NAME_TO_FILENAME[$selection]}"
        IFS='|' read -r _ _ _ install_type <<< "${SCRIPT_MAP[$script_file]}"
        
        local mode_arg=""
        
        # Selectable 타입인 경우 사용자에게 모드 선택 요청
        if [[ "$install_type" == "Selectable" ]]; then
            local mode_choice
            mode_choice=$(ui_create_menu "Installation Mode" "Select Mode for ${selection}" \
                "How should ${selection} be installed?" 15 60 5 \
                "user" "User Mode (Install to Home Directory)" \
                "system" "System Mode (Install to /opt, requires sudo)")
            
            if [[ "$mode_choice" == "CANCEL" ]]; then
                echo "[WARN] Installation of '${selection}' cancelled by user."
                continue
            fi
            mode_arg="$mode_choice"
        fi

        if [[ -n "$logic_func" ]] && command -v "$logic_func" &>/dev/null; then
            echo "----------------------------------------"
            echo "[INFO] Running installer for: ${selection}"
            if [[ -n "$mode_arg" ]]; then
                "$logic_func" "$mode_arg"
            else
                "$logic_func"
            fi
        else
            echo "[WARN] No logic function found for '${selection}'. Check NAME_TO_LOGIC map. Skipping."
        fi
    done

    read -rp $'\nAll selected operations completed. Press Enter to continue...'
}
