#!/usr/bin/env python3

"""Script to check for common issues with a Johnny Decimal system."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import typing
import sys
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Any, Literal, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable
import tomllib


###############################################################################
# Exceptions
###############################################################################


class ConfigError(Exception):
    """An error in the jdlint config."""

    def __init__(self, key: str, message: str) -> None:
        """Create a config error, given the key it occurs at and a message."""
        super().__init__(f"Error in config at key: {key}.  {message}")


class ConfigKeyError(ConfigError):
    """An unexpected key in the jdlint config."""

    def __init__(self, key: str, valid: list[str]) -> None:
        """Create a key error, given the extra key and a list of valid keys."""
        super().__init__(
            key,
            f"Not an expected key.  Valid keys are: [{', '.join(valid)}]",
        )


class ConfigTypeError(ConfigError):
    """A value with the wrong type in the jdlint config."""

    def __init__(self, key: str, expected: str, got: str) -> None:
        """Create a type error, given the key it occurs at, the expected type, and the actual type."""
        super().__init__(key, f"Wrong type.  Expected: {expected}  Got: {got}")


class ConfigValueError(ConfigError):
    """A bad value in the jdlint config."""

    def __init__(self, key, issue, got):
        """Create a value error, given the key it occurs at, the issue with the value, and the actual value."""
        super().__init__(key, f"Bad value.  Got: {got}  Issue: {issue}")


class ConfigConflictError(ConfigError):
    """A conflict in the jdlint config."""

    def __init__(self, key, issue):
        """Create a conflict error, given the key it occurs at and the issue."""
        super().__init__(key, f"Conflict in config.  Issue: {issue}")


###############################################################################
# Config
###############################################################################


class ConfigSystemRoot:
    """A root (base folder) of a JD system to check for correctness, e.g. ~/Documents."""

    def __init__(self, at: str, from_file: dict) -> None:
        """Create a valid configuration given a loaded section of a config file."""
        # Acquire and set defaults
        self.name = from_file.pop("name")
        self.path = Path(from_file.pop("path")).expanduser()
        self.ignore = from_file.pop("ignore", [])

        if not isinstance(self.name, str):
            raise ConfigTypeError(
                f"{at}.name",
                "str",
                type(self.name).__name__,
            )

        # Validate path is good
        if not self.path.is_dir():
            raise ConfigValueError(
                f"{at}.path",
                "Root path isn't a folder that exists!",
                self.path,
            )
        if not isinstance(self.ignore, list):
            raise ConfigTypeError(
                f"{at}.ignore",
                "list",
                type(self.ignore).__name__,
            )
        for r in self.ignore:
            if not isinstance(r, str):
                raise ConfigTypeError(f"{at}.ignore", "str", type(r).__name__)

        # Ensure no extra fields
        for key in from_file:
            raise ConfigKeyError(f"{at}.{key}", list(self.__dict__.keys()))


class ConfigSystemJDex:
    """Valid configuration for the JDex of a system."""

    def __init__(self, at: str, from_file: dict) -> None:
        """Create a valid configuration given a loaded section of a config file."""
        # Acquire and set defaults
        self.path = Path(from_file.pop("path")).expanduser()
        self.ignore = from_file.pop("ignore", [])

        # Validate
        if not self.path.is_dir():
            raise ConfigValueError(
                f"{at}.path",
                "JDex path isn't a folder that exists!",
                self.path,
            )
        if not isinstance(self.ignore, list):
            raise ConfigTypeError(
                f"{at}.ignore",
                "list",
                type(self.ignore).__name__,
            )
        for r in self.ignore:
            if not isinstance(r, str):
                raise ConfigTypeError(f"{at}.ignore", "str", type(r).__name__)

        self.children = [
            ConfigJDexTier(
                f"{at}.children[{i}]",
                [],
                v,
            )
            for i, v in enumerate(from_file.pop("children", []))
        ]
        self.notes = [
            ConfigJDexNotes(
                f"{at}.notes[{i}]",
                [],
                v,
            )
            for i, v in enumerate(from_file.pop("notes", []))
        ]
        if self.notes and self.children:
            raise ConfigConflictError(
                at,
                "Only one of notes and children may be specified.",
            )

        # Ensure no extra fields
        for key in from_file:
            raise ConfigKeyError(f"{at}.{key}", list(self.__dict__.keys()))


class ConfigLinter:
    """Valid configuration for the linter."""

    def __init__(self, from_file: dict) -> None:
        """Create a valid configuration given a loaded linter section of a config file."""
        # Acquire and set defaults
        self.disable_rules = from_file.pop("disable_rules", [])
        self.json_output = from_file.pop("json_output", False)
        self.ignore = from_file.pop("ignore", [])

        # Validate
        if not isinstance(self.disable_rules, list):
            raise ConfigTypeError(
                "linter.disable_rules",
                "list",
                type(self.disable_rules).__name__,
            )
        for r in self.disable_rules:
            if r in [e.type for e in typing.get_args(ErrorType)]:
                continue
            raise ConfigValueError("linter.disable_rules", "not a valid rule name", r)

        if not isinstance(self.json_output, bool):
            raise ConfigTypeError(
                "linter.json_output",
                "bool",
                type(self.json_output).__name__,
            )

        if not isinstance(self.ignore, list):
            raise ConfigTypeError(
                "linter.ignore",
                "list",
                type(self.ignore).__name__,
            )
        for r in self.ignore:
            if not isinstance(r, str):
                raise ConfigTypeError("linter.ignore", "str", type(r).__name__)

        # Ensure no extra fields
        for key in from_file:
            raise ConfigKeyError(f"linter.{key}", list(self.__dict__.keys()))


class ConfigSystem:
    """Valid configuration for the JD system."""

    def __init__(self, from_file: dict) -> None:
        """Create a valid configuration given a loaded system section of a config file."""
        self.roots = [
            ConfigSystemRoot(
                f"system.roots[{i}]",
                v,
            )
            for i, v in enumerate(from_file.pop("roots", []))
        ]

        if "jdex" in from_file:
            self.jdex = ConfigSystemJDex("system.jdex", from_file.pop("jdex"))
        else:
            self.jdex = None

        self.children = [
            ConfigSystemTier(
                f"system.children[{i}]",
                [],
                v,
            )
            for i, v in enumerate(from_file.pop("children", []))
        ]
        # Ensure no extra fields
        for key in from_file:
            raise ConfigKeyError(f"system.{key}", list(self.__dict__.keys()))


class ConfigJDexNotes:
    """Configuration for how JDex notes are formatted."""

    def __init__(
        self,
        at: str,
        parent_segments: list[str],
        from_file: dict,
    ) -> None:
        """Create a valid note format given a loaded section of a config file."""
        # Acquire and set defaults
        self.name = from_file.pop("name")

        # Validate
        if not isinstance(self.name, str):
            raise ConfigTypeError(
                f"{at}.name",
                "str",
                type(self.name).__name__,
            )
        if not isinstance(from_file["format"], str):
            raise ConfigTypeError(
                f"{at}.format",
                "str",
                type(from_file["format"]).__name__,
            )
        # Compile Format
        self.format = ConfigFormat(
            f"{at}.format",
            parent_segments,
            from_file.pop("format"),
        )

        # Ensure no extra fields
        for key in from_file:
            raise ConfigKeyError(f"{at}.{key}", list(self.__dict__.keys()))


class ConfigFolderTier:
    """A tier (hierarchical level) of a JD system, e.g. a Category, whether in the JDex or the system itself."""

    def __init__(
        self,
        child_class: Callable,
        at: str,
        parent_segments: list[str],
        from_file: dict,
    ) -> None:
        """Create a valid tier given a loaded section of a config file."""
        # Acquire and set defaults
        self.name = from_file.pop("name")
        self.allow_arbitrary_contents = from_file.pop("allow_arbitrary_contents", False)

        # Validate
        if not isinstance(self.name, str):
            raise ConfigTypeError(
                f"{at}.name",
                "str",
                type(self.name).__name__,
            )
        if not isinstance(from_file["format"], str):
            raise ConfigTypeError(
                f"{at}.format",
                "str",
                type(from_file["format"]).__name__,
            )
        if not isinstance(self.allow_arbitrary_contents, bool):
            raise ConfigTypeError(
                f"{at}.allow_arbitrary_contents",
                "bool",
                type(self.allow_arbitrary_contents).__name__,
            )

        # Compile Format & Children
        self.format = ConfigFormat(
            f"{at}.format",
            parent_segments,
            from_file.pop("format"),
        )
        self.children = [
            child_class(
                f"{at}.children[{i}]",
                self.format.known_segments,
                v,
            )
            for i, v in enumerate(from_file.pop("children", []))
        ]
        if self.children and self.allow_arbitrary_contents:
            raise ConfigConflictError(
                at,
                "If children are specified, allow_arbitrary_contents must be false.",
            )


class ConfigSystemTier(ConfigFolderTier):
    """A tier (hierarchical level) of a JD system, e.g. a Category, in the system (not the JDex)."""

    def __init__(self, at: str, parent_segments: list[str], from_file: dict) -> None:
        """Create a valid tier given a loaded section of a config file."""
        # Acquire and set defaults
        self.jdex_note = from_file.pop("jdex_note", None)
        self.can_be_file = from_file.pop("can_be_file", False)

        # Call the folder tier stuff
        super().__init__(ConfigSystemTier, at, parent_segments, from_file)

        # Validate
        if self.jdex_note is not None and not isinstance(self.jdex_note, str):
            raise ConfigTypeError(
                f"{at}.jdex_note",
                "str",
                type(self.jdex_note).__name__,
            )
        if not isinstance(self.can_be_file, bool):
            raise ConfigTypeError(
                f"{at}.can_be_file",
                "bool",
                type(self.can_be_file).__name__,
            )

        if self.children and (self.can_be_file):
            raise ConfigConflictError(
                at,
                "If children are specified, can_be_file must be false.",
            )
        # Ensure no extra fields
        for key in from_file:
            raise ConfigKeyError(f"{at}.{key}", list(self.__dict__.keys()))


class ConfigJDexTier(ConfigFolderTier):
    """A tier (hierarchical level) of a JD system, e.g. a Category, in the JDex."""

    def __init__(self, at: str, parent_segments: list[str], from_file: dict) -> None:
        """Create a valid tier given a loaded section of a config file."""
        # Call the folder tier stuff
        super().__init__(ConfigJDexTier, at, parent_segments, from_file)

        self.notes = [
            ConfigJDexNotes(
                f"{at}.notes[{i}]",
                self.format.known_segments,
                v,
            )
            for i, v in enumerate(from_file.pop("notes", []))
        ]

        if not self.notes and not self.children:
            raise ConfigConflictError(
                at,
                "A JDex tier must specify either notes or children.",
            )

        if self.notes and self.children:
            raise ConfigConflictError(
                at,
                "Only one of notes and children may be specified.",
            )

        # Ensure no extra fields
        for key in from_file:
            raise ConfigKeyError(f"{at}.{key}", list(self.__dict__.keys()))


class ConfigFormat:
    """A format for a file or folder."""

    # A valid variable segment of a format
    variable_segment_re = re.compile(r"(=|\*|[#]+)([A-Za-z]+)")

    def __init__(self, at: str, parent_segments: list[str], from_file: str) -> None:
        """Create a valid format given a string from a config file."""
        if from_file.count("/") % 2 != 0:
            raise ConfigValueError(
                at,
                "Malformed format; there must be an even number of / characters.  You have an extra one/are missing one.",
                from_file,
            )
        if from_file == "":
            raise ConfigValueError(
                at,
                "Malformed format; must not be empty.",
                from_file,
            )
        regex = []
        new_segments = []
        for i, v in enumerate(from_file.split("/")):
            if i % 2 == 0:
                # Literal segment
                regex.append(lambda _, v=v: re.escape(v))
            else:
                # Variable segment
                match = ConfigFormat.variable_segment_re.fullmatch(v)
                if not match:
                    raise ConfigValueError(
                        at,
                        "Malformed format; variable segment must consist of =, *, or one or more # followed by an alphabetic identifier.",
                        v,
                    )
                if match.group(1) == "=":
                    if match.group(2) in parent_segments:
                        p = match.group(2)
                        regex.append(lambda d, p=p: re.escape(d[p]))
                    elif match.group(2) in new_segments:
                        identifier = match.group(2)
                        regex.append(
                            lambda _, identifier=identifier: f"(?P={identifier})",
                        )

                    else:
                        raise ConfigValueError(
                            at,
                            "Malformed format; variable segment referenced an identifier not bound in a parent.",
                            v,
                        )
                else:
                    if match.group(2) in parent_segments:
                        raise ConfigValueError(
                            at,
                            "Malformed format; variable segment tried to rebind an identifier already bound in a parent.",
                            v,
                        )
                    if match.group(2) in new_segments:
                        raise ConfigValueError(
                            at,
                            "Malformed format; variable segment tried to rebind an identifier already bound.",
                            v,
                        )
                    identifier = match.group(2)
                    new_segments.append(match.group(2))
                    if match.group(1) == "*":
                        regex.append(
                            lambda _, identifier=identifier: f"(?P<{identifier}>.+)",
                        )
                    else:
                        # Must be a ## type variable
                        regex.append(
                            lambda _, identifier=identifier, match_len=len(match.group(1)): (
                                f"(?P<{identifier}>[0-9]{{{match_len}}})"
                            ),
                        )

        self.known_segments = parent_segments + new_segments
        self.build_regex = lambda d: "".join([f(d) for f in regex])
        self.raw_format = from_file


class Config:
    def __init__(self, from_file):
        self.linter = ConfigLinter(from_file.get("linter", {}))
        self.system = ConfigSystem(from_file["system"])


###############################################################################
# Issues
###############################################################################


@dataclass(frozen=True)
class JDexIssue:
    """A single error detected in the JDex."""

    file: PurePath
    type = None

    def display(self) -> str:
        """Display this particular instance of an error."""
        raise NotImplementedError

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        raise NotImplementedError


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
class JDexIssueFileWhereFolderExpected(JDexIssue):
    """A JDex file that matched an expected folder was found."""

    matched_format: str
    type: Literal["JDEX_FILE_WHERE_FOLDER_EXPECTED"] = "JDEX_FILE_WHERE_FOLDER_EXPECTED"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f'{self.file!s} (matched "{self.matched_format}")'

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A JDex file was found that matched the format of an expected child folder.",
            fix="Your JDex format should not mix folders and notes that share a naming scheme.",
        )


@dataclass(frozen=True)
class JDexIssueArbitraryContentWhereNotAllowed(JDexIssue):
    """Content was found in the JDex that didn't match any expected format."""

    possible_formats: list[str]
    type: Literal["JDEX_ARBITRARY_CONTENT_WHERE_NOT_ALLOWED"] = (
        "JDEX_ARBITRARY_CONTENT_WHERE_NOT_ALLOWED"
    )

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f'{self.file!s} (matched none of "{self.possible_formats}")'

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Files or folders were found in the JDex that matched no expected format.",
            fix="You should either make the content match or set allow_arbitrary_content to true if it is intended for random content to be mixed in.",
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


JDexIssueType = (
    JDexAreaHeaderDifferentFromArea
    | JDexAreaHeaderWithoutArea
    | JDexCategoryInWrongArea
    | JDexDuplicateArea
    | JDexDuplicateAreaHeader
    | JDexDuplicateCategory
    | JDexDuplicateId
    | JDexIssueFileWhereFolderExpected
    | JDexIdInWrongCategory
    | JDexInvalidAreaName
    | JDexInvalidCategoryName
    | JDexInvalidIDName
)


@dataclass(frozen=True)
class File:
    """A file or folder that has been detected by jdlint."""

    name: Path
    path: Path


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
class StructureTree:
    """A node in the tree of the system."""

    name: str
    children: list[StructureTree]


@dataclass(frozen=True)
class LintResults:
    """All errors returned from linting files, as well as a tree of the structure of the JD system."""

    errors: list[Error]
    jdex_errors: list[JDexIssue]
    structure: list[StructureTree]


@dataclass
class _JDexAccumulator:
    """Accumulator used by _get_jdex_entries to gather information about the JDex."""

    errors: list[JDexIssue]
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

    areas: dict[str, str]
    categories: dict[str, str]
    ids: dict[str, str]


class _EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o: object) -> object:
        # Add JSON encoding for dataclasses and paths
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)  # ty:ignore[invalid-argument-type]
        if isinstance(o, PurePath):
            return str(o)
        return super().default(o)


def _sort_error(e: JDexIssue) -> tuple[str, tuple[tuple[str, ...], str]]:
    # Sort errors alphabetically by type, then by file affected
    if e.type is None:
        raise NotImplementedError
    return (
        e.type,
        (e.file.parent.parts, e.file.name),
    )


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


E = TypeVar("E")


# def _error_if_dups(  # Python's types are horrid and it just is awful to try to type this better
#     make_error_type: Callable[[str], Any],
#     make_error: Callable[[Any, list[File]], E],
#     d: dict[str, list[tuple[Any, File]]],
# ) -> list[E]:
#     return [
#         make_error(
#             make_error_type(k),
#             sorted([file for (_, file) in v], key=_sort_file),
#         )
#         for k, v in d.items()
#         if len(v) > 1
#     ]


def _insert_append(k, v, d) -> None:  # noqa: ANN001
    """Add value as a singleton if it's not already in the dict, else append it to the list."""
    if k not in d:
        d.update({k: []})

    d[k].append(v)


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
        areas=file_areas,
        categories=file_categories,
        ids=file_ids,
    )


# def _process_flat_jdex_structure(
#     files: list[os.DirEntry],
#     jdex: _JDexAccumulator,
#     *,
#     ignored: list[str] | None,
#     alt_zeros: bool = False,
# ) -> None:
#     """Process a JDex that is a series of flat files."""
#     area_re = re.compile(
#         "0([0-9])\\.00 (.+?)( area management)?( index)?(\\.md)?"
#         if alt_zeros
#         else "([0-9])0\\.00 (.+?)( area management)?( index)?(\\.md)?",
#         flags=re.IGNORECASE,
#     )
#     category_re = re.compile(
#         # We need to tolerate the "area management" suffix for a category as well, to create categories from e.g. `01.00 Life Admin Area Management`
#         "([0-9][0-9])\\.00 (.+?)( (category|area) management)?( index)?(\\.md)?"
#         if alt_zeros
#         else "([0-9][1-9])\\.00 (.+?)( category management)?( index)?(\\.md)?",
#         flags=re.IGNORECASE,
#     )

#     for jid in files:
#         if _entry_is_ignored(ignored, [], jid):
#             continue

#         file = File(name=jid.name, full_path=jid.path, nested_under=[])

#         # Check if the file matches an area
#         area_match = area_re.fullmatch(jid.name)
#         if area_match:
#             _insert_append(
#                 area_match.group(1),
#                 (area_match.group(2), file),
#                 jdex.areas,
#             )

#         # Check if the file matches a category
#         cat_match = category_re.fullmatch(jid.name)
#         if cat_match:
#             _insert_append(
#                 cat_match.group(1),
#                 (cat_match.group(2), file),
#                 jdex.categories,
#             )

#         # Check if it's a header match for alt zeros
#         header_match = jdex_note_header_re.fullmatch(jid.name)
#         if header_match:
#             _insert_append(
#                 header_match.group(1),
#                 (header_match.group(2), file),
#                 jdex.headers,
#             )
#             continue

#         # The file should also be a valid ID (or is bad)
#         id_match = jdex_note_generic_id_re.fullmatch(jid.name)
#         if id_match:
#             _insert_append(
#                 f"{id_match.group(1)}.{id_match.group(2)}",
#                 (id_match.group(3), file),
#                 jdex.ids,
#             )
#         else:
#             jdex.errors.append(
#                 JDexIssue(error=JDexInvalidIDName(), files=[file]),
#             )


# def _process_nested_jdex_structure(
#     path: Path,
#     jdex: _JDexAccumulator,
#     root_level_files: list[os.DirEntry],
#     *,
#     ignored: list[str] | None,
# ) -> None:
#     for area in os.scandir(path):
#         if _entry_is_ignored(ignored, [], area):
#             continue
#         if area.is_file():
#             # Maybe we have a flat structure
#             root_level_files.append(area)
#             continue

#         # Otherwise, a directory, so nested structure
#         area_file = File(name=area.name, full_path=area.path, nested_under=[])
#         area_match = valid_area_re.fullmatch(area.name)
#         if not area_match:
#             jdex.errors.append(
#                 JDexIssue(error=JDexInvalidAreaName(), files=[area_file]),
#             )
#             continue
#         _insert_append(
#             area_match.group(1),
#             (area_match.group(2), area_file),
#             jdex.areas,
#         )
#         cat_re = _valid_category_re(area_match.group(1))
#         with os.scandir(area.path) as cats_it:
#             for cat in cats_it:
#                 if _entry_is_ignored(ignored, [area.name], cat):
#                     continue
#                 cat_file = File(
#                     name=cat.name,
#                     full_path=cat.path,
#                     nested_under=[area.name],
#                 )
#                 if cat.is_file():
#                     jdex.errors.append(
#                         JDexIssue(
#                             error=JDexFileOutsideCategory(),
#                             files=[cat_file],
#                         ),
#                     )
#                     continue

#                 if cat_match := cat_re.fullmatch(cat.name):
#                     _insert_append(
#                         cat_match.group(1),
#                         (cat_match.group(2), cat_file),
#                         jdex.categories,
#                     )
#                     id_re = _jdex_note_id_re(cat_match.group(1))
#                     with os.scandir(cat.path) as ids_it:
#                         nested_under = [area.name, cat.name]
#                         for jid in ids_it:
#                             if _entry_is_ignored(ignored, nested_under, jid):
#                                 continue
#                             id_file = File(
#                                 name=jid.name,
#                                 full_path=jid.path,
#                                 nested_under=nested_under,
#                             )
#                             if id_match := id_re.fullmatch(jid.name):
#                                 _insert_append(
#                                     id_match.group(1),
#                                     (id_match.group(2), id_file),
#                                     jdex.ids,
#                                 )
#                             elif gen_match := jdex_note_generic_id_re.fullmatch(
#                                 jid.name,
#                             ):
#                                 jdex.errors.append(
#                                     JDexIssue(
#                                         error=JDexIdInWrongCategory(
#                                             id_ac=gen_match.group(1),
#                                             file_ac=cat_match.group(1),
#                                         ),
#                                         files=[id_file],
#                                     ),
#                                 )
#                             else:
#                                 jdex.errors.append(
#                                     JDexIssue(
#                                         error=JDexInvalidIDName(),
#                                         files=[id_file],
#                                     ),
#                                 )

#                 elif gen_match := generic_category_re.fullmatch(cat.name):
#                     jdex.errors.append(
#                         JDexIssue(
#                             error=JDexCategoryInWrongArea(
#                                 category_area=gen_match.group(1),
#                                 file_area=area_match.group(1),
#                             ),
#                             files=[cat_file],
#                         ),
#                     )
#                 else:
#                     jdex.errors.append(
#                         JDexIssue(error=JDexInvalidCategoryName(), files=[cat_file]),
#                     )


# def _get_jdex_entries(
#     jdex_dir: Path,
#     *,
#     ignored: list[str] | None,
#     alt_zeros: bool = False,
# ) -> _JDexResults | list[JDexIssue]:
#     """Return canonical JDex information or a list of errors for it."""
#     if jdex_dir.is_file():
#         # Single file JDex
#         return _process_single_file_jdex(jdex_dir)

#     jdex: _JDexAccumulator = _JDexAccumulator()
#     root_level_files: list[os.DirEntry] = []

#     _process_nested_jdex_structure(jdex_dir, jdex, root_level_files, ignored=ignored)

#     if jdex.ids or jdex.errors:
#         # Not a flat structure, so we need to add all root level files as invalid
#         jdex.errors.extend(
#             [
#                 JDexIssue(
#                     error=JDexFileOutsideCategory(),
#                     files=[
#                         File(
#                             name=f.name,
#                             full_path=f.path,
#                             nested_under=[],
#                         ),
#                     ],
#                 )
#                 for f in root_level_files
#             ],
#         )

#     else:
#         # Nothing nested, and not a file, so assume a flat structure
#         _process_flat_jdex_structure(
#             root_level_files,
#             jdex,
#             ignored=ignored,
#             alt_zeros=alt_zeros,
#         )

#     # These duplicate errors apply regardless of JDex type
#     jdex.errors.extend(_error_if_dups(JDexDuplicateArea, JDexIssue, jdex.areas))
#     jdex.errors.extend(
#         _error_if_dups(JDexDuplicateCategory, JDexIssue, jdex.categories),
#     )
#     jdex.errors.extend(_error_if_dups(JDexDuplicateId, JDexIssue, jdex.ids))
#     jdex.errors.extend(_error_if_dups(JDexDuplicateAreaHeader, JDexIssue, jdex.headers))

#     for header, files in jdex.headers.items():
#         if header not in jdex.areas:
#             jdex.errors.append(
#                 JDexIssue(
#                     error=JDexAreaHeaderWithoutArea(area=header),
#                     files=[f for (_, f) in files],
#                 ),
#             )
#         elif len(files) == 1 and files[0][0] != jdex.areas[header][0][0]:
#             jdex.errors.append(
#                 JDexIssue(
#                     error=JDexAreaHeaderDifferentFromArea(
#                         area=header,
#                         jdex_name=f"{_print_area(header)} {jdex.areas[header][0][0]}",
#                     ),
#                     files=[f for (_, f) in files],
#                 ),
#             )

#     if jdex.errors:
#         return jdex.errors
#     return _JDexResults(
#         areas={k: f"{_print_area(k)} {v[0][0]}" for k, v in jdex.areas.items()},
#         categories={k: f"{k} {v[0][0]}" for k, v in jdex.categories.items()},
#         ids={k: f"{k} {v[0][0]}" for k, v in jdex.ids.items()},
#     )


# def lint_dir(
#     path: Path,
#     ignored: list[str] | None = None,
# ) -> LintResults:
#     """Check a root of a JD system for issues."""
#     errors: list[Error] = []
#     used_areas: dict[str, list[tuple[str, File]]] = {}
#     used_categories: dict[str, list[tuple[str, File]]] = {}
#     used_ids: dict[str, list[tuple[str, File]]] = {}

#     def check_inbox(nested_under: list[str], f: os.DirEntry) -> None:
#         if inbox_re.fullmatch(f.name):
#             entries = len(os.listdir(f.path))
#             if entries:
#                 errors.append(
#                     Error(
#                         error=NonemptyInbox(num_items=entries),
#                         files=[
#                             File(
#                                 name=f.name,
#                                 full_path=f.path,
#                                 nested_under=nested_under,
#                             ),
#                         ],
#                     ),
#                 )

#     def check_if_out_of_id(file: os.DirEntry, nested_under: list[str]) -> bool:
#         if file.is_file():
#             errors.append(
#                 Error(
#                     error=FileOutsideId(),
#                     files=[
#                         File(
#                             name=file.name,
#                             full_path=file.path,
#                             nested_under=nested_under,
#                         ),
#                     ],
#                 ),
#             )
#             return True
#         return False

#     with os.scandir(path) as areas_it:
#         for area in areas_it:
#             if _entry_is_ignored(ignored, [], area) or check_if_out_of_id(area, []):
#                 continue
#             area_file = File(
#                 name=area.name,
#                 full_path=area.path,
#                 nested_under=[],
#             )
#             area_match = valid_area_re.fullmatch(area.name)
#             if not area_match:
#                 errors.append(
#                     Error(
#                         error=InvalidAreaName(),
#                         files=[area_file],
#                     ),
#                 )
#                 continue
#             # Valid area
#             _insert_append(
#                 area_match.group(1),
#                 (area_match.group(2), area_file),
#                 used_areas,
#             )
#             cat_re = _valid_category_re(area_match.group(1))
#             with os.scandir(area.path) as cats_it:
#                 for cat in cats_it:
#                     if _entry_is_ignored(
#                         ignored,
#                         [area.name],
#                         cat,
#                     ) or check_if_out_of_id(cat, [area.name]):
#                         continue
#                     cat_file = File(
#                         name=cat.name,
#                         full_path=cat.path,
#                         nested_under=[area.name],
#                     )
#                     if cat_match := cat_re.fullmatch(cat.name):
#                         _insert_append(
#                             cat_match.group(1),
#                             (cat_match.group(2), cat_file),
#                             used_categories,
#                         )
#                         id_re = _valid_id_re(cat_match.group(1))
#                         with os.scandir(cat.path) as ids_it:
#                             nested_under = [area.name, cat.name]

#                             for jid in ids_it:
#                                 if _entry_is_ignored(
#                                     ignored,
#                                     nested_under,
#                                     jid,
#                                 ) or check_if_out_of_id(jid, nested_under):
#                                     continue
#                                 id_file = File(
#                                     name=jid.name,
#                                     full_path=jid.path,
#                                     nested_under=nested_under,
#                                 )
#                                 if id_match := id_re.fullmatch(jid.name):
#                                     _insert_append(
#                                         id_match.group(1),
#                                         (id_match.group(2), id_file),
#                                         used_ids,
#                                     )

#                                     check_inbox(nested_under, jid)
#                                 elif gen_match := generic_id_re.fullmatch(jid.name):
#                                     errors.append(
#                                         Error(
#                                             error=IdInWrongCategory(
#                                                 id_ac=gen_match.group(
#                                                     1,
#                                                 ),
#                                                 file_ac=cat_match.group(
#                                                     1,
#                                                 ),
#                                             ),
#                                             files=[id_file],
#                                         ),
#                                     )

#                                 else:
#                                     errors.append(
#                                         Error(
#                                             error=InvalidIDName(),
#                                             files=[id_file],
#                                         ),
#                                     )
#                     elif gen_match := generic_category_re.fullmatch(cat.name):
#                         errors.append(
#                             Error(
#                                 error=CategoryInWrongArea(
#                                     category_area=gen_match.group(1),
#                                     file_area=area_match.group(1),
#                                 ),
#                                 files=[cat_file],
#                             ),
#                         )
#                     else:
#                         errors.append(
#                             Error(
#                                 error=InvalidCategoryName(),
#                                 files=[cat_file],
#                             ),
#                         )

#         errors.extend(_error_if_dups(DuplicateArea, Error, used_areas))
#         errors.extend(_error_if_dups(DuplicateCategory, Error, used_categories))
#         errors.extend(_error_if_dups(DuplicateId, Error, used_ids))

#     return LintResults(
#         errors=sorted(errors, key=_sort_error),
#         used_areas=used_areas,
#         used_categories=used_categories,
#         used_ids=used_ids,
#     )


# def lint_dir_and_jdex(
#     *,
#     path: Path,
#     jdex_path: Path,
#     ignored: list[str] | None = None,
#     alt_zeros: bool = False,
# ) -> tuple[list[Error], list[JDexIssue]]:
#     """Check a root of a JD system and its JDex for issues."""
#     results = lint_dir(path, ignored)
#     jdex = _get_jdex_entries(jdex_path, ignored=ignored, alt_zeros=alt_zeros)
#     if isinstance(jdex, list):
#         return (results.errors, sorted(jdex, key=_sort_error))

#     errors = results.errors

#     for area, files in results.used_areas.items():
#         if area not in jdex.areas:
#             errors.append(
#                 Error(
#                     error=AreaNotInJDex(area=area),
#                     files=[f for (_, f) in files],
#                 ),
#             )
#         elif len(files) == 1 and files[0][1].name != jdex.areas[area]:
#             errors.append(
#                 Error(
#                     error=AreaDifferentFromJDex(
#                         area=area,
#                         jdex_name=jdex.areas[area],
#                     ),
#                     files=[f for (_, f) in files],
#                 ),
#             )
#     for category, files in results.used_categories.items():
#         if category not in jdex.categories:
#             errors.append(
#                 Error(
#                     error=CategoryNotInJDex(category=category),
#                     files=[f for (_, f) in files],
#                 ),
#             )
#         elif len(files) == 1 and files[0][1].name != jdex.categories[category]:
#             errors.append(
#                 Error(
#                     error=CategoryDifferentFromJDex(
#                         category=category,
#                         jdex_name=jdex.categories[category],
#                     ),
#                     files=[f for (_, f) in files],
#                 ),
#             )
#     for jid, files in results.used_ids.items():
#         if jid not in jdex.ids:
#             errors.append(
#                 Error(error=IdNotInJDex(id=jid), files=[f for (_, f) in files]),
#             )
#         elif len(files) == 1 and files[0][1].name != jdex.ids[jid]:
#             errors.append(
#                 Error(
#                     error=IdDifferentFromJDex(id=jid, jdex_name=jdex.ids[jid]),
#                     files=[f for (_, f) in files],
#                 ),
#             )
#     return (sorted(errors, key=_sort_error), [])


def _print_area(d: str) -> str:
    """Given the number of an area, pretty-print it."""
    return f"{d}0-{d}9"


def _print_nest(f: File) -> str:
    """Pretty-print a nested file."""
    if f.nested_under:
        return str(PurePath(*f.nested_under, f.name))
    return f.name


class JDexEntry:
    """An entry in the JDex."""

    def __init__(self, name: str) -> None:
        """Create a JDexEntry, given its filename."""
        self.name = name


def _get_jdex_notes_here_or_children(
    ignored: list[str],
    bound_segments: dict[str, str],
    path: os.PathLike,
    tier: ConfigJDexTier | ConfigSystemJDex,
) -> tuple[list[JDexEntry], list[JDexIssue]]:
    # Compile regexes for children
    valid_children = [
        (re.compile(c.format.build_regex(bound_segments)), c) for c in tier.children
    ]
    valid_notes = [re.compile(n.format.build_regex(bound_segments)) for n in tier.notes]

    accumulated_notes = []
    accumulated_errors = []

    with os.scandir(path) as contents:
        for x in contents:
            if _entry_is_ignored(ignored, [], x):
                continue
            for child_format, child in valid_children:
                match = child_format.fullmatch(x.name)
                if match:
                    # Is a valid child folder
                    if x.is_file():
                        # This is an error
                        accumulated_errors.append(
                            JDexIssueFileWhereFolderExpected(
                                PurePath(x),
                                child.format.raw_format,
                            ),
                        )
                        break

                    # Walk child
                    (child_notes, child_errors) = _get_jdex_notes_here_or_children(
                        ignored,
                        {**bound_segments, **match.groupdict()},
                        x.path,
                        child,
                    )
                    accumulated_notes.extend(child_notes)
                    accumulated_errors.extend(child_errors)
                    break
            else:
                for note_format in valid_notes:
                    match = note_format.fullmatch(x.name)
                    if match:
                        # Is a valid JDex note
                        if x.is_dir():
                            # This is an error
                            # TODO report error
                            break

                        # Create note entry
                        accumulated_notes.append(JDexEntry(x.name))
                        break
                else:
                    # If we got here, it matched no known child/note
                    if not getattr(tier, "allow_arbitrary_contents", False):
                        # This is an error
                        accumulated_errors.append(
                            JDexIssueArbitraryContentWhereNotAllowed(
                                PurePath(x),
                                [c.format.raw_format for c in tier.children]
                                + [n.format.raw_format for n in tier.notes],
                            ),
                        )
    return (accumulated_notes, accumulated_errors)


def lint_system(config: Config) -> LintResults:
    jdex_errors = []
    if config.system.jdex:
        (jdex_notes, jdex_errors) = _get_jdex_notes_here_or_children(
            config.linter.ignore + config.system.jdex.ignore,
            {},
            config.system.jdex.path,
            config.system.jdex,
        )
    return LintResults([], sorted(jdex_errors, key=_sort_error), [])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="jdlint",
        description="Ensure that your Johnny Decimal system is neat and clean",
    )
    parser.add_argument(
        "path",
        metavar="ROOT_PATH",
        help='The root of a JD file structure; should contain folders called e.g. "10-19 Life Admin"',
    )
    parser.add_argument(
        "--jdex",
        "--index",
        metavar="JDEX_FILES",
        help="Folder containing your JDex/index notes",
    )
    parser.add_argument(
        "-i",
        "--ignore",
        dest="ignored",
        action="append",
        metavar="IGNORED_FILE",
        default=[],
        help="A file/directory name/pattern to ignore if it is encountered",
    )
    parser.add_argument(
        "-d",
        "--disable",
        dest="disable",
        action="append",
        metavar="RULE_TO_DISABLE",
        default=[],
        help="A rule to disable by name, e.g. NONEMPTY_INBOX",
    )
    parser.add_argument(
        "-j",
        "--json",
        dest="json",
        action="store_const",
        const=True,
        help="Output as machine-readable JSON",
    )
    parser.add_argument(
        "--altzeros",
        dest="altzeros",
        action="store_const",
        const=True,
        help="Specify use of the alternative standard zeros layout; see the README for more info",
    )

    args = parser.parse_args()

    # Get all errors
    if args.jdex:
        (errors, jdex_errors) = lint_dir_and_jdex(
            path=Path(args.path),
            jdex_path=Path(args.jdex),
            ignored=args.ignored,
            alt_zeros=args.altzeros,
        )
    else:
        errors = (lint_dir(args.path, args.ignored)).errors
        jdex_errors = []

    # Filter disabled errors
    errors = [e for e in errors if e.type() not in args.disable]
    jdex_errors = [e for e in jdex_errors if e.type() not in args.disable]

    # If there were issues
    if errors or jdex_errors:
        # Dump to JSON if asked
        if args.json:
            json.dump(
                {"errors": errors, "jdex_errors": jdex_errors},
                sys.stdout,
                cls=_EnhancedJSONEncoder,
            )

        # Or print them out
        else:
            # Group errors by type and then by type details
            # Since all explanations are identical, there's no reason to print them multiple times
            jdex_errs_by_type: dict[str, dict[JDexErrorType, list[JDexError]]] = {}
            for je in jdex_errors:
                if je.error.type not in jdex_errs_by_type:
                    jdex_errs_by_type.update({je.error.type: {}})
                _insert_append(je.error, je, jdex_errs_by_type[je.error.type])

            errs_by_type: dict[str, dict[ErrorType, list[Error]]] = {}
            for e in errors:
                if e.error.type not in errs_by_type:
                    errs_by_type.update({e.error.type: {}})
                _insert_append(e.error, e, errs_by_type[e.error.type])

            # Print JDex errors if any
            if jdex_errors:
                print("JDex errors found:")
                for je_type in jdex_errs_by_type.values():
                    first_j_err = next(iter(je_type.keys()))  # Just get the first error
                    explanation = first_j_err.explain()
                    print(f"\n{explanation.explanation} ({first_j_err.type})")
                    print(
                        "\n".join(
                            [
                                "  " + e.display()
                                for jes in je_type.values()
                                for e in jes
                            ],
                        ),
                    )
                    print(explanation.fix)
                    print("\n")

            # Print file errors if any
            if errors:
                print("Errors found:")
                for e_type in errs_by_type.values():
                    first_err = next(iter(e_type.keys()))  # Just get the first error
                    explanation = first_err.explain()
                    print(f"\n{explanation.explanation} ({first_err.type})")
                    print(
                        "\n".join(
                            ["  " + e.display() for es in e_type.values() for e in es],
                        ),
                    )
                    print(explanation.fix)
                    print("\n")

        # Exit unhappily
        sys.exit(1)

    # If we're here, there were no issues
    print("Everything looks good!")

    sys.exit(0)
