#!/bin/bash
# ==============================================================================
# Script Name: setup_service.sh
# Description: Registers the FastAPI application as a systemd service.
# Usage: ./setup_service.sh
# ==============================================================================

# 1. Path Setup
# ------------------------------------------------------------------------------
# Resolve absolute path of the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
TOOLBOX_DIR="${PROJECT_ROOT}/submodules/script_toolbox/ubuntu"

# 2. Load Toolbox
# ------------------------------------------------------------------------------
if [[ -f "${TOOLBOX_DIR}/load_core.sh" ]]; then
    source "${TOOLBOX_DIR}/load_core.sh"
else
    echo "[FATAL] Cannot load toolbox from ${TOOLBOX_DIR}"
    echo "Please ensure submodules are initialized: git submodule update --init --recursive"
    exit 1
fi

# Ensure dialog is installed (load_core.sh loads 02_dialog.sh which checks this)
if ! command -v dialog &>/dev/null; then
    echo "[INFO] Installing 'dialog' for UI..."
    ensure_packages_installed "PACKAGES_LIST" "dialog"
fi

# 3. Detect Defaults
# ------------------------------------------------------------------------------
DEFAULT_USER="${USER}"
DEFAULT_SERVICE_NAME="utility-belt"
DEFAULT_PORT="8000"
DEFAULT_WORKERS="4"

# Try to detect virtual environment
DETECTED_VENV=""
for venv_name in ".venv" "venv" "env"; do
    if [[ -d "${PROJECT_ROOT}/${venv_name}" ]]; then
        DETECTED_VENV="${PROJECT_ROOT}/${venv_name}"
        break
    fi
done
# Fallback default if not found
[[ -z "${DETECTED_VENV}" ]] && DETECTED_VENV="${PROJECT_ROOT}/.venv"

# 4. Gather Information (UI)
# ------------------------------------------------------------------------------
# We use a loop to ensure valid input or cancellation
while true; do
    VALUES=$(ui_create_form "Service Setup" "Configuration" \
        "Please confirm the service configuration." \
        15 75 5 \
        "Service Name:" 1 1 "${DEFAULT_SERVICE_NAME}" 1 20 20 30 \
        "Run User:"     2 1 "${DEFAULT_USER}"         2 20 20 30 \
        "Port:"         3 1 "${DEFAULT_PORT}"         3 20 20 30 \
        "Workers:"      4 1 "${DEFAULT_WORKERS}"      4 20 20 30 \
        "Venv Path:"    5 1 "${DETECTED_VENV}"        5 20 45 100 \
    )

    # Handle Cancel
    if [[ $? -ne 0 ]]; then
        ui_message_box "Installation cancelled by user." "Cancelled"
        exit 0
    fi

    # Parse Results into array (compatible with bash 4.0+)
    mapfile -t CONFIG_VALUES <<< "${VALUES}"
    
    SERVICE_NAME="${CONFIG_VALUES[0]}"
    RUN_USER="${CONFIG_VALUES[1]}"
    PORT="${CONFIG_VALUES[2]}"
    WORKERS="${CONFIG_VALUES[3]}"
    VENV_PATH="${CONFIG_VALUES[4]}"

    # Basic Validation
    UVICORN_BIN="${VENV_PATH}/bin/uvicorn"
    
    if [[ ! -f "${UVICORN_BIN}" ]]; then
        ui_message_box "[ERROR] uvicorn not found at:\n${UVICORN_BIN}\n\nPlease check the VirtualEnv Path.\n(Make sure 'pip install -r requirements.txt' was run)" "Validation Error"
        # Loop continues to let user fix the path
    else
        break # Validation passed
    fi
done

# 5. Generate Service File Content
# ------------------------------------------------------------------------------
# Note: Using absolute paths and PYTHONPATH to ensure modules are found
SERVICE_FILE_CONTENT="[Unit]\nDescription=${SERVICE_NAME} (FastAPI)\nAfter=network.target\n\n[Service]\nUser=${RUN_USER}\nGroup=$(id -gn "${RUN_USER}")\nWorkingDirectory=${PROJECT_ROOT}\nEnvironment=\"PATH=${VENV_PATH}/bin:/usr/local/bin:/usr/bin:/bin\"\nEnvironment=\"PYTHONPATH=${PROJECT_ROOT}\"\nExecStart=${UVICORN_BIN} web.main:app --host 0.0.0.0 --port ${PORT} --workers ${WORKERS}\nRestart=always\nRestartSec=5\n\n[Install]\nWantedBy=multi-user.target\n"

# 6. Install Service
# ------------------------------------------------------------------------------
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

if ui_confirm "Ready to install systemd service.\n\nService: ${SERVICE_NAME}\nFile: ${SERVICE_PATH}\nUser: ${RUN_USER}\nPort: ${PORT}" "Confirm Installation"; then
    
    # Create temp file
    TEMP_SERVICE_FILE=$(mktemp)
    echo "${SERVICE_FILE_CONTENT}" > "${TEMP_SERVICE_FILE}"
    
    echo "=================================================================="
    echo " Installing Service..."
    echo "=================================================================="

    # 1. Install .service file
    echo "[INFO] Copying service file..."
    if [[ "${G_IS_ROOT}" == "false" ]]; then
        sudo install -m 644 "${TEMP_SERVICE_FILE}" "${SERVICE_PATH}"
    else
        install -m 644 "${TEMP_SERVICE_FILE}" "${SERVICE_PATH}"
    fi
    rm -f "${TEMP_SERVICE_FILE}"

    # 2. Reload daemon
    echo "[INFO] Reloading systemd..."
    ${G_SUDO_PREFIX} systemctl daemon-reload

    # 3. Enable service
    echo "[INFO] Enabling service..."
    ${G_SUDO_PREFIX} systemctl enable "${SERVICE_NAME}"

    # 4. Restart service
    echo "[INFO] Starting service..."
    ${G_SUDO_PREFIX} systemctl restart "${SERVICE_NAME}"

    # 5. Check status
    echo "[INFO] Checking status..."
    sleep 2
    if ${G_SUDO_PREFIX} systemctl is-active --quiet "${SERVICE_NAME}"; then
        ui_message_box "Service '${SERVICE_NAME}' is now running!\n\nLogs: sudo journalctl -u ${SERVICE_NAME} -f" "Success"
    else
        # Show last few logs on failure
        LOGS=$(${G_SUDO_PREFIX} journalctl -u "${SERVICE_NAME}" -n 10 --no-pager)
        ui_message_box "Service '${SERVICE_NAME}' failed to start.\n\nRecent logs:\n${LOGS}" "Failure"
    fi

else
    echo "Installation cancelled."
    exit 0
fi
