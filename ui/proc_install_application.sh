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
        # [Config 연동] 설치 성공 시 DRIVER_LIST에 기록
        local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
        set_config_value "${CONFIG_FILE}" "DRIVER_LIST" "nvidia-driver" "${selected_driver} (${timestamp})"
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
    local install_dir="${SCRIPT_DIR}/script/install"
    
    # 스크립트 파일명 => "UI 표시 이름|설정 파일 키|설정 파일 섹션|설치 권한 유형" 매핑
    # 권한 유형: System (강제 시스템 설치), Selectable (설치 시 User/System 선택 가능)
    declare -A SCRIPT_MAP=(
        ["conda.sh"]="Conda|conda|APPLICATION_LIST|Selectable"
        ["vscode.sh"]="VS Code|code|APPLICATION_LIST|System"
        ["nvidia_driver.sh"]="NVIDIA Driver|nvidia-driver|DRIVER_LIST|System"
        ["cuda_toolkit.sh"]="CUDA Toolkit|cuda-toolkit|APPLICATION_LIST|System"
        ["cudnn_library.sh"]="cuDNN Library|cudnn-library|APPLICATION_LIST|System"
        ["docker.sh"]="Docker|docker|APPLICATION_LIST|System"
    )
    # UI 표시 이름 => 실제 실행할 함수 이름 매핑
    declare -A NAME_TO_LOGIC=(
        ["Conda"]="install_conda_logic"
        ["VS Code"]="install_vscode_logic"
        ["NVIDIA Driver"]="_ui_install_nvidia_driver"
        ["CUDA Toolkit"]="install_cuda_toolkit_logic"
        ["cuDNN Library"]="install_cudnn_library_logic"
        ["Docker"]="install_docker_logic"
    )
    # UI 표시 이름 => 설치 확인 함수 매핑
    declare -A NAME_TO_CHECK=(
        ["Conda"]="is_installed_conda"
        ["VS Code"]="is_installed_vscode"
        ["NVIDIA Driver"]="is_installed_nvidia_driver"
        ["CUDA Toolkit"]="is_installed_cuda_toolkit"
        ["cuDNN Library"]="is_installed_cudnn_library"
        ["Docker"]="is_installed_docker"
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

        # [개선된 로직] 설치 확인 함수 우선 사용
        local check_func="${NAME_TO_CHECK[$name]}"
        local installed=false
        local is_verified_externally=false # 상태 검증 여부

        if [[ -n "$check_func" ]] && command -v "$check_func" &>/dev/null; then
            if "$check_func"; then
                installed=true
            fi
            is_verified_externally=true
        else
            # Fallback: 기존 Config/DPKG 확인 방식
            if [[ "$section" == "DRIVER_LIST" && "$key" == "nvidia-driver" ]]; then
                if dpkg-query -W -f='${Status}' nvidia-driver-* 2>/dev/null | grep -q 'install ok installed'; then
                    installed=true
                fi
                is_verified_externally=true
            elif [[ -n "$(get_config_value "${CONFIG_FILE}" "$section" "$key")" ]]; then
                installed=true
            fi
        fi

        if [[ "$installed" == "true" ]]; then
            is_checked="on"
            status_desc="(Installed)"

            # [SPECIAL] CUDA Toolkit: Always force OFF to allow entering Management Menu
            if [[ "$name" == "CUDA Toolkit" ]]; then
                is_checked="off"
                status_desc="(Installed - Check to Manage)"
            fi
        fi
        
        # [Sync Config] 실제 설치 상태와 설정 파일 동기화
        if [[ "$is_verified_externally" == "true" ]]; then
            # [SPECIAL] CUDA Toolkit은 버전별 개별 키를 사용하므로 범용 키 동기화 제외
            if [[ "$name" != "CUDA Toolkit" ]]; then
                local current_conf_val
                current_conf_val=$(get_config_value "${CONFIG_FILE}" "$section" "$key")

                if [[ "$installed" == "true" ]]; then
                    if [[ -z "$current_conf_val" ]]; then
                        local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
                        set_config_value "${CONFIG_FILE}" "$section" "$key" "${timestamp}"
                    fi
                else
                    if [[ -n "$current_conf_val" ]]; then
                        delete_config_value "${CONFIG_FILE}" "$section" "$key"
                    fi
                fi
            fi
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

    # --- 4. 선택된 항목 순차 처리 (설치/삭제) ---
    local -a selections
    eval "selections=($selections_str)"

    local any_action_performed=false
    clear
    echo "--- Processing software setup changes ---"

    # 모든 스크립트에 대해 상태 변화 감지
    for script_file in "${available_scripts[@]}"; do
        if [[ -z "${SCRIPT_MAP[$script_file]}" ]]; then continue; fi

        IFS='|' read -r name key section install_type <<< "${SCRIPT_MAP[$script_file]}"
        
        local is_selected=false
        for sel in "${selections[@]}"; do
            if [[ "$sel" == "$name "* ]]; then
                is_selected=true
                break
            fi
        done

        local initial_state="${initial_states[$name]}"
        local logic_func="${NAME_TO_LOGIC[$name]}"
        
        # [Case 1] 신규 설치: 초기 OFF -> 현재 ON
        if [[ "$initial_state" == "off" && "$is_selected" == "true" ]]; then
            any_action_performed=true
            echo "----------------------------------------"
            echo "[ACTION] Installing: ${name}"
            
            local mode_arg=""
            local conda_type="miniconda" 

            if [[ "$name" == "Conda" ]]; then
                conda_type=$(ui_create_menu "Conda Distribution" "Select Distribution" \
                    "Which distribution do you want to install?" 15 60 5 \
                    "miniconda" "Miniconda (Lightweight, Recommended)" \
                    "anaconda" "Anaconda (Full, Large)")
                if [[ "$conda_type" == "CANCEL" ]]; then continue; fi
            fi

            if [[ "$install_type" == "Selectable" ]]; then
                mode_arg=$(ui_create_menu "Installation Mode" "Select Mode for ${name}" \
                    "How should ${name} be installed?" 15 60 5 \
                    "user" "User Mode" "system" "System Mode")
                [[ "$mode_arg" == "CANCEL" ]] && continue
            fi

            if [[ -n "$logic_func" ]] && command -v "$logic_func" &>/dev/null; then
                if [[ "$name" == "Conda" ]]; then
                    "$logic_func" "$mode_arg" "$conda_type"
                else
                    "$logic_func" "$mode_arg"
                fi
            fi

        # [Case 2] 삭제: 초기 ON -> 현재 OFF
        elif [[ "$initial_state" == "on" && "$is_selected" == "false" ]]; then
            any_action_performed=true
            echo "----------------------------------------"
            echo "[ACTION] Uninstalling: ${name}"
            local uninstall_func="${logic_func/install/uninstall}"
            if [[ -n "$uninstall_func" ]] && command -v "$uninstall_func" &>/dev/null; then
                "$uninstall_func"
                delete_config_value "${CONFIG_FILE}" "$section" "$key"
            fi
        fi
    done

    if [[ "$any_action_performed" == "true" ]]; then
        read -rp $'\nAll selected operations completed. Press Enter to continue...'
    fi
}
