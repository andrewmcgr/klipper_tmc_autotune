#!/bin/bash

KLIPPER_PATH="${HOME}/klipper"
AUTOTUNETMC_PATH="${HOME}/klipper_tmc_autotune"

IS_K1_OS=0
if grep -Fqs "ID=buildroot" /etc/os-release; then
  KLIPPER_PATH="/usr/share/klipper"
  AUTOTUNETMC_PATH="/usr/data/klipper_tmc_autotune"
  IS_K1_OS=1
fi

set -eu
export LC_ALL=C


function preflight_checks {
    if [ "$EUID" -eq 0 ]; then
        echo "[PRE-CHECK] This script must not be run as root!"
        exit -1
    fi

    if [ "$(sudo systemctl list-units --full -all -t service --no-legend | grep -F 'klipper.service')" ]; then
        printf "[PRE-CHECK] Klipper service found! Continuing...\n\n"
    else
        echo "[ERROR] Klipper service not found, please install Klipper first!"
        exit -1
    fi
}

function check_download {
    local autotunedirname autotunebasename
    autotunedirname="$(dirname ${AUTOTUNETMC_PATH})"
    autotunebasename="$(basename ${AUTOTUNETMC_PATH})"

    if [ ! -d "${AUTOTUNETMC_PATH}" ]; then

        echo "[DOWNLOAD] Downloading Autotune TMC repository..."
        if git -C $autotunedirname clone https://github.com/pellcorp/klipper_tmc_autotune.git ${AUTOTUNETMC_PATH}; then
            chmod +x ${AUTOTUNETMC_PATH}/install.sh
            printf "[DOWNLOAD] Download complete!\n\n"
        else
            echo "[ERROR] Download of Autotune TMC git repository failed!"
            exit -1
        fi
    else
        printf "[DOWNLOAD] Autotune TMC repository already found locally. Continuing...\n\n"
    fi
}

function link_extension {
    echo "[INSTALL] Linking extension to Klipper..."
    LN_ARGS="-srfn"
    if [[ $IS_K1_OS -eq 1 ]]; then
      LN_ARGS="-sfn"
    fi
    ln $LN_ARGS "${AUTOTUNETMC_PATH}/autotune_tmc.py" "${KLIPPER_PATH}/klippy/extras/autotune_tmc.py"
    ln $LN_ARGS "${AUTOTUNETMC_PATH}/motor_constants.py" "${KLIPPER_PATH}/klippy/extras/motor_constants.py"
    ln $LN_ARGS "${AUTOTUNETMC_PATH}/motor_database.cfg" "${KLIPPER_PATH}/klippy/extras/motor_database.cfg"
}

function restart_klipper {
    echo "[POST-INSTALL] Restarting Klipper..."
    if [[ $IS_K1_OS -eq 1 ]]; then
      /etc/init.d/S55klipper_service restart
    else
      sudo systemctl restart klipper
    fi
}


printf "\n======================================\n"
echo "- Autotune TMC install script -"
printf "======================================\n\n"


# Run steps
if [[ $IS_K1_OS -ne 1 ]]; then
  preflight_checks
fi
check_download
link_extension
restart_klipper
