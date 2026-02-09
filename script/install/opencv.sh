#!/bin/bash
# ==============================================================================
# 파일명: opencv.sh
# 설명: OpenCV (Source Build) 설치 로직 (CUDA Toolkit 감지 및 연동 지원)
# ==============================================================================

# -----------------------------------------------------------------------------
# @description OpenCV 설치 여부 확인
# -----------------------------------------------------------------------------
is_installed_opencv() {
    local installed=1
    
    # 1. pkg-config 확인
    if pkg-config --exists opencv4 2>/dev/null || pkg-config --exists opencv 2>/dev/null; then
        installed=0
    fi

    # 2. Python 바인딩 확인
    if python3 -c "import cv2" &>/dev/null; then
        installed=0
    fi

    return $installed
}

# -----------------------------------------------------------------------------
# @description CUDA Toolkit 설치 여부 및 경로 감지
# -----------------------------------------------------------------------------
_detect_cuda_toolkit() {
    local default_cuda_path="/usr/local/cuda"
    
    if [[ -d "${default_cuda_path}" ]]; then
        echo "${default_cuda_path}"
    elif command -v nvcc &>/dev/null; then
        local nvcc_path
        nvcc_path=$(which nvcc)
        echo "${nvcc_path%/bin/nvcc}"
    else
        echo ""
    fi
}

# -----------------------------------------------------------------------------
# @description OpenCV 설치 메인 로직
# -----------------------------------------------------------------------------
install_opencv_logic() {
    # --- 0. 환경 감지 ---
    local detected_cuda_path
    detected_cuda_path=$(_detect_cuda_toolkit)
    local cpu_cores=$(nproc)
    
    # --- 1. 사용자 옵션 입력 (UI) ---
    
    # 1-1. 버전 선택
    local version
    version=$(ui_input_box "Enter OpenCV version to install:" "OpenCV Setup" "4.10.0")
    [[ -z "$version" || "$version" == "CANCEL" ]] && return 1

    # 1-2. CUDA 옵션 (CUDA Toolkit이 감지된 경우에만)
    local with_cuda="OFF"
    local cuda_path=""
    local gpu_arch=""

    if [[ -n "$detected_cuda_path" ]]; then
        if ui_confirm "CUDA Toolkit detected at '${detected_cuda_path}'.

Do you want to build OpenCV with CUDA acceleration?" "CUDA Support"; then
            with_cuda="ON"
            
            # CUDA 경로 확인 (사용자가 직접 수정 가능)
            cuda_path=$(ui_input_box "Confirm CUDA Toolkit Path:" "CUDA Settings" "${detected_cuda_path}")
            [[ -z "$cuda_path" ]] && cuda_path="${detected_cuda_path}"

            # GPU 아키텍처(Compute Capability) 감지 및 입력
            local detected_arch=""
            if command -v nvidia-smi &>/dev/null; then
                detected_arch=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader,nounits | head -n 1)
            fi
            gpu_arch=$(ui_input_box "Enter GPU Compute Capability (e.g., 8.6, 8.9):" "CUDA Arch" "${detected_arch}")
            [[ -z "$gpu_arch" ]] && gpu_arch="${detected_arch}"
        fi
    fi

    # 1-3. 빌드 및 설치 설정
    local jobs=$(ui_input_box "Enter number of parallel build jobs:" "Build Speed" "${cpu_cores}")
    [[ -z "$jobs" ]] && jobs="${cpu_cores}"

    local prefix=$(ui_input_box "Enter installation prefix:" "Install Path" "/usr/local")
    [[ -z "$prefix" ]] && prefix="/usr/local"

    # --- 2. 의존성 설치 ---
    echo "[INFO] Installing system dependencies..."
    ensure_packages_installed "SYSTEM_TOOLS" "OpenCV Build Dependencies" 
        "build-essential" "cmake" "git" "pkg-config" "unzip" "wget" 
        "libjpeg-dev" "libpng-dev" "libtiff-dev" 
        "libavcodec-dev" "libavformat-dev" "libswscale-dev" "libv4l-dev" 
        "libxvidcore-dev" "libx264-dev" 
        "libgtk-3-dev" "libatlas-base-dev" "gfortran" "python3-dev" "python3-numpy" || return 1

    # --- 3. 소스 다운로드 ---
    local work_dir="/tmp/opencv_build"
    mkdir -p "${work_dir}"
    cd "${work_dir}" || return 1

    echo "[INFO] Downloading OpenCV ${version} and Contrib..."
    for repo in "opencv" "opencv_contrib"; do
        if [[ ! -d "${repo}-${version}" ]]; then
            wget -O "${repo}.zip" "https://github.com/opencv/${repo}/archive/${version}.zip" || return 1
            unzip "${repo}.zip" && rm "${repo}.zip"
        fi
    done

    # --- 4. 빌드 및 설치 ---
    echo "[INFO] Configuring CMake..."
    cd "opencv-${version}" || return 1
    mkdir -p build && cd build || return 1

    local cmake_opts=(
        "-D CMAKE_BUILD_TYPE=RELEASE"
        "-D CMAKE_INSTALL_PREFIX=${prefix}"
        "-D CMAKE_CXX_STANDARD=17"
        "-D OPENCV_EXTRA_MODULES_PATH=../../opencv_contrib-${version}/modules"
        "-D WITH_OPENGL=ON"
        "-D WITH_QT=OFF"
        "-D OPENCV_GENERATE_PKGCONFIG=ON"
        "-D BUILD_opencv_python3=ON"
        "-D ENABLE_FAST_MATH=1"
    )

    if [[ "${with_cuda}" == "ON" ]]; then
        cmake_opts+=(
            "-D WITH_CUDA=ON"
            "-D WITH_CUDNN=ON"
            "-D OPENCV_DNN_CUDA=ON"
            "-D CUDA_TOOLKIT_ROOT_DIR=${cuda_path}"
            "-D CUDA_ARCH_BIN=${gpu_arch}"
            "-D WITH_CUBLAS=1"
            "-D CUDA_FAST_MATH=1"
        )
    fi

    cmake "${cmake_opts[@]}" .. || return 1

    echo "[INFO] Building OpenCV ${version} (Jobs: ${jobs})..."
    make -j"${jobs}" || return 1

    echo "[INFO] Installing to ${prefix}..."
    ${G_SUDO_PREFIX} make install || return 1
    ${G_SUDO_PREFIX} ldconfig

    # --- 5. 완료 기록 ---
    local timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
    set_config_value "${CONFIG_FILE}" "APPLICATION_LIST" "opencv" "${version} (${timestamp})"
    
    ui_message_box "OpenCV ${version} installation completed.
Location: ${prefix}
CUDA Support: ${with_cuda}" "Success"
    return 0
}
