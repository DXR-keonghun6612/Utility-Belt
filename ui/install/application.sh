#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/proc_install_application.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: 추가 소프트웨어(NVIDIA, Miniconda, VSCode 등) 설치를 위한 동적 UI.
# ==============================================================================

##
# @description '추가 소프트웨어 설치' 메인 UI 함수 (동적 체크리스트 방식).
#
ui_install_application() {
    # --- 1. 설정 및 스크립트 스캔 ---
    local install_dir="${SCRIPT_DIR}/script/install"
    
    # UI 표시 이름 => [설정 섹션, 설치 권한 유형, 로직 함수, 체크 함수]
    declare -A APP_DATA=(
        ["Conda"]="APPLICATION_LIST|Selectable|install_conda_logic|is_installed_conda"
        ["VS Code"]="APPLICATION_LIST|System|install_vscode_logic|is_installed_vscode"
        ["Docker"]="APPLICATION_LIST|System|install_docker_logic|is_installed_docker"
        ["ROS 2"]="APPLICATION_LIST|System|install_ros2_logic|is_installed_ros2"
    )

    local app_order=("Conda" "VS Code" "Docker" "ROS 2")

    # --- 2. 체크리스트 옵션 생성 ---
    local dialog_options=()
    declare -A initial_states
    
    for name in "${app_order[@]}"; do
        IFS='|' read -r section install_type logic_func check_func <<< "${APP_DATA[$name]}"

        local is_checked="off"
        local status_desc="Not Installed"

        # 백엔드 함수를 호출하여 상태 감지 및 설정 동기화
        if [[ -n "$check_func" ]] && command -v "$check_func" &>/dev/null; then
            if "$check_func"; then
                is_checked="on"
                status_desc="(Installed)"
            fi
        fi
        
        initial_states["$name"]=$is_checked
        
        local type_label="[System]"
        [[ "$install_type" == "Selectable" ]] && type_label="[User/System]"
        dialog_options+=("${name} ${type_label}" "$status_desc" "$is_checked")
    done

    # --- 3. UI 표시 및 사용자 선택 처리 ---
    local selections_str
    selections_str=$(ui_create_checklist "Additional Software Setup" "Install Software" \
        "Check items to install. [Type] indicates permission level." 20 75 15 "${dialog_options[@]}")

    if [[ "$selections_str" == "CANCEL" ]]; then return; fi

    local -a selections
    eval "selections=($selections_str)"

    local any_action_performed=false
    clear
    echo "--- Processing software setup changes ---"

    for name in "${app_order[@]}"; do
        IFS='|' read -r section install_type logic_func check_func <<< "${APP_DATA[$name]}"
        
        local is_selected=false
        for sel in "${selections[@]}"; do
            if [[ "$sel" == "$name "* ]]; then
                is_selected=true; break
            fi
        done

        local initial_state="${initial_states[$name]}"
        
        # [Case 1] 신규 설치
        if [[ "$initial_state" == "off" && "$is_selected" == "true" ]]; then
            any_action_performed=true
            echo "----------------------------------------"
            echo "[ACTION] Installing: ${name}"
            
            local mode_arg=""
            if [[ "$name" == "Conda" ]]; then
                local conda_type
                conda_type=$(ui_create_menu "Conda Distribution" "Select Distribution" \
                    "Which distribution do you want to install?" 15 60 5 \
                    "miniconda" "Miniconda (Lightweight, Recommended)" \
                    "anaconda" "Anaconda (Full, Large)")
                [[ "$conda_type" == "CANCEL" ]] && continue

                mode_arg=$(ui_create_menu "Installation Mode" "Select Mode for ${name}" \
                    "How should ${name} be installed?" 15 60 5 \
                    "user" "User Mode" "system" "System Mode")
                [[ "$mode_arg" == "CANCEL" ]] && continue
                
                "$logic_func" "$mode_arg" "$conda_type"
            else
                if [[ "$install_type" == "Selectable" ]]; then
                    mode_arg=$(ui_create_menu "Installation Mode" "Select Mode for ${name}" \
                        "How should ${name} be installed?" 15 60 5 \
                        "user" "User Mode" "system" "System Mode")
                    [[ "$mode_arg" == "CANCEL" ]] && continue
                fi
                "$logic_func" "$mode_arg"
            fi

        # [Case 2] 삭제
        elif [[ "$initial_state" == "on" && "$is_selected" == "false" ]]; then
            any_action_performed=true
            echo "----------------------------------------"
            echo "[ACTION] Uninstalling: ${name}"
            # TODO: uninstall_..._logic 백엔드 함수 보강 필요
            local uninstall_func="${logic_func/install/uninstall}"
            if [[ -n "$uninstall_func" ]] && command -v "$uninstall_func" &>/dev/null; then
                "$uninstall_func"
            else
                echo "[WARN] Automatic uninstallation not supported for ${name}."
            fi
        fi
    done

    if [[ "$any_action_performed" == "true" ]]; then
        read -rp $'\nAll selected operations completed. Press Enter to continue...'
    fi
}
