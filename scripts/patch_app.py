#!/usr/bin/env python3
"""Create an independently signed ChatGPT build with Codex multiplexing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
DEFAULT_SOURCE = Path("/Applications/ChatGPT.app")
DEFAULT_DESTINATION = Path.home() / "Applications" / "Codex Subscription Router.app"
DEFAULT_STATE_ROOT = Path.home() / ".codex-mux"
CONTROL_PORT = 48123
DESKTOP_PROFILE_NAME = "Codex Subscription Router"
DESKTOP_BUNDLE_IDENTIFIER = "app.cdxmux.multi"
OPENAI_DESKTOP_CODE_IDENTIFIER = "com.openai.codex"
OPENAI_COMPUTER_USE_BUNDLE_IDENTIFIER = "com.openai.sky.CUAService"
COMPUTER_USE_BUNDLE_IDENTIFIER = "com.cdxmux.sky.CUAService"
COMPUTER_USE_DISPLAY_NAME = "Codex Subscription Router Computer Use"
COMPUTER_USE_APP_NAME = f"{COMPUTER_USE_DISPLAY_NAME}.app"
LAUNCH_SERVICES_REGISTER = Path(
    "/System/Library/Frameworks/CoreServices.framework/Frameworks/"
    "LaunchServices.framework/Support/lsregister"
)
ASAR_UNPACK_DIRECTORIES = (
    "node_modules/{@worklouder,better-sqlite3,node-mac-permissions,node-pty,objc-js}"
)
PREFERRED_SIGNING_IDENTITY_PREFIXES = (
    "Developer ID Application:",
    "Apple Development:",
)
OPENAI_INTERNAL_TEAM_IDENTIFIER = "HX7739G8FX"
OPENAI_DISTRIBUTION_TEAM_IDENTIFIER = "2DC432GLL2"
TESTED_SOURCE_BUILDS = {
    (
        "26.803.61601",
        "6396",
    ): "d5a44ed9e2f1db5f81dbbe85408aed256f3203c5b16f00817bb9d7cd941343cf",
    (
        "26.814.41407",
        "6720",
    ): "8fba32f8baa6d984b0f0f4149d3da46221e3adb3b52836f85fe65e31e655a8c0",
    (
        "26.818.31338",
        "6892",
    ): "7db5508d4acd2c324cc572cd6f8d6d07900d185831bd6d54005a573e7186de54",
    (
        "26.818.41509",
        "6962",
    ): "8eb91bd9efbf9a4dd04b9b0afdbfcb4e0bab5da18c1919ad74ca327c00c7e791",
    (
        "26.825.51511",
        "7377",
    ): "f56ac8d5254a10fc4a04e7417fa787d135c3bbca49bad7d668d4ae65833d40c7",
}
SOURCE_ANCHOR_COUNTS = {
    "d5a44ed9e2f1db5f81dbbe85408aed256f3203c5b16f00817bb9d7cd941343cf": (
        49,
        17,
    ),
    "8fba32f8baa6d984b0f0f4149d3da46221e3adb3b52836f85fe65e31e655a8c0": (
        99,
        20,
    ),
    "7db5508d4acd2c324cc572cd6f8d6d07900d185831bd6d54005a573e7186de54": (
        99,
        16,
    ),
    "8eb91bd9efbf9a4dd04b9b0afdbfcb4e0bab5da18c1919ad74ca327c00c7e791": (
        99,
        16,
    ),
    "f56ac8d5254a10fc4a04e7417fa787d135c3bbca49bad7d668d4ae65833d40c7": (
        49,
        16,
    ),
}
SUPPORTED_CUA_IDENTIFIER_COUNTS = frozenset({49, 99})
SUPPORTED_ASAR_CUA_COUNTS = frozenset({16, 17, 20})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {PROJECT_VERSION}")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument(
        "--managed-primary",
        action="store_true",
        help=(
            "Preserve the ChatGPT app identity and standard profile without "
            "installing a separate Computer Use app."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing destination after moving it to a timestamped backup.",
    )
    parser.add_argument(
        "--allow-adhoc-signing",
        action="store_true",
        help="Allow an ad-hoc signature (Appshots and Computer Use may stop working).",
    )
    parser.add_argument(
        "--allow-untested-source",
        action="store_true",
        help=(
            "Allow a source without an official OpenAI signature. Version and hash "
            "mismatches are handled by structural validation without this flag."
        ),
    )
    parser.add_argument(
        "--allow-signing-team-change",
        action="store_true",
        help="Replace an existing build signed by a different Apple team.",
    )
    return parser.parse_args()


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def output(command: list[str]) -> str:
    return subprocess.check_output(command, text=True).strip()


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"required tool not found: {name}")


def validate_javascript_source(
    path: Path,
    source: str,
    *,
    module: bool,
) -> None:
    """Parse patched JavaScript using the same module mode as Electron."""
    command = ["node"]
    if module:
        command.append("--input-type=module")
    command.append("--check")
    result = subprocess.run(
        command,
        input=source,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return
    detail = next(
        (
            line.strip()
            for line in result.stderr.splitlines()
            if "SyntaxError:" in line
        ),
        "JavaScript syntax error",
    )
    raise RuntimeError(
        f"patched JavaScript syntax check failed for {path.name}: {detail}"
    )


def validate_patched_javascript(extracted: Path) -> None:
    renderer_paths: list[Path] = []
    renderer_root = extracted / "webview" / "assets"
    for path in renderer_root.glob("*.js"):
        source = path.read_text(encoding="utf-8")
        if not any(
            marker in source
            for marker in ("CodexMux", "codexMux", "CODEX_MUX")
        ):
            continue
        renderer_paths.append(path)
        validate_javascript_source(path, source, module=True)
    if not renderer_paths:
        raise RuntimeError("no patched renderer JavaScript was found to validate")

    build_root = extracted / ".vite" / "build"
    main_paths = list(build_root.glob("main-*.js"))
    bootstrap_paths = list(build_root.glob("bootstrap-*.js"))
    if len(main_paths) != 1 or len(bootstrap_paths) != 1:
        raise RuntimeError(
            "could not isolate patched main-process JavaScript for validation"
        )
    for path in [*bootstrap_paths, *main_paths]:
        validate_javascript_source(
            path,
            path.read_text(encoding="utf-8"),
            module=False,
        )


def resolve_signing_identity(allow_adhoc: bool) -> str:
    configured = os.environ.get("CODEX_MUX_SIGNING_IDENTITY", "").strip()
    if configured:
        return configured
    identities = output(["security", "find-identity", "-v", "-p", "codesigning"])
    available = re.findall(
        r'^\s*\d+\)\s+[0-9A-F]+\s+"([^"]+)"',
        identities,
        re.MULTILINE,
    )
    for prefix in PREFERRED_SIGNING_IDENTITY_PREFIXES:
        for identity in available:
            if identity.startswith(prefix):
                return identity
    if allow_adhoc:
        print(
            "Warning: using an ad-hoc signature; Appshots and Computer Use may be unavailable.",
            file=sys.stderr,
        )
        return "-"
    raise RuntimeError(
        "no team-backed code-signing identity found; set CODEX_MUX_SIGNING_IDENTITY "
        "or explicitly pass --allow-adhoc-signing"
    )


def signing_team_identifier(identity: str) -> str | None:
    if identity == "-":
        return None
    configured = os.environ.get("CODEX_MUX_SIGNING_TEAM_IDENTIFIER", "").strip()
    if configured:
        if re.fullmatch(r"[A-Z0-9]{10}", configured) is None:
            raise RuntimeError("CODEX_MUX_SIGNING_TEAM_IDENTIFIER must be a 10-character Apple team ID")
        return configured
    certificate = subprocess.run(
        ["security", "find-certificate", "-c", identity, "-p"],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    subject = subprocess.run(
        ["openssl", "x509", "-noout", "-subject", "-nameopt", "RFC2253"],
        check=True,
        input=certificate,
        stdout=subprocess.PIPE,
        text=False,
    ).stdout.decode("utf-8", errors="strict")
    match = re.search(r"(?:^|,)OU=([A-Z0-9]{10})(?:,|$)", subject)
    if match is None:
        raise RuntimeError(
            "the signing certificate does not contain a 10-character Apple team ID"
        )
    return match.group(1)


def signed_code_metadata(path: Path) -> tuple[str | None, str | None]:
    result = subprocess.run(
        ["codesign", "--display", "--verbose=4", str(path)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    details = result.stdout + result.stderr
    identifier_match = re.search(r"^Identifier=(.+)$", details, re.MULTILINE)
    team_match = re.search(r"^TeamIdentifier=(.+)$", details, re.MULTILINE)
    identifier = identifier_match.group(1).strip() if identifier_match else None
    team = team_match.group(1).strip() if team_match else None
    if team == "not set":
        team = None
    return identifier, team


def verify_source_provenance(source: Path) -> None:
    """Require an intact ChatGPT bundle signed by an official OpenAI team."""
    identifier, team = signed_code_metadata(source)
    if identifier != OPENAI_DESKTOP_CODE_IDENTIFIER or team not in {
        OPENAI_INTERNAL_TEAM_IDENTIFIER,
        OPENAI_DISTRIBUTION_TEAM_IDENTIFIER,
    }:
        raise RuntimeError(
            "the source requires an official OpenAI signature"
        )
    run(["codesign", "--verify", "--deep", "--strict", str(source)])


def verify_or_allow_source_provenance(
    source: Path,
    *,
    allow_untested_source: bool,
) -> None:
    """Verify the whole source bundle unless the diagnostic override is explicit."""
    if allow_untested_source:
        print(
            "Warning: source signature verification was explicitly bypassed.",
            file=sys.stderr,
        )
        return
    verify_source_provenance(source)


def validate_replacement_count(
    description: str,
    actual: int,
    *,
    expected: int | None,
    supported: set[int] | frozenset[int],
) -> int:
    """Validate a known exact count or a previously reviewed structural count."""
    if expected is not None:
        if actual != expected:
            raise RuntimeError(
                f"expected {expected} {description}, found {actual}"
            )
        return actual
    if actual not in supported:
        supported_values = ", ".join(str(value) for value in sorted(supported))
        raise RuntimeError(
            f"unsupported {description} count {actual}; expected one of "
            f"{supported_values}"
        )
    return actual


def verify_signed_code(
    path: Path,
    expected_identifier: str,
    expected_team: str | None,
) -> None:
    run(["codesign", "--verify", "--deep", "--strict", str(path)])
    identifier, team = signed_code_metadata(path)
    if identifier != expected_identifier:
        raise RuntimeError(
            f"unexpected signing identifier on {path}: {identifier!r}"
        )
    if team != expected_team:
        raise RuntimeError(f"unexpected signing team on {path}: {team!r}")


def existing_signing_team(path: Path) -> str | None:
    if not path.exists():
        return None
    plist_path = path / "Contents" / "Info.plist"
    if plist_path.is_file():
        try:
            with plist_path.open("rb") as handle:
                recorded = plistlib.load(handle).get("CodexMuxSigningTeamIdentifier")
            if isinstance(recorded, str) and recorded != "":
                return None if recorded == "adhoc" else recorded
        except (OSError, plistlib.InvalidFileException):
            pass
    _, team = signed_code_metadata(path)
    return team


def require_signing_team_continuity(
    installed_team: str | None,
    selected_team: str | None,
    *,
    managed_primary: bool,
    allow_change: bool,
) -> None:
    if installed_team == selected_team or allow_change:
        return
    if managed_primary and installed_team in {
        OPENAI_INTERNAL_TEAM_IDENTIFIER,
        OPENAI_DISTRIBUTION_TEAM_IDENTIFIER,
    }:
        return
    raise RuntimeError(
        "the selected signing team differs from the installed build; reuse the "
        "prior identity or pass --allow-signing-team-change"
    )


def ensure_components_are_stopped(paths: tuple[Path, ...]) -> None:
    for path in paths:
        if not path.exists():
            continue
        result = subprocess.run(
            ["pgrep", "-f", str(path)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            raise RuntimeError(
                f"quit the running component before replacing it: {path}"
            )


MACH_O_MAGICS = {
    b"\xfe\xed\xfa\xce",  # 32-bit, big endian
    b"\xfe\xed\xfa\xcf",  # 64-bit, big endian
    b"\xce\xfa\xed\xfe",  # 32-bit, little endian
    b"\xcf\xfa\xed\xfe",  # 64-bit, little endian
    b"\xca\xfe\xba\xbe",  # universal binary
    b"\xbe\xba\xfe\xca",  # universal binary, little endian
}


def is_mach_o(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(4) in MACH_O_MAGICS
    except OSError:
        return False


def arm64_swift_small_string(value: str) -> bytes:
    """Encode the instructions used to materialize a 10-byte Swift string."""
    encoded = value.encode("ascii")
    if len(encoded) != 10:
        raise ValueError("a signing team identifier must contain 10 ASCII bytes")

    def instruction(base: int, immediate: int, register: int, shift: int = 0) -> bytes:
        word = base | ((shift // 16) << 21) | (immediate << 5) | register
        return word.to_bytes(4, "little")

    chunks = [
        int.from_bytes(encoded[index : index + 2], "little")
        for index in range(0, len(encoded), 2)
    ]
    return b"".join(
        (
            instruction(0xD2800000, chunks[0], 0),
            instruction(0xF2800000, chunks[1], 0, 16),
            instruction(0xF2800000, chunks[2], 0, 32),
            instruction(0xF2800000, chunks[3], 0, 48),
            instruction(0xD2800000, chunks[4], 1),
            instruction(0xF2800000, 0xEA00, 1, 48),
        )
    )


def arm64_peer_authorizer_team(value: str) -> bytes:
    """Encode the build 7377 instructions that materialize its trusted team."""
    encoded = value.encode("ascii")
    if len(encoded) != 10:
        raise ValueError("a signing team identifier must contain 10 ASCII bytes")

    def instruction(base: int, immediate: int, register: int, shift: int = 0) -> bytes:
        word = base | ((shift // 16) << 21) | (immediate << 5) | register
        return word.to_bytes(4, "little")

    chunks = [
        int.from_bytes(encoded[index : index + 2], "little")
        for index in range(0, len(encoded), 2)
    ]
    return b"".join(
        (
            instruction(0xD2800000, chunks[0], 13),
            instruction(0xF2800000, chunks[1], 13, 16),
            instruction(0xF2800000, chunks[2], 13, 32),
            instruction(0xF2800000, chunks[3], 13, 48),
            instruction(0x52800000, chunks[4], 14),
        )
    )


def replace_same_length_identifier(
    path: Path, original: str, replacement: str
) -> int:
    """Replace an embedded identifier without changing binary or bundle offsets."""
    original_bytes = original.encode("ascii")
    replacement_bytes = replacement.encode("ascii")
    if len(original_bytes) != len(replacement_bytes):
        raise RuntimeError("replacement identifiers must have the same byte length")
    data = path.read_bytes()
    count = data.count(original_bytes)
    if count:
        path.write_bytes(data.replace(original_bytes, replacement_bytes))
    return count


def computer_use_package(app: Path) -> Path:
    return (
        app
        / "Contents"
        / "Resources"
        / "cua_node"
        / "lib"
        / "node_modules"
        / "@oai"
        / "sky"
    )


def retire_stale_cached_computer_use_app(*, managed_primary: bool = False) -> None:
    """Move aside a known stale helper without touching Computer Use state."""
    cached_app = (
        Path.home() / ".codex" / "computer-use" / "Codex Computer Use.app"
    )
    if cached_app.is_symlink():
        return
    plist_path = cached_app / "Contents" / "Info.plist"
    if not plist_path.is_file():
        return
    try:
        with plist_path.open("rb") as handle:
            bundle_identifier = plistlib.load(handle).get("CFBundleIdentifier")
    except (OSError, plistlib.InvalidFileException):
        return
    removable_identifiers = {COMPUTER_USE_BUNDLE_IDENTIFIER}
    if managed_primary:
        removable_identifiers.add(OPENAI_COMPUTER_USE_BUNDLE_IDENTIFIER)
    if bundle_identifier not in removable_identifiers:
        return
    if LAUNCH_SERVICES_REGISTER.is_file():
        run([str(LAUNCH_SERVICES_REGISTER), "-u", str(cached_app)])
    backup = cached_app.with_name(
        f"Codex Computer Use backup-{time.strftime('%Y%m%d-%H%M%S')}"
    )
    cached_app.rename(backup)
    print(f"Stale cached Computer Use helper moved to {backup}")


def patch_computer_use_identity(
    app: Path,
    team_identifier: str | None,
    expected_identifier_replacements: int | None,
) -> None:
    """Give the copied CUA service an independent identity and trusted callers."""
    package = computer_use_package(app)
    service = package / "Codex Computer Use.app"
    executable = service / "Contents" / "MacOS" / "SkyComputerUseService"
    if not executable.is_file():
        raise RuntimeError("bundled Codex Computer Use service was not found")

    for profile in package.rglob("embedded.provisionprofile"):
        profile.unlink()

    identifier_replacements = 0
    for candidate in package.rglob("*"):
        if candidate.is_file() and not candidate.is_symlink():
            identifier_replacements += replace_same_length_identifier(
                candidate,
                OPENAI_COMPUTER_USE_BUNDLE_IDENTIFIER,
                COMPUTER_USE_BUNDLE_IDENTIFIER,
            )
    validate_replacement_count(
        "Computer Use identity references",
        identifier_replacements,
        expected=expected_identifier_replacements,
        supported=SUPPORTED_CUA_IDENTIFIER_COUNTS,
    )

    plist_path = service / "Contents" / "Info.plist"
    with plist_path.open("rb") as handle:
        info = plistlib.load(handle)
    info["CFBundleIdentifier"] = COMPUTER_USE_BUNDLE_IDENTIFIER
    info["CFBundleDisplayName"] = COMPUTER_USE_DISPLAY_NAME
    info["CFBundleName"] = COMPUTER_USE_DISPLAY_NAME
    for key in list(info):
        if key.startswith("SU"):
            del info[key]
    with plist_path.open("wb") as handle:
        plistlib.dump(info, handle, fmt=plistlib.FMT_BINARY, sort_keys=False)

    if team_identifier is None:
        return
    binary = executable.read_bytes()
    replacement = arm64_swift_small_string(team_identifier)
    for original_team, description in (
        (OPENAI_INTERNAL_TEAM_IDENTIFIER, "internal"),
        (OPENAI_DISTRIBUTION_TEAM_IDENTIFIER, "distribution"),
    ):
        original = arm64_swift_small_string(original_team)
        match_count = binary.count(original)
        if match_count != 2:
            raise RuntimeError(
                f"expected two Computer Use {description}-team checks, "
                f"found {match_count}; the official app layout may have changed"
            )
        binary = binary.replace(original, replacement)

        raw_original = original_team.encode("ascii")
        raw_replacement = team_identifier.encode("ascii")
        raw_match_count = binary.count(raw_original)
        expected_raw_matches = 1 if description == "internal" else 17
        if raw_match_count != expected_raw_matches:
            raise RuntimeError(
                f"expected {expected_raw_matches} Computer Use {description}-team "
                f"constants, found {raw_match_count}; the official app layout may have changed"
            )
        binary = binary.replace(raw_original, raw_replacement)

    original_bundle_id = b"com.openai.codex\0"
    replacement_bundle_id = DESKTOP_BUNDLE_IDENTIFIER.encode("ascii") + b"\0"
    if len(replacement_bundle_id) != len(original_bundle_id):
        raise RuntimeError(
            "the independent bundle identifier must match the CUA identifier length"
        )
    if binary.count(original_bundle_id) != 1:
        raise RuntimeError("could not find the Computer Use production bundle ID")
    executable.write_bytes(binary.replace(original_bundle_id, replacement_bundle_id))


def patch_asar_computer_use_identity(
    extracted: Path,
    expected_replacements: int | None,
) -> None:
    """Keep desktop launch, temp-file, and service references on the new CUA ID."""
    replacements = 0
    for candidate in extracted.rglob("*"):
        if candidate.is_file() and not candidate.is_symlink():
            replacements += replace_same_length_identifier(
                candidate,
                OPENAI_COMPUTER_USE_BUNDLE_IDENTIFIER,
                COMPUTER_USE_BUNDLE_IDENTIFIER,
            )
    validate_replacement_count(
        "Computer Use references in app.asar",
        replacements,
        expected=expected_replacements,
        supported=SUPPORTED_ASAR_CUA_COUNTS,
    )


def patch_native_peer_authorizer(
    app: Path,
    team_identifier: str | None,
) -> Path | None:
    """Trust the team used to re-sign Codex app-tools pipe clients."""
    addon = (
        app
        / "Contents"
        / "Resources"
        / "native"
        / "browser-use-peer-authorization.node"
    )
    if not addon.is_file() or team_identifier is None:
        return None
    original = OPENAI_DISTRIBUTION_TEAM_IDENTIFIER.encode("ascii")
    replacement = team_identifier.encode("ascii")
    if len(replacement) != len(original):
        raise RuntimeError("the signing team identifier must contain 10 ASCII bytes")
    data = addon.read_bytes()
    references = data.count(original)
    if references != 8:
        raise RuntimeError(
            "expected 8 native peer-authorizer team references, "
            f"found {references}"
        )
    compiled_original = arm64_peer_authorizer_team(
        OPENAI_DISTRIBUTION_TEAM_IDENTIFIER
    )
    compiled_replacement = arm64_peer_authorizer_team(team_identifier)
    compiled_references = data.count(compiled_original)
    if compiled_references != 1:
        raise RuntimeError(
            "expected 1 compiled native peer-authorizer team reference, "
            f"found {compiled_references}"
        )
    data = data.replace(compiled_original, compiled_replacement, 1)
    # Keep the diagnostic team string aligned too. The other seven copies are
    # part of the old signature and disappear when codesign replaces it.
    addon.write_bytes(data.replace(original, replacement, 1))
    return addon


def sign_native_code_tree(root: Path, identity: str) -> None:
    """Sign native modules before ASAR records their final sizes."""
    if not root.is_dir():
        return
    for candidate in root.rglob("*"):
        if not is_mach_o(candidate):
            continue
        run(
            [
                "codesign",
                "--force",
                "--sign",
                identity,
                "--timestamp=none",
                "--options",
                "runtime",
                str(candidate),
            ]
        )


TEAM_SCOPED_ENTITLEMENTS = (
    "com.apple.application-identifier",
    "com.apple.developer.aps-environment",
    "com.apple.developer.team-identifier",
    "com.apple.security.application-groups",
    "keychain-access-groups",
)


def sanitized_runtime_entitlements(executable: Path) -> dict[str, object] | None:
    """Keep runtime capabilities while removing the official app's team grants."""
    result = subprocess.run(
        ["codesign", "--display", "--entitlements", ":-", str(executable)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if not result.stdout.strip():
        return None
    try:
        entitlements = plistlib.loads(result.stdout)
    except plistlib.InvalidFileException as error:
        raise RuntimeError(
            f"could not read signing entitlements from {executable}"
        ) from error
    if not isinstance(entitlements, dict):
        raise RuntimeError(f"invalid signing entitlements on {executable}")
    for key in TEAM_SCOPED_ENTITLEMENTS:
        entitlements.pop(key, None)
    return entitlements or None


AUTO_ENTITLEMENTS = object()


def sign_runtime_executable(
    executable: Path,
    identity: str,
    identifier: str | None = None,
    entitlements: dict[str, object] | None | object = AUTO_ENTITLEMENTS,
    runtime: bool = True,
) -> None:
    """Re-sign an embedded runtime without breaking JIT-backed processes."""
    if entitlements is AUTO_ENTITLEMENTS:
        entitlements = sanitized_runtime_entitlements(executable)
    command = [
        "codesign",
        "--force",
        "--sign",
        identity,
        "--timestamp=none",
    ]
    if runtime:
        command.extend(("--options", "runtime"))
    if identifier is None:
        command.append("--preserve-metadata=identifier")
    else:
        command.extend(("--identifier", identifier))
    if entitlements is None:
        run([*command, str(executable)])
        return
    with tempfile.TemporaryDirectory(prefix=".codesign-entitlements-") as temporary:
        entitlements_path = Path(temporary) / "entitlements.plist"
        with entitlements_path.open("wb") as handle:
            plistlib.dump(
                entitlements,
                handle,
                fmt=plistlib.FMT_XML,
                sort_keys=True,
            )
        run([*command, "--entitlements", str(entitlements_path), str(executable)])


def bundle_main_executable(bundle: Path) -> Path | None:
    plist_path = bundle / "Contents" / "Info.plist"
    executable_root = bundle / "Contents" / "MacOS"
    if bundle.suffix == ".framework":
        plist_path = bundle / "Versions" / "Current" / "Resources" / "Info.plist"
        executable_root = bundle / "Versions" / "Current"
    if not plist_path.is_file():
        return None
    with plist_path.open("rb") as handle:
        executable_name = plistlib.load(handle).get("CFBundleExecutable")
    if not isinstance(executable_name, str) or executable_name == "":
        return None
    executable = executable_root / executable_name
    return executable if executable.is_file() else None


def sign_runtime_bundle(
    bundle: Path,
    identity: str,
    identifier: str | None = None,
    entitlements: dict[str, object] | None | object = AUTO_ENTITLEMENTS,
    runtime: bool = True,
) -> None:
    if entitlements is AUTO_ENTITLEMENTS:
        executable = bundle_main_executable(bundle)
        entitlements = (
            sanitized_runtime_entitlements(executable)
            if executable is not None
            else None
        )
    command = [
        "codesign",
        "--force",
        "--sign",
        identity,
        "--timestamp=none",
    ]
    if runtime:
        command.extend(("--options", "runtime"))
    if identifier is not None:
        command.extend(("--identifier", identifier))
    if entitlements is None:
        run([*command, str(bundle)])
        return
    with tempfile.TemporaryDirectory(prefix=".codesign-entitlements-") as temporary:
        entitlements_path = Path(temporary) / "entitlements.plist"
        with entitlements_path.open("wb") as handle:
            plistlib.dump(
                entitlements,
                handle,
                fmt=plistlib.FMT_XML,
                sort_keys=True,
            )
        run([*command, "--entitlements", str(entitlements_path), str(bundle)])


def capture_computer_use_entitlements(
    app: Path,
) -> dict[Path, dict[str, object] | None]:
    service = computer_use_package(app) / "Codex Computer Use.app"
    if not service.is_dir():
        raise RuntimeError("bundled Codex Computer Use service was not found")
    return {
        executable.relative_to(service): sanitized_runtime_entitlements(executable)
        for executable in service.rglob("*")
        if is_mach_o(executable)
    }


def sign_computer_use_code(
    app: Path,
    identity: str,
    preserved_entitlements: dict[Path, dict[str, object] | None],
) -> None:
    """Keep the Computer Use service and its callers on one signing team."""
    resources = app / "Contents" / "Resources"
    service = computer_use_package(app) / "Codex Computer Use.app"
    if not service.is_dir():
        raise RuntimeError("bundled Codex Computer Use service was not found")

    for executable in sorted(
        (candidate for candidate in service.rglob("*") if is_mach_o(candidate)),
        key=lambda candidate: len(candidate.parts),
        reverse=True,
    ):
        relative = executable.relative_to(service)
        sign_runtime_executable(
            executable,
            identity,
            entitlements=preserved_entitlements.get(relative),
        )

    bundle_suffixes = {".app", ".appex", ".bundle", ".framework", ".xpc"}
    bundles = [
        candidate
        for candidate in service.rglob("*")
        if candidate.is_dir() and candidate.suffix in bundle_suffixes
    ]
    bundles.append(service)
    for bundle in sorted(
        set(bundles),
        key=lambda candidate: len(candidate.parts),
        reverse=True,
    ):
        identifier = (
            COMPUTER_USE_BUNDLE_IDENTIFIER if bundle == service else None
        )
        executable = bundle_main_executable(bundle)
        entitlements = (
            preserved_entitlements.get(executable.relative_to(service))
            if executable is not None
            else None
        )
        sign_runtime_bundle(bundle, identity, identifier, entitlements)
        run(["codesign", "--verify", "--deep", "--strict", str(bundle)])

    for executable_name in ("node", "node_repl"):
        executable = resources / "cua_node" / "bin" / executable_name
        sign_runtime_executable(executable, identity)
    sign_runtime_executable(
        app / "Contents" / "MacOS" / "ChatGPT",
        identity,
        OPENAI_DESKTOP_CODE_IDENTIFIER,
        runtime=False,
    )


def sign_independent_app(
    app: Path,
    identity: str,
    team_identifier: str | None,
    expected_cua_identifier_replacements: int | None,
) -> None:
    """Apply one stable identity throughout the modified Electron bundle."""
    computer_use_entitlements = capture_computer_use_entitlements(app)
    patch_computer_use_identity(
        app,
        team_identifier,
        expected_cua_identifier_replacements,
    )
    sign_computer_use_code(app, identity, computer_use_entitlements)
    peer_authorizer = patch_native_peer_authorizer(app, team_identifier)
    if peer_authorizer is not None:
        sign_runtime_executable(
            peer_authorizer,
            identity,
            "browser_use_peer_authorization.node",
        )
    real_codex = app / "Contents" / "Resources" / "codex.real"
    if not real_codex.is_file():
        raise RuntimeError("the original Codex app-server binary is missing")
    # Computer Use authenticates the responsible process chain. The real
    # app-server launches its client, so it must use the same team as the
    # independently signed desktop, helper, and client rather than OpenAI's.
    sign_runtime_executable(real_codex, identity, "codex")
    run(
        [
            "codesign",
            "--force",
            "--sign",
            identity,
            "--timestamp=none",
            str(app / "Contents" / "Resources" / "codex"),
        ]
    )
    # Signing nested code can cause macOS to attach local metadata to the
    # staging bundle. It is not part of the signature and must not reach the
    # final outer signing operation.
    run(["xattr", "-cr", str(app)])
    run(
        [
            "codesign",
            "--force",
            "--sign",
            identity,
            "--timestamp=none",
            str(app),
        ]
    )


def load_or_create_token() -> str:
    if DEFAULT_STATE_ROOT.exists():
        if stat.S_IMODE(DEFAULT_STATE_ROOT.stat().st_mode) != 0o700:
            raise RuntimeError(f"insecure state directory permissions at {DEFAULT_STATE_ROOT}")
    else:
        DEFAULT_STATE_ROOT.mkdir(mode=0o700, parents=True)
    token_path = DEFAULT_STATE_ROOT / "control-token"
    if token_path.exists():
        if stat.S_IMODE(token_path.stat().st_mode) != 0o600:
            raise RuntimeError(f"insecure control token permissions at {token_path}")
        token = token_path.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[0-9a-f]{64}", token) is None:
            raise RuntimeError(f"invalid control token at {token_path}")
        return token
    token = secrets.token_hex(32)
    descriptor = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(token)
    return token


def build_proxy(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "go",
            "build",
            "-trimpath",
            "-ldflags=-s -w",
            "-o",
            str(destination),
            "./cmd/codex-mux",
        ],
        cwd=PROJECT_ROOT,
    )
    destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install_launcher(app: Path) -> None:
    """Pass Chromium its isolated profile before Electron's main process starts."""
    launcher = app / "Contents" / "MacOS" / "CodexSubscriptionRouterLauncher"
    run(
        [
            "xcrun",
            "clang",
            "-Os",
            "-Wall",
            "-Wextra",
            "-o",
            str(launcher),
            str(PROJECT_ROOT / "native" / "launcher.c"),
        ]
    )


def ensure_asar_tool() -> Path:
    asar = PROJECT_ROOT / "node_modules" / ".bin" / "asar"
    package_manifest = PROJECT_ROOT / "node_modules" / "@electron" / "asar" / "package.json"
    expected = json.loads(
        (PROJECT_ROOT / "package.json").read_text(encoding="utf-8")
    )["devDependencies"]["@electron/asar"]
    if not asar.exists() or not package_manifest.is_file():
        raise RuntimeError("run `npm ci --ignore-scripts` before patching")
    actual = json.loads(package_manifest.read_text(encoding="utf-8")).get("version")
    if actual != expected:
        raise RuntimeError(
            f"installed @electron/asar is {actual!r}, expected {expected!r}; "
            "run `npm ci --ignore-scripts`"
        )
    return asar


def patch_app_server_request_bridge(bundle: str) -> str:
    """Scope plugin RPCs while tolerating minifier-only symbol renames."""
    pattern = re.compile(
        r"async sendRequest\(e,t,n\)\{if\(this\.dispatchMessage==null\)throw Error\("
        r"`AppServerRequestClient is missing a message dispatcher`\);return "
        r"e===`config/read`\?this\.sendConfigReadRequest\(t,n\):this\.enqueueRequest\("
        r"e,t,e===`plugin/list`&&n\?\.timeoutMs==null\?\{\.\.\.n,timeoutMs:"
        r"[A-Za-z_$][\w$]*\}:n\)\}"
    )
    matches = list(pattern.finditer(bundle))
    if len(matches) != 1:
        raise RuntimeError("could not find the native app-server request bridge")
    match = matches[0]
    replacement = match.group(0).replace(
        ");return e===`config/read`?",
        ");t=codexMuxScopePluginRequest(e,t);return e===`config/read`?",
        1,
    )
    return bundle[: match.start()] + replacement + bundle[match.end() :]


def detect_renderer_profile(bundle: str, *, direct_rpc_renderer: bool) -> str:
    if not direct_rpc_renderer:
        return "legacy"
    fingerprints = {
        "direct": ("function A_a(){", "function M_a(){", "function kxc(e){"),
        "current": ("function eSa(){", "function nSa(){", "function zFc(e){"),
        "latest": ("function TCa(){", "function DCa(){", "function Bsc(e){"),
        "build_7377": ("function adi(){", "function sdi(){", "function swo(e){"),
    }
    matches = [
        name
        for name, markers in fingerprints.items()
        if all(marker in bundle for marker in markers)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "no supported renderer layout matched the source bundle"
        )
    return matches[0]


def adapt_account_menu_component(
    component: str,
    *,
    direct_rpc_renderer: bool,
    renderer_profile: str,
) -> str:
    if not direct_rpc_renderer:
        return component

    symbol_maps = {
        "direct": {
            "e7": "d7",
            "QLs": "kxc",
            "kXc": "NIl",
            "Lo": "Ss",
            "BW": "Tz",
            "_H": "rL",
            "S2": "z2",
            "CH": "lL",
            "jLa": "jwa",
            "lt": "ct",
        },
        "current": {
            "e7": "d7",
            "QLs": "qFc",
            "kXc": "OKl",
            "Lo": "vs",
            "BW": "UR",
            "_H": "lI",
            "S2": "GGl",
            "CH": "hI",
            "jLa": "_Aa",
            "lt": "ct",
        },
        "latest": {
            "e7": "d7",
            "QLs": "Bsc",
            "kXc": "Pql",
            "Lo": "ys",
            "BW": "VR",
            "_H": "mI",
            "S2": "g0",
            "CH": "bI",
            "jLa": "Hja",
            "lt": "ct",
        },
        "build_7377": {
            "e7": "u8",
            "QLs": "swo",
            "kXc": "Lwc",
            "Lo": "k_",
            "Q": "$",
            "BW": "QL",
            "_H": "lz",
            "CH": "hz",
            "lt": "xx",
        },
    }
    component_symbols = symbol_maps.get(renderer_profile)
    if component_symbols is None:
        raise RuntimeError(
            f"missing account-menu symbols for renderer layout {renderer_profile}"
        )
    for original, replacement in component_symbols.items():
        component = re.sub(
            rf"(?<![\w$]){re.escape(original)}(?![\w$])",
            replacement,
            component,
        )
    return component


def patch_renderer(extracted: Path, token: str) -> None:
    webview = extracted / "webview"
    index_path = webview / "index.html"
    index = index_path.read_text(encoding="utf-8")

    connect_anchor = "connect-src &#39;self&#39;"
    if connect_anchor not in index:
        raise RuntimeError("could not find ChatGPT renderer CSP connect-src")
    index = index.replace(
        connect_anchor,
        f"{connect_anchor} http://127.0.0.1:{CONTROL_PORT}",
        1,
    )
    index_path.write_text(index, encoding="utf-8")

    initial_bundles = list((webview / "assets").glob("app-initial-*.js"))
    if len(initial_bundles) != 1:
        raise RuntimeError(
            f"expected one ChatGPT initial renderer bundle, found {len(initial_bundles)}"
        )
    bundle_path = initial_bundles[0]
    bundle = bundle_path.read_text(encoding="utf-8")
    if "function CodexMuxAccountMenu(" in bundle:
        raise RuntimeError("source app already contains the Codex multiplexer menu")

    component = (PROJECT_ROOT / "ui" / "account-menu.js").read_text(encoding="utf-8")
    component = component.replace("__CODEX_MUX_CONTROL_PORT__", str(CONTROL_PORT))
    component = component.replace("__CODEX_MUX_CONTROL_TOKEN__", token)
    component_anchor = "function wXc({sidebarFooter:e,triggerButton:t})"
    direct_rpc_renderer = False
    if bundle.count(component_anchor) == 1:
        renderer_profile = detect_renderer_profile(
            bundle,
            direct_rpc_renderer=False,
        )
        bundle = bundle.replace(component_anchor, component + "\n" + component_anchor, 1)
    else:
        component_pattern = re.compile(
            r"function [A-Za-z_$][\w$]*\([A-Za-z_$][\w$]*\)\{"
            r"let [A-Za-z_$][\w$]*=\(0,[A-Za-z_$][\w$]*\.c\)\(\d+\),"
            r"\{sidebarFooter:[A-Za-z_$][\w$]*,"
            r"triggerButton:[A-Za-z_$][\w$]*\}=[A-Za-z_$][\w$]*"
        )
        component_matches = list(component_pattern.finditer(bundle))
        if len(component_matches) != 1:
            raise RuntimeError("could not find the native ChatGPT profile menu component")
        direct_rpc_renderer = True
        renderer_profile = detect_renderer_profile(
            bundle,
            direct_rpc_renderer=True,
        )
        component = adapt_account_menu_component(
            component,
            direct_rpc_renderer=True,
            renderer_profile=renderer_profile,
        )
        component_start = component_matches[0].start()
        bundle = bundle[:component_start] + component + "\n" + bundle[component_start:]

    legacy_app_server_request_anchor = (
        "function gm(e,t,n){return n==null?h6e.sendRequest(e,t):"
        "h6e.sendRequest(e,t,n)}"
    )
    if bundle.count(legacy_app_server_request_anchor) == 1:
        plugin_rpc_mapping_anchors = (
            '"list-apps":q9((e,{priority:t,source:n,timeoutMs:r,trace:i,...a})=>'
            "e.sendRequest(`app/list`,a,",
            '"list-installed-apps":q9((e,t)=>e.sendRequest(`app/installed`,t))',
            '"read-apps":q9((e,t)=>e.sendRequest(`app/read`,t))',
            '"login-mcp-server":q9((e,t)=>'
            "e.sendRequest(`mcpServer/oauth/login`,t))",
            '"list-mcp-server-status":K9((e,{priority:t,source:n,timeoutMs:r,'
            "trace:i,...a})=>e.listMcpServers(a,",
            "listMcpServers(e,t){let n=JSON.stringify({options:t,params:e})",
            "let i=this.sendRequest(`mcpServerStatus/list`,e,t);",
        )
        for mapping_anchor in plugin_rpc_mapping_anchors:
            if bundle.count(mapping_anchor) != 1:
                raise RuntimeError(
                    "could not verify the native Plugins request-to-RPC mapping"
                )
        bundle = bundle.replace(
            legacy_app_server_request_anchor,
            "function gm(e,t,n){let r=codexMuxScopePluginRequest(e,t);"
            "return n==null?h6e.sendRequest(e,r):h6e.sendRequest(e,r,n)}",
            1,
        )
    else:
        bundle = patch_app_server_request_bridge(bundle)
    current_rpc_renderer = renderer_profile == "current"
    latest_rpc_renderer = renderer_profile == "latest"
    build_7377_renderer = renderer_profile == "build_7377"

    profile_query_pattern = re.compile(
        r"let (?P<result>[A-Za-z_$][\w$]*)=await "
        r"[A-Za-z_$][\w$]*\.safeGet\(`/wham/profiles/me`\)"
    )
    bundle, profile_query_replacements = profile_query_pattern.subn(
        lambda match: (
            f"let {match.group('result')}=await codexMuxProfileData("
            "globalThis.__codexMuxSelectedProfileAccountId??null)"
        ),
        bundle,
        count=1,
    )
    if profile_query_replacements != 1:
        raise RuntimeError("could not find the native profile stats request")

    native_usage_modal_name = (
        "swo"
        if build_7377_renderer
        else (
            "Bsc"
            if latest_rpc_renderer
            else (
                "zFc"
                if current_rpc_renderer
                else ("kxc" if direct_rpc_renderer else "QLs")
            )
        )
    )
    native_usage_modal_anchor = f"function {native_usage_modal_name}(e){{"
    if bundle.count(native_usage_modal_anchor) != 1:
        raise RuntimeError("could not find the native Usage modal component")
    bundle = bundle.replace(
        native_usage_modal_anchor,
        f"function {native_usage_modal_name}(e){{CodexMuxUseResetAccountState();",
        1,
    )

    current_reset_query_anchor = (
        "function eSa(){let e=(0,jV.c)(1),t;return "
        "e[0]===Symbol.for(`react.memo_cache_sentinel`)?"
        "(t={queryKey:[`rate-limit-reset-credits`],queryFn:tSa,"
        "refetchInterval:jp.ONE_MINUTE,staleTime:jp.FIVE_SECONDS},e[0]=t):"
        "t=e[0],It(t)}"
    )
    latest_reset_query_anchor = (
        "function TCa(){let e=(0,MV.c)(1),t;return "
        "e[0]===Symbol.for(`react.memo_cache_sentinel`)?"
        "(t={queryKey:[`rate-limit-reset-credits`],queryFn:ECa,"
        "refetchInterval:jp.ONE_MINUTE,staleTime:jp.FIVE_SECONDS},e[0]=t):"
        "t=e[0],It(t)}"
    )
    build_7377_reset_query_anchor = (
        "function adi(){let e=(0,pR.c)(1),t;return "
        "e[0]===Symbol.for(`react.memo_cache_sentinel`)?"
        "(t={queryKey:[`rate-limit-reset-credits`],queryFn:odi,"
        "refetchInterval:yx.ONE_MINUTE,staleTime:yx.FIVE_SECONDS},e[0]=t):"
        "t=e[0],wx(t)}"
    )
    reset_query_anchor = (
        build_7377_reset_query_anchor
        if build_7377_renderer
        else current_reset_query_anchor
        if current_rpc_renderer
        else latest_reset_query_anchor
        if latest_rpc_renderer
        else (
            "function A_a(){let e=(0,fH.c)(1),t;return "
            "e[0]===Symbol.for(`react.memo_cache_sentinel`)?"
            "(t={queryKey:[`rate-limit-reset-credits`],queryFn:j_a,"
            "refetchInterval:Lp.ONE_MINUTE,staleTime:Lp.FIVE_SECONDS},e[0]=t):"
            "t=e[0],It(t)}"
            if direct_rpc_renderer
            else
        "function l6r(){let e=(0,$F.c)(1),t;return "
        "e[0]===Symbol.for(`react.memo_cache_sentinel`)?"
        "(t={queryKey:[`rate-limit-reset-credits`],queryFn:u6r,"
        "refetchInterval:vm.ONE_MINUTE,staleTime:vm.FIVE_SECONDS},e[0]=t):"
        "t=e[0],Lt(t)}"
        )
    )
    if bundle.count(reset_query_anchor) != 1:
        raise RuntimeError("could not find the native reset-credit query")
    reset_query_replacement = (
        "function adi(){let e=window.__codexMuxResetAccountId;return wx({"
        "queryKey:[`rate-limit-reset-credits`,e??`primary`],"
        "queryFn:e?()=>codexMuxRateLimitResets(e):odi,"
        "refetchInterval:yx.ONE_MINUTE,staleTime:yx.FIVE_SECONDS})}"
        if build_7377_renderer
        else "function TCa(){let e=window.__codexMuxResetAccountId;return It({"
        "queryKey:[`rate-limit-reset-credits`,e??`primary`],"
        "queryFn:e?()=>codexMuxRateLimitResets(e):ECa,"
        "refetchInterval:jp.ONE_MINUTE,staleTime:jp.FIVE_SECONDS})}"
        if latest_rpc_renderer
        else "function eSa(){let e=window.__codexMuxResetAccountId;return It({"
        "queryKey:[`rate-limit-reset-credits`,e??`primary`],"
        "queryFn:e?()=>codexMuxRateLimitResets(e):tSa,"
        "refetchInterval:jp.ONE_MINUTE,staleTime:jp.FIVE_SECONDS})}"
        if current_rpc_renderer
        else (
            "function A_a(){let e=window.__codexMuxResetAccountId;return It({"
            "queryKey:[`rate-limit-reset-credits`,e??`primary`],"
            "queryFn:e?()=>codexMuxRateLimitResets(e):j_a,"
            "refetchInterval:Lp.ONE_MINUTE,staleTime:Lp.FIVE_SECONDS})}"
            if direct_rpc_renderer
            else
        "function l6r(){let e=window.__codexMuxResetAccountId;return Lt({"
        "queryKey:[`rate-limit-reset-credits`,e??`primary`],"
        "queryFn:e?()=>codexMuxRateLimitResets(e):u6r,"
        "refetchInterval:vm.ONE_MINUTE,staleTime:vm.FIVE_SECONDS})}"
        )
    )
    bundle = bundle.replace(reset_query_anchor, reset_query_replacement, 1)

    reset_mutation_anchor = (
        "function sdi(){let e=(0,pR.c)(3),t=xx(),n=yD(),r;return "
        "e[0]!==n||e[1]!==t?(r={mutationFn:cdi,onSuccess:(e,r)=>{"
        "let{creditId:i}=r,a=e.code;if(a===`reset`||a===`already_redeemed`){"
        "let n=e.code===`reset`?e.credit?.id??i:i;"
        "t.setQueryData([`rate-limit-reset-credits`],e=>jui(e,a,n))}"
        "Promise.all([n([`rate-limit-status`]),n([`rate-limit-reset-credits`])])}},"
        "e[0]=n,e[1]=t,e[2]=r):r=e[2],Ex(r)}"
        if build_7377_renderer
        else "function DCa(){let e=(0,MV.c)(3),t=ct(),n=vb(),r;return "
        "e[0]!==n||e[1]!==t?(r={mutationFn:OCa,onSuccess:(e,r)=>{"
        "let{creditId:i}=r,a=e.code;if(a===`reset`||a===`already_redeemed`){"
        "let n=e.code===`reset`?e.credit?.id??i:i;"
        "t.setQueryData([`rate-limit-reset-credits`],e=>ZSa(e,a,n))}"
        "Promise.all([n([`rate-limit-status`]),n([`rate-limit-reset-credits`])])}},"
        "e[0]=n,e[1]=t,e[2]=r):r=e[2],Qt(r)}"
        if latest_rpc_renderer
        else
        "function nSa(){let e=(0,jV.c)(3),t=ct(),n=yb(),r;return "
        "e[0]!==n||e[1]!==t?(r={mutationFn:rSa,onSuccess:(e,r)=>{"
        "let{creditId:i}=r,a=e.code;if(a===`reset`||a===`already_redeemed`){"
        "let n=e.code===`reset`?e.credit?.id??i:i;"
        "t.setQueryData([`rate-limit-reset-credits`],e=>Exa(e,a,n))}"
        "Promise.all([n([`rate-limit-status`]),n([`rate-limit-reset-credits`])])}},"
        "e[0]=n,e[1]=t,e[2]=r):r=e[2],Qt(r)}"
        if current_rpc_renderer
        else (
            "function M_a(){let e=(0,fH.c)(3),t=ct(),n=Lb(),r;return "
            "e[0]!==n||e[1]!==t?(r={mutationFn:N_a,onSuccess:(e,r)=>{"
            "let{creditId:i}=r,a=e.code;if(a===`reset`||a===`already_redeemed`){"
            "let n=e.code===`reset`?e.credit?.id??i:i;"
            "t.setQueryData([`rate-limit-reset-credits`],e=>n_a(e,a,n))}"
            "Promise.all([n([`rate-limit-status`]),n([`rate-limit-reset-credits`])])}},"
            "e[0]=n,e[1]=t,e[2]=r):r=e[2],Qt(r)}"
            if direct_rpc_renderer
            else
        "function d6r(){let e=(0,$F.c)(3),t=lt(),n=zO(),r;return "
        "e[0]!==n||e[1]!==t?(r={mutationFn:f6r,onSuccess:(e,r)=>{"
        "let{creditId:i}=r,a=e.code;if(a===`reset`||a===`already_redeemed`){"
        "let n=e.code===`reset`?e.credit?.id??i:i;"
        "t.setQueryData([`rate-limit-reset-credits`],e=>F3r(e,a,n))}"
        "Promise.all([n([`rate-limit-status`]),n([`rate-limit-reset-credits`])])}},"
        "e[0]=n,e[1]=t,e[2]=r):r=e[2],$t(r)}"
        )
    )
    if bundle.count(reset_mutation_anchor) != 1:
        raise RuntimeError("could not find the native reset-credit mutation")
    reset_mutation_replacement = (
        "function sdi(){let e=xx(),t=yD(),n=window.__codexMuxResetAccountId,"
        "r=[`rate-limit-reset-credits`,n??`primary`];return Ex({"
        "mutationFn:n?i=>codexMuxConsumeRateLimitReset(n,i):cdi,"
        "onSuccess:(n,i)=>{let{creditId:a}=i,o=n.code;"
        "if(o===`reset`||o===`already_redeemed`){let t=o===`reset`?"
        "n.credit?.id??a:a;e.setQueryData(r,e=>jui(e,o,t))}"
        "Promise.all([t([`rate-limit-status`]),t(r)])}})}"
        if build_7377_renderer
        else "function DCa(){let e=ct(),t=vb(),n=window.__codexMuxResetAccountId,"
        "r=[`rate-limit-reset-credits`,n??`primary`];return Qt({"
        "mutationFn:n?i=>codexMuxConsumeRateLimitReset(n,i):OCa,"
        "onSuccess:(n,i)=>{let{creditId:a}=i,o=n.code;"
        "if(o===`reset`||o===`already_redeemed`){let t=o===`reset`?"
        "n.credit?.id??a:a;e.setQueryData(r,e=>ZSa(e,o,t))}"
        "Promise.all([t([`rate-limit-status`]),t(r)])}})}"
        if latest_rpc_renderer
        else "function nSa(){let e=ct(),t=yb(),n=window.__codexMuxResetAccountId,"
        "r=[`rate-limit-reset-credits`,n??`primary`];return Qt({"
        "mutationFn:n?i=>codexMuxConsumeRateLimitReset(n,i):rSa,"
        "onSuccess:(n,i)=>{let{creditId:a}=i,o=n.code;"
        "if(o===`reset`||o===`already_redeemed`){let t=o===`reset`?"
        "n.credit?.id??a:a;e.setQueryData(r,e=>Exa(e,o,t))}"
        "Promise.all([t([`rate-limit-status`]),t(r)])}})}"
        if current_rpc_renderer
        else (
            "function M_a(){let e=ct(),t=Lb(),n=window.__codexMuxResetAccountId,"
            "r=[`rate-limit-reset-credits`,n??`primary`];return Qt({"
            "mutationFn:n?i=>codexMuxConsumeRateLimitReset(n,i):N_a,"
            "onSuccess:(n,i)=>{let{creditId:a}=i,o=n.code;"
            "if(o===`reset`||o===`already_redeemed`){let t=o===`reset`?"
            "n.credit?.id??a:a;e.setQueryData(r,e=>n_a(e,o,t))}"
            "Promise.all([t([`rate-limit-status`]),t(r)])}})}"
            if direct_rpc_renderer
            else
        "function d6r(){let e=lt(),t=zO(),n=window.__codexMuxResetAccountId,"
        "r=[`rate-limit-reset-credits`,n??`primary`];return $t({"
        "mutationFn:n?i=>codexMuxConsumeRateLimitReset(n,i):f6r,"
        "onSuccess:(n,i)=>{let{creditId:a}=i,o=n.code;"
        "if(o===`reset`||o===`already_redeemed`){let t=o===`reset`?"
        "n.credit?.id??a:a;e.setQueryData(r,e=>F3r(e,o,t))}"
        "Promise.all([t([`rate-limit-status`]),t(r)])}})}"
        )
    )
    bundle = bundle.replace(reset_mutation_anchor, reset_mutation_replacement, 1)

    selected_usage_anchor = "let y=v;if(g!=null){"
    if bundle.count(selected_usage_anchor) != 1:
        raise RuntimeError("could not find the native usage-window selection")
    bundle = bundle.replace(
        selected_usage_anchor,
        "let y=window.__codexMuxSelectedUsageWindows??v;if(g!=null){",
        1,
    )

    usage_header_anchor = (
        "let _e;t[46]===he?_e=t[47]:"
        "(_e=(0,wQ.jsxs)(ER,{children:[he,ge]}),t[46]=he,t[47]=_e);"
        if build_7377_renderer
        else "let _e;t[46]===he?_e=t[47]:"
        "(_e=(0,u0.jsxs)(IR,{children:[he,ge]}),t[46]=he,t[47]=_e);"
        if latest_rpc_renderer
        else "let _e;t[46]===he?_e=t[47]:"
        "(_e=(0,d4.jsxs)(RR,{children:[he,ge]}),t[46]=he,t[47]=_e);"
        if current_rpc_renderer
        else (
            "let _e;t[46]===he?_e=t[47]:"
            "(_e=(0,N2.jsxs)(bz,{children:[he,ge]}),t[46]=he,t[47]=_e);"
            if direct_rpc_renderer
            else
        "let ve;t[46]===ge?ve=t[47]:"
        "(ve=(0,k2.jsxs)(LL,{children:[ge,_e]}),t[46]=ge,t[47]=ve);"
        )
    )
    if bundle.count(usage_header_anchor) != 1:
        raise RuntimeError("could not find the native Usage sheet header")
    usage_header_replacement = (
        "let _e=(0,wQ.jsxs)(ER,{children:[he,ge,"
        "window.__codexMuxResetAccountSelector??null]});"
        if build_7377_renderer
        else "let _e=(0,u0.jsxs)(IR,{children:[he,ge,"
        "window.__codexMuxResetAccountSelector??null]});"
        if latest_rpc_renderer
        else "let _e=(0,d4.jsxs)(RR,{children:[he,ge,"
        "window.__codexMuxResetAccountSelector??null]});"
        if current_rpc_renderer
        else (
            "let _e=(0,N2.jsxs)(bz,{children:[he,ge,"
            "window.__codexMuxResetAccountSelector??null]});"
            if direct_rpc_renderer
            else
        "let ve=(0,k2.jsxs)(LL,{children:[ge,_e,"
        "window.__codexMuxResetAccountSelector??null]});"
        )
    )
    bundle = bundle.replace(usage_header_anchor, usage_header_replacement, 1)

    usage_anchor = "usageItems:Ct" if direct_rpc_renderer else "usageItems:Ge"
    if bundle.count(usage_anchor) != 1:
        raise RuntimeError("could not find the native ChatGPT usage menu slot")
    bundle = bundle.replace(
        usage_anchor,
        (
            "usageItems:(0,u8.jsx)(CodexMuxAccountMenu,{})"
            if build_7377_renderer
            else "usageItems:(0,d7.jsx)(CodexMuxAccountMenu,{})"
            if direct_rpc_renderer
            else "usageItems:(0,e7.jsx)(CodexMuxAccountMenu,{})"
        ),
        1,
    )

    open_change_anchors = (
        (
            "triggerButton:Dt,onOpenChange:c,children:[N,null]",
            "open:s,onOpenChange:c,contentWidth:`panel`,triggerButton:Dt,children:Rt",
        )
        if build_7377_renderer
        else (
            "triggerButton:Dt,onOpenChange:l,children:P",
            "open:s,onOpenChange:l,contentWidth:`panel`,triggerButton:Dt,children:Rt",
        )
        if direct_rpc_renderer
        else (
            "triggerButton:Ke,onOpenChange:o,children:(0,e7.jsx)(bXc",
            "return(0,e7.jsx)(vH,{open:a,onOpenChange:o,contentWidth:`panel`",
        )
    )
    open_change_handler = (
        "c" if build_7377_renderer else "l" if direct_rpc_renderer else "o"
    )
    for anchor in open_change_anchors:
        if bundle.count(anchor) != 1:
            raise RuntimeError("could not find a native profile menu open-state hook")
        bundle = bundle.replace(
            anchor,
            anchor.replace(
                f"onOpenChange:{open_change_handler}",
                "onOpenChange:CodexMuxProfileMenuOpenChange("
                f"{open_change_handler})",
            ),
            1,
        )

    depleted_alert_anchors = (
        "defaultMessage:`You\u2019re out of Codex and Work usage`",
        "defaultMessage:`You\u2019ve used all Codex and Work usage`",
        "defaultMessage:`You\u2019ve reached your usage limit`",
    )
    for depleted_anchor in depleted_alert_anchors:
        if bundle.count(depleted_anchor) != 1:
            raise RuntimeError("could not find a native subscription depletion alert")
        bundle = bundle.replace(
            depleted_anchor,
            "defaultMessage:`All connected subscriptions are depleted`",
            1,
        )
    bundle_path.write_text(bundle, encoding="utf-8")

    profile_bundles = list((webview / "assets").glob("profile-*.js"))
    if len(profile_bundles) != 1:
        raise RuntimeError(
            f"expected one native Profile settings bundle, found {len(profile_bundles)}"
        )
    profile_bundle_path = profile_bundles[0]
    profile_bundle = profile_bundle_path.read_text(encoding="utf-8")
    if direct_rpc_renderer:
        profile_avatar_anchor = (
            '"aria-busy":ht,className:`flex flex-col items-center`,children:vt'
            if build_7377_renderer
            else '"aria-busy":Kt,className:`flex flex-col items-center`,children:Jt'
            if latest_rpc_renderer
            else '"aria-busy":Ut,className:`flex flex-col items-center`,children:Wt'
            if current_rpc_renderer
            else '"aria-busy":Gt,className:`flex flex-col items-center`,children:qt'
        )
        if profile_bundle.count(profile_avatar_anchor) != 1:
            raise RuntimeError("could not find the native Profile avatar")
        profile_avatar_replacement = (
            '"aria-busy":ht,className:`flex flex-col items-center`,children:'
            "globalThis.__codexMuxSelectedProfileAccountId?vt:"
            "(globalThis.CodexMuxProfileAvatarStack?.("
            "{onSelect:()=>F.refetch()})??vt)"
            if build_7377_renderer
            else '"aria-busy":Kt,className:`flex flex-col items-center`,children:'
            "globalThis.__codexMuxSelectedProfileAccountId?Jt:"
            "(globalThis.CodexMuxProfileAvatarStack?.("
            "{onSelect:()=>M.refetch()})??Jt)"
            if latest_rpc_renderer
            else '"aria-busy":Ut,className:`flex flex-col items-center`,children:'
            "globalThis.__codexMuxSelectedProfileAccountId?Wt:"
            "(globalThis.CodexMuxProfileAvatarStack?.("
            "{onSelect:()=>M.refetch()})??Wt)"
            if current_rpc_renderer
            else (
                '"aria-busy":Gt,className:`flex flex-col items-center`,children:'
                "globalThis.__codexMuxSelectedProfileAccountId?qt:"
                "(globalThis.CodexMuxProfileAvatarStack?.("
                "{onSelect:()=>M.refetch()})??qt)"
            )
        )
        profile_bundle = profile_bundle.replace(
            profile_avatar_anchor, profile_avatar_replacement, 1
        )
    else:
        profile_avatar_anchor = (
            "children:[(0,$.jsxs)(`div`,{className:`relative mb-4 size-20`,children:["
        )
        if profile_bundle.count(profile_avatar_anchor) != 1:
            raise RuntimeError("could not find the native Profile avatar")
        profile_bundle = profile_bundle.replace(
            profile_avatar_anchor,
            "children:[globalThis.CodexMuxProfileAvatarStack?.("
            "{onSelect:()=>A.refetch()})??null,"
            "(0,$.jsxs)(`div`,{className:"
            "globalThis.CodexMuxProfileAvatarStack?"
            "`hidden`:`relative mb-4 size-20`,children:[",
            1,
        )

        profile_name_anchor = "className:`flex w-full justify-center`"
        if profile_bundle.count(profile_name_anchor) != 1:
            raise RuntimeError("could not find the native Profile display name")
        profile_bundle = profile_bundle.replace(
            profile_name_anchor,
            "className:globalThis.__codexMuxSelectedProfileAccountId&&!A.isFetching?"
            "`flex w-full justify-center`:`hidden`",
            1,
        )
        profile_identity_anchor = (
            "className:`mt-1 flex min-h-7 items-center gap-1.5 text-base leading-5 "
            "font-normal text-token-text-tertiary`"
        )
        if profile_bundle.count(profile_identity_anchor) != 1:
            raise RuntimeError("could not find the native Profile username and plan badge")
        profile_bundle = profile_bundle.replace(
            profile_identity_anchor,
            "className:globalThis.__codexMuxSelectedProfileAccountId&&!A.isFetching?"
            "`mt-1 flex min-h-7 items-center gap-1.5 text-base leading-5 font-normal "
            "text-token-text-tertiary`:`hidden`",
            1,
        )
    profile_bundle_path.write_text(profile_bundle, encoding="utf-8")

    plugin_scope_anchor = "action:F,children:w})"
    plugin_bundles = [
        path
        for path in (webview / "assets").glob("plugins-settings-*.js")
        if plugin_scope_anchor in path.read_text(encoding="utf-8")
    ]
    if len(plugin_bundles) != 1:
        raise RuntimeError(
            f"expected one native Plugins settings bundle, found {len(plugin_bundles)}"
        )
    plugin_bundle_path = plugin_bundles[0]
    plugin_bundle = plugin_bundle_path.read_text(encoding="utf-8")
    if plugin_bundle.count(plugin_scope_anchor) != 1:
        raise RuntimeError("could not find the native Plugins settings content")
    plugin_bundle = plugin_bundle.replace(
        plugin_scope_anchor,
        "action:F,children:[globalThis.CodexMuxPluginScope?.()??null,w]})",
        1,
    )
    plugin_bundle_path.write_text(plugin_bundle, encoding="utf-8")

    legacy_thread_component_anchor = "function bE(){let e=(0,wE.c)(57)"
    direct_thread_component_anchor = "function xE(e){let t=(0,wE.c)(32)"
    current_thread_component_anchor = "function VT(e){let t=(0,WT.c)(33)"
    build_7377_thread_component_anchor = "function oE(e){let t=(0,lE.c)(34)"
    thread_bundles = [
        path
        for path in (webview / "assets").glob("local-conversation-thread-*.js")
        if legacy_thread_component_anchor in path.read_text(encoding="utf-8")
        or direct_thread_component_anchor in path.read_text(encoding="utf-8")
        or current_thread_component_anchor in path.read_text(encoding="utf-8")
        or build_7377_thread_component_anchor in path.read_text(encoding="utf-8")
    ]
    if len(thread_bundles) != 1:
        raise RuntimeError(
            "expected one local conversation summary renderer bundle, "
            f"found {len(thread_bundles)}"
        )
    thread_bundle_path = thread_bundles[0]
    thread_bundle = thread_bundle_path.read_text(encoding="utf-8")
    thread_component = (PROJECT_ROOT / "ui" / "thread-subscription.js").read_text(
        encoding="utf-8"
    )
    thread_component = thread_component.replace(
        "__CODEX_MUX_CONTROL_PORT__", str(CONTROL_PORT)
    )
    thread_component = thread_component.replace("__CODEX_MUX_CONTROL_TOKEN__", token)
    if build_7377_renderer:
        thread_component_symbols = {
            "TE": "XT",
            "zE": "uE",
            "$n": "oa",
            "sr": "Ca",
            "K": "Z",
        }
    elif latest_rpc_renderer:
        thread_component_symbols = {
            "TE": "jT",
            "zE": "GT",
            "$n": "$t",
            "sr": "ge",
            "K": "Z",
        }
    elif current_rpc_renderer:
        thread_component_symbols = {
            "TE": "jT",
            "zE": "GT",
            "$n": "Ji",
            "sr": "hc",
            "K": "q",
        }
    elif direct_rpc_renderer:
        thread_component_symbols = {
            "TE": "dE",
            "zE": "TE",
            "$n": "Xn",
            "sr": "ec",
            "K": "Z",
        }
    if direct_rpc_renderer:
        for original, replacement in thread_component_symbols.items():
            thread_component = re.sub(
                rf"(?<![\w$]){re.escape(original)}(?![\w$])",
                replacement,
                thread_component,
            )
    thread_component_anchor = (
        build_7377_thread_component_anchor
        if build_7377_renderer
        else current_thread_component_anchor
        if latest_rpc_renderer or current_rpc_renderer
        else (
            direct_thread_component_anchor
            if direct_rpc_renderer
            else legacy_thread_component_anchor
        )
    )
    if thread_bundle.count(thread_component_anchor) != 1:
        raise RuntimeError("could not find the native thread summary sources component")
    thread_bundle = thread_bundle.replace(
        thread_component_anchor,
        thread_component + "\n" + thread_component_anchor,
        1,
    )
    summary_children_anchor = (
        "children:[l,u,d,f,p,m,h,_,v,g,y,b,x,S,C,w]"
        if build_7377_renderer
        else "children:[l,u,d,f,p,m,h,g,_,v,y,b,x,S,C]"
        if latest_rpc_renderer or current_rpc_renderer
        else (
            "children:[l,u,d,f,p,m,h,g,_,v,y,b,x,S]"
            if direct_rpc_renderer
            else "children:[c,l,u,d,f,p,m,h,g,_,v,y,b,x]"
        )
    )
    if thread_bundle.count(summary_children_anchor) != 1:
        raise RuntimeError("could not find the native thread summary section list")
    thread_bundle = thread_bundle.replace(
        summary_children_anchor,
        (
            "children:[l,u,d,f,(0,uE.jsx)(CodexMuxThreadSubscription,{}),"
            "p,m,h,_,v,g,y,b,x,S,C,w]"
            if build_7377_renderer
            else "children:[l,u,d,f,(0,GT.jsx)(CodexMuxThreadSubscription,{}),"
            "p,m,h,g,_,v,y,b,x,S,C]"
            if latest_rpc_renderer or current_rpc_renderer
            else (
                "children:[l,u,d,f,(0,TE.jsx)(CodexMuxThreadSubscription,{}),"
                "p,m,h,g,_,v,y,b,x,S]"
                if direct_rpc_renderer
                else
                "children:[c,l,u,d,f,(0,zE.jsx)(CodexMuxThreadSubscription,{}),"
                "p,m,h,g,_,v,y,b,x]"
            )
        ),
        1,
    )
    thread_bundle_path.write_text(thread_bundle, encoding="utf-8")


def patch_desktop_profile(
    extracted: Path,
    installed_computer_use_app: Path,
    managed_primary: bool = False,
) -> None:
    """Configure the Electron profile, Computer Use path, and update policy."""
    bootstrap_files = list((extracted / ".vite" / "build").glob("bootstrap-*.js"))
    if len(bootstrap_files) != 1:
        raise RuntimeError(
            f"expected one ChatGPT bootstrap bundle, found {len(bootstrap_files)}"
        )

    bootstrap_path = bootstrap_files[0]
    bootstrap = bootstrap_path.read_text(encoding="utf-8")
    profile_pattern = re.compile(
        r"(?P<electron>[A-Za-z_$][\w$]*)\.app\.setPath\("
        r"`userData`,[A-Za-z_$][\w$]*\(\{"
        r"appDataPath:(?P=electron)\.app\.getPath\(`appData`\),"
        r"buildFlavor:[^,}]+,env:process\.env\}\)\)"
    )

    def replacement(match: re.Match[str]) -> str:
        electron = match.group("electron")
        computer_use_pipe = json.dumps(str(DEFAULT_STATE_ROOT / "computer-use.sock"))
        computer_use_app = json.dumps(str(installed_computer_use_app))
        environment = (
            f"process.env.SKY_CUA_SERVICE_NATIVE_PIPE_PATH={computer_use_pipe};"
            f"process.env.SKY_CUA_SERVICE_PATH={computer_use_app};"
            f"process.env.CODEX_ELECTRON_COMPUTER_USE_APP_PATH={computer_use_app};"
            "process.env.CODEX_ELECTRON_SKIP_COMPUTER_USE_CANONICAL_REFRESH=`1`;"
        )
        if managed_primary:
            return environment + match.group(0)
        return environment + (
            f"{electron}.app.setPath(`userData`,"
            f"{electron}.app.getPath(`appData`)+`/{DESKTOP_PROFILE_NAME}`)"
        )

    bootstrap, replacements = profile_pattern.subn(replacement, bootstrap, count=1)
    if replacements != 1:
        raise RuntimeError("could not isolate the copied ChatGPT desktop profile")

    # The copied app must never replace itself with an unpatched official update.
    updater_pattern = re.compile(
        r"await [A-Za-z_$][\w$]*\.initialize\(\);"
        r"(?=(?:try\{)?let\{runMainAppStartup:)"
    )
    bootstrap, updater_replacements = updater_pattern.subn("", bootstrap, count=1)
    if updater_replacements != 1:
        raise RuntimeError("could not disable updates in the copied ChatGPT app")
    bootstrap_path.write_text(bootstrap, encoding="utf-8")

    main_files = list((extracted / ".vite" / "build").glob("main-*.js"))
    if len(main_files) != 1:
        raise RuntimeError(
            f"expected one ChatGPT desktop main bundle, found {len(main_files)}"
        )
    main_path = main_files[0]
    main = main_path.read_text(encoding="utf-8")
    managed_service_pattern = re.compile(
        r"(?P<prefix>[A-Za-z_$][\w$]*=new [A-Za-z_$][\w$]*\()"
        r"[A-Za-z_$][\w$]*\([A-Za-z_$][\w$]*\.codexHome\)"
        r"(?P<suffix>,\{onServiceAvailable:)"
    )
    main, managed_service_replacements = managed_service_pattern.subn(
        lambda match: (
            match.group("prefix")
            + json.dumps(str(installed_computer_use_app))
            + match.group("suffix")
        ),
        main,
        count=1,
    )
    if managed_service_replacements != 1:
        raise RuntimeError(
            "could not pin the managed Computer Use service to its installed app"
        )

    computer_use_instruction = (
        "Control desktop apps on macOS through Computer Use."
    )
    strict_computer_use_instruction = (
        "Control desktop apps on macOS through Computer Use via node_repl and "
        "@oai/sky only. Never use shell commands, open, AppleScript, osascript, "
        "JXA, System Events, or CGEvent synthesis for computer interactions or "
        "as a fallback. If Computer Use is unavailable, report the failure "
        "instead of using another automation method."
    )
    if main.count(computer_use_instruction) != 1:
        raise RuntimeError("could not find the Computer Use tool instruction")
    main = main.replace(
        computer_use_instruction,
        strict_computer_use_instruction,
        1,
    )
    ui_test_bridge = extracted / ".vite" / "build" / "ui-test-bridge.cjs"
    shutil.copy2(PROJECT_ROOT / "ui" / "ui-test-bridge.cjs", ui_test_bridge)
    main += (
        "\n;if(process.env.CODEX_MUX_UI_TESTS===`1`)"
        "require(require(`node:path`).join(__dirname,`ui-test-bridge.cjs`)).start();"
    )
    main_path.write_text(main, encoding="utf-8")


def patch_info_plist(
    app: Path,
    asar_path: Path,
    team_identifier: str | None,
    managed_primary: bool = False,
) -> None:
    plist_path = app / "Contents" / "Info.plist"
    with plist_path.open("rb") as handle:
        info = plistlib.load(handle)
    if not managed_primary:
        info["CFBundleDisplayName"] = "Codex Subscription Router"
        info["CFBundleName"] = "Codex Subscription Router"
        # A distinct identifier keeps Launch Services and external Computer Use from
        # confusing this independently signed copy with the official ChatGPT app.
        info["CFBundleIdentifier"] = DESKTOP_BUNDLE_IDENTIFIER
        info["CFBundleExecutable"] = "CodexSubscriptionRouterLauncher"
        info["BundleSigningBaseName"] = "CodexSubscriptionRouter"
        info["CrProductDirName"] = DESKTOP_PROFILE_NAME
    info["CodexMuxSigningTeamIdentifier"] = team_identifier or "adhoc"
    for key in list(info):
        if key.startswith("SU"):
            del info[key]
    info["SUEnableAutomaticChecks"] = False
    info["SUAllowsAutomaticUpdates"] = False
    if not managed_primary:
        for url_type in info.get("CFBundleURLTypes", []):
            schemes = url_type.get("CFBundleURLSchemes", [])
            url_type["CFBundleURLSchemes"] = [
                "codex-subscription-router" if value == "codex" else value
                for value in schemes
            ]
    digest = hashlib.sha256(asar_path.read_bytes()).hexdigest()
    info["ElectronAsarIntegrity"] = {
        "Resources/app.asar": {"algorithm": "SHA256", "hash": digest}
    }
    with plist_path.open("wb") as handle:
        plistlib.dump(info, handle, fmt=plistlib.FMT_BINARY, sort_keys=False)


def patch_app(
    source: Path,
    destination: Path,
    force: bool,
    allow_adhoc_signing: bool,
    allow_untested_source: bool,
    allow_signing_team_change: bool,
    managed_primary: bool = False,
) -> None:
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not source.is_dir() or not (source / "Contents" / "Resources" / "app.asar").is_file():
        raise RuntimeError(f"not a ChatGPT app bundle: {source}")
    if source == destination:
        raise RuntimeError(
            "source and destination must be different; "
            "the original app is never patched in place"
        )
    if managed_primary and destination.name != "ChatGPT.app":
        raise RuntimeError("managed-primary destination must be named ChatGPT.app")
    if destination.exists() and not force:
        raise RuntimeError(
            f"destination exists: {destination} "
            "(pass --force to create a recoverable backup)"
        )

    source_plist = source / "Contents" / "Info.plist"
    with source_plist.open("rb") as handle:
        source_info = plistlib.load(handle)
    source_version = str(source_info.get("CFBundleShortVersionString", "unknown"))
    source_build = str(source_info.get("CFBundleVersion", "unknown"))
    source_asar = source / "Contents" / "Resources" / "app.asar"
    source_asar_hash = hashlib.sha256(source_asar.read_bytes()).hexdigest()
    expected_asar_hash = TESTED_SOURCE_BUILDS.get((source_version, source_build))
    print(
        f"Source ChatGPT version: {source_version} ({source_build}), "
        f"app.asar {source_asar_hash}"
    )
    if expected_asar_hash != source_asar_hash:
        print(
            "Source hash is not recorded; verifying the official signature and "
            "continuing only if every structural capability matches.",
            file=sys.stderr,
        )
    verify_or_allow_source_provenance(
        source,
        allow_untested_source=allow_untested_source,
    )
    (
        expected_cua_identifier_replacements,
        expected_asar_cua_identifier_replacements,
    ) = SOURCE_ANCHOR_COUNTS.get(source_asar_hash, (None, None))

    for tool in (
        "codesign",
        "ditto",
        "go",
        "npm",
        "openssl",
        "security",
        "xattr",
        "xcrun",
    ):
        require_tool(tool)
    asar = ensure_asar_tool()
    token = load_or_create_token()
    signing_identity = resolve_signing_identity(allow_adhoc_signing)
    team_identifier = signing_team_identifier(signing_identity)
    if destination.exists():
        installed_team = existing_signing_team(destination)
        require_signing_team_continuity(
            installed_team,
            team_identifier,
            managed_primary=managed_primary,
            allow_change=allow_signing_team_change,
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    installed_computer_use_app = (
        computer_use_package(DEFAULT_SOURCE) / "Codex Computer Use.app"
        if managed_primary
        else destination.parent / COMPUTER_USE_APP_NAME
    )
    if force:
        components = (destination,) if managed_primary else (
            destination,
            installed_computer_use_app,
        )
        ensure_components_are_stopped(components)

    with tempfile.TemporaryDirectory(prefix=".codex-subscription-router-", dir=destination.parent) as temporary:
        temporary_path = Path(temporary)
        staged_app = temporary_path / destination.name
        staged_computer_use_app = temporary_path / COMPUTER_USE_APP_NAME
        extracted = temporary_path / "asar"
        proxy = temporary_path / "codex-mux"

        print("Building multiplexer...")
        build_proxy(proxy)
        print("Copying ChatGPT.app...")
        run(["ditto", str(source), str(staged_app)])
        # Code signing rejects Finder metadata and resource forks copied from
        # the official bundle. Strip them only from the independent staging copy.
        run(["xattr", "-cr", str(staged_app)])
        if not managed_primary:
            install_launcher(staged_app)

        resources = staged_app / "Contents" / "Resources"
        original_asar = resources / "app.asar"
        print("Patching desktop profile and renderer...")
        run([str(asar), "extract", str(original_asar), str(extracted)])
        patch_asar_computer_use_identity(
            extracted,
            expected_asar_cua_identifier_replacements,
        )
        patch_desktop_profile(
            extracted,
            installed_computer_use_app,
            managed_primary=managed_primary,
        )
        patch_renderer(extracted, token)
        validate_patched_javascript(extracted)
        sign_native_code_tree(extracted, signing_identity)
        repacked_asar = temporary_path / "app.asar"
        run(
            [
                str(asar),
                "pack",
                "--unpack-dir",
                ASAR_UNPACK_DIRECTORIES,
                str(extracted),
                str(repacked_asar),
            ]
        )
        asar_listing = output([str(asar), "list", "--is-pack", str(repacked_asar)])
        required_unpacked_module = (
            "unpack : /node_modules/better-sqlite3/build/Release/"
            "better_sqlite3.node"
        )
        if required_unpacked_module not in asar_listing:
            raise RuntimeError("native ASAR modules were not kept unpacked")
        shutil.copy2(repacked_asar, original_asar)
        repacked_unpacked = temporary_path / "app.asar.unpacked"
        if not repacked_unpacked.is_dir():
            raise RuntimeError("ASAR pack did not produce its unpacked native tree")
        shutil.copytree(
            repacked_unpacked,
            resources / "app.asar.unpacked",
            dirs_exist_ok=True,
        )

        bundled_codex = resources / "codex"
        real_codex = resources / "codex.real"
        if real_codex.exists():
            raise RuntimeError("source app already contains codex.real")
        bundled_codex.rename(real_codex)
        shutil.copy2(proxy, bundled_codex)
        bundled_codex.chmod(0o755)

        patch_info_plist(
            staged_app,
            original_asar,
            team_identifier,
            managed_primary=managed_primary,
        )
        # Repacking the ASAR can copy extended attributes back into the bundle.
        # Clear them again before any nested or outer signatures are applied.
        run(["xattr", "-cr", str(staged_app)])
        build_description = (
            "managed primary app" if managed_primary else "independent app copy"
        )
        print(f"Signing {build_description} with {signing_identity}...")
        sign_independent_app(
            staged_app,
            signing_identity,
            team_identifier,
            expected_cua_identifier_replacements,
        )
        verify_signed_code(
            staged_app,
            (
                OPENAI_DESKTOP_CODE_IDENTIFIER
                if managed_primary
                else DESKTOP_BUNDLE_IDENTIFIER
            ),
            team_identifier,
        )
        verify_signed_code(
            staged_app / "Contents" / "Resources" / "codex.real",
            "codex",
            team_identifier,
        )
        verify_signed_code(
            staged_app / "Contents" / "MacOS" / "ChatGPT",
            OPENAI_DESKTOP_CODE_IDENTIFIER,
            team_identifier,
        )
        bundled_computer_use_app = (
            computer_use_package(staged_app) / "Codex Computer Use.app"
        )
        if managed_primary:
            verify_signed_code(
                bundled_computer_use_app,
                COMPUTER_USE_BUNDLE_IDENTIFIER,
                team_identifier,
            )
        else:
            run(
                [
                    "ditto",
                    str(bundled_computer_use_app),
                    str(staged_computer_use_app),
                ]
            )
            verify_signed_code(
                staged_computer_use_app,
                COMPUTER_USE_BUNDLE_IDENTIFIER,
                team_identifier,
            )

        backup_suffix = time.strftime("%Y%m%d-%H%M%S")
        backup_directory = DEFAULT_STATE_ROOT / "backups" / backup_suffix
        app_backup = backup_directory / destination.name
        helper_backup = backup_directory / installed_computer_use_app.name
        had_app = destination.exists()
        had_helper = not managed_primary and installed_computer_use_app.exists()
        if had_app or had_helper:
            backup_directory.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            backup_directory.parent.chmod(0o700)
            backup_directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        try:
            if had_app:
                destination.rename(app_backup)
                print(f"Existing copy moved to {app_backup}")
            if had_helper:
                installed_computer_use_app.rename(helper_backup)
                print(f"Existing Computer Use helper moved to {helper_backup}")
            staged_app.rename(destination)
            if not managed_primary:
                staged_computer_use_app.rename(installed_computer_use_app)
        except OSError:
            failed_directory = backup_directory / "failed-install"
            failed_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if destination.exists():
                destination.rename(failed_directory / destination.name)
            if not managed_primary and installed_computer_use_app.exists():
                installed_computer_use_app.rename(
                    failed_directory / installed_computer_use_app.name
                )
            if app_backup.exists():
                app_backup.rename(destination)
            if helper_backup.exists():
                helper_backup.rename(installed_computer_use_app)
            raise

    if LAUNCH_SERVICES_REGISTER.is_file():
        registration_targets = [str(destination)]
        if not managed_primary:
            registration_targets.append(str(installed_computer_use_app))
        run([str(LAUNCH_SERVICES_REGISTER), "-f", *registration_targets])
    retire_stale_cached_computer_use_app(managed_primary=managed_primary)

    print(destination)
    if not managed_primary:
        print(installed_computer_use_app)


def main() -> int:
    args = parse_args()
    try:
        patch_app(
            args.source,
            args.destination,
            args.force,
            args.allow_adhoc_signing,
            args.allow_untested_source,
            args.allow_signing_team_change,
            args.managed_primary,
        )
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(f"patch failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
