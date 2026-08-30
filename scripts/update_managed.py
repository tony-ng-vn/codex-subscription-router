#!/usr/bin/env python3
"""Download and verify the latest official ChatGPT app for a managed update."""

from __future__ import annotations

import argparse
import plistlib
import shutil
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from scripts.patch_app import (
    OPENAI_DESKTOP_CODE_IDENTIFIER,
    require_tool,
    run,
    verify_source_provenance,
)


APPCAST_URL = "https://persistent.oaistatic.com/codex-app-prod/appcast.xml"
DEFAULT_INSTALLED_APP = Path("/Applications/ChatGPT.app")
OFFICIAL_DOWNLOAD_HOST = "persistent.oaistatic.com"
SPARKLE_NAMESPACE = "http://www.andymatuschak.org/xml-namespaces/sparkle"
MAX_APPCAST_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True)
class OfficialRelease:
    version: str
    build: str
    url: str
    length: int
    ed_signature: str


def namespaced(name: str) -> str:
    return f"{{{SPARKLE_NAMESPACE}}}{name}"


def validate_release_url(url: str, version: str) -> None:
    parsed = urlparse(url)
    expected_path = (
        f"/codex-app-prod/ChatGPT-darwin-arm64-{version}.zip"
    )
    if (
        parsed.scheme != "https"
        or parsed.hostname != OFFICIAL_DOWNLOAD_HOST
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != expected_path
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError(
            "release does not use the official OpenAI download host and path"
        )


def parse_latest_release(feed: bytes) -> OfficialRelease:
    try:
        root = ET.fromstring(feed)
    except ET.ParseError as error:
        raise RuntimeError(f"could not parse the official update feed: {error}") from error

    releases: list[OfficialRelease] = []
    for item in root.findall("./channel/item"):
        hardware = item.findtext(namespaced("hardwareRequirements"), "").strip()
        if hardware != "arm64":
            continue
        build = item.findtext(namespaced("version"), "").strip()
        version = item.findtext(namespaced("shortVersionString"), "").strip()
        enclosure = item.find("enclosure")
        if not build.isdigit() or not version or enclosure is None:
            continue
        url = enclosure.get("url", "").strip()
        length_text = enclosure.get("length", "").strip()
        signature = enclosure.get(namespaced("edSignature"), "").strip()
        if not length_text.isdigit() or not signature:
            continue
        length = int(length_text)
        if length <= 0 or length > MAX_ARCHIVE_BYTES:
            raise RuntimeError("official update archive has an unsafe byte count")
        validate_release_url(url, version)
        releases.append(
            OfficialRelease(
                version=version,
                build=build,
                url=url,
                length=length,
                ed_signature=signature,
            )
        )

    if not releases:
        raise RuntimeError("official update feed has no complete arm64 release")
    return max(releases, key=lambda release: int(release.build))


def fetch_latest_release() -> OfficialRelease:
    request = urllib.request.Request(
        APPCAST_URL,
        headers={"User-Agent": "codex-subscription-router-updater"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.geturl() != APPCAST_URL:
            raise RuntimeError("redirected update feed response")
        feed = response.read(MAX_APPCAST_BYTES + 1)
    if len(feed) > MAX_APPCAST_BYTES:
        raise RuntimeError("official update feed is unexpectedly large")
    return parse_latest_release(feed)


def download_release(release: OfficialRelease, destination: Path) -> None:
    request = urllib.request.Request(
        release.url,
        headers={"User-Agent": "codex-subscription-router-updater"},
    )
    received = 0
    with urllib.request.urlopen(request, timeout=60) as response:
        if response.geturl() != release.url:
            raise RuntimeError("redirected update archive response")
        content_length = response.headers.get("Content-Length")
        if content_length is not None and int(content_length) != release.length:
            raise RuntimeError("download byte count does not match the official feed")
        with destination.open("xb") as archive:
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                received += len(chunk)
                if received > release.length:
                    raise RuntimeError("download exceeds the official byte count")
                archive.write(chunk)
    if received != release.length:
        raise RuntimeError(
            f"download is incomplete: expected {release.length} bytes, got {received}"
        )


def require_not_downgrade(
    release: OfficialRelease,
    installed_app: Path = DEFAULT_INSTALLED_APP,
) -> None:
    plist_path = installed_app / "Contents" / "Info.plist"
    if not plist_path.is_file():
        return
    with plist_path.open("rb") as handle:
        installed_build = str(plistlib.load(handle).get("CFBundleVersion", ""))
    if not installed_build.isdigit():
        raise RuntimeError("installed ChatGPT build is not numeric")
    if int(release.build) < int(installed_build):
        raise RuntimeError(
            f"official feed build {release.build} is older than installed build "
            f"{installed_build}"
        )


def verify_official_app(app: Path, release: OfficialRelease) -> None:
    plist_path = app / "Contents" / "Info.plist"
    if not plist_path.is_file():
        raise RuntimeError("download did not contain ChatGPT.app")
    with plist_path.open("rb") as handle:
        info = plistlib.load(handle)
    if info.get("CFBundleIdentifier") != OPENAI_DESKTOP_CODE_IDENTIFIER:
        raise RuntimeError("download has an unexpected bundle identifier")
    if str(info.get("CFBundleShortVersionString", "")) != release.version:
        raise RuntimeError("downloaded app version does not match the official feed")
    if str(info.get("CFBundleVersion", "")) != release.build:
        raise RuntimeError("downloaded app build does not match the official feed")
    verify_source_provenance(app)
    run(["spctl", "--assess", "--type", "execute", str(app)])


def prepare_official_app(
    output: Path,
    installed_app: Path = DEFAULT_INSTALLED_APP,
) -> OfficialRelease:
    output = output.expanduser().resolve()
    if output.exists():
        raise RuntimeError(f"output already exists: {output}")
    if output.name != "ChatGPT.app":
        raise RuntimeError("output must be named ChatGPT.app")
    output.parent.mkdir(parents=True, exist_ok=True)
    require_tool("ditto")
    require_tool("codesign")
    require_tool("spctl")

    release = fetch_latest_release()
    require_not_downgrade(release, installed_app)
    size_mb = release.length / (1024 * 1024)
    print(
        f"Latest official ChatGPT: {release.version} ({release.build}), "
        f"{size_mb:.1f} MiB"
    )
    with tempfile.TemporaryDirectory(
        prefix=".codex-subscription-router-update-",
        dir=output.parent,
    ) as temporary:
        temporary_path = Path(temporary)
        archive = temporary_path / "ChatGPT.zip"
        extracted = temporary_path / "extracted"
        extracted.mkdir()
        print("Downloading official ChatGPT update...")
        download_release(release, archive)
        print("Verifying official ChatGPT update...")
        run(["ditto", "-x", "-k", str(archive), str(extracted)])
        app = extracted / "ChatGPT.app"
        verify_official_app(app, release)
        shutil.move(str(app), str(output))
    print(output)
    return release


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Write the verified source app to this new ChatGPT.app path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        prepare_official_app(args.output)
    except (OSError, RuntimeError, ValueError, plistlib.InvalidFileException) as error:
        print(f"update preparation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
