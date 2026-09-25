#!/usr/bin/env python3

#
# Copyright © 2026 SiriusStarr
#
# This code is made available under the terms of the GNU General Public License v3.0
# You should have received a copy of this license along with this code.
# If not, a copy is available here: https://www.gnu.org/licenses/gpl-3.0.en.html
#

"""Tests for jdlint."""

from __future__ import annotations

import contextlib
import json
import os
import unittest
from pathlib import Path, PurePath

import tomllib

import jdlint


class AllTests(unittest.TestCase):
    """Locate and run all tests."""

    def tests(self) -> None:
        """Locate and run all tests."""
        self.maxDiff = None  # Show full diff

        # Find all tests
        with os.scandir(PurePath("tests")) as test_it:
            for f in test_it:
                # Allow files in test folder (for templates or whatnot)
                if f.is_file():
                    continue
                # Make a sub-test and open result file
                with (
                    self.subTest(msg=f.name, f=f),
                    Path(
                        f,
                        "result.json",
                    ).open() as golden_file,
                    Path(f, "jdlint.toml").open("rb") as config_file,
                    contextlib.chdir(f),
                ):
                    # Load JD config file if it exists
                    jd_config_path = Path("jd_config.json")
                    jd_systems = {}
                    if jd_config_path.is_file():
                        jd_systems = jdlint.load_jd_config(jd_config_path)

                    # Load config
                    config = jdlint.Config(jd_systems, tomllib.load(config_file))

                    # Lint the test directory
                    results = jdlint.lint_all_systems(config)

                    expected = json.load(golden_file)

                    # Convert lint results into loaded format
                    actual = json.loads(
                        json.dumps(
                            results,
                            cls=jdlint._EnhancedJSONEncoder,
                        ),
                    )

                    # Compare results
                    self.assertEqual(expected, actual)  # noqa: PT009


if __name__ == "__main__":
    unittest.main()
