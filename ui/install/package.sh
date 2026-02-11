#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/proc_install_package.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: 필수 패키지의 설치 및 제거를 통합 관리하는 UI 스크립트.
# ==============================================================================

##
# @description 패키지 상태를 확인하고 체크리스트 UI를 통해 설치/삭제를 일괄 처리함.
#
ui_package_management() {
    local conf_file="$1"
    
    # --- 1. 설정 파일 파싱 및 현재 상태 확인 ---
    # PACKAGES_LIST 섹션의 모든 패키지와 그 상태(값 존재 여부)를 읽어옵니다.
    declare -A initial_states
    parse_config_to_array "initial_states" < <(get_config_section "${conf_file}" "PACKAGES_LIST")
    
    if [[ ${#initial_states[@]} -eq 0 ]]; then
        ui_message_box "No packages defined in [PACKAGES_LIST] section of config." "Error"
        return 0
    fi

    # --- 2. Dialog 체크리스트 옵션 생성 ---
    # 패키지 이름순으로 정렬하여 UI 목록을 생성합니다.
    local dialog_options=()
    local sorted_keys
    
    # 정렬된 키 목록 생성 (bash의 sort 명령 활용)
    sorted_keys=$(printf "%s\n" "${!initial_states[@]}" | sort)
    
    local config_updated=false
    
    for pkg in ${sorted_keys}; do
        local status_val="${initial_states[$pkg]}"
        local is_checked="off"
        local desc_str="Not Installed"
        
        # 값이 존재하면 설치된 것으로 간주하고 체크박스를 'on'으로 설정
        if [[ -n "$status_val" ]]; then
            is_checked="on"
            desc_str="(Installed)"
        elif is_package_installed "${pkg}"; then
             # Config에는 없지만 실제로 설치되어 있는 경우
             is_checked="on"
             desc_str="(Installed)"
             
             # 발견 즉시 설정 파일 동기화
             local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
             set_config_value "${conf_file}" "PACKAGES_LIST" "${pkg}" "${timestamp}"
             config_updated=true
        fi
        
        dialog_options+=("${pkg}" "${desc_str}" "${is_checked}")
    done
    
    if $config_updated; then
        # 업데이트된 설정 파일 내용을 반영하기 위해 배열 재로딩 (선택 사항, UI에는 이미 반영됨)
        parse_config_to_array "initial_states" < <(get_config_section "${conf_file}" "PACKAGES_LIST")
    fi

    # --- 3. 사용자 입력 (체크리스트) ---
    local selections
    selections=$(ui_create_checklist "Package Management" "Manage Packages" \
        "Check items to install, Uncheck to remove:" \
        20 70 15 "${dialog_options[@]}")

    # 취소 버튼 누름
    if [[ "${selections}" == "CANCEL" ]]; then
        return 0
    fi

    # --- 4. 변경 사항 계산 ---
    # selections 문자열을 배열로 변환
    local -a selected_pkgs
    read -r -a selected_pkgs <<< "${selections}"

    # 빠른 조회를 위해 선택된 패키지를 해시맵(Set)으로 변환
    declare -A selected_set
    for p in "${selected_pkgs[@]}"; do
        selected_set["$p"]=1
    done
    
    local to_install=()
    local to_uninstall=()
    
    for pkg in ${sorted_keys}; do
        local was_installed=0
        [[ -n "${initial_states[$pkg]}" ]] && was_installed=1
        
        local is_selected=0
        [[ -n "${selected_set[$pkg]}" ]] && is_selected=1
        
        if [[ $was_installed -eq 0 && $is_selected -eq 1 ]]; then
            # 원래 없었는데 선택됨 -> 설치 대상
            to_install+=("${pkg}")
        elif [[ $was_installed -eq 1 && $is_selected -eq 0 ]]; then
            # 원래 있었는데 선택 해제됨 -> 삭제 대상
            to_uninstall+=("${pkg}")
        fi
    done
    
    # --- 5. 변경 사항 확인 및 실행 ---
    if [[ ${#to_install[@]} -eq 0 && ${#to_uninstall[@]} -eq 0 ]]; then
        ui_message_box "No changes made." "Info"
        return 0
    fi
    
    # 변경 요약 메시지 작성
    local confirm_msg="The following changes will be applied:\n"
    if [[ ${#to_install[@]} -gt 0 ]]; then
        confirm_msg+="\n[INSTALL]:\n"
        for p in "${to_install[@]}"; do confirm_msg+="  - ${p}\n"; done
    fi
    if [[ ${#to_uninstall[@]} -gt 0 ]]; then
        confirm_msg+="\n[UNINSTALL]:\n"
        for p in "${to_uninstall[@]}"; do confirm_msg+="  - ${p}\n"; done
    fi
    confirm_msg+="\nAre you sure you want to proceed?"

    if ! ui_confirm "${confirm_msg}" "Confirm Changes" 20 60; then
        return 0
    fi
    
    clear
    # 설치 실행
    if [[ ${#to_install[@]} -gt 0 ]]; then
        echo "--- Installing Packages ---"
        sync_package "PACKAGES_LIST" "${to_install[@]}"
    fi
    
    # 삭제 실행
    if [[ ${#to_uninstall[@]} -gt 0 ]]; then
        echo "--- Uninstalling Packages ---"
        uninstall_package "PACKAGES_LIST" "${to_uninstall[@]}"
    fi
    
    read -rp $'
Operation completed. Press Enter to continue...'
}
