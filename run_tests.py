#!/usr/bin/env python3

"""Tests for jdlint."""

from __future__ import annotations
import contextlib

import dataclasses
import tomllib
import json
import os
import unittest
from pathlib import Path, PurePath
from typing import Any

import jdlint


class AllTests(unittest.TestCase):
    """Locate and run all tests."""

    def tests(self) -> None:
        """Locate and run all tests."""
        self.maxDiff = None  # Show full diff

        # Find all tests
        with os.scandir(PurePath("tests")) as test_it:
            for f in test_it:
                # Make a subtest and open result file
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

                    # Lint the test dir
                    results = jdlint.lint_system(config)
                    expected = json.load(golden_file)

                    # Convert lint results into loaded format
                    actual = json.loads(
                        json.dumps(
                            {
                                "errors": {
                                    root_name: root.errors
                                    for root_name, root in results.roots.items()
                                    if root.errors
                                },
                                "jdex_errors": results.jdex.errors
                                if results.jdex
                                else [],
                            },
                            cls=jdlint._EnhancedJSONEncoder,
                        )
                    )

                    # Compare results
                    self.assertEqual(expected, actual)  # noqa: PT009


if __name__ == "__main__":
    unittest.main()
