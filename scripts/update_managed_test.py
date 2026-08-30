#!/usr/bin/env python3
"""Tests for preparing an official ChatGPT source for a managed update."""

from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import update_managed


SAMPLE_FEED = b"""\
<?xml version="1.0" encoding="utf-8"?>
<rss xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
  <channel>
    <item>
      <title>26.825.41651</title>
      <sparkle:version>7345</sparkle:version>
      <sparkle:shortVersionString>26.825.41651</sparkle:shortVersionString>
      <sparkle:hardwareRequirements>arm64</sparkle:hardwareRequirements>
      <enclosure
        url="https://persistent.oaistatic.com/codex-app-prod/ChatGPT-darwin-arm64-26.825.41651.zip"
        length="595252422"
        type="application/octet-stream"
        sparkle:edSignature="older" />
    </item>
    <item>
      <title>26.825.51511</title>
      <sparkle:version>7377</sparkle:version>
      <sparkle:shortVersionString>26.825.51511</sparkle:shortVersionString>
      <sparkle:hardwareRequirements>arm64</sparkle:hardwareRequirements>
      <enclosure
        url="https://persistent.oaistatic.com/codex-app-prod/ChatGPT-darwin-arm64-26.825.51511.zip"
        length="595263123"
        type="application/octet-stream"
        sparkle:edSignature="current" />
    </item>
  </channel>
</rss>
"""


class UpdateManagedFeedTests(unittest.TestCase):
    def test_selects_highest_arm64_build_from_official_feed(self) -> None:
        release = update_managed.parse_latest_release(SAMPLE_FEED)

        self.assertEqual(release.version, "26.825.51511")
        self.assertEqual(release.build, "7377")
        self.assertEqual(release.length, 595263123)
        self.assertEqual(release.ed_signature, "current")

    def test_rejects_download_outside_official_host(self) -> None:
        malicious_feed = SAMPLE_FEED.replace(
            b"https://persistent.oaistatic.com/codex-app-prod/",
            b"https://example.test/codex-app-prod/",
        )

        with self.assertRaisesRegex(RuntimeError, "official OpenAI download host"):
            update_managed.parse_latest_release(malicious_feed)

    def test_rejects_feed_without_arm64_full_archive(self) -> None:
        intel_feed = SAMPLE_FEED.replace(b"arm64", b"x86_64")

        with self.assertRaisesRegex(RuntimeError, "arm64 release"):
            update_managed.parse_latest_release(intel_feed)

    def test_rejects_redirected_update_feed(self) -> None:
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.geturl.return_value = "https://example.test/appcast.xml"
        response.read.return_value = SAMPLE_FEED

        with mock.patch.object(update_managed.urllib.request, "urlopen", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "redirected update feed"):
                update_managed.fetch_latest_release()

    def test_rejects_redirected_update_archive(self) -> None:
        release = update_managed.parse_latest_release(SAMPLE_FEED)
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.geturl.return_value = "https://example.test/ChatGPT.zip"
        response.headers = {"Content-Length": str(release.length)}
        response.read.side_effect = [b""]

        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "ChatGPT.zip"
            with mock.patch.object(
                update_managed.urllib.request,
                "urlopen",
                return_value=response,
            ):
                with self.assertRaisesRegex(RuntimeError, "redirected update archive"):
                    update_managed.download_release(release, destination)


class UpdateManagedAppTests(unittest.TestCase):
    def test_rejects_release_older_than_installed_build(self) -> None:
        release = update_managed.OfficialRelease(
            version="26.825.41651",
            build="7345",
            url=(
                "https://persistent.oaistatic.com/codex-app-prod/"
                "ChatGPT-darwin-arm64-26.825.41651.zip"
            ),
            length=595252422,
            ed_signature="older",
        )
        with tempfile.TemporaryDirectory() as temporary:
            installed = Path(temporary) / "ChatGPT.app"
            contents = installed / "Contents"
            contents.mkdir(parents=True)
            with (contents / "Info.plist").open("wb") as handle:
                plistlib.dump({"CFBundleVersion": "7377"}, handle)

            with self.assertRaisesRegex(RuntimeError, "older than installed build"):
                update_managed.require_not_downgrade(release, installed)

    def test_accepts_matching_official_bundle(self) -> None:
        release = update_managed.parse_latest_release(SAMPLE_FEED)
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary) / "ChatGPT.app"
            contents = app / "Contents"
            contents.mkdir(parents=True)
            with (contents / "Info.plist").open("wb") as handle:
                plistlib.dump(
                    {
                        "CFBundleIdentifier": "com.openai.codex",
                        "CFBundleShortVersionString": release.version,
                        "CFBundleVersion": release.build,
                    },
                    handle,
                )

            with mock.patch.object(update_managed, "verify_source_provenance"):
                with mock.patch.object(update_managed, "run") as run:
                    update_managed.verify_official_app(app, release)

            run.assert_called_once_with(
                ["spctl", "--assess", "--type", "execute", str(app)]
            )

    def test_rejects_bundle_version_mismatch_before_signature_checks(self) -> None:
        release = update_managed.parse_latest_release(SAMPLE_FEED)
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary) / "ChatGPT.app"
            contents = app / "Contents"
            contents.mkdir(parents=True)
            with (contents / "Info.plist").open("wb") as handle:
                plistlib.dump(
                    {
                        "CFBundleIdentifier": "com.openai.codex",
                        "CFBundleShortVersionString": "0.0.0",
                        "CFBundleVersion": release.build,
                    },
                    handle,
                )

            with mock.patch.object(update_managed, "verify_source_provenance") as verify:
                with self.assertRaisesRegex(RuntimeError, "version does not match"):
                    update_managed.verify_official_app(app, release)

            verify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
