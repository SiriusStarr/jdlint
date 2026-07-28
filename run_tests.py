#!/usr/bin/env python3

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
                    # Load config
                    config = jdlint.Config(tomllib.load(config_file))

                    # Lint the test directory
                    results = jdlint.lint_system(config)
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
