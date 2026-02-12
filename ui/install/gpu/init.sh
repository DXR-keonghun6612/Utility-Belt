#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/gpu/init.sh
# 설명: GPU 스택(Driver, CUDA, cuDNN) 설치 UI를 호출하는 메인 메뉴.
# ==============================================================================

ui_install_gpu_stack() {
    while true; do
        local choice
        choice=$(ui_create_menu "GPU Stack Installation" "NVIDIA GPU Stack" \
            "Select a component to manage:" 20 70 10 \
            "DRIVER"  "Install NVIDIA Driver" \
            "CUDA"    "Install/Manage CUDA Toolkit" \
            "CUDNN"   "Install cuDNN Library" \
            "BACK"    "Return to Previous Menu")

        case "${choice}" in
            "DRIVER") ui_install_nvidia_driver ;;
            "CUDA")   ui_install_cuda_toolkit ;;
            "CUDNN")  ui_install_cudnn_library ;;
            "BACK" | "CANCEL") break ;;
        esac
    done
}
