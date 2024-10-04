#!/usr/bin/env python3

"""Script to check for common issues with a Johnny Decimal system."""

from __future__ import annotations

import argparse
import dataclasses
import json
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


@dataclass
class _JDexAccumulator:
    """Accumulator used by _get_jdex_entries to gather information about the JDex."""

    errors: list[JDexError]
    areas: dict[str, list[tuple[str, File]]]
    categories: dict[str, list[tuple[str, File]]]
    ids: dict[str, list[tuple[str, File]]]
    headers: dict[str, list[tuple[str, File]]]

    def __init__(self) -> None:
        self.errors = []
        self.areas = {}
        self.categories = {}
        self.ids = {}
        self.headers = {}


@dataclass(frozen=True)
class _JDexResults:
    """Canonical results from the JDex, featuring the ID and name of each area/category/ID."""

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


# Match area header JDex notes
jdex_note_header_re = re.compile("([0-9])0\\. (.+?)(\\.md)?")
# Match any valid ID JDex note
jdex_note_generic_id_re = re.compile("([0-9][0-9])\\.([0-9][0-9]) (.+?)(\\.md)?")


def _jdex_note_id_re(ac: str) -> re.Pattern:
    """Match only valid JDex note IDs for a given area and category."""
    return re.compile("(" + ac + "\\.[0-9][0-9]) (.+?)(\\.md)?")


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


def _process_single_file_jdex(path: Path) -> _JDexResults:
    """Process a JDex located in a single file."""
    # Matches JDex areas in a single-file format
    jdex_line_area_re = re.compile("([0-9])0-(?:\\1)9 (.+?)\\s*(//.*)?")
    # Matches JDex categories in a single-file format
    jdex_line_category_re = re.compile("([0-9][0-9]) (.+?)\\s*(//.*)?")
    # Matches JDex ids in a single-file format
    jdex_line_id_re = re.compile("([0-9][0-9].[0-9][0-9]) (.+?)\\s*(//.*)?")

    file_areas = {}
    file_categories = {}
    file_ids = {}

    with path.open() as jdex_it:
        for entry in jdex_it:
            area_match = jdex_line_area_re.fullmatch(entry.strip())
            if area_match:
                file_areas[area_match.group(1)] = (
                    f"{area_match.group(1)}0-09 {area_match.group(2)}"
                )
                continue
            category_match = jdex_line_category_re.fullmatch(entry.strip())
            if category_match:
                file_categories[category_match.group(1)] = (
                    f"{category_match.group(1)} {category_match.group(2)}"
                )
                continue
            id_match = jdex_line_id_re.fullmatch(entry.strip())
            if id_match:
                file_ids[id_match.group(1)] = f"{id_match.group(1)} {id_match.group(2)}"
                continue
    return _JDexResults(
        jdex_areas=file_areas,
        jdex_categories=file_categories,
        jdex_ids=file_ids,
    )


def _process_flat_jdex_structure(
    files: list[os.DirEntry],
    jdex: _JDexAccumulator,
    *,
    ignored: list[str] | None,
    alt_zeros: bool = False,
) -> None:
    """Process a JDex that is a series of flat files."""
    area_re = re.compile(
        "0([0-9])\\.00 (.+?)( area management)?( index)?(\\.md)?"
        if alt_zeros
        else "([0-9])0\\.00 (.+?)( area management)?( index)?(\\.md)?",
        flags=re.IGNORECASE,
    )
    category_re = re.compile(
        # We need to tolerate the "area management" suffix for a category as well, to create categories from e.g. `01.00 Life Admin Area Management`
        "([0-9][0-9])\\.00 (.+?)( (category|area) management)?( index)?(\\.md)?"
        if alt_zeros
        else "([0-9][1-9])\\.00 (.+?)( category management)?( index)?(\\.md)?",
        flags=re.IGNORECASE,
    )

    for jid in files:
        if _entry_is_ignored(ignored, [], jid):
            continue

        file = File(name=jid.name, full_path=jid.path, nested_under=[])

        # Check if the file matches an area
        area_match = area_re.fullmatch(jid.name)
        if area_match:
            _insert_append(
                area_match.group(1),
                (area_match.group(2), file),
                jdex.areas,
            )

        # Check if the file matches a category
        cat_match = category_re.fullmatch(jid.name)
        if cat_match:
            _insert_append(
                cat_match.group(1),
                (cat_match.group(2), file),
                jdex.categories,
            )

        # Check if it's a header match for alt zeros
        header_match = jdex_note_header_re.fullmatch(jid.name)
        if header_match:
            _insert_append(
                header_match.group(1),
                (header_match.group(2), file),
                jdex.headers,
            )
            continue

        # The file should also be a valid ID (or is bad)
        id_match = jdex_note_generic_id_re.fullmatch(jid.name)
        if id_match:
            _insert_append(
                f"{id_match.group(1)}.{id_match.group(2)}",
                (id_match.group(3), file),
                jdex.ids,
            )
        else:
            jdex.errors.append(
                JDexError(error=JDexInvalidIDName(), files=[file]),
            )


def _process_nested_jdex_structure(
    path: Path,
    jdex: _JDexAccumulator,
    root_level_files: list[os.DirEntry],
    *,
    ignored: list[str] | None,
) -> None:
    for area in os.scandir(path):
        if _entry_is_ignored(ignored, [], area):
            continue
        if area.is_file():
            # Maybe we have a flat structure
            root_level_files.append(area)
            continue

        # Otherwise, a directory, so nested structure
        area_file = File(name=area.name, full_path=area.path, nested_under=[])
        area_match = valid_area_re.fullmatch(area.name)
        if not area_match:
            jdex.errors.append(
                JDexError(error=JDexInvalidAreaName(), files=[area_file]),
            )
            continue
        _insert_append(
            area_match.group(1),
            (area_match.group(2), area_file),
            jdex.areas,
        )
        cat_re = _valid_category_re(area_match.group(1))
        with os.scandir(area.path) as cats_it:
            for cat in cats_it:
                if _entry_is_ignored(ignored, [area.name], cat):
                    continue
                cat_file = File(
                    name=cat.name,
                    full_path=cat.path,
                    nested_under=[area.name],
                )
                if cat.is_file():
                    jdex.errors.append(
                        JDexError(
                            error=JDexFileOutsideCategory(),
                            files=[cat_file],
                        ),
                    )
                    continue

                if cat_match := cat_re.fullmatch(cat.name):
                    _insert_append(
                        cat_match.group(1),
                        (cat_match.group(2), cat_file),
                        jdex.categories,
                    )
                    id_re = _jdex_note_id_re(cat_match.group(1))
                    with os.scandir(cat.path) as ids_it:
                        nested_under = [area.name, cat.name]
                        for jid in ids_it:
                            if _entry_is_ignored(ignored, nested_under, jid):
                                continue
                            id_file = File(
                                name=jid.name,
                                full_path=jid.path,
                                nested_under=nested_under,
                            )
                            if id_match := id_re.fullmatch(jid.name):
                                _insert_append(
                                    id_match.group(1),
                                    (id_match.group(2), id_file),
                                    jdex.ids,
                                )
                            elif gen_match := jdex_note_generic_id_re.fullmatch(
                                jid.name,
                            ):
                                jdex.errors.append(
                                    JDexError(
                                        error=JDexIdInWrongCategory(
                                            id_ac=gen_match.group(1),
                                            file_ac=cat_match.group(1),
                                        ),
                                        files=[id_file],
                                    ),
                                )
                            else:
                                jdex.errors.append(
                                    JDexError(
                                        error=JDexInvalidIDName(),
                                        files=[id_file],
                                    ),
                                )

                elif gen_match := generic_category_re.fullmatch(cat.name):
                    jdex.errors.append(
                        JDexError(
                            error=JDexCategoryInWrongArea(
                                category_area=gen_match.group(1),
                                file_area=area_match.group(1),
                            ),
                            files=[cat_file],
                        ),
                    )
                else:
                    jdex.errors.append(
                        JDexError(error=JDexInvalidCategoryName(), files=[cat_file]),
                    )


def _get_jdex_entries(
    jdex_dir: Path,
    *,
    ignored: list[str] | None,
    alt_zeros: bool = False,
) -> _JDexResults | list[JDexError]:
    """Return canonical JDex information or a list of errors for it."""
    if jdex_dir.is_file():
        # Single file JDex
        return _process_single_file_jdex(jdex_dir)

    jdex: _JDexAccumulator = _JDexAccumulator()
    root_level_files: list[os.DirEntry] = []

    _process_nested_jdex_structure(jdex_dir, jdex, root_level_files, ignored=ignored)

    if jdex.ids or jdex.errors:
        # Not a flat structure, so we need to add all root level files as invalid
        jdex.errors.extend(
            [
                JDexError(
                    error=JDexFileOutsideCategory(),
                    files=[
                        File(
                            name=f.name,
                            full_path=f.path,
                            nested_under=[],
                        ),
                    ],
                )
                for f in root_level_files
            ],
        )

    else:
        # Nothing nested, and not a file, so assume a flat structure
        _process_flat_jdex_structure(
            root_level_files,
            jdex,
            ignored=ignored,
            alt_zeros=alt_zeros,
        )

    # These duplicate errors apply regardless of JDex type
    jdex.errors.extend(_error_if_dups(JDexDuplicateArea, JDexError, jdex.areas))
    jdex.errors.extend(
        _error_if_dups(JDexDuplicateCategory, JDexError, jdex.categories)
    )
    jdex.errors.extend(_error_if_dups(JDexDuplicateId, JDexError, jdex.ids))
    jdex.errors.extend(_error_if_dups(JDexDuplicateAreaHeader, JDexError, jdex.headers))

    for header, files in jdex.headers.items():
        if header not in jdex.areas:
            jdex.errors.append(
                JDexError(
                    error=JDexAreaHeaderWithoutArea(area=header),
                    files=[f for (_, f) in files],
                ),
            )
        elif len(files) == 1 and files[0][0] != jdex.areas[header][0][0]:
            jdex.errors.append(
                JDexError(
                    error=JDexAreaHeaderDifferentFromArea(
                        area=header,
                        jdex_name=f"{_print_area(header)} {jdex.areas[header][0][0]}",
                    ),
                    files=[f for (_, f) in files],
                ),
            )

    if jdex.errors:
        return jdex.errors
    return _JDexResults(
        jdex_areas={k: f"{_print_area(k)} {v[0][0]}" for k, v in jdex.areas.items()},
        jdex_categories={k: f"{k} {v[0][0]}" for k, v in jdex.categories.items()},
        jdex_ids={k: f"{k} {v[0][0]}" for k, v in jdex.ids.items()},
    )


def lint_dir(
    path: Path,
    ignored: list[str] | None = None,
) -> LintResults:
    """Check a root of a JD system for issues."""
    errors: list[Error] = []
    used_areas: dict[str, list[tuple[str, File]]] = {}
    used_categories: dict[str, list[tuple[str, File]]] = {}
    used_ids: dict[str, list[tuple[str, File]]] = {}

    def check_inbox(nested_under: list[str], f: os.DirEntry) -> None:
        if inbox_re.fullmatch(f.name):
            entries = len(os.listdir(f.path))
            if entries:
                errors.append(
                    Error(
                        error=NonemptyInbox(num_items=entries),
                        files=[
                            File(
                                name=f.name,
                                full_path=f.path,
                                nested_under=nested_under,
                            ),
                        ],
                    ),
                )

    def check_if_out_of_id(file: os.DirEntry, nested_under: list[str]) -> bool:
        if file.is_file():
            errors.append(
                Error(
                    error=FileOutsideId(),
                    files=[
                        File(
                            name=file.name,
                            full_path=file.path,
                            nested_under=nested_under,
                        ),
                    ],
                ),
            )
            return True
        return False

    with os.scandir(path) as areas_it:
        for area in areas_it:
            if _entry_is_ignored(ignored, [], area) or check_if_out_of_id(area, []):
                continue
            area_file = File(
                name=area.name,
                full_path=area.path,
                nested_under=[],
            )
            area_match = valid_area_re.fullmatch(area.name)
            if not area_match:
                errors.append(
                    Error(
                        error=InvalidAreaName(),
                        files=[area_file],
                    ),
                )
                continue
            # Valid area
            _insert_append(
                area_match.group(1),
                (area_match.group(2), area_file),
                used_areas,
            )
            cat_re = _valid_category_re(area_match.group(1))
            with os.scandir(area.path) as cats_it:
                for cat in cats_it:
                    if _entry_is_ignored(
                        ignored,
                        [area.name],
                        cat,
                    ) or check_if_out_of_id(cat, [area.name]):
                        continue
                    cat_file = File(
                        name=cat.name,
                        full_path=cat.path,
                        nested_under=[area.name],
                    )
                    if cat_match := cat_re.fullmatch(cat.name):
                        _insert_append(
                            cat_match.group(1),
                            (cat_match.group(2), cat_file),
                            used_categories,
                        )
                        id_re = _valid_id_re(cat_match.group(1))
                        with os.scandir(cat.path) as ids_it:
                            nested_under = [area.name, cat.name]

                            for jid in ids_it:
                                if _entry_is_ignored(
                                    ignored,
                                    nested_under,
                                    jid,
                                ) or check_if_out_of_id(jid, nested_under):
                                    continue
                                id_file = File(
                                    name=jid.name,
                                    full_path=jid.path,
                                    nested_under=nested_under,
                                )
                                if id_match := id_re.fullmatch(jid.name):
                                    _insert_append(
                                        id_match.group(1),
                                        (id_match.group(2), id_file),
                                        used_ids,
                                    )

                                    check_inbox(nested_under, jid)
                                elif gen_match := generic_id_re.fullmatch(jid.name):
                                    errors.append(
                                        Error(
                                            error=IdInWrongCategory(
                                                id_ac=gen_match.group(
                                                    1,
                                                ),
                                                file_ac=cat_match.group(
                                                    1,
                                                ),
                                            ),
                                            files=[id_file],
                                        ),
                                    )

                                else:
                                    errors.append(
                                        Error(
                                            error=InvalidIDName(),
                                            files=[id_file],
                                        ),
                                    )
                    elif gen_match := generic_category_re.fullmatch(cat.name):
                        errors.append(
                            Error(
                                error=CategoryInWrongArea(
                                    category_area=gen_match.group(1),
                                    file_area=area_match.group(1),
                                ),
                                files=[cat_file],
                            ),
                        )
                    else:
                        errors.append(
                            Error(
                                error=InvalidCategoryName(),
                                files=[cat_file],
                            ),
                        )

        errors.extend(_error_if_dups(DuplicateArea, Error, used_areas))
        errors.extend(_error_if_dups(DuplicateCategory, Error, used_categories))
        errors.extend(_error_if_dups(DuplicateId, Error, used_ids))

    return LintResults(
        errors=sorted(errors, key=_sort_error),
        used_areas=used_areas,
        used_categories=used_categories,
        used_ids=used_ids,
    )
