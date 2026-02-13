#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/software/ros2.sh
# 설명: ROS 2 설치를 위한 전용 UI.
# ==============================================================================

ui_install_ros2() {
    local status="(Not Installed)"
    is_installed_ros2 && status="(Installed)"

    local choice
    choice=$(ui_create_menu "ROS 2 Management" "Robot Operating System 2" "Status: ${status}

Select action:" 15 60 5 \
        "INSTALL" "Install ROS 2 (Select Variant)" \
        "UNINSTALL" "Uninstall ROS 2" \
        "BACK" "Back")

    case "${choice}" in
        "INSTALL")
            local variant
            variant=$(ui_create_menu "Select ROS 2 Variant" "Installation Type" "Select the package set to install:" 15 65 3 \
                "desktop"  "Full version (Tools, RViz, Demos)" \
                "ros-base" "Base version (Libraries, No GUI)" \
                "ros-core" "Core version (Minimal stack)")
            
            [[ "${variant}" == "CANCEL" ]] && return 1

            clear
            install_ros2_logic "${variant}"
            read -rp $'
Press Enter to continue...'
            ;;
        "UNINSTALL")
            if ui_confirm "Are you sure you want to uninstall ROS 2?" "Confirm Uninstall"; then
                clear
                uninstall_ros2_logic
                read -rp $'
Press Enter to continue...'
            fi
            ;;
    esac
}
