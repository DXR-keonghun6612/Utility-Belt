#!/bin/bash
# ==============================================================================
# 파일명: proc_custom_service.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: 'custom_service' 디렉토리 내 커스텀 서비스의 설치/제거를 통합 관리하는 UI.
# ==============================================================================

# --- [통합 헬퍼] 커스텀 서비스 관리 (설치/제거 통합) ---
_ui_manage_custom_services_toggle() {
    local custom_service_dir="${SCRIPT_DIR}/custom_service"
    if [[ ! -d "${custom_service_dir}" ]]; then
        dialog --msgbox "Directory not found: ${custom_service_dir}" 8 60; return
    fi

    # --- 1. 서비스 목록 및 상태 파악 ---
    # 파일 시스템에 존재하는 모든 서비스 디렉토리를 찾습니다.
    local available_services=()
    mapfile -t available_services < <(find "${custom_service_dir}" -mindepth 1 -maxdepth 1 -type d -printf "%f\n" | sort)

    if [[ ${#available_services[@]} -eq 0 ]]; then
        dialog --msgbox "No custom services found in ${custom_service_dir}." 8 60; return
    fi

    local dialog_options=()
    
    # 각 서비스의 현재 설치 상태를 확인하여 체크리스트 옵션 구성
    for service_name in "${available_services[@]}"; do
        local is_checked="off"
        local status_desc="Not Installed"
        local installed_timestamp
        
        # 설정 파일에서 설치 기록 확인
        installed_timestamp=$(get_config_value "${CONFIG_FILE}" "CUSTOM_SERVICES" "${service_name}")
        
        if [[ -n "${installed_timestamp}" ]]; then
            is_checked="on"
            status_desc="(Installed)"
        fi
        
        dialog_options+=("${service_name}" "${status_desc}" "${is_checked}")
    done

    # --- 2. 사용자 입력 (체크리스트) ---
    local selections_str
    selections_str=$(ui_create_checklist "Custom Service Management" "Manage Services" \
        "Check items to install, Uncheck to uninstall:" 20 75 15 \
        "${dialog_options[@]}")

    if [[ "${selections_str}" == "CANCEL" ]]; then
        return
    fi

    # --- 3. 변경 사항 계산 ---
    local -a selected_services
    read -r -a selected_services <<< "${selections_str}"

    # 빠른 조회를 위한 해시맵(Set) 생성
    declare -A selected_set
    for s in "${selected_services[@]}"; do
        selected_set["$s"]=1
    done

    local to_install=()
    local to_uninstall=()

    for service_name in "${available_services[@]}"; do
        local was_installed=0
        [[ -n "$(get_config_value "${CONFIG_FILE}" "CUSTOM_SERVICES" "${service_name}")" ]] && was_installed=1
        
        local is_selected=0
        [[ -n "${selected_set[$service_name]}" ]] && is_selected=1
        
        if [[ $was_installed -eq 0 && $is_selected -eq 1 ]]; then
            to_install+=("${service_name}")
        elif [[ $was_installed -eq 1 && $is_selected -eq 0 ]]; then
            to_uninstall+=("${service_name}")
        fi
    done

    # --- 4. 변경 사항 확인 및 실행 ---
    if [[ ${#to_install[@]} -eq 0 && ${#to_uninstall[@]} -eq 0 ]]; then
        dialog --msgbox "No changes made." 6 40; return
    fi

    local confirm_msg="The following changes will be applied:\n"
    if [[ ${#to_install[@]} -gt 0 ]]; then
        confirm_msg+="\n[INSTALL]:\n"
        for s in "${to_install[@]}"; do confirm_msg+="  - ${s}\n"; done
    fi
    if [[ ${#to_uninstall[@]} -gt 0 ]]; then
        confirm_msg+="\n[UNINSTALL]:\n"
        for s in "${to_uninstall[@]}"; do confirm_msg+="  - ${s}\n"; done
    fi
    confirm_msg+="\nAre you sure you want to proceed?"

    if ! ui_confirm "${confirm_msg}" "Confirm Changes" 20 60; then
        return
    fi

    clear
    local timestamp; timestamp=$(date "+%Y-%m-%d %H:%M:%S")

    # 설치 실행
    if [[ ${#to_install[@]} -gt 0 ]]; then
        echo "--- Installing Services ---"
        for service_name in "${to_install[@]}"; do
            local setup_script="${custom_service_dir}/${service_name}/setup.sh"
            echo "[INFO] Processing install for '${service_name}'..."
            
            if [[ ! -f "${setup_script}" ]]; then
                echo "[ERROR] setup.sh not found for '${service_name}'. Skipping."
                continue
            fi
            
            if _run_interactive_installer "${setup_script}"; then
                echo "[SUCCESS] Installed '${service_name}'."
                set_config_value "CUSTOM_SERVICES" "${service_name}" "\"${timestamp}\"" "${CONFIG_FILE}"
            else
                echo "[Failed] Installation failed for '${service_name}'."
            fi
        done
    fi

    # 제거 실행
    if [[ ${#to_uninstall[@]} -gt 0 ]]; then
        echo "--- Uninstalling Services ---"
        for service_name in "${to_uninstall[@]}"; do
            local uninstall_script="${custom_service_dir}/${service_name}/uninstall.sh"
            echo "[INFO] Processing uninstall for '${service_name}'..."
            
            if [[ ! -f "${uninstall_script}" ]]; then
                echo "[ERROR] uninstall.sh not found for '${service_name}'. Removing record only."
                # 스크립트가 없으면 기록만 삭제
                set_config_value "CUSTOM_SERVICES" "${service_name}" "" "${CONFIG_FILE}"
                continue
            fi

            if _run_interactive_installer "${uninstall_script}"; then
                echo "[SUCCESS] Uninstalled '${service_name}'."
                set_config_value "CUSTOM_SERVICES" "${service_name}" "" "${CONFIG_FILE}"
            else
                echo "[Failed] Uninstallation failed for '${service_name}'."
            fi
        done
    fi

    read -rp $"
Operation completed. Press Enter to continue..."
}

# --- '커스텀 서비스 관리' 메인 UI 함수 ---
ui_manage_custom_services() {
    # 이제 메뉴가 필요 없으므로 바로 통합 관리 함수 호출
    _ui_manage_custom_services_toggle
}
