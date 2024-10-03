#!/usr/bin/env python3

"""Script to check for common issues with a Johnny Decimal system."""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, Callable, Literal, TypeVar


@dataclass(frozen=True)
class AreaDifferentFromJDex:
    """An area with a differently-named JDex entry."""

    area: str
    jdex_name: str
    type: Literal["AREA_DIFFERENT_FROM_JDEX"] = "AREA_DIFFERENT_FROM_JDEX"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [JDex name: {self.jdex_name}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An area was found, the name of which is different from its corresponding JDex entry.",
            fix="Update the one that is incorrect.",
        )


@dataclass(frozen=True)
class AreaNotInJDex:
    """An area without a corresponding JDex entry."""

    area: str
    type: Literal["AREA_NOT_IN_JDEX"] = "AREA_NOT_IN_JDEX"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [area: {_print_area(self.area)}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An area was found in your files that is missing from your JDex.",
            fix="Go add a corresponding entry to your JDex, or delete this if it's unused.",
        )


@dataclass(frozen=True)
class CategoryDifferentFromJDex:
    """A category with a differently-named JDex entry."""

    category: str
    jdex_name: str
    type: Literal["CATEGORY_DIFFERENT_FROM_JDEX"] = "CATEGORY_DIFFERENT_FROM_JDEX"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [JDex name: {self.jdex_name}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A category was found, the name of which is different from its corresponding JDex entry.",
            fix="Update the one that is incorrect.",
        )


@dataclass(frozen=True)
class CategoryInWrongArea:
    """A category that, by its number, has been put in the wrong area."""

    category_area: str
    file_area: str
    type: Literal["CATEGORY_IN_WRONG_AREA"] = "CATEGORY_IN_WRONG_AREA"

    def display(self, files: list[File]) -> str:
        """Given the file's name, print the error message for it."""
        return f"{_print_nest(files[0])} [in {_print_area(self.file_area)} but should be in {_print_area(self.category_area)}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Some categories are in the wrong area.",
            fix="Move them into the correct area folder.",
        )


@dataclass(frozen=True)
class CategoryNotInJDex:
    """An category without a corresponding JDex entry."""

    category: str
    type: Literal["CATEGORY_NOT_IN_JDEX"] = "CATEGORY_NOT_IN_JDEX"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [category: {self.category}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A category was found in the files that is missing from the JDex.",
            fix="Go add a corresponding entry to your JDex.",
        )


@dataclass(frozen=True)
class DuplicateArea:
    """An area that has been used multiple times."""

    area: str
    type: Literal["DUPLICATE_AREA"] = "DUPLICATE_AREA"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"Area {_print_area(self.area)}:\n    " + "\n    ".join(
            [_print_nest(f) for f in files],
        )

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Duplicate areas were used.",
            fix="Assign a new area to one of them.",
        )


@dataclass(frozen=True)
class DuplicateCategory:
    """A category that has been used multiple times."""

    category: str
    type: Literal["DUPLICATE_CATEGORY"] = "DUPLICATE_CATEGORY"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"Category {self.category}:\n    " + "\n    ".join(
            [_print_nest(f) for f in files],
        )

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Duplicate categories were used.",
            fix="Assign a new category to one of them.",
        )


@dataclass(frozen=True)
class DuplicateId:
    """An ID that has been used multiple times."""

    id: str
    type: Literal["DUPLICATE_ID"] = "DUPLICATE_ID"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"ID {self.id}:\n    " + "\n    ".join([_print_nest(f) for f in files])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Duplicate IDs were used.",
            fix="Assign a new ID to one of them.",
        )


@dataclass(frozen=True)
class FileOutsideId:
    """A file was encountered not in a terminal ID folder."""

    type: Literal["FILE_OUTSIDE_ID"] = "FILE_OUTSIDE_ID"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return _print_nest(files[0])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Files were found outside of IDs.",
            fix="Files should only be kept in IDs and not higher in the hierarchy.",
        )


@dataclass(frozen=True)
class IdDifferentFromJDex:
    """An ID with a differently-named JDex entry."""

    id: str
    jdex_name: str
    type: Literal["ID_DIFFERENT_FROM_JDEX"] = "ID_DIFFERENT_FROM_JDEX"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [JDex name: {self.jdex_name}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An ID was found, the name of which is different from its corresponding JDex entry.",
            fix="Update the one that is incorrect.",
        )


@dataclass(frozen=True)
class IdInWrongCategory:
    """An ID that, by its number, has been put in the wrong category."""

    id_ac: str
    file_ac: str
    type: Literal["ID_IN_WRONG_CATEGORY"] = "ID_IN_WRONG_CATEGORY"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return (
            f"{_print_nest(files[0])} [in {self.file_ac} but should be in {self.id_ac}]"
        )

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Some IDs are in the wrong category.",
            fix="Move them into the correct category folder.",
        )


@dataclass(frozen=True)
class IdNotInJDex:
    """An ID without a corresponding JDex entry."""

    id: str
    type: Literal["ID_NOT_IN_JDEX"] = "ID_NOT_IN_JDEX"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [ID: {self.id}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An ID was found in the files that is missing from the JDex.",
            fix="Go add a corresponding entry to your JDex.",
        )


@dataclass(frozen=True)
class InvalidAreaName:
    """A folder at the area level that doesn't match the normal format."""

    type: Literal["INVALID_AREA_NAME"] = "INVALID_AREA_NAME"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return _print_nest(files[0])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Some areas have invalid names.",
            fix='Valid area names look like "10-19 Life Admin", so edit the names to match that format.',
        )


@dataclass(frozen=True)
class InvalidCategoryName:
    """A folder at the category level that doesn't match the normal format."""

    type: Literal["INVALID_CATEGORY_NAME"] = "INVALID_CATEGORY_NAME"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return _print_nest(files[0])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Some categories have invalid names.",
            fix='Valid category names look like "11 Me, Myself, & I", so edit the names to match that format.',
        )


@dataclass(frozen=True)
class InvalidIDName:
    """A folder at the ID level that doesn't match the normal format."""

    type: Literal["INVALID_ID_NAME"] = "INVALID_ID_NAME"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return _print_nest(files[0])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Some IDs have invalid names.",
            fix='Valid ID names look like "11.11 A Cool Project", so edit the names to match that format.',
        )


@dataclass(frozen=True)
class NonemptyInbox:
    """An inbox (AC.01) that contains items."""

    num_items: int
    type: Literal["NONEMPTY_INBOX"] = "NONEMPTY_INBOX"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [{self.num_items} items]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Files were found in an inbox.",
            fix="Go sort them into the appropriate IDs.",
        )


ErrorType = (
    AreaDifferentFromJDex
    | AreaNotInJDex
    | CategoryDifferentFromJDex
    | CategoryInWrongArea
    | CategoryNotInJDex
    | DuplicateArea
    | DuplicateCategory
    | DuplicateId
    | FileOutsideId
    | IdDifferentFromJDex
    | IdInWrongCategory
    | IdNotInJDex
    | InvalidAreaName
    | InvalidCategoryName
    | InvalidIDName
    | NonemptyInbox
)


@dataclass(frozen=True)
class JDexAreaHeaderDifferentFromArea:
    """An area header with a different name than the correspnoding area."""

    area: str
    jdex_name: str
    type: Literal["JDEX_AREA_HEADER_DIFFERENT_FROM_AREA"] = (
        "JDEX_AREA_HEADER_DIFFERENT_FROM_AREA"
    )

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [JDex name: {self.jdex_name}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An area header was found, the name of which is different from its corresponding JDex entry.",
            fix="Update the one that is incorrect.",
        )


@dataclass(frozen=True)
class JDexAreaHeaderWithoutArea:
    """An area header with no corresponding area."""

    area: str
    type: Literal["JDEX_AREA_HEADER_WITHOUT_AREA"] = "JDEX_AREA_HEADER_WITHOUT_AREA"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"{_print_nest(files[0])} [area: {_print_area(self.area)}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An area header was found in the JDex with no corresponding area entry.",
            fix="Go add a corresponding entry to your JDex, or delete this header if it is no longer needed.",
        )


@dataclass(frozen=True)
class JDexCategoryInWrongArea:
    """A JDex category that, by its number, has been put in the wrong area."""

    category_area: str
    file_area: str
    type: Literal["JDEX_CATEGORY_IN_WRONG_AREA"] = "JDEX_CATEGORY_IN_WRONG_AREA"

    def display(self, files: list[File]) -> str:
        """Given the file's name, print the error message for it."""
        return f"{_print_nest(files[0])} [in {_print_area(self.file_area)} but should be in {_print_area(self.category_area)}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Some JDex categories are in the wrong area.",
            fix="Move them into the correct area folder, or use a flat JDex structure.",
        )


@dataclass(frozen=True)
class JDexDuplicateArea:
    """A JDex area that has been used multiple times."""

    area: str
    type: Literal["JDEX_DUPLICATE_AREA"] = "JDEX_DUPLICATE_AREA"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"Area {_print_area(self.area)}:\n    " + "\n    ".join(
            [_print_nest(f) for f in files],
        )

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Duplicate areas were used in the JDex.",
            fix="Assign a new area to one of them.",
        )


@dataclass(frozen=True)
class JDexDuplicateAreaHeader:
    """Multiple headers for the same area."""

    area: str
    type: Literal["JDEX_DUPLICATE_AREA_HEADER"] = "JDEX_DUPLICATE_AREA_HEADER"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return f"Area {_print_area(self.area)}:\n    " + "\n    ".join(
            [_print_nest(f) for f in files],
        )

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Duplicate headers were found for the same area in the JDex.",
            fix="Delete the one that is incorrect or fix the area number.",
        )


@dataclass(frozen=True)
class JDexDuplicateCategory:
    """A JDex category that has been used multiple times."""

    category: str
    type: Literal["JDEX_DUPLICATE_CATEGORY"] = "JDEX_DUPLICATE_CATEGORY"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return (
            self.category + ":\n    " + "\n    ".join([_print_nest(f) for f in files])
        )

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Duplicate categories were used in the JDex.",
            fix="Assign a new category to one of them.",
        )


@dataclass(frozen=True)
class JDexDuplicateId:
    """A JDex ID that has been used multiple times."""

    id: str
    type: Literal["JDEX_DUPLICATE_ID"] = "JDEX_DUPLICATE_ID"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return self.id + ":\n    " + "\n    ".join([_print_nest(f) for f in files])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Duplicate IDs were used in the JDex.",
            fix="Assign a new ID to one of them.",
        )


@dataclass(frozen=True)
class JDexFileOutsideCategory:
    """A JDex file was encountered not in a terminal category folder."""

    type: Literal["JDEX_FILE_OUTSIDE_CATEGORY"] = "JDEX_FILE_OUTSIDE_CATEGORY"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return _print_nest(files[0])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="JDex files were found outside of categories in a nested structure.",
            fix="JDex files should be entirely flat, or nested under area then category.",
        )


@dataclass(frozen=True)
class JDexIdInWrongCategory:
    """A JDex ID that, by its number, has been put in the wrong category."""

    id_ac: str
    file_ac: str
    type: Literal["JDEX_ID_IN_WRONG_CATEGORY"] = "JDEX_ID_IN_WRONG_CATEGORY"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return (
            f"{_print_nest(files[0])} [in {self.file_ac} but should be in {self.id_ac}]"
        )

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Some JDex IDs are in the wrong category.",
            fix="Move them into the correct category folder, or use a flat JDex structure.",
        )


@dataclass(frozen=True)
class JDexInvalidAreaName:
    """A folder at the JDex area level that doesn't match the normal format."""

    type: Literal["JDEX_INVALID_AREA_NAME"] = "JDEX_INVALID_AREA_NAME"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return _print_nest(files[0])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Some JDex areas have invalid names.",
            fix='Valid area names look like "10-19 Life Admin", so edit the names to match that format.',
        )


@dataclass(frozen=True)
class JDexInvalidCategoryName:
    """A folder at the JDex category level that doesn't match the normal format."""

    type: Literal["JDEX_INVALID_CATEGORY_NAME"] = "JDEX_INVALID_CATEGORY_NAME"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return _print_nest(files[0])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Some JDex categories have invalid names.",
            fix='Valid category names look like "11 Me, Myself, & I", so edit the names to match that format.',
        )


@dataclass(frozen=True)
class JDexInvalidIDName:
    """A JDex note that doesn't match the normal format."""

    type: Literal["JDEX_INVALID_ID_NAME"] = "JDEX_INVALID_ID_NAME"

    def display(self, files: list[File]) -> str:
        """Display this particular instance of an error."""
        return _print_nest(files[0])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Some JDex IDs have invalid names.",
            fix='Valid ID names look like "11.11 A Cool Project", so edit the names to match that format.',
        )


JDexErrorType = (
    JDexAreaHeaderDifferentFromArea
    | JDexAreaHeaderWithoutArea
    | JDexCategoryInWrongArea
    | JDexDuplicateArea
    | JDexDuplicateAreaHeader
    | JDexDuplicateCategory
    | JDexDuplicateId
    | JDexFileOutsideCategory
    | JDexIdInWrongCategory
    | JDexInvalidAreaName
    | JDexInvalidCategoryName
    | JDexInvalidIDName
)


@dataclass(frozen=True)
class File:
    """A file or folder that has been detected by jdlint."""

    name: str
    full_path: str
    nested_under: list[str]


@dataclass(frozen=True)
class _Explanation:
    explanation: str
    fix: str


@dataclass(frozen=True)
class Error:
    """A single error detected."""

    error: ErrorType
    files: list[File]

    def type(self) -> str:
        """Return the name (type) of the error."""
        return self.error.type

    def display(self) -> str:
        """Display this particular instance of an error."""
        return self.error.display(self.files)

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return self.error.explain()


@dataclass(frozen=True)
class JDexError:
    """A single error detected in the JDex."""

    error: JDexErrorType
    files: list[File]

    def type(self) -> str:
        """Return the name (type) of the error."""
        return self.error.type

    def display(self) -> str:
        """Display this particular instance of an error."""
        return self.error.display(self.files)

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return self.error.explain()


@dataclass(frozen=True)
class LintResults:
    """All errors returned from linting files, as well as dictionaries of all areas, categories, and IDs used (and their names)."""

    errors: list[Error]
    used_areas: dict[str, list[tuple[str, File]]]
    used_categories: dict[str, list[tuple[str, File]]]
    used_ids: dict[str, list[tuple[str, File]]]


@dataclass(frozen=True)
class _JDexResults:
    jdex_areas: dict[str, str]
    jdex_categories: dict[str, str]
    jdex_ids: dict[str, str]


class _EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o: object) -> object:
        # Add JSON encoding for dataclasses and paths
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)  # type: ignore[arg-type]
        if isinstance(o, PurePath):
            return str(o)
        return super().default(o)


def _sort_error(e: Error | JDexError) -> tuple[str, list[tuple[list[str], str]]]:
    # Sort errors alphabetically by type, then by file/s affected
    return (
        e.error.type,
        [_sort_file(f) for f in e.files],
    )


def _sort_file(f: File) -> tuple[list[str], str]:
    # Sort files first by degree of nesting, then alphabetically
    return (f.nested_under, f.name)


# Any valid area folder name
valid_area_re = re.compile("([0-9])0-(?:\\1)9 (.+)")
# Any valid category folder name
generic_category_re = re.compile("([0-9])[0-9] .+")
# Any valid ID folder name
generic_id_re = re.compile("([0-9][0-9])\\.([0-9][0-9]) (.+)")
# Matches only IDs that are inboxes
inbox_re = re.compile("[0-9][0-9]\\.01 .+")


def _valid_category_re(a: str) -> re.Pattern:
    """Match only valid categories for a given area."""
    return re.compile("(" + a + "[0-9]) (.+)")


def _valid_id_re(ac: str) -> re.Pattern:
    """Match only valid IDs for a given area and category."""
    return re.compile("(" + ac + "\\.[0-9][0-9]) (.+)")


def _jdex_note_area_re(*, alt_zeros: bool = False) -> re.Pattern:
    """Match JDex IDs that should be an area name."""
    if alt_zeros:
        return re.compile(
            "0([0-9])\\.00 (.+?)( area management)?( index)?(\\.md)?",
            flags=re.IGNORECASE,
        )
    return re.compile(
        "([0-9])0\\.00 (.+?)( area management)?( index)?(\\.md)?",
        flags=re.IGNORECASE,
    )


def _jdex_note_category_re(*, alt_zeros: bool = False) -> re.Pattern:
    """Match JDex IDs that should be category name."""
    if alt_zeros:
        # We need to tolerate the "area management" suffix for a category as well, to create categories from e.g. `01.00 Life Admin Area Management`
        return re.compile(
            "([0-9][0-9])\\.00 (.+?)( (category|area) management)?( index)?(\\.md)?",
            flags=re.IGNORECASE,
        )
    return re.compile(
        "([0-9][1-9])\\.00 (.+?)( category management)?( index)?(\\.md)?",
        flags=re.IGNORECASE,
    )


def _jdex_note_id_re(ac: str) -> re.Pattern:
    """Match only valid JDex note IDs for a given area and category."""
    return re.compile("(" + ac + "\\.[0-9][0-9]) (.+?)(\\.md)?")


# Match area header JDex notes
jdex_note_header_re = re.compile("([0-9])0\\. (.+?)(\\.md)?")
# Match any valid ID JDex note
jdex_note_generic_id_re = re.compile("([0-9][0-9])\\.([0-9][0-9]) (.+?)(\\.md)?")


# Matches JDex areas in a single-file format
jdex_line_area_re = re.compile("([0-9])0-(?:\\1)9 (.+?)\\s*(//.*)?")
# Matches JDex categories in a single-file format
jdex_line_category_re = re.compile("([0-9][0-9]) (.+?)\\s*(//.*)?")
# Matches JDex ids in a single-file format
jdex_line_id_re = re.compile("([0-9][0-9].[0-9][0-9]) (.+?)\\s*(//.*)?")


def _entry_is_ignored(
    ignored: list[str] | None,
    nested_under: list[str],
    f: os.DirEntry,
) -> bool:
    """Check if a given file/directory should be ignored."""
    if not ignored:
        return False
    p = PurePath(*nested_under, f.name)
    return any(p.match(pattern) for pattern in ignored)
