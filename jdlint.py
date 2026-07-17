#!/usr/bin/env python3

"""Script to check for common issues with a Johnny Decimal system."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
import typing
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import TYPE_CHECKING, Literal, TypeVar

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


class ConfigMissingKeyError(ConfigError):
    """A missing key in the jdlint config."""

    def __init__(self, key: str) -> None:
        """Create a missing key error."""
        super().__init__(
            key,
            "Required key not found.",
        )


class ConfigExtraKeyError(ConfigError):
    """An unexpected key in the jdlint config."""

    def __init__(self, key: str, valid: tuple[str, ...]) -> None:
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
        if "name" not in from_file:
            raise (ConfigMissingKeyError(f"{at}.name"))
        self.name = from_file.pop("name")
        if "path" not in from_file:
            raise (ConfigMissingKeyError(f"{at}.path"))
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
            raise ConfigExtraKeyError(f"{at}.{key}", tuple(self.__dict__.keys()))


class ConfigSystemJDex:
    """Valid configuration for the JDex of a system."""

    def __init__(self, at: str, from_file: dict) -> None:
        """Create a valid configuration given a loaded section of a config file."""
        # Acquire and set defaults
        if "path" not in from_file:
            raise (ConfigMissingKeyError(f"{at}.path"))
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
                ConfigFormatAncestorInfo((), ()),
                v,
            )
            for i, v in enumerate(from_file.pop("children", []))
        ]
        self.notes = [
            ConfigJDexNotes(
                f"{at}.notes[{i}]",
                ConfigFormatAncestorInfo((), ()),
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
            raise ConfigExtraKeyError(f"{at}.{key}", tuple(self.__dict__.keys()))


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
            if r in [e.type for e in typing.get_args(AnyIssueType)]:
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
            raise ConfigExtraKeyError(f"linter.{key}", tuple(self.__dict__.keys()))


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

        accum_names = {}
        accum_paths = {}
        for root in self.roots:
            if root.name in accum_names:
                raise ConfigConflictError(
                    "system.roots",
                    f"System root names must be unique. {root.name} occurs multiple times.",
                )
            if root.path in accum_paths:
                raise ConfigConflictError(
                    "system.roots",
                    f"System root paths must be unique. {root.path} occurs multiple times.",
                )

        if "jdex" in from_file:
            self.jdex = ConfigSystemJDex("system.jdex", from_file.pop("jdex"))
        else:
            self.jdex = None

        self.children = [
            ConfigSystemTier(
                f"system.children[{i}]",
                ConfigFormatAncestorInfo((), ()),
                v,
            )
            for i, v in enumerate(from_file.pop("children", []))
        ]

        # Ensure no extra fields
        for key in from_file:
            raise ConfigExtraKeyError(f"system.{key}", tuple(self.__dict__.keys()))


class ConfigStaticFormat:
    """Configuration for how to assign a static ID or JDex note."""

    # A valid variable segment of an ID format
    variable_static_segment_re = re.compile(r"=([A-Za-z]+)")

    def __init__(
        self,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        from_file: str,
    ) -> None:
        """Create a valid format given a string from a config file."""
        # Validate
        if not isinstance(from_file, str):
            raise ConfigTypeError(
                at,
                "str",
                type(from_file).__name__,
            )
        if from_file.count("/") % 2 != 0:
            raise ConfigValueError(
                at,
                "Malformed id/JDex note format; there must be an even number of / characters.  You have an extra one/are missing one.",
                from_file,
            )
        if from_file == "":
            raise ConfigValueError(
                at,
                "Malformed id/JDex note format; must not be empty.",
                from_file,
            )

        build = []

        for i, v in enumerate(from_file.split("/")):
            if i % 2 == 0:
                # Literal segment
                build.append(lambda _, v=v: v)
            else:
                # Variable segment
                match = ConfigStaticFormat.variable_static_segment_re.fullmatch(v)
                if not match:
                    raise ConfigValueError(
                        at,
                        "Malformed id/JDex note format; variable segment must consist of = followed by an alphabetic identifier.",
                        v,
                    )
                if match.group(1) in ancestors.segments:
                    p = match.group(1)
                    build.append(lambda d, p=p: d[p])

                else:
                    raise ConfigValueError(
                        at,
                        "Malformed id/JDex note format; variable segment referenced an identifier never bound.",
                        v,
                    )

        self.build = lambda d: "".join([f(d) for f in build])


class ConfigJDexNotes:
    """Configuration for how JDex notes are formatted."""

    def __init__(
        self,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        from_file: dict,
    ) -> None:
        """Create a valid note format given a loaded section of a config file."""
        # Compile Format
        if "format" not in from_file:
            raise (ConfigMissingKeyError(f"{at}.format"))
        self.format = ConfigFormat(
            f"{at}",
            ancestors,
            from_file,
        )
        if "ids" not in from_file:
            raise (ConfigMissingKeyError(f"{at}.ids"))
        self.ids = [
            ConfigStaticFormat(
                f"{at}.ids[{i}]",
                self.format,
                v,
            )
            for i, v in enumerate(from_file.pop("ids", []))
        ]

        # Ensure no extra fields
        for key in from_file:
            raise ConfigExtraKeyError(f"{at}.{key}", tuple(self.__dict__.keys()))


class ConfigFolderTier:
    """A tier (hierarchical level) of a JD system, e.g. a Category, whether in the JDex or the system itself."""

    def __init__(
        self,
        child_class: Callable,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        from_file: dict,
    ) -> None:
        """Create a valid tier given a loaded section of a config file."""
        # Acquire and set defaults
        self.allow_arbitrary_contents = from_file.pop("allow_arbitrary_contents", False)

        # Validate
        if not isinstance(self.allow_arbitrary_contents, bool):
            raise ConfigTypeError(
                f"{at}.allow_arbitrary_contents",
                "bool",
                type(self.allow_arbitrary_contents).__name__,
            )

        # Compile Format & Children
        self.format = ConfigFormat(
            at,
            ancestors,
            from_file,
        )
        self.children = [
            child_class(
                f"{at}.children[{i}]",
                self.format,
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

    def __init__(
        self,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        from_file: dict,
    ) -> None:
        """Create a valid tier given a loaded section of a config file."""
        # Acquire and set defaults

        self.can_be_file = from_file.pop("can_be_file", False)

        # Call the folder tier stuff
        super().__init__(ConfigSystemTier, at, ancestors, from_file)

        if "jdex_note" in from_file:
            self.jdex_note = ConfigStaticFormat(
                f"{at}.jdex_note",
                self.format,
                from_file.pop("jdex_note"),
            )
        else:
            self.jdex_note = None

        if "id" not in from_file:
            raise (ConfigMissingKeyError(f"{at}.id"))
        self.id = ConfigStaticFormat(
            f"{at}.id",
            self.format,
            from_file.pop("id"),
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
            raise ConfigExtraKeyError(f"{at}.{key}", tuple(self.__dict__.keys()))


class ConfigJDexTier(ConfigFolderTier):
    """A tier (hierarchical level) of a JD system, e.g. a Category, in the JDex."""

    def __init__(
        self,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        from_file: dict,
    ) -> None:
        """Create a valid tier given a loaded section of a config file."""
        # Call the folder tier stuff
        super().__init__(ConfigJDexTier, at, ancestors, from_file)

        self.notes = [
            ConfigJDexNotes(
                f"{at}.notes[{i}]",
                self.format,
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
            raise ConfigExtraKeyError(f"{at}.{key}", tuple(self.__dict__.keys()))


@dataclass
class ConfigFormatAncestorInfo:
    name: tuple[str, ...]
    segments: tuple[str, ...]


class ConfigFormat(ConfigFormatAncestorInfo):
    """A format for a file or folder."""

    # A valid variable segment of a format
    variable_segment_re = re.compile(r"(=|\*|[#]+)([A-Za-z]+)")

    def __init__(
        self,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        from_file: dict,
    ) -> None:
        """Create a valid format given a string from a config file."""
        if "format" not in from_file:
            raise (ConfigMissingKeyError(f"{at}.format"))

        self.raw_format = from_file.pop("format")

        if "name" not in from_file:
            raise (ConfigMissingKeyError(f"{at}.name"))

        # Validate
        if not isinstance(from_file["name"], str):
            raise ConfigTypeError(
                f"{at}.name",
                "str",
                type(from_file["name"]).__name__,
            )
        if not isinstance(self.raw_format, str):
            raise ConfigTypeError(
                f"{at}.format",
                "str",
                type(self.raw_format).__name__,
            )

        if from_file["name"] == "":
            raise ConfigValueError(
                f"{at}.name",
                "Malformed name; must not be empty.",
                from_file,
            )
        if self.raw_format.count("/") % 2 != 0:
            raise ConfigValueError(
                f"{at}.format",
                "Malformed format; there must be an even number of / characters.  You have an extra one/are missing one.",
                from_file,
            )
        if self.raw_format == "":
            raise ConfigValueError(
                f"{at}.format",
                "Malformed format; must not be empty.",
                from_file,
            )

        regex = []
        new_segments = []

        for i, v in enumerate(self.raw_format.split("/")):
            if i % 2 == 0:
                # Literal segment
                regex.append(lambda _, v=v: re.escape(v))
            else:
                # Variable segment
                match = ConfigFormat.variable_segment_re.fullmatch(v)
                if not match:
                    raise ConfigValueError(
                        f"{at}.format",
                        "Malformed format; variable segment must consist of =, *, or one or more # followed by an alphabetic identifier.",
                        v,
                    )
                if match.group(1) == "=":
                    if match.group(2) in ancestors.segments:
                        p = match.group(2)
                        regex.append(lambda d, p=p: re.escape(d[p]))
                    elif match.group(2) in new_segments:
                        identifier = match.group(2)
                        regex.append(
                            lambda _, identifier=identifier: f"(?P={identifier})",
                        )

                    else:
                        raise ConfigValueError(
                            f"{at}.format",
                            "Malformed format; variable segment referenced an identifier never bound.",
                            v,
                        )
                else:
                    if match.group(2) in ancestors.segments:
                        raise ConfigValueError(
                            f"{at}.format",
                            "Malformed format; variable segment tried to rebind an identifier already bound in a parent.",
                            v,
                        )
                    if match.group(2) in new_segments:
                        raise ConfigValueError(
                            f"{at}.format",
                            "Malformed format; variable segment tried to rebind an identifier already bound.",
                            v,
                        )
                    identifier = match.group(2)
                    new_segments.append(identifier)
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

        self.name = (*ancestors.name, from_file.pop("name"))
        self.segments = ancestors.segments + tuple(new_segments)
        self.build_regex = lambda d: "".join([f(d) for f in regex])


class Config:
    def __init__(self, from_file):
        self.linter = ConfigLinter(from_file.get("linter", {}))

        if "system" not in from_file:
            raise (ConfigMissingKeyError("system"))
        self.system = ConfigSystem(from_file["system"])


###############################################################################
# Issues
###############################################################################


@dataclass(frozen=True)
class Issue:
    """A single error detected in the system."""

    file: PurePath
    type = None

    def display(self) -> str:
        """Display this particular instance of an error."""
        raise NotImplementedError

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        raise NotImplementedError


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
class IssueEmptyFolder(Issue):
    """A folder is completely empty (and is not arbitrary content)."""

    type: Literal["EMPTY_FOLDER"] = "EMPTY_FOLDER"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.file!s}"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A folder that matched a pattern in the system has no contents.",
            fix="If this folder is unused, it shouldn't exist. Remove it or explicitly set it ignored if it must exist.",
        )


@dataclass(frozen=True)
class IssueFileWhereFolderExpected(Issue):
    """A file that matched an expected folder was found."""

    matched_pattern: ContentPattern
    type: Literal["FILE_WHERE_FOLDER_EXPECTED"] = "FILE_WHERE_FOLDER_EXPECTED"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f'{self.file!s} (matched "{self.matched_pattern}")'

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A file was found that matched the format of an expected child folder.",
            fix="Your format should not mix folders and notes that share a naming scheme.",
        )


@dataclass(frozen=True)
class IssueArbitraryContentWhereNotAllowed(Issue):
    """Content was found in the that didn't match any expected format."""

    possible_formats: tuple[ContentPattern, ...]
    type: Literal["ARBITRARY_CONTENT_WHERE_NOT_ALLOWED"] = (
        "ARBITRARY_CONTENT_WHERE_NOT_ALLOWED"
    )

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f'{self.file!s} (matched none of "{self.possible_formats}")'

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Files or folders were found that matched no expected format.",
            fix="You should either make the content match or set allow_arbitrary_content to true if it is intended for random content to be mixed in.",
        )


@dataclass(frozen=True)
class IssueDuplicateID(Issue):
    """An ID that has been used multiple times."""

    files: tuple[PurePath, ...]
    id: str
    type: Literal["DUPLICATE_ID"] = "DUPLICATE_ID"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.id}:\n    " + "\n    ".join([str(f.name) for f in self.files])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Duplicate IDs were used.",
            fix="Assign a new ID to one of them.",
        )


@dataclass(frozen=True)
class IssueIDNotInJDex(Issue):
    """An ID without a corresponding JDex entry."""

    id: str
    type: Literal["ID_NOT_IN_JDEX"] = "ID_NOT_IN_JDEX"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.file} [ID: {self.id}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An ID was found in files that is missing from the JDex.",
            fix="Go add a corresponding entry to your JDex.",
        )


@dataclass(frozen=True)
class IssueIDDifferentFromJDex(Issue):
    """An ID with a differently-named JDex entry."""

    id: str
    expected_jdex_note: str
    known_jdex_notes: list[PurePath]
    type: Literal["ID_DIFFERENT_FROM_JDEX"] = "ID_DIFFERENT_FROM_JDEX"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.id}: {self.file} [Expected JDex: {self.expected_jdex_note}i; actual JDex: {self.known_jdex_notes}]"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An ID was found, the name of which is different from its corresponding JDex entry.",
            fix="Update the one that is incorrect.",
        )


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


@dataclass(frozen=True)
class File:
    """A file or folder that has been detected by jdlint."""

    name: Path
    path: Path


@dataclass(frozen=True)
class JDexIssueDuplicateID(JDexIssue):
    """A JDex ID that has been used multiple times."""

    files: tuple[PurePath, ...]
    id: str
    type: Literal["JDEX_DUPLICATE_ID"] = "JDEX_DUPLICATE_ID"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.id}:\n    " + "\n    ".join([str(f.name) for f in self.files])

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Duplicate IDs were used in the JDex.",
            fix="Assign a new ID to one of them.",
        )


@dataclass(frozen=True)
class JDexIssueFileWhereFolderExpected(JDexIssue):
    """A JDex file that matched an expected folder was found."""

    matched_pattern: ContentPattern
    type: Literal["JDEX_FILE_WHERE_FOLDER_EXPECTED"] = "JDEX_FILE_WHERE_FOLDER_EXPECTED"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f'{self.file!s} (matched "{self.matched_pattern}")'

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A JDex file was found that matched the format of an expected child folder.",
            fix="Your JDex format should not mix folders and notes that share a naming scheme.",
        )


@dataclass(frozen=True)
class JDexIssueFolderWhereNoteExpected(JDexIssue):
    """A JDex folder that matched an expected note was found."""

    matched_pattern: ContentPattern
    type: Literal["JDEX_FOLDER_WHERE_NOTE_EXPECTED"] = "JDEX_FOLDER_WHERE_NOTE_EXPECTED"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f'{self.file!s} (matched "{self.matched_pattern}")'

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A JDex folder was found that matched the format of an expected note.",
            fix="Your JDex format should not mix folders and notes that share a naming scheme.",
        )


@dataclass(frozen=True)
class ContentPattern:
    """A possible pattern that could be matched."""

    name: tuple[str, ...]
    format: str


@dataclass(frozen=True)
class JDexIssueArbitraryContentWhereNotAllowed(JDexIssue):
    """Content was found in the JDex that didn't match any expected format."""

    possible_formats: tuple[ContentPattern, ...]
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
class JDexIssueEmptyFolder(JDexIssue):
    """A folder in the JDex is completely empty (and is not arbitrary content)."""

    type: Literal["JDEX_EMPTY_FOLDER"] = "JDEX_EMPTY_FOLDER"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.file!s}"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A folder that matched a pattern in the JDex has no contents.",
            fix="You should ensure that all JDex notes exist; if this folder truly contains no IDs, it shouldn't exist.",
        )


JDexIssueType = (
    JDexIssueArbitraryContentWhereNotAllowed
    | JDexIssueDuplicateID
    | JDexIssueEmptyFolder
    | JDexIssueFileWhereFolderExpected
    | JDexIssueFolderWhereNoteExpected
)
IssueType = (
    IssueArbitraryContentWhereNotAllowed
    | IssueDuplicateID
    | IssueEmptyFolder
    | IssueFileWhereFolderExpected
)

AnyIssueType = JDexIssueType | IssueType


@dataclass(frozen=True)
class _Explanation:
    explanation: str
    fix: str


@dataclass(frozen=True)
class SystemFolder:
    """A folder detected in a JD root, including its path and its children (by ID)"""

    path: PurePath
    children: dict[str, list[SystemFolder]]


@dataclass(frozen=True)
class LintResults:
    """All errors returned from linting files, as well as the JDex and filesystems structures."""

    errors: dict[str, list[Issue]]
    jdex_errors: list[JDexIssue]
    jdex: dict[str, list[PurePath]]
    structure: dict[str, dict[str, list[SystemFolder]]]


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


def _sort_jdex_error(e: JDexIssue) -> tuple[str, tuple[tuple[str, ...], str]]:
    # Sort errors alphabetically by type, then by file affected
    # This is split from _sort_error for type-checking nonsense
    if e.type is None:
        raise NotImplementedError
    return (
        e.type,
        (e.file.parent.parts, e.file.name),
    )


def _sort_error(e: Issue) -> tuple[str, tuple[tuple[str, ...], str]]:
    # Sort errors alphabetically by type, then by file affected
    # This is split from _sort_jdex_error for type-checking nonsense
    if e.type is None:
        raise NotImplementedError
    return (
        e.type,
        (e.file.parent.parts, e.file.name),
    )


def _entry_is_ignored(
    ignored: tuple[str] | None,
    nested_under: list[str],
    f: os.DirEntry,
) -> bool:
    """Check if a given file/directory should be ignored."""
    # TODO this is now wrong with the nested under shit and needs fixing
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


def _insert_concat(k, vs: list, d) -> None:  # noqa: ANN001
    """Add value as a singleton if it's not already in the dict, else append it to the list."""
    if k not in d:
        d.update({k: []})

    d[k].extend(vs)


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


def _get_jdex_notes_here_or_children(
    ignored: tuple[str],
    bound_segments: dict[str, str],
    path: os.PathLike,
    tier: ConfigJDexTier | ConfigSystemJDex,
) -> tuple[dict[str, list[PurePath]], list[JDexIssue]]:
    # Compile regexes for children
    valid_children = [
        (re.compile(c.format.build_regex(bound_segments)), c) for c in tier.children
    ]
    valid_notes = [
        (re.compile(n.format.build_regex(bound_segments)), n) for n in tier.notes
    ]

    accumulated_notes = {}
    accumulated_errors = []

    has_content = False
    with os.scandir(path) as contents:
        for x in contents:
            if _entry_is_ignored(ignored, [], x):
                continue
            has_content = True
            for child_format, child in valid_children:
                match = child_format.fullmatch(x.name)
                if match:
                    # Is a valid child folder
                    if x.is_file():
                        # This is an error
                        accumulated_errors.append(
                            JDexIssueFileWhereFolderExpected(
                                PurePath(x),
                                ContentPattern(
                                    child.format.name,
                                    child.format.raw_format,
                                ),
                            ),
                        )
                        break

                    # Walk child
                    (child_notes, child_errors) = _get_jdex_notes_here_or_children(
                        ignored,
                        {**bound_segments, **match.groupdict()},
                        PurePath(x),
                        child,
                    )
                    for id, notes in child_notes.items():
                        _insert_concat(id, notes, accumulated_notes)
                    accumulated_errors.extend(child_errors)
                    break
            else:
                for note_format, note in valid_notes:
                    match = note_format.fullmatch(x.name)
                    if match:
                        # Is a valid JDex note
                        if x.is_dir():
                            # This is an error
                            accumulated_errors.append(
                                JDexIssueFolderWhereNoteExpected(
                                    PurePath(x),
                                    ContentPattern(
                                        note.format.name,
                                        note.format.raw_format,
                                    ),
                                ),
                            )
                            break

                        # Create note entry
                        for id in note.ids:
                            _insert_append(
                                id.build({**bound_segments, **match.groupdict()}),
                                PurePath(x),
                                accumulated_notes,
                            )
                        break
                else:
                    # If we got here, it matched no known child/note
                    if not getattr(tier, "allow_arbitrary_contents", False):
                        # This is an error
                        accumulated_errors.append(
                            JDexIssueArbitraryContentWhereNotAllowed(
                                PurePath(x),
                                tuple(
                                    ContentPattern(c.format.name, c.format.raw_format)
                                    for c in tier.children
                                )
                                + tuple(
                                    ContentPattern(n.format.name, n.format.raw_format)
                                    for n in tier.notes
                                ),
                            ),
                        )
    if not has_content:
        # We have a fully empty JDex folder; it shouldn't exist if it's doing nothing.
        accumulated_errors.append(JDexIssueEmptyFolder(PurePath(path)))
    return (accumulated_notes, accumulated_errors)


def _process_jdex(
    ignored: tuple[str],
    jdex: ConfigSystemJDex,
) -> tuple[dict[str, list[PurePath]], list[JDexIssue]]:
    (jdex_notes_by_id, jdex_errors) = _get_jdex_notes_here_or_children(
        ignored + jdex.ignore,
        {},
        jdex.path,
        jdex,
    )

    # Check for duplicate ids
    duplicate_id_errors = [
        JDexIssueDuplicateID(ns[0], tuple(ns), id)
        for id, ns in jdex_notes_by_id.items()
        if len(ns) != 1
    ]
    return (
        jdex_notes_by_id,
        jdex_errors + duplicate_id_errors,
    )


def _process_system_level_and_children(
    ignored: tuple[str],
    bound_segments: dict[str, str],
    path: os.PathLike,
    tier: ConfigSystem | ConfigSystemTier,
    jdex: None | dict[str, list[PurePath]],
    by_id_dict: dict[str, list[tuple[str | None, PurePath]]],
) -> tuple[dict[str, list[SystemFolder]], list[Issue]]:
    # Compile regexes for children
    valid_children = [
        (re.compile(c.format.build_regex(bound_segments)), c) for c in tier.children
    ]

    accumulated_errors = []
    accumulated_structure = {}

    has_content = False
    with os.scandir(path) as contents:
        for x in contents:
            if _entry_is_ignored(ignored, [], x):
                continue
            has_content = True
            for child_format, child in valid_children:
                match = child_format.fullmatch(x.name)
                if match:
                    # Is a valid child folder
                    if x.is_file():
                        # This is an error
                        accumulated_errors.append(
                            IssueFileWhereFolderExpected(
                                PurePath(x),
                                ContentPattern(
                                    child.format.name,
                                    child.format.raw_format,
                                ),
                            ),
                        )
                        break

                    # Walk child
                    (child_structure, child_errors) = (
                        _process_system_level_and_children(
                            ignored,
                            {**bound_segments, **match.groupdict()},
                            PurePath(x),
                            child,
                            jdex,
                            by_id_dict,
                        )
                    )

                    child_id = child.id.build({**bound_segments, **match.groupdict()})
                    _insert_append(
                        child_id,
                        SystemFolder(PurePath(x), child_structure),
                        accumulated_structure,
                    )
                    _insert_append(
                        child_id,
                        (
                            child.jdex_note.build(
                                {**bound_segments, **match.groupdict()}
                            )
                            if child.jdex_note
                            else None,
                            PurePath(x),
                        ),
                        by_id_dict,
                    )
                    accumulated_errors.extend(child_errors)
                    break
            else:
                # If we got here, it matched no known child/note
                if not getattr(tier, "allow_arbitrary_contents", False):
                    # This is an error
                    accumulated_errors.append(
                        IssueArbitraryContentWhereNotAllowed(
                            PurePath(x),
                            tuple(
                                ContentPattern(c.format.name, c.format.raw_format)
                                for c in tier.children
                            ),
                        ),
                    )
    if not has_content:
        # We have a fully empty folder; it shouldn't exist if it's doing nothing.
        accumulated_errors.append(IssueEmptyFolder(PurePath(path)))
    return (accumulated_structure, accumulated_errors)


def _process_system_root(
    ignored: tuple[str],
    root: ConfigSystemRoot,
    system: ConfigSystem,
    jdex: None | dict[str, list[PurePath]],
) -> tuple[dict[str, list[SystemFolder]], list[Issue]]:
    by_id: dict[str, list[tuple[str | None, PurePath]]] = {}
    (root_structure, root_errors) = _process_system_level_and_children(
        ignored + root.ignore, {}, root.path, system, jdex, by_id
    )

    # Check for duplicate IDs
    duplicate_id_errors = [
        IssueDuplicateID(fs[0][1], tuple([f[1] for f in fs]), id)
        for id, fs in by_id.items()
        if len(fs) != 1
    ]

    # If we have a JDex, we can do some additional checks
    id_errors = []
    if jdex is not None:
        for id, fs in by_id.items():
            if id not in jdex:
                id_errors.append(IssueIDNotInJDex(fs[0][1], id))
            else:
                jdex_notes = [n.name for n in jdex[id]]
                for expected_jdex_note, f in fs:
                    if expected_jdex_note and expected_jdex_note not in jdex_notes:
                        id_errors.append(
                            IssueIDDifferentFromJDex(
                                f, id, expected_jdex_note, jdex[id]
                            )
                        )

    return (root_structure, root_errors + duplicate_id_errors + id_errors)


def lint_system(config: Config) -> LintResults:
    jdex_errors = []
    jdex_notes = {}
    if config.system.jdex:
        (jdex_notes, jdex_errors) = _process_jdex(
            config.linter.ignore,
            config.system.jdex,
        )
    errors = {}
    structure = {}
    for root in config.system.roots:
        (root_structure, root_errors) = _process_system_root(
            config.linter.ignore,
            root,
            config.system,
            jdex_notes if config.system.jdex else None,
        )
        if root_errors:
            errors[root.name] = sorted(root_errors, key=_sort_error)
        structure[root.name] = root_structure

    return LintResults(
        errors,
        sorted(jdex_errors, key=_sort_jdex_error),
        jdex_notes,
        structure,
    )


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
