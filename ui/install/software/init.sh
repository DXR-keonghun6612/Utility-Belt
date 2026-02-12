#!/usr/bin/env bash
# ==============================================================================
# 파일명: ui/install/software/init.sh
# 설명: 개별 소프트웨어(Docker, VSCode, Conda, ROS2, OpenCV) 설치 UI를 호출하는 메인 메뉴.
# ==============================================================================

ui_install_software_main() {
    while true; do
        local choice
        choice=$(ui_create_menu "Software Installation" "Select Software to Manage" \
            "Choose a software to install, configure, or remove:" 20 70 12 \
            "DOCKER"  "Docker Engine & NVIDIA Container Toolkit" \
            "VSCODE"  "Visual Studio Code" \
            "CONDA"   "Miniconda/Anaconda Distribution" \
            "ROS2"    "Robot Operating System 2" \
            "OPENCV"  "OpenCV (Source Build & Install)" \
            "BACK"    "Return to Previous Menu")

        case "${choice}" in
            "DOCKER") ui_install_docker ;;
            "VSCODE") ui_install_vscode ;;
            "CONDA")  ui_install_conda ;;
            "ROS2")   ui_install_ros2 ;;
            "OPENCV") ui_install_opencv ;;
            "BACK" | "CANCEL") break ;;
        esac
    done
}
