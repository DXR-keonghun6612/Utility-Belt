#!/bin/bash
# ==============================================================================
# 파일명: proc_system_monitor.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: utils/02_system_monitor.sh의 기능을 사용하여 시스템 하드웨어 정보를 표시하거나 JSON으로 내보냅니다.
# ==============================================================================

##
# @description 시스템의 주요 하드웨어 정보를 수집하여 dialog textbox로 표시합니다.
#
_ui_show_system_info_textbox() {
    # 임시 파일을 생성하여 모든 하드웨어 정보를 저장합니다.
    local temp_file
    temp_file=$(mktemp) || { echo "Failed to create temp file"; return 1; }
    trap 'rm -f "${temp_file}"' RETURN

    # 모든 정보 수집 함수를 호출하고 그 결과를 임시 파일에 씁니다.
    {
        echo "--- CPU Info ---"
        get_cpu_info
        echo ""
        echo "--- Motherboard Info ---"
        get_motherboard_info
        echo ""
        echo "--- Memory Info ---"
        get_memory_info
        echo ""
        echo "--- GPU Info ---"
        get_gpu_info
        echo ""
        echo "--- Storage Info ---"
        get_storage_info
    } > "${temp_file}"

    # 공통 래퍼 함수 사용
    ui_show_textbox "${temp_file}" "System Hardware Information" 25 80
}

##
# @description 시스템 정보를 JSON으로 파일에 저장하는 UI를 제공합니다.
#
_ui_export_system_info_json() {
    local filepath
    # 공통 래퍼 함수 사용
    filepath=$(ui_file_select "${PWD}/system_info.json" "Export System Info to JSON" 14 70)

    if [[ -z "$filepath" ]]; then
        ui_message_box "Export cancelled." "Cancelled"
        return
    fi

    # JSON 데이터 생성 및 파일에 저장
    if get_system_info_json > "${filepath}"; then
        ui_message_box "System information successfully exported to:\n${filepath}" "Export Successful"
    else
        ui_message_box "Failed to export system information." "Error"
    fi
}


##
# @description 시스템 모니터의 메인 메뉴
#
ui_system_monitor_menu() {
     while true; do
        local choice
        choice=$(ui_create_menu "Main Menu > System Monitor" \
            "System Monitor" \
            "Select an action:" \
            "15" "60" "10" \
            "1" "View Hardware Info" \
            "2" "Export to JSON" \
            "0" "Back")

        case "${choice}" in
            1) _ui_show_system_info_textbox ;; 
            2) _ui_export_system_info_json ;; 
            0 | CANCEL) break ;; 
        esac
    done
}