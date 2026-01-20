#!/bin/bash
# ==============================================================================
# 파일명: proc_network.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: network.sh의 기능을 활용하여 네트워크 관리를 위한 사용자 인터페이스를 제공.
# 필요: dialog, network.sh (백엔드 로직)
# ==============================================================================

# ==============================================================================
# --- 메인 UI ---
# ==============================================================================

ui_network_management() {
    while true; do
        local choice=$(ui_create_menu \
            "Network Management Utility" \
            "Main Menu" \
            "Select an option:" \
            "18" "60" "7" \
            "1" "View Current IP Info" \
            "2" "Check Connection Status" \
            "3" "Set Static IP" \
            "4" "Create Network Bond" \
            "5" "Manage Hosts File (/etc/hosts)" \
            "EXIT" "Exit Program")

        case "${choice}" in
            1) ui_show_current_ip ;; 
            2) ui_check_connection ;; 
            3) ui_edit_ip_settings ;; 
            4) ui_create_bond ;; 
            5) ui_hosts_file_management ;; 
            EXIT | CANCEL) clear; break ;; 
            *) ui_message_box "Invalid option: ${choice}" "Error" 6 40 ;; 
        esac
    done
}

# ==============================================================================
# --- 기본 네트워크 UI 기능 ---
# ==============================================================================

ui_show_current_ip() {
    local ip_info; ip_info=$(get_current_ip_info)
    local tmp_file; tmp_file=$(mktemp)
    echo "${ip_info}" > "${tmp_file}"
    ui_show_textbox "${tmp_file}" "Current IP Information" 20 70
    rm -f "${tmp_file}"
}

ui_check_connection() {
    local target
    target=$(ui_input_box "Enter a host to ping:" "Check Connection" "8.8.8.8" 8 40)
    if [[ -z "$target" ]]; then return; fi

    clear
    check_connection_status "${target}"
    read -rp "Press Enter to continue..."
}

ui_edit_ip_settings() {
    local interfaces_raw; interfaces_raw=$(list_network_interfaces)
    if [[ -z "$interfaces_raw" ]]; then
        ui_message_box "No configurable network interfaces found." "Error" 8 50; return
    fi
    
    local menu_options=(); read -r -a interfaces_array <<< "$interfaces_raw"
    for iface in "${interfaces_array[@]}"; do menu_options+=("$iface" ""); done

    local target_iface
    target_iface=$(ui_create_menu "IP Settings" "Step 1: Select Interface" "Select an interface to configure:" 15 50 5 "${menu_options[@]}")
    if [[ "$target_iface" == "CANCEL" ]]; then
        return
    fi

    local details; details=$(get_interface_details "${target_iface}")
    local current_ip; current_ip=$(echo "$details" | cut -d';' -f1)
    local current_gw; current_gw=$(echo "$details" | cut -d';' -f2)
    local current_dns; current_dns=$(echo "$details" | cut -d';' -f3)

    local values
    values=$(ui_create_form "IP Settings" "Step 2: Edit Settings for '${target_iface}'" "" 15 60 4 \
        "IP/CIDR:"  1 1 "${current_ip:-"Not set"}"  1 15 30 0 \
        "Gateway:"  2 1 "${current_gw:-"Not set"}"  2 15 30 0 \
        "DNS:"      3 1 "${current_dns:-"Not set"}" 3 15 30 0)
    
    if [[ $? -ne 0 ]]; then return; fi
    
    local ip; ip=$(echo "$values" | sed -n '1p')
    local gw; gw=$(echo "$values" | sed -n '2p')
    local dns; dns=$(echo "$values" | sed -n '3p')

    if ui_confirm "Apply these settings to '${target_iface}'?\n\nIP: ${ip}\nGateway: ${gw}\nDNS: ${dns}" "Confirm Changes" 12 50; then
        clear
        set_static_ip "$target_iface" "$ip" "$gw" "$dns"
        read -rp "Press Enter to continue..."
    fi
}

ui_create_bond() {
    local interfaces_raw; interfaces_raw=$(list_network_interfaces)
    if [[ -z "$interfaces_raw" ]]; then
        ui_message_box "No available interfaces for bonding." "Error" 8 50; return
    fi
    
    local checklist_options=(); read -r -a interfaces_array <<< "$interfaces_raw"
    for iface in "${interfaces_array[@]}"; do checklist_options+=("$iface" "" "off"); done
    
    local selected_slaves_str
    selected_slaves_str=$(ui_create_checklist "Create Bond" "Step 1: Select Slaves" "Select slave interfaces for bonding (use Space bar):" 20 60 10 "${checklist_options[@]}")
    if [[ "$selected_slaves_str" == "CANCEL" ]]; then
        return
    fi
    
    local slaves_csv; slaves_csv=$(echo "$selected_slaves_str" | sed 's/"//g' | tr ' ' ',');
    if [[ -z "$slaves_csv" ]]; then ui_message_box "No interfaces selected." "Error" 8 40; return; fi

    local bond_name; bond_name=$(ui_input_box "Step 2: Enter bond name (e.g., bond0):" "Create Bond" "bond0" 8 40)
    if [[ -z "$bond_name" ]]; then return; fi

    local mode
    mode=$(ui_create_selection "radiolist" "Create Bond" "Step 3: Select Mode" "Select bonding mode:" 15 50 4 \
        "active-backup" "Fault Tolerance" "on" \
        "802.3ad" "Link Aggregation (LACP)" "off" \
        "balance-rr" "Load Balancing" "off")
    
    if [[ "$mode" == "CANCEL" || -z "$mode" ]]; then return; fi

    if ui_confirm "Create bond '${bond_name}' with slaves '${slaves_csv}' in mode '${mode}'?" "Confirm" 10 60; then
        clear
        create_network_bond "$bond_name" "$mode" "$slaves_csv"
        read -rp "Press Enter to continue..."
    fi
}

# ==============================================================================
# --- 호스트 파일(/etc/hosts) 관리 UI ---
# ==============================================================================

ui_hosts_file_management() {
    while true; do
        local choice=$(ui_create_menu \
            "Hosts File Management" \
            "Manage Hosts File (/etc/hosts)" \
            "Select an option:" \
            "16" "60" "5" \
            "1" "Add New Host Mapping" \
            "2" "Edit Existing Host Mapping" \
            "3" "Edit File Directly (nano)" \
            "BACK" "Return to Main Menu")

        case "${choice}" in
            1) ui_add_host_mapping ;; 
            2) ui_edit_host_mapping ;; 
            3) nano /etc/hosts ;; 
            BACK | CANCEL) break ;; 
            *) ui_message_box "Invalid option: ${choice}" "Error" 6 40 ;; 
        esac
    done
}

ui_add_host_mapping() {
    local values
    values=$(ui_create_form "Hosts File" "Add New Host Mapping" "" 15 60 4 \
        "IP Address:"  1 1 "" 1 15 30 0 \
        "Hostname:"    2 1 "" 2 15 30 0)
    
    if [[ $? -ne 0 ]]; then return; fi

    local ip; ip=$(echo "$values" | sed -n '1p')
    local host; host=$(echo "$values" | sed -n '2p')

    if [[ -z "$ip" || -z "$host" ]]; then
        ui_message_box "IP address and hostname are required." "Error" 8 50
        return
    fi
    
    clear
    set_host_ip_mapping "$ip" "$host"
    read -rp "Press Enter to continue..."
}

ui_edit_host_mapping() {
    local hosts_entries
    hosts_entries=$(grep -vE '^\s*#|^\s*$|localhost|::1' /etc/hosts)
    
    if [[ -z "$hosts_entries" ]]; then
        ui_message_box "No host mappings found to edit." "Error" 8 50; return
    fi

    local menu_options=()
    while IFS= read -r line; do
        local ip; ip=$(echo "$line" | awk '{print $1}')
        local host; host=$(echo "$line" | awk '{print $2}')
        menu_options+=("$host" "$ip")
    done <<< "$hosts_entries"

    local selected_host
    selected_host=$(ui_create_menu "Hosts File" "Edit Mapping" "Select a host to edit:" 20 60 10 "${menu_options[@]}")
    if [[ "$selected_host" == "CANCEL" ]]; then
        return
    fi

    local current_ip
    for i in "${!menu_options[@]}"; do
        if [[ "${menu_options[i]}" == "${selected_host}" ]]; then
            current_ip="${menu_options[i+1]}"
            break
        fi
    done
    
    local values
    values=$(ui_create_form "Hosts File" "Edit mapping for '${selected_host}'" "" 15 60 4 \
        "IP Address:"  1 1 "${current_ip}"  1 15 30 0 \
        "Hostname:"    2 1 "${selected_host}" 2 15 30 0)
    
    if [[ $? -ne 0 ]]; then return; fi

    local new_ip; new_ip=$(echo "$values" | sed -n '1p')
    local new_host; new_host=$(echo "$values" | sed -n '2p')
    
    if [[ -z "$new_ip" || -z "$new_host" ]]; then
        ui_message_box "IP address and hostname are required." "Error" 8 50
        return
    fi

    clear
    set_host_ip_mapping "$new_ip" "$new_host"
    read -rp "Press Enter to continue..."
}
