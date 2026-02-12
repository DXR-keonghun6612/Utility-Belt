#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/software/vscode.sh
# 설명: VS Code 설치를 위한 전용 UI.
# ==============================================================================

ui_install_vscode() {
    local status="(Not Installed)"
    is_installed_vscode && status="(Installed)"

    local choice
    choice=$(ui_create_menu "VS Code Management" "Visual Studio Code" "Status: ${status}

Select action:" 15 60 5 \
        "INSTALL" "Install/Update VS Code" \
        "UNINSTALL" "Uninstall VS Code" \
        "BACK" "Back")

    case "${choice}" in
        "INSTALL")
            clear
            install_vscode_logic
            read -rp $'
Press Enter to continue...'
            ;;
        "UNINSTALL")
            if ui_confirm "Are you sure you want to uninstall VS Code?" "Confirm Uninstall"; then
                clear
                uninstall_vscode_logic
                read -rp $'
Press Enter to continue...'
            fi
            ;;
    esac
}
