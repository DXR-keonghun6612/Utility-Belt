#!/bin/bash
# ==============================================================================
# 파일명: opencv.sh
# 설명: OpenCV 빌드 및 설치 로직 (4-Stage Pipeline 준수)
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
                set_config_value   "${G_STATE_FILE}" "APPLICATION_LIST" "opencv" "${ver} (${timestamp})"
            fi
        else
            delete_config_value "${G_STATE_FILE}" "APPLICATION_LIST" "opencv"
        fi
    fi

    return $installed
}

# -----------------------------------------------------------------------------
# @description OpenCV 빌드/작업 경로 계산 (중복 로직 방지)
# @param $1 version, $2 with_cuda, $3 gpu_arch, $4 cpp_std, $5 base_work_dir, $6 cuda_ver, $7 cudnn_ver
# @stdout "work_dir|build_dir"
# -----------------------------------------------------------------------------
_resolve_opencv_paths() {
    local version="$1"
    local with_cuda="$2"
    local gpu_arch="$3"
    local cpp_std="$4"
    local base_work_dir="$5"
    local cuda_ver="$6"
    local cudnn_ver="$7"

    local suffix="cpu"
    if [[ "${with_cuda}" == "ON" ]]; then
        suffix="cuda"
        [[ -n "${cuda_ver}" ]]  && suffix+="-v${cuda_ver}"
        [[ -n "${cudnn_ver}" ]] && suffix+="-dn${cudnn_ver}"
        
        # 멀티 아키텍처 문자열 정제 (공백/세미콜론을 언더바로 변경)
        local arch_clean; arch_clean=$(echo "${gpu_arch:-unknown}" | tr ' ;' '__' | sed 's/__*/_/g' | sed 's/^_//;s/_$//')
        suffix+="-${arch_clean}"
    fi

    local specific_dir="opencv-${version}"
    local work_dir="${base_work_dir%/}/${specific_dir}"
    local build_dir="${work_dir}/build-${suffix}-cpp${cpp_std}"
    
    echo "${work_dir}|${build_dir}"
}

# -----------------------------------------------------------------------------
# @description [Stage 1] OpenCV 빌드 및 실행에 필요한 시스템 의존성 설치
# -----------------------------------------------------------------------------
_ensure_opencv_dependencies() {
    log_info "Installing build dependencies for OpenCV..."
    
    local base_deps=(
        "build-essential" "cmake" "git" "pkg-config" "unzip" "wget"
    )
    local img_deps=(
        "libjpeg-dev" "libpng-dev" "libtiff-dev" "libwebp-dev" "libopenexr-dev"
    )
    local vid_deps=(
        "libavcodec-dev" "libavformat-dev" "libswscale-dev" 
        "libv4l-dev" "libxvidcore-dev" "libx264-dev" 
        "libgstreamer1.0-dev" "libgstreamer-plugins-base1.0-dev"
    )
    local ui_math_deps=(
        "libgtk-3-dev" "libatlas-base-dev" "gfortran" 
        "libtbb-dev" "libgl1-mesa-dev" "libglu1-mesa-dev"
    )
    local py_deps=(
        "python3-dev" "python3-numpy"
    )

    ensure_packages_installed "PACKAGES_LIST" "OpenCV Build Dependencies" \
        "${base_deps[@]}" \
        "${img_deps[@]}" \
        "${vid_deps[@]}" \
        "${ui_math_deps[@]}" \
        "${py_deps[@]}" || return 1
}


# -----------------------------------------------------------------------------
# @description [Stage 2-1] OpenCV CMake 설정 (컴파일 제외)
# @private
# -----------------------------------------------------------------------------
_configure_opencv_logic() {
    local version="$1"
    local with_cuda="$2"
    local gpu_arch="$3"
    local prefix="$4"
    local base_work_dir="$5"
    local python_executable="$6"
    local cpp_std="$7"
    local build_dir="$8"

    log_info "Configuring CMake for OpenCV ${version} (C++${cpp_std})..."
    mkdir -p "${build_dir}" && cd "${build_dir}" || return 1

    local cmake_opts=(
        "-D CMAKE_BUILD_TYPE=RELEASE"
        "-D CMAKE_INSTALL_PREFIX=${prefix}"
        "-D CMAKE_CXX_STANDARD=${cpp_std}"
        "-D OPENCV_EXTRA_MODULES_PATH=../opencv_contrib-${version}/modules"
        "-D WITH_OPENGL=ON"
        "-D WITH_QT=OFF"
        "-D OPENCV_GENERATE_PKGCONFIG=ON"
        "-D ENABLE_FAST_MATH=1"
        "-D BUILD_opencv_python3=ON"
        "-D PYTHON3_EXECUTABLE=${python_executable}"
        "-D BUILD_opencv_python2=OFF"
        "-D WITH_PYTHON=OFF"
    )

    if [[ "${with_cuda}" == "ON" ]]; then
        local cuda_path; cuda_path=$(detect_cuda_toolkit_path)
        local cmake_gpu_arch; cmake_gpu_arch=$(echo "${gpu_arch}" | tr ' ' ';')
        cmake_opts+=(
            "-D WITH_CUDA=ON"
            "-D WITH_CUDNN=ON"
            "-D OPENCV_DNN_CUDA=ON"
            "-D CUDA_TOOLKIT_ROOT_DIR=${cuda_path}"
            "-D CUDA_ARCH_BIN=${cmake_gpu_arch}"
            "-D WITH_CUBLAS=1"
            "-D CUDA_FAST_MATH=1"
        )
    fi

    cmake "${cmake_opts[@]}" "../opencv-${version}"
}

# -----------------------------------------------------------------------------
# @description [Stage 2-2] OpenCV 실제 컴파일 및 메타데이터 기록
# @private
# -----------------------------------------------------------------------------
_build_opencv_logic() {
    local version="$1"
    local with_cuda="$2"
    local gpu_arch="$3"
    local jobs="$4"
    local prefix="$5"
    local base_work_dir="$6"
    local python_executable="$7"
    local cpp_std="$8"
    local build_dir="$9"
    local work_dir="${10}"
    local cuda_ver="${11}"
    local cudnn_ver="${12}"

    # 1. CMake 설정 호출
    _configure_opencv_logic "${version}" "${with_cuda}" "${gpu_arch}" "${prefix}" \
        "${base_work_dir}" "${python_executable}" "${cpp_std}" "${build_dir}" || return 1

    # 2. 컴파일 실행
    log_info "Compiling OpenCV ${version} (Jobs: ${jobs})..."
    make -j"${jobs}" || return 1

    # 3. 빌드 메타데이터 저장
    local meta_file="${build_dir}/asap_build_info.ini"
    
    log_info "Saving build metadata to ${meta_file}..."
    {
        echo "[OPENCV_BUILD_METADATA]"
        echo "version=${version}"
        echo "cuda_support=${with_cuda}"
        echo "cuda_version=${cuda_ver:-N/A}"
        echo "cudnn_version=${cudnn_ver:-N/A}"
        echo "gpu_arch=${gpu_arch:-N/A}"
        echo "cpp_standard=${cpp_std}"
        echo "python_executable=${python_executable}"
        echo "install_prefix=${prefix}"
        echo "base_work_dir=${base_work_dir}"
        echo "actual_work_dir=${work_dir}"
        echo "parallel_jobs=${jobs}"
        echo "build_date=$(date '+%Y-%m-%d %H:%M:%S')"
        echo "build_host=$(hostname)"
        echo "os_info=$(grep PRETTY_NAME /etc/os-release | cut -d'=' -f2 | tr -d '\"')"
        echo "kernel_version=$(uname -r)"
    } > "${meta_file}"

    log_success "OpenCV ${version} build completed successfully."
    return 0
}

# -----------------------------------------------------------------------------
# @description [Stage 3] 빌드된 결과물을 시스템에 설치
# @private
# -----------------------------------------------------------------------------
_perform_opencv_install() {
    local version="$1"
    local with_cuda="$2"
    local gpu_arch="$3"
    local prefix="$4"
    local build_dir="$5"
    local work_dir="$6"
    local python_path="$7"
    local cpp_std="$8"
    local cuda_ver="$9"
    local cudnn_ver="${10}"

    log_info "Installing OpenCV ${version} from ${build_dir} to ${prefix}..."
    cd "${build_dir}" || return 1
    
    ${G_SUDO_PREFIX} make install && ${G_SUDO_PREFIX} ldconfig || return 1
    # 상태 기록
    add_config_section "${G_STATE_FILE}" "OPENCV_INFO"
    set_config_value   "${G_STATE_FILE}" "OPENCV_INFO" "version"        "${version}"
    set_config_value   "${G_STATE_FILE}" "OPENCV_INFO" "cuda"           "${with_cuda}"
    set_config_value   "${G_STATE_FILE}" "OPENCV_INFO" "cuda_version"  "${cuda_ver}"
    set_config_value   "${G_STATE_FILE}" "OPENCV_INFO" "cudnn_version" "${cudnn_ver}"
    set_config_value   "${G_STATE_FILE}" "OPENCV_INFO" "arch"          "${gpu_arch}"
    set_config_value   "${G_STATE_FILE}" "OPENCV_INFO" "installed_at"  "$(date '+%Y-%m-%dT%H:%M:%S')"

    log_success "OpenCV ${version} installed successfully."
}

# -----------------------------------------------------------------------------
# @description OpenCV 처리 로직 (통합 인터페이스)
# -----------------------------------------------------------------------------
process_opencv_logic() {
    local opt="${1:-all}"
    local version="${2:-4.11.0}"
    local with_cuda="${3:-OFF}"
    local gpu_arch="${4}"
    local jobs="${5:-$(nproc)}"
    local prefix="${6:-/usr/local}"
    local base_work_dir="${7:-/tmp/opencv_build}"
    local python_path="${8:-$(which python3)}"
    local cpp_std="${9:-17}"

    # 1. 의존성 및 환경 감지
    _ensure_opencv_dependencies || return 1
    
    local cuda_path; cuda_path=$(detect_cuda_toolkit_path)
    local cuda_ver=""
local cudnn_ver=""

    if [[ "${with_cuda}" == "ON" ]]; then
        cuda_ver=$(detect_cuda_version "${cuda_path}")
        cudnn_ver=$(detect_cudnn_version)
        [[ -z "${gpu_arch}" ]] && gpu_arch="7.5"
    fi

    local paths;     paths=$(_resolve_opencv_paths "${version}" "${with_cuda}" "${gpu_arch}" "${cpp_std}" "${base_work_dir}" "${cuda_ver}" "${cudnn_ver}")
    local work_dir="${paths%|*}"
local build_dir="${paths#*|}"
    local build_tag=$(basename "${build_dir}")
    local meta_file="${work_dir}/build_${version}_${build_tag}.ini"

    # 2. 빌드 유효성 검사 및 보정 로직
    local need_fresh_build=false

    if [[ -f "${build_dir}/Makefile" ]]; then
        log_info "Existing build detected at ${build_dir}."
        
        if [[ -f "${meta_file}" ]]; then
            # 메타데이터에서 중요 환경 정보 추출
            local old_os; old_os=$(get_config_value "${meta_file}" "OPENCV_BUILD_METADATA" "os_info")
            local old_cuda; old_cuda=$(get_config_value "${meta_file}" "OPENCV_BUILD_METADATA" "cuda_version")
            local old_cudnn; old_cudnn=$(get_config_value "${meta_file}" "OPENCV_BUILD_METADATA" "cudnn_version")
            local old_path; old_path=$(get_config_value "${meta_file}" "OPENCV_BUILD_METADATA" "actual_work_dir")
            
            local current_os; current_os=$(grep PRETTY_NAME /etc/os-release | cut -d'=' -f2 | tr -d '\"')

            # [Case A] 환경 변화 감지 -> 무조건 재빌드
            if [[ "${old_os}" != "${current_os}" ]] || [[ "${old_cuda}" != "${cuda_ver}" ]] || [[ "${old_cudnn}" != "${cudnn_ver}" ]]; then
                log_warn "System environment has changed. Existing build is invalid."
                need_fresh_build=true

            # [Case B] 경로 불일치 감지 -> CMake 설정만 갱신 후 Touch
            elif [[ "${old_path}" != "${work_dir}" ]]; then
                log_warn "Path mismatch detected. Fixing paths via CMake (fast)..."

                cd "${work_dir}" || return 1

                _configure_opencv_logic "${version}" "${with_cuda}" "${gpu_arch}" "${prefix}" \
                    "${base_work_dir}" "${python_path}" "${cpp_std}" "${build_dir}" || return 1

                (cd "${build_dir}" && make -j"${jobs}" -t > /dev/null 2>&1)

            # [Case C] 모두 일치 -> Touch만 수행
            else
                log_info "Environment and path match. Updating timestamps..."
                (cd "${build_dir}" && make -j"${jobs}" -t > /dev/null 2>&1)
            fi
        else
            log_warn "Metadata file missing. Forcing fresh build."
            need_fresh_build=true
        fi
    else
        need_fresh_build=true
    fi

    # 3. 소스 다운로드 및 전체 빌드 (필요 시)
    if [[ "${need_fresh_build}" == "true" ]]; then
        log_info "Starting a fresh build of OpenCV ${version}..."

        [[ -d "${build_dir}" ]] && ${G_SUDO_PREFIX} rm -rf "${build_dir}"

        _build_opencv_logic "${version}" "${with_cuda}" "${gpu_arch}" "${jobs}" "${prefix}" \
            "${base_work_dir}" "${python_path}" "${cpp_std}" "${build_dir}" "${work_dir}" "${cuda_ver}" "${cudnn_ver}" || return 1
    fi

    # 4. 시스템 설치 수행
    if [[ "${opt}" == "all" ]]; then
        _perform_opencv_install "${version}" "${with_cuda}" "${gpu_arch}" "${prefix}" \
            "${build_dir}" "${work_dir}" "${python_path}" "${cpp_std}" "${cuda_ver}" "${cudnn_ver}"
    fi
}
