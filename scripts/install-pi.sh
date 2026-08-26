#!/usr/bin/env bash
set -Eeuo pipefail

readonly APP_ROOT=/opt/familybox
readonly STATE_ROOT=/srv/familybox
readonly CONFIG_ROOT=/etc/familybox
readonly SERVICE_NAME=familybox.service
readonly BEGIN_MARKER="# BEGIN FAMILYBOX"
readonly END_MARKER="# END FAMILYBOX"

WITH_ONOFF_SHIM=false
REQUESTED_HOSTNAME=""

usage() {
  cat <<'EOF'
Usage: sudo ./scripts/install-pi.sh [options]

Install FamilyBox on Raspberry Pi OS Lite 64-bit.

Options:
  --hostname NAME       Set a unique mDNS hostname (for example familybox-alice)
  --with-onoff-shim     Enable GPIO4/17 power overlays; the SHIM must be installed
  -h, --help            Show this help

The script enables the service for the next boot but never reboots automatically.
EOF
}

die() {
  printf 'familybox install: %s\n' "$*" >&2
  exit 1
}

note() {
  printf 'familybox install: %s\n' "$*"
}

while (($#)); do
  case "$1" in
    --hostname)
      (($# >= 2)) || die "--hostname requires a value"
      REQUESTED_HOSTNAME=$2
      shift 2
      ;;
    --with-onoff-shim)
      WITH_ONOFF_SHIM=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "unknown option: $1 (use --help)"
      ;;
  esac
done

[[ ${EUID} -eq 0 ]] || die "run this script as root (sudo $0 ...)"
[[ -r /proc/device-tree/model ]] || die "no Raspberry Pi device tree found"
grep -aq 'Raspberry Pi' /proc/device-tree/model || die "this installer supports Raspberry Pi OS only"
command -v apt-get >/dev/null || die "apt-get is required"
command -v dpkg >/dev/null || die "dpkg is required"
command -v systemctl >/dev/null || die "systemd is required"
[[ $(dpkg --print-architecture) == arm64 ]] \
  || die "FamilyBox requires Raspberry Pi OS Lite 64-bit (arm64)"

if [[ -n ${REQUESTED_HOSTNAME} ]]; then
  [[ ${REQUESTED_HOSTNAME} =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]] \
    || die "hostname must be 1-63 lowercase letters, digits, or hyphens and cannot start/end with a hyphen"
fi

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
SOURCE_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd -P)
[[ -f ${SOURCE_ROOT}/pyproject.toml ]] || die "run the installer from a complete FamilyBox checkout"
[[ -f ${SOURCE_ROOT}/systemd/${SERVICE_NAME} ]] || die "missing systemd/${SERVICE_NAME}"

if [[ -f /boot/firmware/config.txt ]]; then
  BOOT_CONFIG=/boot/firmware/config.txt
elif [[ -f /boot/config.txt ]]; then
  BOOT_CONFIG=/boot/config.txt
else
  die "could not find Raspberry Pi config.txt"
fi

# Once enabled, retain the SHIM overlays on routine installer updates. Removing
# power-control support should be an explicit manual hardware/configuration act.
if grep -Fq 'dtoverlay=gpio-poweroff,gpiopin=4,active_low=1,input=1' "${BOOT_CONFIG}"; then
  WITH_ONOFF_SHIM=true
fi

note "installing Raspberry Pi OS packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  alsa-utils \
  avahi-daemon \
  build-essential \
  libnss-mdns \
  mpv \
  python3 \
  python3-dev \
  python3-gpiozero \
  python3-pip \
  python3-spidev \
  python3-venv \
  rsync \
  sqlite3

command -v raspi-config >/dev/null || die "raspi-config is required on Raspberry Pi OS"
note "enabling hardware SPI0"
raspi-config nonint do_spi 0

if [[ -n ${REQUESTED_HOSTNAME} ]]; then
  note "setting hostname to ${REQUESTED_HOSTNAME}"
  raspi-config nonint do_hostname "${REQUESTED_HOSTNAME}"
fi

if ! getent group familybox >/dev/null; then
  groupadd --system familybox
fi
if ! id familybox >/dev/null 2>&1; then
  useradd \
    --system \
    --gid familybox \
    --home-dir "${STATE_ROOT}" \
    --shell /usr/sbin/nologin \
    familybox
fi

for hardware_group in audio gpio spi; do
  getent group "${hardware_group}" >/dev/null \
    || die "expected Raspberry Pi OS group is missing: ${hardware_group}"
  usermod --append --groups "${hardware_group}" familybox
done

install -d -o root -g root -m 0755 "${APP_ROOT}"
install -d -o familybox -g familybox -m 0750 \
  "${STATE_ROOT}" \
  "${STATE_ROOT}/media" \
  "${STATE_ROOT}/data" \
  "${STATE_ROOT}/cache" \
  "${STATE_ROOT}/logs"
install -d -o root -g familybox -m 0750 "${CONFIG_ROOT}"

if [[ ${SOURCE_ROOT} == "${APP_ROOT}" || ${SOURCE_ROOT} == "${APP_ROOT}/"* ]]; then
  DEPLOY_SOURCE=${SOURCE_ROOT}
else
  DEPLOY_SOURCE=${APP_ROOT}/source
  install -d -o root -g root -m 0755 "${DEPLOY_SOURCE}"
  note "copying application source to ${DEPLOY_SOURCE}"
  rsync -a \
    --chown=root:root \
    --exclude .familybox \
    --exclude .git \
    --exclude .mypy_cache \
    --exclude .pytest_cache \
    --exclude .ruff_cache \
    --exclude .venv \
    --exclude build \
    --exclude dist \
    --exclude '__pycache__' \
    --exclude '*.egg-info' \
    "${SOURCE_ROOT}/" "${DEPLOY_SOURCE}/"
fi

if [[ ! -x ${APP_ROOT}/.venv/bin/python ]]; then
  note "creating Python virtual environment"
  python3 -m venv --system-site-packages "${APP_ROOT}/.venv"
fi

note "installing FamilyBox and Raspberry Pi hardware dependencies"
"${APP_ROOT}/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
"${APP_ROOT}/.venv/bin/python" -m pip install "${DEPLOY_SOURCE}[pi]"

CURRENT_HOSTNAME=${REQUESTED_HOSTNAME:-$(hostname -s)}
if [[ ! ${CURRENT_HOSTNAME} =~ ^familybox- ]]; then
  note "hostname '${CURRENT_HOSTNAME}' does not follow the recommended familybox-<device> pattern"
  note "rerun with --hostname familybox-<device> for the documented mDNS address"
fi
ENV_FILE=${CONFIG_ROOT}/familybox.env
if [[ ! -e ${ENV_FILE} ]]; then
  note "creating ${ENV_FILE}"
  DEVICE_ID=$(python3 -c 'import uuid; print(uuid.uuid4())')
  {
    printf 'FAMILYBOX_ROOT=%s\n' "${STATE_ROOT}"
    printf 'FAMILYBOX_HARDWARE=raspberry_pi\n'
    printf 'FAMILYBOX_AUDIO=mpv\n'
    printf 'FAMILYBOX_DEVICE_ID=%s\n' "${DEVICE_ID}"
    printf 'FAMILYBOX_DEVICE_NAME=%s\n' "${CURRENT_HOSTNAME}"
    printf 'FAMILYBOX_HOSTNAME=%s\n' "${CURRENT_HOSTNAME}"
    printf 'FAMILYBOX_MPV_SOCKET=/run/familybox/mpv.sock\n'
    printf 'FAMILYBOX_WEB_HOST=0.0.0.0\n'
    printf 'FAMILYBOX_WEB_PORT=80\n'
    printf 'FAMILYBOX_PROGRESS_SAVE_INTERVAL=60\n'
    printf 'FAMILYBOX_LOG_LEVEL=INFO\n'
    printf 'FAMILYBOX_JSON_LOGS=true\n'
    printf 'FAMILYBOX_DEV_ENDPOINTS=false\n'
  } > "${ENV_FILE}"
else
  note "preserving existing ${ENV_FILE}"
  if [[ -n ${REQUESTED_HOSTNAME} ]]; then
    if grep -q '^FAMILYBOX_HOSTNAME=' "${ENV_FILE}"; then
      sed -i "s/^FAMILYBOX_HOSTNAME=.*/FAMILYBOX_HOSTNAME=${REQUESTED_HOSTNAME}/" "${ENV_FILE}"
    else
      printf 'FAMILYBOX_HOSTNAME=%s\n' "${REQUESTED_HOSTNAME}" >> "${ENV_FILE}"
    fi
  fi
fi
chown root:familybox "${ENV_FILE}"
chmod 0640 "${ENV_FILE}"

# The overlay registers the card with this stable name. Make it ALSA's default
# explicitly so a connected HDMI display cannot win card-ordering races.
ASOUND_CONFIG=/etc/asound.conf
ASOUND_BEGIN="# BEGIN FAMILYBOX AUDIO"
ASOUND_END="# END FAMILYBOX AUDIO"
ASOUND_TMP=$(mktemp /etc/asound.conf.familybox.XXXXXX)
trap 'rm -f -- "${ASOUND_TMP:-}"' EXIT
if [[ -f ${ASOUND_CONFIG} ]]; then
  sed "/^${ASOUND_BEGIN}$/,/^${ASOUND_END}$/d" "${ASOUND_CONFIG}" > "${ASOUND_TMP}"
fi
{
  printf '\n%s\n' "${ASOUND_BEGIN}"
  printf '%s\n' 'pcm.!default {'
  printf '%s\n' '  type plug'
  printf '%s\n' '  slave.pcm "hw:CARD=MAX98357A,DEV=0"'
  printf '%s\n' '}'
  printf '%s\n' "${ASOUND_END}"
} >> "${ASOUND_TMP}"
install -o root -g root -m 0644 "${ASOUND_TMP}" "${ASOUND_CONFIG}"
rm -f -- "${ASOUND_TMP}"
trap - EXIT

if [[ ${WITH_ONOFF_SHIM} == true ]]; then
  note "configuring I2S audio and OnOff SHIM power control"
else
  note "configuring I2S audio"
fi
BOOT_TMP=$(mktemp "${BOOT_CONFIG}.familybox.XXXXXX")
trap 'rm -f -- "${BOOT_TMP:-}"' EXIT
sed "/^${BEGIN_MARKER}$/,/^${END_MARKER}$/d" "${BOOT_CONFIG}" > "${BOOT_TMP}"
{
  printf '\n%s\n' "${BEGIN_MARKER}"
  printf '%s\n' '[all]'
  printf '%s\n' 'dtparam=audio=off'
  printf '%s\n' 'dtparam=i2s=on'
  printf '%s\n' 'dtoverlay=max98357a,no-sdmode'
  if [[ ${WITH_ONOFF_SHIM} == true ]]; then
    printf '%s\n' 'dtoverlay=gpio-shutdown,gpio_pin=17,active_low=1,gpio_pull=up,debounce=100'
    printf '%s\n' 'dtoverlay=gpio-poweroff,gpiopin=4,active_low=1,input=1'
  fi
  printf '%s\n' "${END_MARKER}"
} >> "${BOOT_TMP}"
cp -- "${BOOT_TMP}" "${BOOT_CONFIG}"
rm -f -- "${BOOT_TMP}"
trap - EXIT

install -o root -g root -m 0644 \
  "${SOURCE_ROOT}/systemd/${SERVICE_NAME}" \
  "/etc/systemd/system/${SERVICE_NAME}"

systemctl daemon-reload
systemctl enable avahi-daemon.service
systemctl enable "${SERVICE_NAME}"

note "installation complete; reboot to activate SPI/I2S overlays and start FamilyBox"
note "after reboot, open http://${CURRENT_HOSTNAME}.local"
if [[ ${WITH_ONOFF_SHIM} == false ]]; then
  note "OnOff SHIM overlays were not enabled; install the SHIM, then rerun with --with-onoff-shim"
fi
