#!/bin/bash
# ==============================================================================
# 파일명: network.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: 네트워크 조회, 연결 확인, 설정 변경 등 핵심 기능을 수행하는 유틸리티 모듈.
#       최신 리눅스 환경과의 호환성을 위해 NetworkManager(nmcli)를 기준으로 함.
# ==============================================================================


# ==============================================================================
# 초기화
# ==============================================================================

# -----------------------------------------------------------------------------
# @description 패키지 설치 유틸리티에 필요한 패키지를 확인하고 설치함.
#           - 'sudo' 명령어가 없고 root 권한도 없는 경우, 설치를 시도하지 않음.
#           - 'sudo' 명령어가 있거나 root 권한이 있는 경우, 설치를 시도.
#           - 설치가 실패하면 오류 메시지를 출력하고 종료.
# @return
#          0: 성공
#          1: 패키지 정보 업데이트 실패
#          2: 패키지 설치 실패
#          3: 설치 함수 호출 인자 오류
#          4: 설정 파일 오류
#          5: 권한 부족 해당 패키지 사용 불가
# -----------------------------------------------------------------------------
_initialize_network_utils() {
    # ensure_packages_installed 함수를 사용하여 패키지 확인 및 설치
    # ping 명령어를 위한 iputils-ping 추가
    ensure_packages_installed "PACKAGES_LIST" "Network Management Utils" "NetworkManager" "iputils-ping" || return $?
    
    echo "[INFO] Network management utility initialized successfully." >&2
    return 0
}

# 초기화 함수 호출
_initialize_network_utils

# ==============================================================================
# 정보 조회 기능
# ==============================================================================

##
# @description 설정 가능한 물리적 네트워크 인터페이스 목록을 반환.
# @return stdout "eth0 eth1 enp0s3 ..." 형태의 공백으로 구분된 문자열
#
list_network_interfaces() {
    # /sys/class/net 디렉터리는 시스템의 모든 네트워크 장치를 표시.
    # lo(루프백), bond, br- 등 가상 인터페이스를 제외한 목록을 반환.
    ls /sys/class/net | grep -vE '^(lo|bond|br-|veth|docker)' | tr '\n' ' '
}

##
# @description 특정 인터페이스의 현재 IP, 게이트웨이, DNS 설정을 가져옴. (nmcli 기반)
# @param $1 interface_name
# @return stdout "IP/CIDR;GATEWAY;DNS" 형태의 세미콜론으로 구분된 문자열
#
get_interface_details() {
    local interface="$1"
    # nmcli가 없으면 이 기능은 작동하지 않음.
    if ! command -v nmcli &> /dev/null; then return; fi

    # nmcli의 -g 옵션으로 특정 값을 추출하고, 개행 문자를 세미콜론으로 변경.
    local details; details=$(nmcli -g IP4.ADDRESS,IP4.GATEWAY,IP4.DNS dev show "${interface}" 2>/dev/null | tr '\n' ';')
    # 마지막에 추가될 수 있는 세미콜론을 제거하고 출력.
    echo "${details%;}"
}

##
# @description 시스템의 모든 네트워크 인터페이스와 할당된 IP 주소를 출력.
#
get_current_ip_info() {
    echo "Fetching current IP address information..."
    # ip -br a: 간단한 테이블 형태로 IP 정보를 보여주는 현대적인 명령어
    ip -br a
}

##
# @description 외부 호스트에 ping을 보내 네트워크 연결 상태를 확인.
# @param $1 target_host (선택) ping을 보낼 대상, 기본값: 8.8.8.8
#
check_connection_status() {
    local target_host="${1:-8.8.8.8}"
    echo "[INFO] Pinging ${target_host} to check network connectivity..."
    
    if ping -c 4 "${target_host}"; then
        echo "[SUCCESS] Connection to ${target_host} is successful."
        return 0
    else
        echo "[ERROR] Connection to ${target_host} failed."
        return 1
    fi
}

# ==============================================================================
# 설정 변경 기능 (nmcli 및 hostnamectl 기반)
# ==============================================================================

##
# @description /etc/hosts 파일에 IP와 호스트 이름 매핑을 추가/업데이트.
# @param $1 ip_address 매핑할 IP 주소
# @param $2 hostname 매핑할 호스트 이름
#
set_host_ip_mapping() {
    local ip_address="$1"
    local hostname="$2"
    local hosts_file="/etc/hosts"

    # 1. 입력 유효성 검사: IP와 호스트명이 모두 제공되었는지 확인합니다.
    if [[ -z "${ip_address}" || -z "${hostname}" ]]; then
        echo "[ERROR] IP address and hostname are required." >&2
        return 1
    fi

    # 2. 안전한 임시 파일 생성: mktemp를 사용하여 충돌 없는 임시 파일을 만듭니다.
    local temp_file
    temp_file=$(mktemp)
    if [[ ! -f "${temp_file}" ]]; then
        echo "[ERROR] Failed to create a temporary file." >&2
        return 1
    fi

    echo "[INFO] Preparing update for ${hosts_file}: ${hostname} -> ${ip_address}..."

    # 3. awk로 기존 항목을 필터링하여 임시 파일에 저장합니다.
    #    - 주석 처리된 라인(`^\s*#`)은 건드리지 않습니다.
    #    - `\\<`와 `\\>`는 단어 경계를 의미하여, 'host1'이 'host11'의 일부로 인식되는 것을 방지합니다.
    awk -v host="${hostname}" '!($0 !~ /^\s*#/ && $0 ~ "\\<" host "\\>")' "${hosts_file}" > "${temp_file}"

    # 4. 새로운 호스트 정보를 임시 파일의 끝에 추가합니다.
    echo -e "${ip_address}\t${hostname}" >> "${temp_file}"

    # 5. commit_file_change를 호출하여 변경사항을 안전하게 적용합니다.
    #    이 함수는 원본 파일의 소유자와 권한을 보존하면서 임시 파일을 덮어씁니다.
    local commit_status=0
    commit_file_change "${temp_file}" "${hosts_file}"
    commit_status=$? # commit_file_change의 반환 코드를 저장

    # 6. 임시 파일을 삭제하고 결과에 따라 상태 코드를 반환합니다.
    rm -f "${temp_file}"
    if (( commit_status == 0 )); then
        echo "[SUCCESS] ${hosts_file} has been updated successfully."
        return 0
    else
        echo "[ERROR] Failed to apply changes to ${hosts_file}." >&2
        return 1
    fi
}


##
# @description 시스템의 호스트 이름을 변경. (systemd 필요)
# @param $1 new_hostname 설정할 새 호스트 이름
#
set_hostname() {
    local new_hostname="$1"

    if [[ -z "${new_hostname}" ]]; then
        echo "[ERROR] New hostname cannot be empty." >&2
        return 1
    fi

    if ! command -v hostnamectl &> /dev/null; then
        echo "[ERROR] 'hostnamectl' is not available. This function requires a systemd-based system." >&2
        return 1
    fi

    echo "Changing hostname to '${new_hostname}'..."
    if ${G_SUDO_PREFIX} hostnamectl set-hostname "${new_hostname}"; then
        echo "Hostname successfully changed to '${new_hostname}'."
        echo "Note: A reboot or new login session may be required for the change to be fully reflected."
    else
        echo "[ERROR] Failed to change hostname." >&2
        return 1
    fi
}

# ------------------------------------------------------------------------------
# @description systemd-networkd를 사용해 특정 인터페이스에 고정 IP를 설정.
#           - networkd가 활성화되어 있어야 함.
# @param $1 interface_name 설정할 인터페이스 (예: eth0)
# @param $2 ip_with_cidr IP 주소와 서브넷 마스크 (예: 192.168.1.100/24)
# @param $3 gateway 게이트웨이 주소
# @param $4 dns DNS 서버 주소
# ------------------------------------------------------------------------------
_set_static_ip_nmcli() {
    local interface="$1"; local ip_cidr="$2"; local gateway="$3"; local dns="$4"
    
    echo "[INFO] Applying static IP via NetworkManager (nmcli)..."
    if ${G_SUDO_PREFIX} nmcli con mod "${interface}" ipv4.method manual ipv4.addresses "${ip_cidr}" ipv4.gateway "${gateway}" ipv4.dns "${dns}" && \
       ${G_SUDO_PREFIX} nmcli con down "${interface}" && ${G_SUDO_PREFIX} nmcli con up "${interface}"; then
        echo "[SUCCESS] Successfully applied new IP settings via nmcli."
        return 0
    else
        echo "[ERROR] Failed to apply IP settings using nmcli." >&2
        return 1
    fi
}

# ------------------------------------------------------------------------------
# @description systemd-networkd를 사용해 특정 인터페이스에 고정 IP를 설정.
#           - networkd가 활성화되어 있어야 함.
# @param $1 interface_name 설정할 인터페이스 (예: eth0)
# @param $2 ip_with_cidr IP 주소와 서브넷 마스크 (예: 192.168.1.100/24)
# @param $3 gateway 게이트웨이 주소
# @param $4 dns DNS 서버 주소
# ------------------------------------------------------------------------------
_set_static_ip_networkd() {
    local interface="$1"; local ip_cidr="$2"; local gateway="$3"; local dns="$4"
    local conf_file="/etc/systemd/network/10-${interface}.network"

    echo "[INFO] Creating network configuration for systemd-networkd..."
    
    local network_config="[Match]\nName=${interface}\n\n[Network]\nAddress=${ip_cidr}\nGateway=${gateway}\nDNS=${dns}"
    
    # 설정 파일을 생성
    if ! echo -e "${network_config}" | ${G_SUDO_PREFIX} tee "${conf_file}" > /dev/null; then
        echo "[ERROR] Failed to write network configuration to ${conf_file}." >&2
        return 1
    fi

    echo "[INFO] Applying configuration for '${interface}' without a full service restart..."
    # systemctl restart 대신 networkctl reconfigure 사용
    if ${G_SUDO_PREFIX} networkctl reconfigure "${interface}"; then
        echo "[SUCCESS] Successfully applied settings for '${interface}' via systemd-networkd."
        # systemd-resolved를 사용하는 경우 재시작하여 DNS 변경 사항 즉시 적용
        if systemctl is-active --quiet systemd-resolved; then
            ${G_SUDO_PREFIX} systemctl restart systemd-resolved
            echo "[INFO] Restarted systemd-resolved to apply new DNS settings."
        fi
        return 0
    else
        echo "[ERROR] Failed to reconfigure interface '${interface}' using networkctl." >&2
        return 1
    fi
}

##
# @description 지정된 인터페이스에 고정 IP를 설정. (NetworkManager 필요)
# @param $1 interface_name 설정할 인터페이스 (예: eth0)
# @param $2 ip_with_cidr IP 주소와 서브넷 마스크 (예: 192.168.1.100/24)
# @param $3 gateway 게이트웨이 주소
# @param $4 dns DNS 서버 주소
# @return 0: 성공, 1: 실패, 2: 지원 도구 없음
#
set_static_ip() {
    # 1. NetworkManager (nmcli)가 있으면, nmcli 헬퍼에게 모든 것을 위임.
    if command -v nmcli &> /dev/null; then
        _set_static_ip_nmcli "$@"
        return $?
    
    # 2. systemd-networkd가 있으면, networkd 헬퍼에게 모든 것을 위임.
    elif command -v networkctl &> /dev/null; then
        _set_static_ip_networkd "$@"
        return $?

    # 3. 지원하는 도구가 없으면 에러 처리.
    else
        echo "[ERROR] Supported network manager (NetworkManager or systemd-networkd) not found." >&2
        return 2
    fi
}

##
# @description 여러 인터페이스를 묶어 네트워크 본딩을 생성. (NetworkManager 필요)
# @param $1 bond_name 생성할 본드 이름 (예: bond0)
# @param $2 mode 본딩 모드 (예: active-backup, 802.3ad)
# @param $3 slave_interfaces 쉼표로 구분된 슬레이브 인터페이스 목록 (예: "eth0,eth1")
#
create_network_bond() {
    local bond_name="$1"; local mode="$2"; local slaves_str="$3"

    if ! command -v nmcli &> /dev/null; then
        echo "[ERROR] 'nmcli' is not available. This function requires NetworkManager." >&2
        return 1
    fi

    if nmcli con show "${bond_name}" &> /dev/null; then
        echo "[ERROR] Bond '${bond_name}' already exists." >&2
        return 1
    fi

    echo "[INFO] Creating network bond '${bond_name}'..."
    
    # 1. 본드 마스터 연결 프로필 생성
    if ! ${G_SUDO_PREFIX} nmcli con add type bond con-name "${bond_name}" ifname "${bond_name}" bond.options "mode=${mode}"; then
        echo "[ERROR] Failed to create bond master." >&2; return 1
    fi

    # 2. 쉼표로 구분된 문자열을 배열로 변환해 각 슬레이브를 추가
    IFS=',' read -ra slaves <<< "${slaves_str}"
    for slave in "${slaves[@]}"; do
        echo "[INFO] Adding slave interface '${slave}' to '${bond_name}'..."
        # 기존 연결을 삭제하고 슬레이브로 추가
        ${G_SUDO_PREFIX} nmcli con delete "${slave}" 2>/dev/null
        if ! ${G_SUDO_PREFIX} nmcli con add type bond-slave con-name "${bond_name}-slave-${slave}" ifname "${slave}" master "${bond_name}"; then
            echo "[ERROR] Failed to add slave '${slave}'." >&2; return 1
        fi
    done
    
    # 3. 본드 활성화
    if ${G_SUDO_PREFIX} nmcli con up "${bond_name}"; then
        echo "[SUCCESS] Network bond '${bond_name}' created and activated successfully."
    else
        echo "[ERROR] Failed to activate bond '${bond_name}'." >&2
        return 1
    fi
}
