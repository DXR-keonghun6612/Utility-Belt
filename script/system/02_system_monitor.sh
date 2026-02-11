#!/bin/bash
# ==============================================================================
# 파일명: 02_system_monitor.sh
# 최종 수정일: 2026-01-20
# 작업자 : K.H. Choi
# 설명: 시스템 하드웨어 정보 수집 및 JSON 출력 유틸리티.
# ==============================================================================


# ==============================================================================
# 초기화
# ==============================================================================

# -----------------------------------------------------------------------------
# @description 패키지 설치 유틸리티에 필요한 패키지를 확인하고 설치함.
# -----------------------------------------------------------------------------
_initialize_monitoring_utils() {
    # ensure_packages_installed 함수를 사용하여 패키지 확인 및 설치
    ensure_packages_installed "PACKAGES_LIST" "Monitoring Management Utils" "dmidecode" "util-linux" || return $?
    
    log_success "System monitoring utility initialized successfully."
    return 0
}

# 초기화 함수 호출
_initialize_monitoring_utils

get_cpu_info() {
    local model; model=$(lscpu | grep "Model name:" | sed 's/Model name:[ \t]*//')
    local cores; cores=$(lscpu | grep "^CPU(s):" | awk '{print $2}')
    echo "CPU Model: $model"
    echo "CPU Cores: $cores"
}

# 메인보드 정보 수집
get_motherboard_info() {
    local manufacturer; manufacturer=$(${G_SUDO_PREFIX} dmidecode -t 2 | grep 'Manufacturer:' | awk -F': ' '{print $2}')
    local product; product=$(${G_SUDO_PREFIX} dmidecode -t 2 | grep 'Product Name:' | awk -F': ' '{print $2}')
    echo "M/B Manufacturer: $manufacturer"
    echo "M/B Product: $product"
}

# 메모리 정보 수집
get_memory_info() {
    local raw_details; raw_details=$(_get_memory_details_raw)

    local installed_slots=0
    if [[ -z "$raw_details" ]]; then
        echo "  No installed memory modules found."
    else
        echo "Installed Memory Modules:"
        local total_size_mb=0
        
        while IFS='|' read -r count manufacturer type size_mb speed_mts; do
            installed_slots=$((installed_slots + count))
            total_size_mb=$((total_size_mb + count * size_mb))
            
            local size_str="${size_mb} MB"
            [[ "$size_mb" -ge 1024 ]] && size_str="$((size_mb / 1024)) GB"
            local speed_str="${speed_mts} MT/s"
            
            echo "  - ${count}x ${type} ${size_str} @ ${speed_str} (Manufacturer: ${manufacturer})"
        done <<< "$raw_details"

        if [[ "$total_size_mb" -gt 0 ]]; then
            local total_size_gb=$((total_size_mb / 1024))
            if [[ "$total_size_gb" -gt 0 ]]; then
                echo "Total Installed Memory: ${total_size_gb} GB"
            else
                echo "Total Installed Memory: ${total_size_mb} MB"
            fi
        fi
    fi

    # 빈 슬롯 정보 출력
    local total_slots; total_slots=$(${G_SUDO_PREFIX} dmidecode -t 16 | grep "Number Of Devices:" | awk -F': ' '{print $2}')
    if [[ -n "$total_slots" && "$total_slots" -gt 0 ]]; then
        local empty_slots=$((total_slots - installed_slots))
        echo "Total Memory Slots: ${total_slots}"
        echo "Installed Slots: ${installed_slots}"
        echo "Empty Slots: ${empty_slots}"
    fi
}

# GPU 정보 수집
get_gpu_info() {
    if command -v nvidia-smi &> /dev/null; then
        local model; model=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits)
        local memory; memory=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits)
        echo "GPU Chipset: ${model:-N/A}"
        echo "GPU Memory: ${memory:-N/A} MiB"
    else
        echo "GPU Info: NVIDIA Driver/SMI Not Found"
    fi
}

# 저장 장치 정보 수집
get_storage_info() {
    echo "Storage Devices:"
    lsblk -d -o NAME,MODEL,SIZE | grep -E 'sd|hd|vd|nvme'
}

# ==============================================================================
# --- 내부 헬퍼 함수 ---
# ==============================================================================

_get_memory_details_raw() {
    local memory_details; memory_details=$(${G_SUDO_PREFIX} dmidecode -t 17 | awk '
        BEGIN { RS = ""; FS = "\n" }
        {
            manufacturer = "N/A"; type = "N/A"; size_raw = "N/A"; speed = "N/A";
            for (i = 1; i <= NF; i++) {
                if ($i ~ /^[ \t]+Manufacturer:/) { sub(/^[^:]+:[ \t]*/, "", $i); manufacturer = $i }
                if ($i ~ /^[ \t]+Type:/)       { sub(/^[^:]+:[ \t]*/, "", $i); type = $i }
                if ($i ~ /^[ \t]+Size:/)       { sub(/^[^:]+:[ \t]*/, "", $i); size_raw = $i }
                if ($i ~ /^[ \t]+Configured Memory Speed:/) { sub(/^[^:]+:[ \t]*/, "", $i); speed = $i }
            }
            if (size_raw !~ /No Module Installed/ && size_raw !~ /N\/A/) {
                gsub(/^[ \t]+|[ \t]+$/, "", manufacturer);
                gsub(/^[ \t]+|[ \t]+$/, "", type);
                gsub(/^[ \t]+|[ \t]+$/, "", size_raw);
                gsub(/^[ \t]+|[ \t]+$/, "", speed);
                
                split(size_raw, size_parts, " ");
                val = size_parts[1];
                unit = size_parts[2];
                
                size_mb = 0;
                if (unit == "GB") {
                    size_mb = val * 1024;
                } else if (unit == "MB") {
                    size_mb = val;
                } else if (unit == "kB") {
                    size_mb = val / 1024;
                } else {
                    size_mb = val;
                }

                speed_mts = speed;
                sub(/ .*/, "", speed_mts);

                print manufacturer "|" type "|" size_mb "|" speed_mts
            }
        }')
    
    if [[ -n "$memory_details" ]]; then
        local summary; summary=$(echo "${memory_details}" | sort | uniq -c)
        while IFS= read -r line; do
            local count; count=$(echo "$line" | sed 's/^ *//' | cut -d' ' -f1)
            local data; data=$(echo "$line" | sed 's/^ *//' | cut -d' ' -f2-)
            echo "${count}|${data}"
        done <<< "$summary"
    fi
}

# ==============================================================================
# --- JSON 출력 함수 (재설계됨) ---
# ==============================================================================

get_system_info_json() {
    json_escape() {
        echo -n "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
    }

    local cpu_model="N/A"; local cpu_cores="0"
    if command -v lscpu &> /dev/null; then
        cpu_model=$(lscpu | grep "Model name:" | sed 's/Model name:[ \t]*//')
        cpu_cores=$(lscpu | grep "^CPU(s):" | awk '{print $2}')
    fi

    local mb_manufacturer="N/A"; local mb_product="N/A"
    if command -v dmidecode &> /dev/null; then
        mb_manufacturer=$(${G_SUDO_PREFIX} dmidecode -t 2 | grep 'Manufacturer:' | head -n 1 | awk -F': ' '{print $2}')
        mb_product=$(${G_SUDO_PREFIX} dmidecode -t 2 | grep 'Product Name:' | head -n 1 | awk -F': ' '{print $2}')
    fi

    local gpu_chipset="N/A"; local gpu_board_vendor="N/A"; local gpu_memory_mib="0"
    if command -v nvidia-smi &> /dev/null; then
        gpu_chipset=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits | head -n 1)
        gpu_memory_mib=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -n 1)
    fi

    local storage_json_array; storage_json_array=$(lsblk -d -o NAME,MODEL,SIZE -b | awk '
        NR > 1 {
            name=$1
            size=$NF
            model=""
            for (i=2; i<NF; i++) { model = model (i==2 ? "" : " ") $i }
            gsub(/\"/, "\\\"", model)
            if (NR > 2) printf ","
            printf "{\"name\":\"%s\",\"model\":\"%s\",\"size_bytes\":%s}", name, model, size
        }' | sed 's/^/[/' | sed 's/$/]/')

    local raw_mem_details; raw_mem_details=$(_get_memory_details_raw)
    local modules_json_parts=()
    if [[ -n "$raw_mem_details" ]]; then
        while IFS='|' read -r count manufacturer type size_mb speed_mts; do
            modules_json_parts+=( "$(printf '{"count":%s,"manufacturer":"%s","type":"%s","size_mb":%s,"speed_mts":%s}' \
                "$count" "$(json_escape "$manufacturer")" "$(json_escape "$type")" "${size_mb:-0}" "${speed_mts:-0}")" )
        done <<< "$raw_mem_details"
    fi
    
    local memory_modules_json="["
    [[ ${#modules_json_parts[@]} -gt 0 ]] && memory_modules_json+=$(IFS=,; echo "${modules_json_parts[*]}")
    memory_modules_json+="]"

    local total_slots="0"
    if command -v dmidecode &> /dev/null; then
        total_slots=$(${G_SUDO_PREFIX} dmidecode -t 16 | grep "Number Of Devices:" | awk -F': ' '{print $2}')
    fi
    
    local installed_slots=0
    [[ -n "$raw_mem_details" ]] && installed_slots=$(echo "$raw_mem_details" | awk -F'|' '{s+=$1} END {print s}')
    local empty_slots=$((total_slots - installed_slots))

    printf "{\n"
    printf '  "cpu": {\n'
    printf '    "model": "%s",\n' "$(json_escape "$cpu_model")"
    printf '    "cores": %s\n' "${cpu_cores:-0}"
    printf '  },\n'
    printf '  "motherboard": {\n'
    printf '    "manufacturer": "%s",\n' "$(json_escape "$mb_manufacturer")"
    printf '    "product": "%s"\n' "$(json_escape "$mb_product")"
    printf '  },\n'
    printf '  "gpu": {\n'
    printf '    "chipset": "%s",\n' "$(json_escape "$gpu_chipset")"
    printf '    "board_vendor": "%s",\n' "$(json_escape "$gpu_board_vendor")"
    printf '    "memory_mib": %s\n' "${gpu_memory_mib:-0}"
    printf '  },\n'
    printf '  "memory": {\n'
    printf '    "slots": {\n'
    printf '      "total": %s,\n' "${total_slots:-0}"
    printf '      "installed": %s,\n' "${installed_slots:-0}"
    printf '      "empty": %s\n' "${empty_slots:-0}"
    printf '    },\n'
    printf '    "modules": %s\n' "$memory_modules_json"
    printf '  },\n'
    printf '  "storage": %s\n' "${storage_json_array:-[]}"
    printf "}\n"
}
