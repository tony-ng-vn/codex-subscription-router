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


class UpdateManagedAppTests(unittest.TestCase):
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
