#!/bin/bash
# ==============================================================================
# 파일명: opencv.sh
# 설명: OpenCV 빌드 및 설치 로직
# ==============================================================================

# -----------------------------------------------------------------------------
# @description OpenCV 설치 여부 확인 및 설정 동기화
# @return 0: 설치됨, 1: 설치 안 됨
# -----------------------------------------------------------------------------
is_installed_opencv() {
    local installed=1
    
    # 1. pkg-config 확인
    if pkg-config --exists opencv4 2>/dev/null || pkg-config --exists opencv 2>/dev/null; then
        installed=0
    fi

    # 2. Python 바인딩 확인
    if [[ $installed -ne 0 ]]; then
        if python3 -c "import cv2" &>/dev/null; then
            installed=0
        fi
    fi

    # [Sync Config] 설치 상태 동기화
    if [[ -n "${G_STATE_FILE}" ]]; then
        if [[ $installed -eq 0 ]]; then
            local current_val
            current_val=$(get_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "opencv")
            if [[ -z "${current_val}" ]]; then
                local timestamp; timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
                local ver="detected"
                # pkg-config로 버전 추출 시도
                if pkg-config --exists opencv4 2>/dev/null; then
                    ver=$(pkg-config --modversion opencv4)
                elif pkg-config --exists opencv 2>/dev/null; then
                    ver=$(pkg-config --modversion opencv)
                fi
                add_config_section "${G_STATE_FILE}" "APPLICATION_LIST"
                set_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "opencv" "${ver} (${timestamp})"
            fi
        else
            delete_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "opencv"
        fi
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
# @description OpenCV 빌드 로직 (소스 다운로드 및 컴파일)
# @param $1 version
# @param $2 with_cuda
# @param $3 gpu_arch
# @param $4 jobs
# @param $5 prefix
# @param $6 build_path (기본값: /tmp/opencv_build)
# -----------------------------------------------------------------------------
build_opencv_logic() {
    local version="${1:-4.10.0}"
    local with_cuda="${2:-OFF}"
    local gpu_arch="${3}"
    local jobs="${4:-$(nproc)}"
    local prefix="${5:-/usr/local}"
    local work_dir="${6:-/tmp/opencv_build}"

    local detected_cuda_path=$(_detect_cuda_toolkit)
    
    if [[ "${with_cuda}" == "ON" && -z "${detected_cuda_path}" ]]; then
        log_error "CUDA support requested but CUDA Toolkit not found."
        return 1
    fi

    if [[ "${with_cuda}" == "ON" && -z "${gpu_arch}" ]]; then
        if command -v nvidia-smi &>/dev/null; then
            gpu_arch=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader,nounits | head -n 1)
        fi
        [[ -z "${gpu_arch}" ]] && gpu_arch="7.5"
    fi

    log_info "Installing build dependencies for OpenCV ${version}..."
    ensure_packages_installed "PACKAGES_LIST" "OpenCV Build Dependencies" \
        "build-essential" "cmake" "git" "pkg-config" "unzip" "wget" \
        "libjpeg-dev" "libpng-dev" "libtiff-dev" \
        "libavcodec-dev" "libavformat-dev" "libswscale-dev" "libv4l-dev" \
        "libxvidcore-dev" "libx264-dev" \
        "libgtk-3-dev" "libatlas-base-dev" "gfortran" "python3-dev" "python3-numpy" || return 1

    mkdir -p "${work_dir}"
    cd "${work_dir}" || return 1

    log_info "Downloading OpenCV ${version} into ${work_dir}..."
    for repo in "opencv" "opencv_contrib"; do
        if [[ ! -d "${repo}-${version}" ]]; then
            wget -O "${repo}.zip" "https://github.com/opencv/${repo}/archive/${version}.zip" || return 1
            unzip "${repo}.zip" && rm "${repo}.zip"
        fi
    done

    log_info "Configuring CMake for OpenCV ${version}..."
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
            "-D CUDA_TOOLKIT_ROOT_DIR=${detected_cuda_path}"
            "-D CUDA_ARCH_BIN=${gpu_arch}"
            "-D WITH_CUBLAS=1"
            "-D CUDA_FAST_MATH=1"
        )
    fi

    cmake "${cmake_opts[@]}" .. || return 1

    log_info "Building OpenCV ${version} (Jobs: ${jobs})..."
    make -j"${jobs}" || return 1

    log_success "OpenCV ${version} build completed."
    return 0
}

# -----------------------------------------------------------------------------
# @description OpenCV 설치 로직 (시스템 적용)
# @param $1 version
# @param $2 with_cuda
# @param $3 gpu_arch
# @param $4 jobs
# @param $5 prefix
# @param $6 build_path (기본값: /tmp/opencv_build)
# -----------------------------------------------------------------------------
install_opencv_logic() {
    local version="${1:-4.10.0}"
    local prefix="${5:-/usr/local}"
    local work_dir="${6:-/tmp/opencv_build}"
    local build_dir="${work_dir}/opencv-${version}/build"

    if [[ ! -f "${build_dir}/Makefile" ]]; then
        log_info "Build artifacts not found at ${build_dir}. Starting build first..."
        build_opencv_logic "$@" || return 1
    fi

    log_info "Installing OpenCV ${version} from ${build_dir} to ${prefix}..."
    cd "${build_dir}" || return 1
    
    if ! ${G_SUDO_PREFIX} make install; then
        log_error "OpenCV installation failed."
        return 1
    fi

    ${G_SUDO_PREFIX} ldconfig

    local timestamp=$(date "+%Y-%m-%dT%H:%M:%S")
    add_config_section "${G_STATE_FILE}" "APPLICATION_LIST"
    set_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "opencv" "${version} (${timestamp})"

    log_success "OpenCV ${version} installed successfully."
    return 0
}
