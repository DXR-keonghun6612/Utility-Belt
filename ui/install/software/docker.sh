#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/software/docker.sh
# 설명: Docker Engine 설치 및 권한 설정을 위한 전용 UI.
# ==============================================================================

ui_install_docker() {
    local is_installed=false
    local has_permission=false
    local target_user="${SUDO_USER:-$USER}"

    if is_installed_docker; then
        is_installed=true
        if groups "${target_user}" | grep -q "\bdocker\b"; then
            has_permission=true
        fi
    fi

    local prompt="[Status]
"
    if ! $is_installed; then
        prompt+="  - Docker: Not Installed
"
    else
        prompt+="  - Docker: Installed
"
        if $has_permission; then
            prompt+="  - Access: Granted for '${target_user}'
"
        else
            prompt+="  - Access: DENIED for '${target_user}' (Permission Required)
"
        fi
    fi
    prompt+="
What would you like to do?"

    local options=()
    if ! $is_installed; then
        options+=("INSTALL" "Install Docker Engine & NVIDIA Toolkit")
    else
        if ! $has_permission; then
            options+=("GRANT_ACCESS" "Fix Permission (Add current user to group)")
        fi
        options+=("REINSTALL" "Reinstall/Update Docker Engine")
        options+=("UNINSTALL" "Remove Docker Engine from System")
    fi

    local choice
    choice=$(ui_create_menu "Docker Management" "Docker Engine" "${prompt}" 18 70 5 "${options[@]}")

    case "${choice}" in
        "INSTALL" | "REINSTALL" | "GRANT_ACCESS")
            clear
            if install_docker_logic; then
                if ! groups "${target_user}" | grep -q "\bdocker\b"; then
                    if ui_confirm "Docker configuration has changed. A system reboot is required to apply group permissions. Reboot now?" "Reboot Recommended"; then
                        ${G_SUDO_PREFIX} reboot
                    fi
                fi
            fi
            read -rp $'
Press Enter to continue...'
            ;;
        "UNINSTALL")
            if ui_confirm "Are you sure you want to uninstall Docker?" "Confirm Uninstall"; then
                clear
                uninstall_docker_logic
                read -rp $'
Press Enter to continue...'
            fi
            ;;
    esac
}
