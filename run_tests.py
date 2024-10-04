#!/usr/bin/env python3

"""Tests for jdlint."""

from __future__ import annotations

import dataclasses
import json
import os
import unittest
from pathlib import Path, PurePath
from typing import Any

import jdlint


def _convert_err(e: jdlint.Error | jdlint.JDexError) -> dict[str, Any]:
    return {
        "error": dataclasses.asdict(e.error)  # type: ignore[arg-type]
        if dataclasses.is_dataclass(e.error)
        else e.error,
        "files": [
            # Strip full_path, since it's dependent on where we're running the test
            {"name": f.name, "nested_under": f.nested_under}
            for f in e.files
        ],
    }


class AllTests(unittest.TestCase):
    """Locate and run all tests."""

    def tests_without_jdex(self) -> None:
        """Locate and run tests that don't require the jdex."""
        self.maxDiff = None  # Show full diff

        # Find all tests
        with os.scandir(PurePath("tests", "without_jdex")) as test_it:
            for f in test_it:
                # Make a subtest and open result file
                with self.subTest(msg=f.name, f=f), Path(
                    f,
                    "result.json",
                ).open() as golden_file:
                    # Get ignore file if any
                    try:
                        ignore = Path(f, "ignore").read_text().splitlines()
                    except FileNotFoundError:
                        ignore = []

                    # Lint the test dir
                    results = jdlint.lint_dir(
                        Path(f, "files"),
                        ignored=ignore,
                    )
                    expected = json.load(golden_file)

                    # Convert lint results into loaded format
                    actual = {
                        "errors": [_convert_err(e) for e in results.errors],
                        "jdex_errors": [],
                    }

                    # Compare results
                    self.assertEqual(expected, actual)  # noqa: PT009

    def tests_with_jdex(self) -> None:
        """Locate and run tests that have the JDex."""
        self.maxDiff = None  # Show full diff

        # Find all tests
        with os.scandir(PurePath("tests", "with_jdex")) as test_it:
            for f in test_it:
                # Make a subtest and open result file
                with self.subTest(msg=f.name, f=f), Path(
                    f,
                    "result.json",
                ).open() as golden_file:
                    # Get ignore file if any
                    try:
                        ignore = Path(f, "ignore").read_text().splitlines()
                    except FileNotFoundError:
                        ignore = []

                    # Lint the test dir and JDex
                    (errors, jdex_errors) = jdlint.lint_dir_and_jdex(
                        path=Path(f, "files"),
                        jdex_path=Path(f, "jdex"),
                        ignored=ignore,
                        alt_zeros=Path(f, "altzeros").exists(),
                    )
                    expected = json.load(golden_file)

                    # Convert lint results into loaded format
                    actual = {
                        "errors": [_convert_err(e) for e in errors],
                        "jdex_errors": [_convert_err(e) for e in jdex_errors],
                    }

                    # Compare results
                    self.assertEqual(expected, actual)  # noqa: PT009


if __name__ == "__main__":
    unittest.main()
