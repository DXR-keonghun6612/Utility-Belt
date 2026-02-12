#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/software/opencv.sh
# 최종 수정일: 2026-02-11
# 설명: OpenCV 설치를 위한 전용 UI (가독성 강화 버전).
# ==============================================================================

##
# @description OpenCV 설치를 위한 전용 UI.
#
ui_install_opencv() {
    # 1. 초기값 및 기본 설정
    local version="4.11.0"
    local with_cuda="OFF"
    local gpu_arch=""
    local gpu_arch_label="N/A"
    local cpp_std="17"
    local base_work_dir="/tmp/opencv_build"
    local install_prefix="/usr/local"
    local python_path; python_path=$(which python3)
    local jobs; jobs=$(nproc)

    # 2. OpenCV 버전 선택
    local ver_prompt="Select the version of OpenCV you wish to build.\n"
    ver_prompt+="Note: 4.x versions are recommended for most modern applications."
    
    version=$(ui_create_menu "OpenCV Setup" "Step 1: Select Version" "${ver_prompt}" 18 65 8 \
        "4.11.0" "Latest Stable" \
        "4.10.0" "Stable" \
        "4.9.0"  "Stable" \
        "4.8.0"  "Stable" \
        "4.5.5"  "Legacy (LTS-like)" \
        "3.4.16" "Legacy 3.x" \
        "CUSTOM" "Enter version manually")
    [[ "${version}" == "CANCEL" ]] && return 1

    if [[ "${version}" == "CUSTOM" ]]; then
        version=$(ui_input_box "Enter OpenCV version string (e.g., 4.11.0):" "Custom Version" "4.11.0")
        [[ -z "$version" || "$version" == "CANCEL" ]] && return 1
    fi

    # 3. CUDA 지원 여부 확인
    local cuda_confirm_msg="Do you want to enable NVIDIA GPU acceleration via CUDA?\n\n"
    cuda_confirm_msg+="Prerequisites:\n"
    cuda_confirm_msg+="- NVIDIA Driver and CUDA Toolkit must be installed.\n"
    cuda_confirm_msg+="- Compatible NVIDIA GPU required."

    if ui_confirm "${cuda_confirm_msg}" "Step 2: CUDA Support"; then
        with_cuda="ON"
        
        local detected_arch=""
        [[ -x "$(command -v nvidia-smi)" ]] && \
            detected_arch=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader,nounits | head -n 1)

        local arch_prompt="Select your GPU Compute Capability (Multiple select allowed).\n"
        arch_prompt+="Detected Architecture: ${detected_arch:-Unknown}\n\n"
        arch_prompt+="Note: Selecting multiple architectures increases build time."

        # 체크리스트 옵션: "태그" "설명" "상태(ON/OFF)"
        local arch_options=(
            "9.0" "Hopper (H100)" "OFF"
            "8.9" "Ada Lovelace (RTX 40-series, L4)" "OFF"
            "8.6" "Ampere (RTX 30-series, A10/A30/A40)" "OFF"
            "8.0" "Ampere (A100)" "OFF"
            "7.5" "Turing (RTX 20-series, T4, GTX 16-series)" "OFF"
            "7.2" "Xavier (Jetson AGX/NX)" "OFF"
            "7.0" "Volta (V100)" "OFF"
            "6.1" "Pascal (GTX 10-series, P4/P40)" "OFF"
            "6.0" "Pascal (P100)" "OFF"
            "5.2" "Maxwell (GTX 900-series, M40/M60)" "OFF"
            "3.5" "Kepler (K40/K80)" "OFF"
        )

        # 감지된 아키텍처가 목록에 있으면 자동으로 ON 설정
        if [[ -n "${detected_arch}" ]]; then
            for ((i=0; i<${#arch_options[@]}; i+=3)); do
                if [[ "${arch_options[i]}" == "${detected_arch}" ]]; then
                    arch_options[i+2]="ON"
                    break
                fi
            done
        fi

        gpu_arch=$(ui_create_checklist "CUDA Arch" "Step 2-1: GPU Architecture" "${arch_prompt}" 20 75 12 "${arch_options[@]}")
        [[ "${gpu_arch}" == "CANCEL" ]] && return 1

        # 아무것도 선택하지 않았을 경우 처리
        if [[ -z "${gpu_arch}" ]]; then
            if ui_confirm "No architecture selected. Enter manually?" "Warning"; then
                gpu_arch=$(ui_input_box "Enter GPU Compute Capability (e.g., 8.6 8.9):" "Custom CUDA Arch" "${detected_arch}")
                [[ -z "$gpu_arch" ]] && gpu_arch="${detected_arch}"
            else
                return 1
            fi
        fi
        
        gpu_arch_label="Selected: ${gpu_arch// /;}"
    fi

    # 4. C++ Standard 선택
    local cpp_prompt="Choose the C++ standard for compilation.\n"
    cpp_prompt+="C++17 is the recommended default for OpenCV 4.x."

    cpp_std=$(ui_create_menu "C++ Standard" "Step 3: Language Standard" "${cpp_prompt}" 15 60 4 \
        "11" "C++11" \
        "14" "C++14" \
        "17" "C++17 (Recommended)" \
        "20" "C++20")
    [[ "${cpp_std}" == "CANCEL" ]] && return 1

    # 5. 상세 빌드 설정 루프 (취소 시 재편집 가능)
    while true; do
        local build_settings
        build_settings=$(ui_create_form "Configuration" "Step 4: Path and Performance" "Review and edit build paths:" 18 70 0 \
            "Base Build Dir:"  1 1 "${base_work_dir}" 1 20 45 0 \
            "Install Prefix:"  2 1 "${install_prefix}" 2 20 45 0 \
            "Python Path:"     3 1 "${python_path}"    3 20 45 0 \
            "Parallel Jobs:"   4 1 "${jobs}"           4 20 10 0)
        
        [[ $? -ne 0 ]] && return 1

        { read -r base_work_dir; read -r install_prefix; read -r python_path; read -r jobs; } <<< "${build_settings}"
        
        base_work_dir="${base_work_dir:-/tmp/opencv_build}"
        install_prefix="${install_prefix:-/usr/local}"
        python_path="${python_path:-$(which python3)}"
        jobs="${jobs:-$(nproc)}"

        # 백엔드 함수를 사용하여 실제 생성될 경로 미리 계산 (CUDA/cuDNN 버전 감지 포함)
        local cuda_path; cuda_path=$(detect_cuda_toolkit_path)
        local detected_cuda_v; detected_cuda_v=$(detect_cuda_version "${cuda_path}")
        local detected_cudnn_v; detected_cudnn_v=$(detect_cudnn_version)

        local paths; paths=$(_resolve_opencv_paths "${version}" "${with_cuda}" "${gpu_arch}" "${cpp_std}" "${base_work_dir}" "${detected_cuda_v}" "${detected_cudnn_v}")
        local work_dir="${paths%|*}"
        local build_dir="${paths#*|}"

        local preview="[PROPOSED_BUILD_PLAN]\n"
        preview+="--------------------------------------------------\n"
        preview+="Version        : ${version}\n"
        preview+="C++ Standard   : C++${cpp_std}\n"
        preview+="CUDA Support   : ${with_cuda}\n"
        if [[ "${with_cuda}" == "ON" ]]; then
            preview+="  - GPU Arch   : ${gpu_arch} (${gpu_arch_label})\n"
            preview+="  - CUDA Toolkit: ${detected_cuda_v:-NOT_FOUND}\n"
            preview+="  - cuDNN Lib  : ${detected_cudnn_v:-NOT_FOUND}\n"
        fi
        preview+="Python Path    : ${python_path}\n"
        preview+="Install Prefix : ${install_prefix}\n"
        preview+="Work Directory : ${work_dir}\n"
        preview+="Build Directory: ${build_dir}\n"
        preview+="Parallel Jobs  : ${jobs}\n"
        preview+="--------------------------------------------------\n\n"
        preview+="Does this configuration look correct?"

        if ui_confirm "${preview}" "Step 5: Final Review" 22 75; then
            break
        fi
    done

    # 6. 실행 액션 선택
    local action_prompt="Final Step: Choose your target action.\n\n"
    action_prompt+="- INSTALL: Compile and apply changes to the system.\n"
    action_prompt+="- BUILD  : Compile only, keep results in the build dir."

    local action
    action=$(ui_create_menu "Action Selection" "Step 6: Execute" "${action_prompt}" 15 70 2 \
        "INSTALL" "Build and Install to System" \
        "BUILD"   "Build Only (No System Install)")
    [[ "${action}" == "CANCEL" ]] && return 1

    clear
    if [[ "${action}" == "INSTALL" ]]; then
        install_opencv_logic "${version}" "${with_cuda}" "${gpu_arch}" "${jobs}" "${install_prefix}" "${base_work_dir}" "${python_path}" "${cpp_std}"
    else
        build_opencv_logic "${version}" "${with_cuda}" "${gpu_arch}" "${jobs}" "${install_prefix}" "${base_work_dir}" "${python_path}" "${cpp_std}"
    fi

    # 7. 종료 결과 표시
    # 실제 생성된 경로를 다시 한번 계산하여 메타데이터 파일 확인
    local cuda_path; cuda_path=$(detect_cuda_toolkit_path)
    local cuda_ver=""; [[ "${with_cuda}" == "ON" ]] && cuda_ver=$(detect_cuda_version "${cuda_path}")
    local cudnn_ver=""; [[ "${with_cuda}" == "ON" ]] && cudnn_ver=$(detect_cudnn_version)
    local paths; paths=$(_resolve_opencv_paths "${version}" "${with_cuda}" "${gpu_arch}" "${cpp_std}" "${base_work_dir}" "${cuda_ver}" "${cudnn_ver}")
    local work_dir="${paths%|*}"
    local meta_file="${work_dir}/asap_build_info.ini"

    if [[ -f "${meta_file}" ]]; then
        ui_show_textbox "${meta_file}" "Process Complete: Build Metadata" 20 80
    else
        log_info "Process finished. Check build artifacts in ${work_dir}"
        read -rp $'\nPress Enter to continue...'
    fi
}
