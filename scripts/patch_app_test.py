from __future__ import annotations

import hashlib
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import patch_app


class PatchAppSigningTests(unittest.TestCase):
    def test_accepts_explicit_team_identifier_for_restricted_keychains(self) -> None:
        with mock.patch.dict(
            "os.environ",
            {"CODEX_MUX_SIGNING_TEAM_IDENTIFIER": "TESTTEAM01"},
        ):
            self.assertEqual(
                patch_app.signing_team_identifier("Apple Development: Test"),
                "TESTTEAM01",
            )

    def test_signs_real_codex_child_with_router_team(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary) / "Codex Subscription Router.app"
            real_codex = app / "Contents" / "Resources" / "codex.real"
            real_codex.parent.mkdir(parents=True)
            real_codex.write_bytes(b"test executable")

            with (
                mock.patch.object(
                    patch_app,
                    "capture_computer_use_entitlements",
                    return_value={},
                ),
                mock.patch.object(patch_app, "patch_computer_use_identity"),
                mock.patch.object(patch_app, "sign_computer_use_code"),
                mock.patch.object(patch_app, "sign_runtime_executable") as sign_runtime,
                mock.patch.object(patch_app, "run"),
            ):
                patch_app.sign_independent_app(
                    app,
                    "Apple Development: Test",
                    "TESTTEAM01",
                    99,
                )

            sign_runtime.assert_any_call(
                real_codex,
                "Apple Development: Test",
                "codex",
            )


class PatchAppComputerUseCacheTests(unittest.TestCase):
    def test_retires_official_cache_for_managed_primary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            cached_app = home / ".codex/computer-use/Codex Computer Use.app"
            plist_path = cached_app / "Contents/Info.plist"
            plist_path.parent.mkdir(parents=True)
            with plist_path.open("wb") as handle:
                plistlib.dump(
                    {"CFBundleIdentifier": patch_app.OPENAI_COMPUTER_USE_BUNDLE_IDENTIFIER},
                    handle,
                )

            with (
                mock.patch.object(Path, "home", return_value=home),
                mock.patch.object(patch_app.time, "strftime", return_value="20260821-223139"),
                mock.patch.object(patch_app, "run"),
            ):
                patch_app.retire_stale_cached_computer_use_app(
                    managed_primary=True
                )

            self.assertFalse(cached_app.exists())
            self.assertTrue(
                cached_app.with_name(
                    "Codex Computer Use backup-20260821-223139"
                ).is_dir()
            )


class PatchAppControlTokenTests(unittest.TestCase):
    def test_reads_existing_secure_token_without_rewriting_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary) / ".codex-mux"
            state_root.mkdir(mode=0o700)
            token_path = state_root / "control-token"
            token_path.write_text("a" * 64, encoding="utf-8")
            token_path.chmod(0o600)

            with mock.patch.object(patch_app, "DEFAULT_STATE_ROOT", state_root):
                token = patch_app.load_or_create_token()

            self.assertEqual(token, "a" * 64)

    def test_rejects_insecure_existing_state_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary) / ".codex-mux"
            state_root.mkdir(mode=0o755)

            with (
                mock.patch.object(patch_app, "DEFAULT_STATE_ROOT", state_root),
                self.assertRaisesRegex(RuntimeError, "insecure state directory"),
            ):
                patch_app.load_or_create_token()


class PatchAppCompatibilityTests(unittest.TestCase):
    def test_supports_chatgpt_build_6962(self) -> None:
        source = ("26.818.41509", "6962")
        expected_hash = (
            "8eb91bd9efbf9a4dd04b9b0afdbfcb4e0bab5da18c1919ad74ca327c00c7e791"
        )

        self.assertEqual(patch_app.TESTED_SOURCE_BUILDS[source], expected_hash)
        self.assertEqual(patch_app.SOURCE_ANCHOR_COUNTS[expected_hash], (99, 16))

    def test_supports_chatgpt_build_6892(self) -> None:
        source = ("26.818.31338", "6892")
        expected_hash = (
            "7db5508d4acd2c324cc572cd6f8d6d07900d185831bd6d54005a573e7186de54"
        )

        self.assertEqual(patch_app.TESTED_SOURCE_BUILDS[source], expected_hash)
        self.assertEqual(patch_app.SOURCE_ANCHOR_COUNTS[expected_hash], (99, 16))

    def test_scopes_plugin_requests_through_current_app_server_bridge(self) -> None:
        source = (
            "async sendRequest(e,t,n){if(this.dispatchMessage==null)throw Error("
            "`AppServerRequestClient is missing a message dispatcher`);return "
            "e===`config/read`?this.sendConfigReadRequest(t,n):this.enqueueRequest("
            "e,t,e===`plugin/list`&&n?.timeoutMs==null?{...n,timeoutMs:SFt}:n)}"
        )

        patched = patch_app.patch_app_server_request_bridge(source)

        self.assertIn("t=codexMuxScopePluginRequest(e,t);return", patched)

    def test_detects_current_renderer_layout_without_using_build_number(self) -> None:
        bundle = "function eSa(){let e=(0,jV.c)(1)"

        self.assertEqual(
            patch_app.detect_renderer_profile(bundle, direct_rpc_renderer=True),
            "current",
        )

    def test_detects_latest_renderer_layout_without_using_build_number(self) -> None:
        bundle = "function TCa(){let e=(0,MV.c)(1)"

        self.assertEqual(
            patch_app.detect_renderer_profile(bundle, direct_rpc_renderer=True),
            "latest",
        )

    def test_rejects_an_unknown_renderer_layout(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "supported renderer layout"):
            patch_app.detect_renderer_profile(
                "function changedByUpstream(){}",
                direct_rpc_renderer=True,
            )

    def test_accepts_supported_anchor_counts_for_unrecorded_source(self) -> None:
        self.assertEqual(
            patch_app.validate_replacement_count(
                "Computer Use identity",
                99,
                expected=None,
                supported={49, 99},
            ),
            99,
        )

    def test_rejects_new_anchor_counts_for_unrecorded_source(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "unsupported Computer Use identity"):
            patch_app.validate_replacement_count(
                "Computer Use identity",
                100,
                expected=None,
                supported={49, 99},
            )

    def test_adapts_account_menu_symbols_for_current_layout(self) -> None:
        component = "e7 QLs kXc Lo BW _H S2 CH jLa lt"

        adapted = patch_app.adapt_account_menu_component(
            component,
            direct_rpc_renderer=True,
            renderer_profile="current",
        )

        self.assertEqual(
            adapted,
            "d7 qFc OKl vs UR lI GGl hI _Aa ct",
        )

    def test_adapts_account_menu_symbols_for_latest_layout(self) -> None:
        component = "e7 QLs kXc Lo BW _H S2 CH jLa lt"

        adapted = patch_app.adapt_account_menu_component(
            component,
            direct_rpc_renderer=True,
            renderer_profile="latest",
        )

        self.assertEqual(
            adapted,
            "d7 Bsc Pql ys VR mI g0 bI Hja ct",
        )


class PatchAppManagedPrimaryTests(unittest.TestCase):
    def test_preserves_primary_app_identity_and_disables_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            app = Path(temporary) / "ChatGPT.app"
            plist_path = app / "Contents" / "Info.plist"
            asar_path = app / "Contents" / "Resources" / "app.asar"
            asar_path.parent.mkdir(parents=True)
            asar_path.write_bytes(b"patched asar")
            info = {
                "CFBundleDisplayName": "ChatGPT",
                "CFBundleName": "ChatGPT",
                "CFBundleIdentifier": "com.openai.codex",
                "CFBundleExecutable": "ChatGPT",
                "CrProductDirName": "com.openai.codex",
                "CFBundleURLTypes": [{"CFBundleURLSchemes": ["codex"]}],
                "SUFeedURL": "https://example.test/appcast.xml",
            }
            with plist_path.open("wb") as handle:
                plistlib.dump(info, handle)

            patch_app.patch_info_plist(
                app,
                asar_path,
                "TESTTEAM01",
                managed_primary=True,
            )

            with plist_path.open("rb") as handle:
                patched = plistlib.load(handle)
            self.assertEqual(patched["CFBundleDisplayName"], "ChatGPT")
            self.assertEqual(patched["CFBundleName"], "ChatGPT")
            self.assertEqual(patched["CFBundleIdentifier"], "com.openai.codex")
            self.assertEqual(patched["CFBundleExecutable"], "ChatGPT")
            self.assertEqual(patched["CrProductDirName"], "com.openai.codex")
            self.assertEqual(
                patched["CFBundleURLTypes"][0]["CFBundleURLSchemes"], ["codex"]
            )
            self.assertNotIn("SUFeedURL", patched)
            self.assertFalse(patched["SUEnableAutomaticChecks"])
            self.assertFalse(patched["SUAllowsAutomaticUpdates"])
            self.assertEqual(
                patched["ElectronAsarIntegrity"]["Resources/app.asar"]["hash"],
                hashlib.sha256(b"patched asar").hexdigest(),
            )

    def test_preserves_primary_user_data_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            extracted = Path(temporary) / "asar"
            build = extracted / ".vite" / "build"
            build.mkdir(parents=True)
            bootstrap_path = build / "bootstrap-test.js"
            bootstrap_path.write_text(
                "electron.app.setPath(`userData`,resolveProfile({"
                "appDataPath:electron.app.getPath(`appData`),"
                "buildFlavor:flavor,env:process.env}));"
                "await updater.initialize();let{runMainAppStartup:boot}=entry;",
                encoding="utf-8",
            )
            main_path = build / "main-test.js"
            main_path.write_text(
                "service=new Manager(resolve(config.codexHome),"
                "{onServiceAvailable:ready});"
                "const instruction=`Control desktop apps on macOS through Computer Use.`;",
                encoding="utf-8",
            )
            embedded_service = Path(
                "/Applications/ChatGPT.app/Contents/Resources/cua_node/"
                "lib/node_modules/@oai/sky/Codex Computer Use.app"
            )

            patch_app.patch_desktop_profile(
                extracted,
                embedded_service,
                managed_primary=True,
            )

            bootstrap = bootstrap_path.read_text(encoding="utf-8")
            self.assertIn(
                "electron.app.setPath(`userData`,resolveProfile({"
                "appDataPath:electron.app.getPath(`appData`),"
                "buildFlavor:flavor,env:process.env}))",
                bootstrap,
            )
            self.assertNotIn("Codex Subscription Router", bootstrap)
            self.assertNotIn("updater.initialize", bootstrap)
            self.assertIn(str(embedded_service), bootstrap)


if __name__ == "__main__":
    unittest.main()
