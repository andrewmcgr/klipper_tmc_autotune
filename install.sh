#!/bin/bash

KLIPPER_PATH="${HOME}/klipper"
AUTOTUNETMC_PATH="${HOME}/klipper_tmc_autotune"

if [[ -e ${KLIPPER_PATH}/klippy/plugins/ ]]; then
    KLIPPER_PLUGINS_PATH="${KLIPPER_PATH}/klippy/plugins/"
else
    KLIPPER_PLUGINS_PATH="${KLIPPER_PATH}/klippy/extras/"
fi

set -eu
export LC_ALL=C


function preflight_checks {
    if [ "$EUID" -eq 0 ]; then
        echo "[PRE-CHECK] This script must not be run as root!"
        exit 1
    fi

    if sudo systemctl list-units --full -all -t service --no-legend | grep -q 'klipper.service'; then
        echo "[PRE-CHECK] Klipper service found!"
    else
        echo "[ERROR] Klipper service not found, please install Klipper first!"
        exit 1
    fi

    # Try to determine the klippy virtual environment from the local Moonraker instance
    KLIPPY_PYTHON_PATH=$(wget -qO- http://localhost:7125/printer/info | python -c 'import sys, json; print(json.load(sys.stdin)["result"]["python_path"])' 2>/dev/null || true)
    # Fall back to the default location
    KLIPPY_PYTHON_PATH=${KLIPPY_PYTHON_PATH:-"${HOME}/klippy-env/bin/python"}
    # Get the major Python version
    KLIPPY_PYTHON_VERSION=$("${KLIPPY_PYTHON_PATH}" -c 'import sys; print(sys.version_info.major)')

    if [[ ${KLIPPY_PYTHON_VERSION} -lt 3 ]]; then
        echo "[ERROR] Klipper must be using Python 3 - detected outdated Python 2"
        exit 1
    else
        echo "[PRE-CHECK] Klipper is using Python 3!"
    fi

    printf "\n\n"
}

function check_download {
    local autotunedirname autotunebasename
    autotunedirname="$(dirname "${AUTOTUNETMC_PATH}")"
    autotunebasename="$(basename "${AUTOTUNETMC_PATH}")"

    if [ ! -d "${AUTOTUNETMC_PATH}" ]; then
        echo "[DOWNLOAD] Downloading Autotune TMC repository..."
        if git -C "${autotunedirname}" clone https://github.com/andrewmcgr/klipper_tmc_autotune.git $autotunebasename; then
            chmod +x "${AUTOTUNETMC_PATH}"/install.sh
            printf "[DOWNLOAD] Download complete!\n\n"
        else
            echo "[ERROR] Download of Autotune TMC git repository failed!"
            exit 1
        fi
    else
        printf "[DOWNLOAD] Autotune TMC repository already found locally. Continuing...\n\n"
    fi
}

function link_extension {
    echo "[INSTALL] Linking extension to Klipper..."

    ln -srfn "${AUTOTUNETMC_PATH}/autotune_tmc.py" "${KLIPPER_PLUGINS_PATH}/autotune_tmc.py"
    ln -srfn "${AUTOTUNETMC_PATH}/motor_constants.py" "${KLIPPER_PLUGINS_PATH}/motor_constants.py"
    ln -srfn "${AUTOTUNETMC_PATH}/motor_database.cfg" "${KLIPPER_PLUGINS_PATH}/motor_database.cfg"
}

function restart_klipper {
    echo "[POST-INSTALL] Restarting Klipper..."
    sudo systemctl restart klipper
}


printf "\n======================================\n"
echo "- Autotune TMC install script -"
printf "======================================\n\n"


# Run steps
preflight_checks
check_download
link_extension
restart_klipper
