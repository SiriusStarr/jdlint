#!/usr/bin/env python3

"""Script to check for common issues with a Johnny Decimal system."""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import sys
import textwrap
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

    def __init__(self, key: str, issue: str, got: str) -> None:
        """Create a value error, given the key it occurs at, the issue with the value, and the actual value."""
        super().__init__(key, f"Bad value.  Got: {got}  Issue: {issue}")


class ConfigConflictError(ConfigError):
    """A conflict in the jdlint config."""

    def __init__(self, key: str, issue: str) -> None:
        """Create a conflict error, given the key it occurs at and the issue."""
        super().__init__(key, f"Conflict in config.  Issue: {issue}")


###############################################################################
# Config
###############################################################################
def _report_extra_keys(at: str, from_file: dict, valid: tuple[str, ...]) -> None:
    # Ensure no extra fields
    for key in from_file:
        err = ConfigExtraKeyError(f"{at}.{key}", valid)
        raise err


class ConfigSystemRoot:
    """A root (base folder) of a JD system to check for correctness, e.g. ~/Documents."""

    def __init__(
        self,
        at: str,
        default_structure: list[ConfigSystemTier],
        from_file: dict,
    ) -> None:
        """Create a valid configuration given a loaded section of a config file."""
        # Acquire and set defaults
        if "name" not in from_file:
            err = ConfigMissingKeyError(f"{at}.name")
            raise err
        self.name = from_file.pop("name")
        if "path" not in from_file:
            err = ConfigMissingKeyError(f"{at}.path")
            raise err
        self.path = Path(from_file.pop("path")).expanduser()
        self.ignore = from_file.pop("ignore", [])

        if not isinstance(self.name, str):
            err = ConfigTypeError(
                f"{at}.name",
                "str",
                type(self.name).__name__,
            )
            raise err

        # Validate path is good
        if not self.path.is_dir():
            err = ConfigValueError(
                f"{at}.path",
                "Root path isn't a folder that exists!",
                str(self.path),
            )
            raise err
        if not isinstance(self.ignore, list):
            err = ConfigTypeError(
                f"{at}.ignore",
                "list",
                type(self.ignore).__name__,
            )
            raise err
        for r in self.ignore:
            if not isinstance(r, str):
                err = ConfigTypeError(f"{at}.ignore", "str", type(r).__name__)
                raise err

        # Load specialized structure, if any
        if "children" in from_file:
            self.children = [
                ConfigSystemTier(
                    f"{at}.children[{i}]",
                    ConfigFormatAncestorInfo((), ()),
                    v,
                )
                for i, v in enumerate(from_file.pop("children", []))
            ]
        elif default_structure:
            self.children = default_structure
        else:
            err = ConfigConflictError(
                f"{at}",
                "Either system.default.children must be specified or every root must specify its own children.",
            )
            raise err

        _report_extra_keys(at, from_file, tuple(self.__dict__.keys()))


class ConfigSystemJDex:
    """Valid configuration for the JDex of a system."""

    def __init__(self, at: str, from_file: dict) -> None:
        """Create a valid configuration given a loaded section of a config file."""
        # Acquire and set defaults
        if "path" not in from_file:
            err = ConfigMissingKeyError(f"{at}.path")
            raise err
        self.path = Path(from_file.pop("path")).expanduser()
        self.ignore = from_file.pop("ignore", [])

        # Validate
        if not self.path.is_dir():
            err = ConfigValueError(
                f"{at}.path",
                "JDex path isn't a folder that exists!",
                str(self.path),
            )
            raise err
        if not isinstance(self.ignore, list):
            err = ConfigTypeError(
                f"{at}.ignore",
                "list",
                type(self.ignore).__name__,
            )
            raise err
        for r in self.ignore:
            if not isinstance(r, str):
                err = ConfigTypeError(f"{at}.ignore", "str", type(r).__name__)
                raise err

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

        _report_extra_keys(at, from_file, tuple(self.__dict__.keys()))


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
            err = ConfigTypeError(
                "linter.disable_rules",
                "list",
                type(self.disable_rules).__name__,
            )
            raise err
        for r in self.disable_rules:
            if r in [e.type for e in typing.get_args(AnyIssueType)]:
                continue
            err = ConfigValueError("linter.disable_rules", "not a valid rule name", r)
            raise err

        if not isinstance(self.json_output, bool):
            err = ConfigTypeError(
                "linter.json_output",
                "bool",
                type(self.json_output).__name__,
            )
            raise err

        if not isinstance(self.ignore, list):
            err = ConfigTypeError(
                "linter.ignore",
                "list",
                type(self.ignore).__name__,
            )
            raise err
        for r in self.ignore:
            if not isinstance(r, str):
                err = ConfigTypeError("linter.ignore", "str", type(r).__name__)
                raise err

        _report_extra_keys("linter", from_file, tuple(self.__dict__.keys()))


class ConfigSystem:
    """Valid configuration for the JD system."""

    def __init__(self, from_file: dict) -> None:
        """Create a valid configuration given a loaded system section of a config file."""
        default_structure = [
            ConfigSystemTier(
                f"system.default.children[{i}]",
                ConfigFormatAncestorInfo((), ()),
                v,
            )
            for i, v in enumerate(from_file.pop("default", {}).pop("children", []))
        ]

        self.roots = [
            ConfigSystemRoot(
                f"system.roots[{i}]",
                default_structure,
                v,
            )
            for i, v in enumerate(from_file.pop("roots", []))
        ]

        accum_names = {}
        accum_paths = {}
        for root in self.roots:
            if root.name in accum_names:
                err = ConfigConflictError(
                    "system.roots",
                    f"System root names must be unique. {root.name} occurs multiple times.",
                )
                raise err
            if root.path in accum_paths:
                err = ConfigConflictError(
                    "system.roots",
                    f"System root paths must be unique. {root.path} occurs multiple times.",
                )
                raise err

        if "jdex" in from_file:
            self.jdex = ConfigSystemJDex("system.jdex", from_file.pop("jdex"))
        else:
            self.jdex = None

        _report_extra_keys("system", from_file, tuple(self.__dict__.keys()))


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


class ConfigJDexID:
    """Configuration for how a JDex ID is related to a note."""

    def __init__(
        self,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        from_file: dict,
    ) -> None:
        """Create a valid note format given a loaded section of a config file."""
        # Compile Format
        if "id" not in from_file:
            err = ConfigMissingKeyError(f"{at}.id")
            raise err
        self.id = ConfigStaticFormat(
            f"{at}.id",
            ancestors,
            from_file.pop("id"),
        )
        if "entry" not in from_file:
            err = ConfigMissingKeyError(f"{at}.entry")
            raise err
        self.entry = ConfigStaticFormat(
            f"{at}.entry",
            ancestors,
            from_file.pop("entry"),
        )

        _report_extra_keys(at, from_file, tuple(self.__dict__.keys()))


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
            err = ConfigMissingKeyError(f"{at}.format")
            raise err
        self.format = ConfigFormat(
            f"{at}",
            ancestors,
            from_file,
        )
        if "ids" not in from_file and not self.format.forbidden:
            err = ConfigMissingKeyError(f"{at}.ids")
            raise err
        self.ids = [
            ConfigJDexID(
                f"{at}.ids[{i}]",
                self.format,
                v,
            )
            for i, v in enumerate(from_file.pop("ids", []))
        ]
        if "jdex_entry" in from_file:
            self.jdex_entry = ConfigStaticFormat(
                f"{at}.jdex_entry",
                self.format,
                from_file.pop("jdex_entry"),
            )
        else:
            self.jdex_entry = None

        _report_extra_keys(at, from_file, tuple(self.__dict__.keys()))


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
            err = ConfigTypeError(
                f"{at}.allow_arbitrary_contents",
                "bool",
                type(self.allow_arbitrary_contents).__name__,
            )
            raise err

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
        if self.format.forbidden and self.children:
            raise ConfigConflictError(
                at,
                "If forbidden, children must not be specified.",
            )
        if self.format.forbidden and self.allow_arbitrary_contents:
            raise ConfigConflictError(
                at,
                "If forbidden, allow_arbitrary_contents must be false.",
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
        self.no_jdex_entry = from_file.pop("no_jdex_entry", False)

        # Call the folder tier stuff
        super().__init__(ConfigSystemTier, at, ancestors, from_file)

        if "jdex_entry" in from_file:
            self.jdex_entry = ConfigStaticFormat(
                f"{at}.jdex_entry",
                self.format,
                from_file.pop("jdex_entry"),
            )
        else:
            self.jdex_entry = None

        if "id" not in from_file:
            err = ConfigMissingKeyError(f"{at}.id")
            raise err
        self.id = ConfigStaticFormat(
            f"{at}.id",
            self.format,
            from_file.pop("id"),
        )

        if not isinstance(self.can_be_file, bool):
            err = ConfigTypeError(
                f"{at}.can_be_file",
                "bool",
                type(self.can_be_file).__name__,
            )
            raise err

        if self.children and self.can_be_file:
            err = ConfigConflictError(
                at,
                "If children are specified, can_be_file must be false.",
            )
            raise err

        if self.format.forbidden and self.can_be_file:
            err = ConfigConflictError(
                at,
                "If forbidden, can_be_file must be false.",
            )
            raise err
        if self.no_jdex_entry and self.jdex_entry:
            err = ConfigConflictError(
                at,
                "Only one of no_jdex_entry and jdex_entry may be set.",
            )
            raise err

        _report_extra_keys(at, from_file, tuple(self.__dict__.keys()))


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

        if self.notes and self.format.forbidden:
            raise ConfigConflictError(
                at,
                "If forbidden, notes cannot be speciefed.",
            )

        _report_extra_keys(at, from_file, tuple(self.__dict__.keys()))


@dataclass
class ConfigFormatAncestorInfo:
    """Information about the ancestors of a format."""

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
            err = ConfigMissingKeyError(f"{at}.format")
            raise err

        self.raw_format = from_file.pop("format")
        self.forbidden = from_file.pop("forbidden", False)

        if "name" not in from_file:
            err = ConfigMissingKeyError(f"{at}.name")
            raise err

        # Validate
        if not isinstance(from_file["name"], str):
            err = ConfigTypeError(
                f"{at}.name",
                "str",
                type(from_file["name"]).__name__,
            )
            raise err
        if not isinstance(self.raw_format, str):
            err = ConfigTypeError(
                f"{at}.format",
                "str",
                type(self.raw_format).__name__,
            )
            raise err
        if not isinstance(self.forbidden, bool):
            err = ConfigTypeError(
                f"{at}.forbidden",
                "bool",
                type(self.forbidden).__name__,
            )
            raise err

        if from_file["name"] == "":
            err = ConfigValueError(
                f"{at}.name",
                "Malformed name; must not be empty.",
                str(from_file),
            )
            raise err
        if self.raw_format.count("/") % 2 != 0:
            err = ConfigValueError(
                f"{at}.format",
                "Malformed format; there must be an even number of / characters.  You have an extra one/are missing one.",
                str(from_file),
            )
            raise err
        if self.raw_format == "":
            err = ConfigValueError(
                f"{at}.format",
                "Malformed format; must not be empty.",
                str(from_file),
            )
            raise err

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
                    err = ConfigValueError(
                        f"{at}.format",
                        "Malformed format; variable segment must consist of =, *, or one or more # followed by an alphabetic identifier.",
                        v,
                    )
                    raise err
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
                        err = ConfigValueError(
                            f"{at}.format",
                            "Malformed format; variable segment referenced an identifier never bound.",
                            v,
                        )
                        raise err
                else:
                    if match.group(2) in ancestors.segments:
                        err = ConfigValueError(
                            f"{at}.format",
                            "Malformed format; variable segment tried to rebind an identifier already bound in a parent.",
                            v,
                        )
                        raise err
                    if match.group(2) in new_segments:
                        err = ConfigValueError(
                            f"{at}.format",
                            "Malformed format; variable segment tried to rebind an identifier already bound.",
                            v,
                        )
                        raise err
                    identifier = match.group(2)
                    new_segments.append(identifier)
                    if match.group(1) == "*":
                        regex.append(
                            lambda _, identifier=identifier: f"(?P<{identifier}>.+)",
                        )
                    else:
                        # Must be a ## type variable
                        match_len = len(match.group(1))
                        regex.append(
                            lambda _, identifier=identifier, match_len=match_len: (
                                f"(?P<{identifier}>[0-9]{{{match_len}}})"
                            ),
                        )

        self.name = (*ancestors.name, from_file.pop("name"))
        self.segments = ancestors.segments + tuple(new_segments)
        self.build_regex = lambda d: "".join([f(d) for f in regex])


class Config:
    """Valid config for jdlint."""

    def __init__(self, from_file: dict) -> None:
        """Attempt to create a valid config from loaded TOML."""
        self.linter = ConfigLinter(from_file.get("linter", {}))

        if "system" not in from_file:
            err = ConfigMissingKeyError("system")
            raise err
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
        return f"{self.file!s}\n    (matched {_print_pattern(self.matched_pattern)})"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A file was found that matched the format of an expected child folder.",
            fix="Your format should not mix folders and notes that share a naming scheme.",
        )


@dataclass(frozen=True)
class IssueArbitraryContentWhereNotAllowed(Issue):
    """Content was found that didn't match any expected format."""

    possible_formats: tuple[ContentPattern, ...]
    type: Literal["ARBITRARY_CONTENT_WHERE_NOT_ALLOWED"] = (
        "ARBITRARY_CONTENT_WHERE_NOT_ALLOWED"
    )

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.file!s}\n{textwrap.indent(_print_unmatched_patterns(self.possible_formats), '  ')}"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Files or folders were found that matched no expected format.",
            fix="You should either make the content match or set allow_arbitrary_content to true if it is intended for random content to be mixed in.",
        )


@dataclass(frozen=True)
class IssueFolderShouldBeEmpty(Issue):
    """Content was found in a folder that should be empty."""

    children: tuple[PurePath, ...]
    type: Literal["FOLDER_SHOULD_BE_EMPTY"] = "FOLDER_SHOULD_BE_EMPTY"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.file!s}\n  has {len(self.children)} children"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="Files or folders were found in a folder that should be empty.",
            fix="Either the folder in question should have allow_arbitrary_content set to true, or you should remove the content.",
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
        return f"{self.file!s} [ID: {self.id}]"

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
    expected_jdex_entry: str
    known_jdex_entries: list[JDexEntry]
    type: Literal["ID_DIFFERENT_FROM_JDEX"] = "ID_DIFFERENT_FROM_JDEX"

    def display(self) -> str:
        """Display this particular instance of an error."""
        known = "\n".join(
            f"{n.entry}    [from {n.path.name}]" for n in self.known_jdex_entries
        )
        return f"{self.file!s}\n  ID: {self.id}\n  Expected:\n    {self.expected_jdex_entry}\n  Actual:\n{textwrap.indent(known, '    ')}"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An ID was found, the name of which is different from its corresponding JDex entry.",
            fix="Update the one that is incorrect.",
        )


@dataclass(frozen=True)
class IssueEncounteredForbiddenFolder(Issue):
    """A file that matched a forbidden format was found."""

    matched_pattern: ContentPattern
    type: Literal["ENCOUNTERED_FORBIDDEN_FOLDER"] = "ENCOUNTERED_FORBIDDEN_FOLDER"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.file!s}\n    (matched {_print_pattern(self.matched_pattern)})"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A file was found that matched the format of a forbidden folder.",
            fix="You should remove/rename the file in question.",
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
        return f"{self.file!s}\n    (matched {_print_pattern(self.matched_pattern)})"

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
        return f"{self.file!s}\n    (matched {_print_pattern(self.matched_pattern)})"

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
        return f"{self.file!s}\n{textwrap.indent(_print_unmatched_patterns(self.possible_formats), '  ')}"

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


@dataclass(frozen=True)
class JDexIssueEncounteredForbiddenFolder(JDexIssue):
    """A JDex file that matched a forbidden format was found."""

    matched_pattern: ContentPattern
    type: Literal["JDEX_ENCOUNTERED_FORBIDDEN_FOLDER"] = (
        "JDEX_ENCOUNTERED_FORBIDDEN_FOLDER"
    )

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.file!s}\n    (matched {_print_pattern(self.matched_pattern)})"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A JDex file was found that matched the format of a forbidden folder.",
            fix="You should remove/rename the file in question.",
        )


@dataclass(frozen=True)
class JDexIssueEncounteredForbiddenNote(JDexIssue):
    """A JDex file that matched a forbidden format was found."""

    matched_pattern: ContentPattern
    type: Literal["JDEX_ENCOUNTERED_FORBIDDEN_NOTE"] = "JDEX_ENCOUNTERED_FORBIDDEN_NOTE"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.file!s}\n    (matched {_print_pattern(self.matched_pattern)})"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A JDex file was found that matched the format of a forbidden note.",
            fix="You should remove/rename the file in question.",
        )


JDexIssueType = (
    JDexIssueArbitraryContentWhereNotAllowed
    | JDexIssueDuplicateID
    | JDexIssueEmptyFolder
    | JDexIssueFileWhereFolderExpected
    | JDexIssueFolderWhereNoteExpected
    | JDexIssueEncounteredForbiddenFolder
    | JDexIssueEncounteredForbiddenNote
)
IssueType = (
    IssueArbitraryContentWhereNotAllowed
    | IssueDuplicateID
    | IssueEmptyFolder
    | IssueFileWhereFolderExpected
    | IssueFolderShouldBeEmpty
    | IssueIDDifferentFromJDex
    | IssueIDNotInJDex
    | IssueEncounteredForbiddenFolder
)

AnyIssueType = JDexIssueType | IssueType


@dataclass(frozen=True)
class _Explanation:
    explanation: str
    fix: str


@dataclass(frozen=True)
class SystemFolder:
    """A folder detected in a JD root, including its path and its children (by ID)."""

    path: PurePath
    children: dict[str, list[SystemFolder | SystemFile]]


@dataclass(frozen=True)
class SystemFile:
    """A file detected in a JD root, consisting of its path."""

    path: PurePath


@dataclass(frozen=True)
class JDexEntry:
    """An entry in a JDex, including the path to the note that defined it."""

    entry: str
    path: PurePath


@dataclass(frozen=True)
class JDexLintResults:
    """All errors returned from linting the JDex."""

    errors: list[JDexIssue]
    path: PurePath
    entries: dict[str, list[JDexEntry]]


@dataclass(frozen=True)
class RootLintResults:
    """All errors returned from linting a system root."""

    errors: list[Issue]
    path: PurePath
    structure: dict[str, list[SystemFolder | SystemFile]]


@dataclass(frozen=True)
class LintResults:
    """All errors returned from linting files, as well as the JDex and filesystems structures."""

    jdex: None | JDexLintResults
    roots: dict[str, RootLintResults]
    ignored_errs: int


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


def _print_pattern(p: ContentPattern) -> str:
    return f"{'/'.join(p.name)}: {p.format}"


def _print_unmatched_patterns(ps: tuple[ContentPattern, ...]) -> str:
    formats = "\n".join(_print_pattern(p) for p in ps)
    return f"matched none of:\n{textwrap.indent(formats, '  ')}"


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


def _sort_jdex_entry(e: JDexEntry) -> tuple[str, PurePath]:
    return (e.entry, e.path)


def _entry_is_ignored(
    ignored: tuple[str] | None,
    f: os.DirEntry,
) -> bool:
    """Check if a given file/directory should be ignored."""
    if not ignored:
        return False
    return any(PurePath(f).match(pattern) for pattern in ignored)


E = TypeVar("E")


def _insert_append_sorted(k, v, d, key=None) -> None:  # noqa: ANN001
    """Add value as a singleton if it's not already in the dict, else append it to the list."""
    if k not in d:
        d.update({k: []})

    d[k].append(v)
    d[k].sort(key=key)


def _insert_concat_sorted(k, vs: list, d, key=None) -> None:  # noqa: ANN001
    """Add value as a singleton if it's not already in the dict, else append it to the list."""
    if k not in d:
        d.update({k: []})

    d[k].extend(vs)
    d[k].sort(key=key)


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


def _get_jdex_entries_here_or_children(
    ignored: tuple[str],
    bound_segments: dict[str, str],
    path: os.PathLike,
    relative_to: PurePath,
    tier: ConfigJDexTier | ConfigSystemJDex,
) -> tuple[dict[str, list[JDexEntry]], list[JDexIssue]]:
    # Compile regexes for children
    valid_children = [
        (re.compile(c.format.build_regex(bound_segments)), c) for c in tier.children
    ]
    valid_notes = [
        (re.compile(n.format.build_regex(bound_segments)), n) for n in tier.notes
    ]

    accumulated_entries: dict[str, list[JDexEntry]] = {}
    accumulated_errors: list[JDexIssue] = []

    has_content = False
    with os.scandir(path) as contents:
        for x in contents:
            if _entry_is_ignored(ignored, x):
                continue
            has_content = True
            for child_format, child in valid_children:
                match = child_format.fullmatch(x.name)
                if match:
                    if child.format.forbidden:
                        accumulated_errors.append(
                            JDexIssueEncounteredForbiddenFolder(
                                PurePath(x).relative_to(relative_to),
                                ContentPattern(
                                    child.format.name,
                                    child.format.raw_format,
                                ),
                            ),
                        )
                        break
                    # Is a valid child folder
                    if x.is_file():
                        # This is an error
                        accumulated_errors.append(
                            JDexIssueFileWhereFolderExpected(
                                PurePath(x).relative_to(relative_to),
                                ContentPattern(
                                    child.format.name,
                                    child.format.raw_format,
                                ),
                            ),
                        )
                        break

                    # Walk child
                    (child_entries, child_errors) = _get_jdex_entries_here_or_children(
                        ignored,
                        {**bound_segments, **match.groupdict()},
                        PurePath(x),
                        relative_to,
                        child,
                    )
                    for jid, entries in child_entries.items():
                        _insert_concat_sorted(
                            jid,
                            entries,
                            accumulated_entries,
                            key=_sort_jdex_entry,
                        )
                    accumulated_errors.extend(child_errors)
                    break
            else:
                for note_format, note in valid_notes:
                    match = note_format.fullmatch(x.name)
                    if match:
                        if note.format.forbidden:
                            accumulated_errors.append(
                                JDexIssueEncounteredForbiddenNote(
                                    PurePath(x).relative_to(relative_to),
                                    ContentPattern(
                                        note.format.name,
                                        note.format.raw_format,
                                    ),
                                ),
                            )
                            break
                        # Is a valid JDex note
                        if x.is_dir():
                            # This is an error
                            accumulated_errors.append(
                                JDexIssueFolderWhereNoteExpected(
                                    PurePath(x).relative_to(relative_to),
                                    ContentPattern(
                                        note.format.name,
                                        note.format.raw_format,
                                    ),
                                ),
                            )
                            break

                        # Create entry
                        for jid in note.ids:
                            _insert_append_sorted(
                                jid.id.build({**bound_segments, **match.groupdict()}),
                                JDexEntry(
                                    jid.entry.build(
                                        {**bound_segments, **match.groupdict()},
                                    ),
                                    PurePath(x).relative_to(relative_to),
                                ),
                                accumulated_entries,
                                key=_sort_jdex_entry,
                            )
                        break
                else:
                    # If we got here, it matched no known child/note
                    if not getattr(tier, "allow_arbitrary_contents", False):
                        # This is an error
                        accumulated_errors.append(
                            JDexIssueArbitraryContentWhereNotAllowed(
                                PurePath(x).relative_to(relative_to),
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
        accumulated_errors.append(
            JDexIssueEmptyFolder(PurePath(path).relative_to(relative_to)),
        )
    return (accumulated_entries, accumulated_errors)


def _process_jdex(
    ignored: tuple[str],
    jdex: ConfigSystemJDex,
) -> tuple[dict[str, list[JDexEntry]], list[JDexIssue]]:
    (jdex_entries_by_id, jdex_errors) = _get_jdex_entries_here_or_children(
        ignored + jdex.ignore,
        {},
        jdex.path,
        jdex.path,
        jdex,
    )

    # Check for duplicate ids
    duplicate_id_errors = [
        JDexIssueDuplicateID(
            ns[0].path,
            tuple(n.path for n in ns),
            jid,
        )
        for jid, ns in jdex_entries_by_id.items()
        if len(ns) != 1
    ]
    return (
        jdex_entries_by_id,
        jdex_errors + duplicate_id_errors,
    )


def _process_system_level_and_children(
    ignored: tuple[str],
    bound_segments: dict[str, str],
    path: os.PathLike,
    relative_to: PurePath,
    tier: ConfigSystemRoot | ConfigSystemTier,
    jdex: None | dict[str, list[JDexEntry]],
    by_id_dict: dict[str, list[tuple[str | None, PurePath]]],
) -> tuple[dict[str, list[SystemFolder | SystemFile]], list[Issue]]:
    # Compile regexes for children
    valid_children = [
        (re.compile(c.format.build_regex(bound_segments)), c) for c in tier.children
    ]

    accumulated_errors = []
    accumulated_structure = {}

    has_content = False
    children_that_should_not_be = []

    with os.scandir(path) as contents:
        for x in contents:
            if _entry_is_ignored(ignored, x):
                continue
            has_content = True
            for child_format, child in valid_children:
                match = child_format.fullmatch(x.name)
                if match:
                    if child.format.forbidden:
                        accumulated_errors.append(
                            IssueEncounteredForbiddenFolder(
                                PurePath(x).relative_to(relative_to),
                                ContentPattern(
                                    child.format.name,
                                    child.format.raw_format,
                                ),
                            ),
                        )
                        break
                    # Is a valid child folder
                    child_id = child.id.build({**bound_segments, **match.groupdict()})
                    if x.is_file():
                        if child.can_be_file:
                            _insert_append_sorted(
                                child_id,
                                SystemFile(
                                    PurePath(x).relative_to(relative_to),
                                ),
                                accumulated_structure,
                                key=lambda e: e.path,
                            )
                        else:
                            # This is an error
                            accumulated_errors.append(
                                IssueFileWhereFolderExpected(
                                    PurePath(x).relative_to(relative_to),
                                    ContentPattern(
                                        child.format.name,
                                        child.format.raw_format,
                                    ),
                                ),
                            )

                    else:
                        # Walk child
                        (child_structure, child_errors) = (
                            _process_system_level_and_children(
                                ignored,
                                {**bound_segments, **match.groupdict()},
                                PurePath(x),
                                relative_to,
                                child,
                                jdex,
                                by_id_dict,
                            )
                        )
                        _insert_append_sorted(
                            child_id,
                            SystemFolder(
                                PurePath(x).relative_to(relative_to),
                                child_structure,
                            ),
                            accumulated_structure,
                            key=lambda e: e.path,
                        )
                        accumulated_errors.extend(child_errors)
                    if not child.no_jdex_entry:
                        _insert_append_sorted(
                            child_id,
                            (
                                child.jdex_entry.build(
                                    {**bound_segments, **match.groupdict()},
                                )
                                if child.jdex_entry
                                else x.name,
                                PurePath(x).relative_to(relative_to),
                            ),
                            by_id_dict,
                            # Sort duplicates by their path, not their JDex entry
                            key=lambda e: e[1],
                        )
                    break
            else:
                # If we got here, it matched no known child/note
                if not getattr(tier, "allow_arbitrary_contents", False):
                    # If the tier has no children specified, it should be empty
                    if not tier.children:
                        children_that_should_not_be.append(
                            PurePath(x).relative_to(relative_to),
                        )
                    else:
                        accumulated_errors.append(
                            IssueArbitraryContentWhereNotAllowed(
                                PurePath(x).relative_to(relative_to),
                                tuple(
                                    ContentPattern(c.format.name, c.format.raw_format)
                                    for c in tier.children
                                ),
                            ),
                        )
    if children_that_should_not_be:
        accumulated_errors.append(
            IssueFolderShouldBeEmpty(
                PurePath(path).relative_to(relative_to),
                tuple(children_that_should_not_be),
            ),
        )
    if not has_content and (
        tier.children or getattr(tier, "allow_arbitrary_contents", False)
    ):
        # We have a fully empty folder; it shouldn't exist if it's doing nothing (unless it should be empty).
        accumulated_errors.append(
            IssueEmptyFolder(PurePath(path).relative_to(relative_to)),
        )
    return (accumulated_structure, accumulated_errors)


def _process_system_root(
    ignored: tuple[str],
    root: ConfigSystemRoot,
    jdex: None | dict[str, list[JDexEntry]],
) -> tuple[dict[str, list[SystemFolder | SystemFile]], list[Issue]]:
    by_id: dict[str, list[tuple[str | None, PurePath]]] = {}
    (root_structure, root_errors) = _process_system_level_and_children(
        ignored + root.ignore,
        {},
        root.path,
        root.path,
        root,
        jdex,
        by_id,
    )

    # Check for duplicate IDs
    duplicate_id_errors = [
        IssueDuplicateID(fs[0][1], tuple([f[1] for f in fs]), jid)
        for jid, fs in by_id.items()
        if len(fs) != 1
    ]

    # If we have a JDex, we can do some additional checks
    id_errors = []
    if jdex is not None:
        for jid, fs in by_id.items():
            if jid not in jdex:
                id_errors.append(IssueIDNotInJDex(fs[0][1], jid))
            else:
                jdex_entries = [n.entry for n in jdex[jid]]
                for expected_jdex_entry, f in fs:
                    if expected_jdex_entry and expected_jdex_entry not in jdex_entries:
                        id_errors.append(
                            IssueIDDifferentFromJDex(
                                f,
                                jid,
                                expected_jdex_entry,
                                jdex[jid],
                            ),
                        )

    return (root_structure, root_errors + duplicate_id_errors + id_errors)


def lint_system(config: Config) -> LintResults:
    """Given a valid jdlint config, lint the specified system and return results."""
    jdex_errors = []
    jdex_entries = {}
    if config.system.jdex:
        (jdex_entries, jdex_errors) = _process_jdex(
            config.linter.ignore,
            config.system.jdex,
        )
    roots = {}
    ignored_errors = 0
    for root in config.system.roots:
        (root_structure, root_errors) = _process_system_root(
            config.linter.ignore,
            root,
            jdex_entries if config.system.jdex else None,
        )
        ignored_errors += sum(
            1 for e in root_errors if e.type in config.linter.disable_rules
        )
        root_errors = [
            e for e in root_errors if e.type not in config.linter.disable_rules
        ]
        roots[root.name] = RootLintResults(
            sorted(root_errors, key=_sort_error),
            root.path,
            root_structure,
        )

    ignored_jdex_errors = sum(
        1 for e in jdex_errors if e.type in config.linter.disable_rules
    )

    return LintResults(
        JDexLintResults(
            sorted(
                [e for e in jdex_errors if e.type not in config.linter.disable_rules],
                key=_sort_jdex_error,
            ),
            config.system.jdex.path,
            jdex_entries,
        )
        if config.system.jdex
        else None,
        roots,
        ignored_errors + ignored_jdex_errors,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="jdlint",
        description="Ensure that your Johnny Decimal system is neat and clean",
    )
    parser.add_argument(
        "-c",
        "--config",
        metavar="CONFIG_FILE_PATH",
        default="./jdlint.toml",
        help="Path to jdlint config file (default ./jdlint.toml)",
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
        help="A rule to disable by name, e.g. DUPLICATE_ID",
    )
    parser.add_argument(
        "-j",
        "--json",
        dest="json",
        action="store_const",
        const=True,
        help="Override config file to output machine-readable JSON",
    )

    args = parser.parse_args()

    with Path.open(args.config, "rb") as config_file:
        config = Config(tomllib.load(config_file))

    if args.json:
        config.linter.json_output = True
    config.linter.ignore.extend(args.ignored)
    for r in args.disable:
        if r in [e.type for e in typing.get_args(AnyIssueType)]:
            continue
        err = ConfigValueError("--disable", "not a valid rule name", r)
        raise err

    config.linter.disable_rules.extend(args.disable)

    # We have a valid config; now run the linter
    results = lint_system(config)

    # Dump to JSON if asked
    if config.linter.json_output:
        json.dump(
            results,
            sys.stdout,
            cls=_EnhancedJSONEncoder,
        )

    any_errors = False

    # If there were issues
    if not config.linter.json_output:
        if results.jdex:
            jdex_errs_by_type: dict[JDexIssueType, list[JDexIssue]] = {}
            for je in results.jdex.errors if results.jdex else []:
                _insert_append_sorted(
                    je.type,
                    je,
                    jdex_errs_by_type,
                    key=_sort_jdex_error,
                )
            # Print JDex errors if any
            if jdex_errs_by_type:
                any_errors = True
                print(f"{'':=^80}\n{'JDex Errors Found':^80}\n{'':=^80}")  # noqa: T201
                for errs in jdex_errs_by_type.values():
                    first_j_err = next(iter(errs))  # Just get the first error
                    explanation = first_j_err.explain()
                    print(f"\n{explanation.explanation} ({first_j_err.type})")  # noqa: T201
                    print(  # noqa: T201
                        textwrap.indent(
                            "\n".join(
                                [e.display() for e in errs],
                            ),
                            "  ",
                        ),
                    )
                    print(explanation.fix)  # noqa: T201
                    print("\n")  # noqa: T201

        # Print file errors if any
        if any(r.errors for r in results.roots.values()):
            any_errors = True
            for location, root in results.roots.items():
                errs_by_type: dict[IssueType, list[Issue]] = {}
                if root.errors:
                    errs_by_type = {}
                    for e in root.errors:
                        _insert_append_sorted(e.type, e, errs_by_type, key=_sort_error)
                    print(f"{'':=^80}\n{location + ' Errors Found:':^80}\n{'':=^80}")  # noqa: T201
                    for errs in errs_by_type.values():
                        first_err = next(iter(errs))  # Just get the first error
                        explanation = first_err.explain()
                        print(f"\n{first_err.type:^80}\n{explanation.explanation}\n---")  # noqa: T201
                        print(  # noqa: T201
                            textwrap.indent(
                                "\n".join(
                                    [e.display() for e in errs],
                                ),
                                "  ",
                            ),
                        )
                        print(f"---\n{explanation.fix}\n")  # noqa: T201

        if results.ignored_errs:
            print(  # noqa: T201
                f"{'':=^80}\n{'Ignored Errors: ' + str(results.ignored_errs):^80}\n{'':=^80}",
            )
    if any_errors:
        # Exit unhappily
        sys.exit(1)

    if not config.linter.json_output:
        print("Everything looks good!")  # noqa: T201
    sys.exit(0)
