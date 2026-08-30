from __future__ import annotations

import unittest

from scripts import check_release


class ReleaseEvidenceTests(unittest.TestCase):
    def test_accepts_complete_release_evidence(self) -> None:
        self.assertTrue(
            check_release.evidence_is_complete("Release status: complete.\n")
        )

    def test_rejects_incomplete_release_evidence(self) -> None:
        self.assertFalse(
            check_release.evidence_is_complete(
                "Release status: incomplete until runtime checks pass.\n"
            )
        )


if __name__ == "__main__":
    unittest.main()
