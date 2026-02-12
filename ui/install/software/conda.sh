#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/software/conda.sh
# 설명: Miniconda/Anaconda 설치를 위한 전용 UI.
# ==============================================================================

ui_install_conda() {
    local status="(Not Installed)"
    is_installed_conda && status="(Installed)"

    local choice
    choice=$(ui_create_menu "Conda Management" "Miniconda/Anaconda" "Status: ${status}

Select action:" 15 60 5 \
        "INSTALL" "Install Conda Distribution" \
        "UNINSTALL" "Uninstall Conda Distribution" \
        "BACK" "Back")

    case "${choice}" in
        "INSTALL")
            local conda_type
            conda_type=$(ui_create_menu "Conda Distribution" "Select Distribution" \
                "Which distribution do you want to install?" 15 60 5 \
                "miniconda" "Miniconda (Lightweight, Recommended)" \
                "anaconda" "Anaconda (Full, Large)")
            [[ "${conda_type}" == "CANCEL" ]] && return

            local mode_arg
            mode_arg=$(ui_create_menu "Installation Mode" "Select Mode" \
                "How should Conda be installed?" 15 60 5 \
                "user" "User Mode" "system" "System Mode")
            [[ "${mode_arg}" == "CANCEL" ]] && return

            clear
            install_conda_logic "${mode_arg}" "${conda_type}"
            read -rp $'
Press Enter to continue...'
            ;;
        "UNINSTALL")
            if ui_confirm "Are you sure you want to uninstall Conda?" "Confirm Uninstall"; then
                clear
                uninstall_conda_logic
                read -rp $'
Press Enter to continue...'
            fi
            ;;
    esac
}
