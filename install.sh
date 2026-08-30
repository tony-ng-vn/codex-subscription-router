#!/bin/bash

set -euo pipefail

readonly HOMEBREW_NODE_22="/opt/homebrew/opt/node@22/bin"
if [ -x "${HOMEBREW_NODE_22}/node" ]; then
    PATH="${HOMEBREW_NODE_22}:${PATH}"
    export PATH
fi

readonly REPOSITORY_URL="https://github.com/tony-ng-vn/codex-subscription-router.git"
readonly DEFAULT_SOURCE_DIR="${HOME}/.codex-subscription-router/source"
readonly SOURCE_DIR="${CODEX_SUBSCRIPTION_ROUTER_SOURCE_DIR:-${DEFAULT_SOURCE_DIR}}"
readonly DESTINATION_APP="${HOME}/Applications/Codex Subscription Router.app"
readonly DESTINATION_HELPER="${HOME}/Applications/Codex Subscription Router Computer Use.app"
readonly MANAGED_DESTINATION_APP="/Applications/ChatGPT.app"
MANAGED_SOURCE_DIR=""

cleanup_managed_source() {
    if [ -z "${MANAGED_SOURCE_DIR}" ]; then
        return
    fi
    case "${MANAGED_SOURCE_DIR}" in
        /tmp/codex-subscription-router-source.*)
            rm -rf -- "${MANAGED_SOURCE_DIR}"
            ;;
    esac
    MANAGED_SOURCE_DIR=""
}

trap cleanup_managed_source EXIT

log() {
    printf '\n==> %s\n' "$1" >&2
}

fail() {
    printf '\nInstall failed: %s\n' "$1" >&2
    exit 1
}

require_prerequisites() {
    if [ "$(uname -s)" != "Darwin" ]; then
        fail "Codex Subscription Router supports macOS only."
    fi
    if [ "$(uname -m)" != "arm64" ]; then
        fail "Codex Subscription Router currently requires Apple silicon."
    fi
    if [ ! -d "/Applications/ChatGPT.app" ]; then
        fail "install the official ChatGPT app in /Applications first."
    fi

    local missing=()
    local command_name
    for command_name in git go node npm python3 security xcrun; do
        if ! command -v "${command_name}" >/dev/null 2>&1; then
            missing+=("${command_name}")
        fi
    done
    if [ "${#missing[@]}" -ne 0 ]; then
        fail "missing prerequisites: ${missing[*]}. Install Xcode Command Line Tools, Go 1.26+, and Node.js 22.12+, then rerun this command."
    fi

    local node_major
    local node_minor
    node_major="$(node -p 'process.versions.node.split(".")[0]')"
    node_minor="$(node -p 'process.versions.node.split(".")[1]')"
    if [ "${node_major}" -lt 22 ] || { [ "${node_major}" -eq 22 ] && [ "${node_minor}" -lt 12 ]; }; then
        fail "Node.js 22.12 or newer is required; found $(node --version)."
    fi

    local go_version
    local go_major
    local go_minor
    go_version="$(go env GOVERSION | sed 's/^go//')"
    go_major="${go_version%%.*}"
    go_minor="${go_version#*.}"
    go_minor="${go_minor%%.*}"
    if [ "${go_major}" -lt 1 ] || { [ "${go_major}" -eq 1 ] && [ "${go_minor}" -lt 26 ]; }; then
        fail "Go 1.26 or newer is required; found go${go_version}."
    fi
}

resolve_source_dir() {
    local script_source="${BASH_SOURCE[0]:-}"
    local script_dir=""
    if [ -n "${script_source}" ] && [ -f "${script_source}" ]; then
        script_dir="$(CDPATH= cd -- "$(dirname -- "${script_source}")" && pwd)"
    fi
    if [ -n "${script_dir}" ] && [ -f "${script_dir}/scripts/patch_app.py" ]; then
        printf '%s\n' "${script_dir}"
        return
    fi

    if [ -d "${SOURCE_DIR}/.git" ]; then
        if [ -n "$(git -C "${SOURCE_DIR}" status --porcelain)" ]; then
            fail "${SOURCE_DIR} has local changes; preserve or commit them before updating."
        fi
        if [ "$(git -C "${SOURCE_DIR}" branch --show-current)" != "main" ]; then
            fail "${SOURCE_DIR} is not on main; switch branches or set CODEX_SUBSCRIPTION_ROUTER_SOURCE_DIR."
        fi
        log "Updating source"
        git -C "${SOURCE_DIR}" remote set-url origin "${REPOSITORY_URL}"
        git -C "${SOURCE_DIR}" pull --ff-only origin main >&2
    elif [ -e "${SOURCE_DIR}" ]; then
        fail "${SOURCE_DIR} exists but is not a Git repository."
    else
        log "Downloading source"
        mkdir -p "$(dirname -- "${SOURCE_DIR}")"
        git clone --depth 1 --branch main "${REPOSITORY_URL}" "${SOURCE_DIR}" >&2
    fi
    printf '%s\n' "${SOURCE_DIR}"
}

stop_bundle_processes() {
    local bundle_path="$1"
    local process_id
    local command_line
    local attempt

    for attempt in 1 2 3 4 5 6 7 8 9 10; do
        local found_process="false"
        for process_id in $(pgrep -f "${bundle_path}/Contents/" 2>/dev/null || true); do
            command_line="$(ps -p "${process_id}" -o command= 2>/dev/null || true)"
            case "${command_line}" in
                "${bundle_path}/Contents/"*)
                    found_process="true"
                    kill "${process_id}" 2>/dev/null || true
                    ;;
            esac
        done
        if [ "${found_process}" = "false" ]; then
            return
        fi
        sleep 1
    done
    fail "could not stop processes belonging to ${bundle_path}."
}

usage() {
    printf '%s\n' "Usage: install.sh [--independent|--managed-primary]"
    printf '%s\n' "  --independent      Install a separate router app. This is the default."
    printf '%s\n' "  --managed-primary  Install or update a signed, recoverable router build."
}

main() {
    local install_mode="independent"
    if [ "${1:-}" = "--managed-primary" ]; then
        install_mode="managed-primary"
        shift
    elif [ "${1:-}" = "--independent" ]; then
        shift
    elif [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
        usage
        return
    fi
    if [ "$#" -ne 0 ]; then
        usage >&2
        fail "unknown installer argument."
    fi

    log "Checking this Mac"
    require_prerequisites

    local project_dir
    project_dir="$(resolve_source_dir)"
    cd "${project_dir}"

    log "Installing locked build tools"
    npm ci --ignore-scripts --no-audit --no-fund

    if [ "${install_mode}" = "managed-primary" ]; then
        MANAGED_SOURCE_DIR="$(mktemp -d /tmp/codex-subscription-router-source.XXXXXX)"
        case "${MANAGED_SOURCE_DIR}" in
            /tmp/codex-subscription-router-source.*) ;;
            *) fail "could not create a safe temporary source directory." ;;
        esac
        local managed_source_app="${MANAGED_SOURCE_DIR}/ChatGPT.app"

        if grep -aq "CodexMuxAccountMenu" \
            "${MANAGED_DESTINATION_APP}/Contents/Resources/app.asar"; then
            log "Preparing the latest official ChatGPT update"
            python3 -m scripts.update_managed --output "${managed_source_app}"
        else
            log "Copying the official ChatGPT app"
            ditto "${MANAGED_DESTINATION_APP}" "${managed_source_app}"
        fi

        log "Stopping ChatGPT"
        stop_bundle_processes "${MANAGED_DESTINATION_APP}"

        log "Building and signing managed ChatGPT"
        python3 scripts/patch_app.py \
            --source "${managed_source_app}" \
            --destination "${MANAGED_DESTINATION_APP}" \
            --managed-primary \
            --force

        cleanup_managed_source
        log "Launching ChatGPT"
        open "${MANAGED_DESTINATION_APP}"
        printf '\nInstalled successfully: %s\n' "${MANAGED_DESTINATION_APP}"
        return
    fi

    local force_argument=""
    if [ -d "${DESTINATION_APP}" ] || [ -d "${DESTINATION_HELPER}" ]; then
        log "Stopping the existing installation"
        stop_bundle_processes "${DESTINATION_APP}"
        stop_bundle_processes "${DESTINATION_HELPER}"
        force_argument="--force"
    fi

    log "Building and signing Codex Subscription Router"
    if [ -n "${force_argument}" ]; then
        python3 scripts/patch_app.py "${force_argument}"
    else
        python3 scripts/patch_app.py
    fi

    log "Launching Codex Subscription Router"
    open "${DESTINATION_APP}"
    printf '\nInstalled successfully: %s\n' "${DESTINATION_APP}"
}

main "$@"
