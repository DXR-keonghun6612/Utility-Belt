#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/opencv.sh
# 최종 수정일: 2026-02-11
# 설명: OpenCV 설치를 위한 전용 UI.
# ==============================================================================

##
# @description OpenCV 설치를 위한 전용 UI.
#
ui_install_opencv() {
    # 1. OpenCV 버전 선택
    local version
    version=$(ui_create_menu "OpenCV Setup" "Select OpenCV Version" \
        "Choose the version of OpenCV to install:" 18 60 8 \
        "4.11.0" "Latest Stable" \
        "4.10.0" "Stable" \
        "4.9.0"  "Stable" \
        "4.8.0"  "Stable" \
        "4.5.5"  "Legacy (LTS-like)" \
        "3.4.16" "Legacy 3.x" \
        "CUSTOM" "Enter version manually")
    
    [[ "${version}" == "CANCEL" ]] && return 1

    if [[ "${version}" == "CUSTOM" ]]; then
        version=$(ui_input_box "Enter OpenCV version (e.g., 4.10.0):" "Custom Version" "4.10.0")
        [[ -z "$version" || "$version" == "CANCEL" ]] && return 1
    fi

    local with_cuda="OFF"
    local gpu_arch=""
    local gpu_arch_label=""
    
    # 2. CUDA 지원 여부 확인
    if ui_confirm "Do you want to build OpenCV with CUDA acceleration?\n(CUDA Toolkit must be installed)" "CUDA Support"; then
        with_cuda="ON"
        
        local detected_arch=""
        if command -v nvidia-smi &>/dev/null; then
            detected_arch=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader,nounits | head -n 1)
        fi

        local arch_prompt="Select GPU Compute Capability (Detected: ${detected_arch:-Unknown})"
        
        # 메뉴 구성을 배열로 정의하여 라벨 추출에 활용
        local arch_options=(
            "8.9" "Ada Lovelace (RTX 40-series, L4)"
            "8.6" "Ampere (RTX 30-series, A10/A30/A40)"
            "8.0" "Ampere (A100)"
            "7.5" "Turing (RTX 20-series, T4, GTX 16-series)"
            "7.2" "Xavier (Jetson AGX/NX)"
            "7.0" "Volta (V100)"
            "6.1" "Pascal (GTX 10-series, P4/P40)"
            "6.0" "Pascal (P100)"
            "5.2" "Maxwell (GTX 900-series, M40/M60)"
            "3.5" "Kepler (K40/K80)"
            "CUSTOM" "Enter custom value manually"
        )

        gpu_arch=$(ui_create_menu "CUDA Arch" "Select Architecture" "${arch_prompt}" 20 75 12 "${arch_options[@]}")

        [[ "${gpu_arch}" == "CANCEL" ]] && return 1

        if [[ "${gpu_arch}" == "CUSTOM" ]]; then
            gpu_arch=$(ui_input_box "Enter GPU Compute Capability (e.g., 8.6, 8.9):" "Custom CUDA Arch" "${detected_arch}")
            [[ -z "$gpu_arch" ]] && gpu_arch="${detected_arch}"
            gpu_arch_label="Custom (${gpu_arch})"
        else
            # 선택된 값에 해당하는 라벨 추출
            for ((i=0; i<${#arch_options[@]}; i+=2)); do
                if [[ "${arch_options[i]}" == "${gpu_arch}" ]]; then
                    gpu_arch_label="${arch_options[i+1]}"
                    break
                fi
            done
        fi
    fi

    # 3. 상세 빌드 설정
    local build_settings
    build_settings=$(ui_create_form "OpenCV Build Settings" "Configuration" "Enter build parameters:" 16 70 0 \
        "Base Build Dir:"  1 1 "/tmp/opencv_build" 1 20 45 0 \
        "Install Prefix:"  2 1 "/usr/local"        2 20 45 0 \
        "Parallel Jobs:"   3 1 "$(nproc)"          3 20 10 0)
    
    if [[ $? -ne 0 ]]; then return 1; fi

    local base_work_dir install_prefix jobs
    { read -r base_work_dir; read -r install_prefix; read -r jobs; } <<< "${build_settings}"
    
    [[ -z "$base_work_dir" ]] && base_work_dir="/tmp/opencv_build"
    [[ -z "$install_prefix" ]] && install_prefix="/usr/local"
    [[ -z "$jobs" ]] && jobs="$(nproc)"

    # 4. 설정 기반 고유 빌드 폴더명 생성
    local sub_dir="opencv-${version}"
    if [[ "${with_cuda}" == "ON" ]]; then
        sub_dir+="-${gpu_arch}"  # 아키텍처 번호만 포함
    else
        sub_dir+="-cpu"
    fi
    local final_work_dir="${base_work_dir}/${sub_dir}"

    # 5. 실행 액션 선택
    local action
    action=$(ui_create_menu "Select Action" "Choose what to do" "" 12 60 2 \
        "INSTALL" "Build and Install to System" \
        "BUILD"   "Build Only (No System Install)")
    
    [[ "${action}" == "CANCEL" ]] && return 1

    # 6. 최종 확인 요약
    local summary="OpenCV Build Plan:\n"
    summary+="- Version: ${version}\n"
    if [[ "${with_cuda}" == "ON" ]]; then
        summary+="- CUDA Support: ON (${gpu_arch_label})\n"
    else
        summary+="- CUDA Support: OFF (CPU Only)\n"
    fi
    summary+="- Install Prefix: ${install_prefix}\n"
    summary+="- Build Path: ${final_work_dir}\n"
    summary+="- Parallel Jobs: ${jobs}\n"
    summary+="- Selected Action: ${action}\n\n"
    summary+="Proceed with these settings?"

    if ! ui_confirm "${summary}" "Final Confirmation" 18 75; then
        return 1
    fi

    clear
    if [[ "${action}" == "INSTALL" ]]; then
        install_opencv_logic "${version}" "${with_cuda}" "${gpu_arch}" "${jobs}" "${install_prefix}" "${final_work_dir}"
    else
        build_opencv_logic "${version}" "${with_cuda}" "${gpu_arch}" "${jobs}" "${install_prefix}" "${final_work_dir}"
    fi

    read -rp $'\nOperation completed. Press Enter to continue...'
}
