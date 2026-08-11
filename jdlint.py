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


def _pop_nonempty_str_attribute(at: str, attr: str, from_file: dict) -> str:
    """Given a parent location, a mandatory attribute to get, and data, return it."""
    if attr not in from_file:
        err = ConfigMissingKeyError(f"{at}.{attr}")
        raise err
    val = from_file.pop(attr)
    if not isinstance(val, str):
        err = ConfigTypeError(
            f"{at}.{attr}",
            "str",
            type(val).__name__,
        )
        raise err
    if val == "":
        err = ConfigValueError(
            f"{at}.{attr}",
            "Must not be empty.",
            val,
        )
        raise err
    return val


def _pop_default_false_bool(at: str, attr: str, from_file: dict) -> bool:
    """Get a boolean at the specified attribute, defaulting to false, or fail."""
    val = from_file.pop(attr, False)
    if not isinstance(val, bool):
        err = ConfigTypeError(
            f"{at}.{attr}",
            "bool",
            type(val).__name__,
        )
        raise err
    return val


def _pop_list(
    at: str,
    attr: str,
    from_file: dict,
    *,
    default_empty: bool = True,
) -> list:
    """Get a list at the specified attribute, defaulting to [], or fail."""
    if not default_empty and attr not in from_file:
        err = ConfigMissingKeyError(f"{at}.{attr}")
        raise err
    val = from_file.pop(attr, [])
    if not isinstance(val, list):
        err = ConfigTypeError(
            f"{at}.{attr}",
            "list",
            type(val).__name__,
        )
        raise err
    return val


def _pop_list_of_strings(
    at: str,
    attr: str,
    from_file: dict,
    *,
    default_empty: bool = True,
) -> list[str]:
    """Get a list of strings at .ignore or fail, defaulting to []."""
    val = _pop_list(at, attr, from_file, default_empty=default_empty)
    for i, r in enumerate(val):
        if not isinstance(r, str):
            err = ConfigTypeError(f"{at}.{attr}[{i}]", "str", type(r).__name__)
            raise err
    return val


class ConfigSystemRoot:
    """A root of a JD system to check for correctness, e.g. ~/Documents."""

    def __init__(
        self,
        at: str,
        default_structure: list[ConfigSystemTier],
        from_file: dict,
    ) -> None:
        """Create a valid configuration given a loaded section of a config file."""
        self.name = _pop_nonempty_str_attribute(at, "name", from_file)
        self.path = Path(
            _pop_nonempty_str_attribute(at, "path", from_file),
        ).expanduser()
        self.ignore = _pop_list_of_strings(at, "ignore", from_file)

        # Validate path is good
        if not self.path.is_dir():
            err = ConfigValueError(
                f"{at}.path",
                "Root path isn't a folder that exists!",
                str(self.path),
            )
            raise err

        # Load specialized structure, if any
        if "children" in from_file:
            self.children = [
                ConfigSystemTier(
                    f"{at}.children[{i}]",
                    ConfigFormatAncestorInfo((), ()),
                    v,
                )
                for i, v in enumerate(
                    _pop_list(at, "children", from_file),
                )
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
        self.path = Path(
            _pop_nonempty_str_attribute(at, "path", from_file),
        ).expanduser()
        self.ignore = _pop_list_of_strings(at, "ignore", from_file)

        self.children = [
            ConfigJDexTier(
                f"{at}.children[{i}]",
                ConfigFormatAncestorInfo((), ()),
                v,
            )
            for i, v in enumerate(_pop_list(at, "children", from_file))
        ]
        self.notes = [
            ConfigJDexNotes(
                f"{at}.notes[{i}]",
                ConfigFormatAncestorInfo((), ()),
                v,
            )
            for i, v in enumerate(_pop_list(at, "notes", from_file))
        ]

        # Validate path
        if not self.path.is_dir():
            if not self.path.is_file():
                # Something's weird
                err = ConfigValueError(
                    f"{at}.path",
                    "JDex path isn't a folder or file that exists!",
                    str(self.path),
                )
                raise err

            # We have a file-based JDex; that's fine
            if self.children or self.notes or self.ignore:
                err = ConfigConflictError(
                    at,
                    "Single file JDexes must not specify children or notes or ignore!",
                )
                raise err
            # Load format
            self.entry = ConfigStaticFormat(
                f"{at}.entry",
                # This is the default info made available to a file JDex
                ConfigFormatAncestorInfo(("Single File JDex",), ("id", "title")),
                _pop_nonempty_str_attribute(at, "entry", from_file),
            )
        _report_extra_keys(at, from_file, tuple(self.__dict__.keys()))


class ConfigLinter:
    """Valid configuration for the linter."""

    def __init__(self, from_file: dict) -> None:
        """Create a valid configuration given a loaded linter section of a config file."""
        # Acquire and set defaults
        self.disable_rules = _pop_list(
            "linter",
            "disable_rules",
            from_file,
        )
        self.json_output = _pop_default_false_bool("linter", "json_output", from_file)
        self.ignore = _pop_list_of_strings("linter", "ignore", from_file)

        # Validate
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
            for i, v in enumerate(
                _pop_list(
                    "system.default",
                    "children",
                    from_file.pop("default", {}),
                ),
            )
        ]

        self.roots = [
            ConfigSystemRoot(
                f"system.roots[{i}]",
                default_structure,
                v,
            )
            for i, v in enumerate(_pop_list("system", "roots", from_file))
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
        if from_file.count("/") % 2 != 0:
            raise ConfigValueError(
                at,
                "Malformed format; there must be an even number of / characters. You have an extra/are missing one.",
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
                        "Malformed format; variable segment must consist of = followed by an alphabetic identifier.",
                        v,
                    )
                if match.group(1) in ancestors.segments:
                    p = match.group(1)
                    build.append(lambda d, p=p: d[p])

                else:
                    raise ConfigValueError(
                        at,
                        "Malformed format; variable segment referenced an identifier never bound.",
                        v,
                    )

        self.build = lambda d: "".join([f(d) for f in build])


class ConfigID:
    """Configuration for how a file, folder, or JDex note is related to an ID."""

    def __init__(
        self,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        from_file: dict,
        *,
        supports_parent: bool,
    ) -> None:
        """Create a valid ID given a loaded section of a config file."""
        self.id = ConfigStaticFormat(
            f"{at}.id",
            ancestors,
            _pop_nonempty_str_attribute(at, "id", from_file),
        )
        if supports_parent:
            try:
                self.parent = ConfigStaticFormat(
                    f"{at}.parent",
                    ancestors,
                    _pop_nonempty_str_attribute(at, "parent", from_file),
                )
            except ConfigMissingKeyError:
                self.parent = None

        try:
            self.entry = ConfigStaticFormat(
                f"{at}.entry",
                ancestors,
                _pop_nonempty_str_attribute(at, "entry", from_file),
            )
        except ConfigMissingKeyError:
            self.entry = None

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
            ConfigID(f"{at}.ids[{i}]", self.format, v, supports_parent=True)
            for i, v in enumerate(_pop_list(at, "ids", from_file))
        ]

        _report_extra_keys(at, from_file, tuple(self.__dict__.keys()))


class ConfigFolderTier:
    """A tier of a JD system, e.g. a Category, whether in the JDex or the system itself."""

    def __init__(
        self,
        child_class: Callable,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        from_file: dict,
    ) -> None:
        """Create a valid tier given a loaded section of a config file."""
        # Acquire and set defaults
        self.allow_arbitrary_contents = _pop_default_false_bool(
            at,
            "allow_arbitrary_contents",
            from_file,
        )

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
            for i, v in enumerate(_pop_list(at, "children", from_file))
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
    """A tier of a JD system, e.g. a Category, in the system (not the JDex)."""

    def __init__(
        self,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        from_file: dict,
    ) -> None:
        """Create a valid tier given a loaded section of a config file."""
        # Acquire and set defaults

        self.can_be_file = _pop_default_false_bool(at, "can_be_file", from_file)
        self.no_jdex_entry = _pop_default_false_bool(at, "no_jdex_entry", from_file)

        # Call the folder tier stuff
        super().__init__(ConfigSystemTier, at, ancestors, from_file)

        self.id = ConfigID(at, self.format, from_file, supports_parent=False)

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
        if self.no_jdex_entry and self.id.entry:
            err = ConfigConflictError(
                at,
                "Only one of no_jdex_entry and entry may be set.",
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
            for i, v in enumerate(_pop_list(at, "notes", from_file))
        ]

        if self.notes and self.format.forbidden:
            raise ConfigConflictError(
                at,
                "If forbidden, notes cannot be specified.",
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
        name = _pop_nonempty_str_attribute(at, "name", from_file)
        self.raw_format = _pop_nonempty_str_attribute(at, "format", from_file)
        self.forbidden = _pop_default_false_bool(at, "forbidden", from_file)

        # Validate
        if self.raw_format.count("/") % 2 != 0:
            err = ConfigValueError(
                f"{at}.format",
                "Malformed format; there must be an even number of / characters.  You have an extra one/are missing one.",
                str(from_file),
            )
            raise err

        regex = []
        new_segments = []

        for i, v in enumerate(self.raw_format.split("/")):
            if i % 2 == 0:
                # Literal segment
                regex.append(lambda _, v=v: re.escape(v))
                continue
            # Variable segment
            match = ConfigFormat.variable_segment_re.fullmatch(v)
            if not match:
                err = ConfigValueError(
                    f"{at}.format",
                    "Malformed format; variable segment must consist of =, *, or one or more # followed by an alphabetic identifier.",
                    v,
                )
                raise err
            segment_type = match.group(1)
            identifier = match.group(2)
            if segment_type == "=":
                if identifier in ancestors.segments:
                    p = identifier
                    regex.append(lambda d, p=p: re.escape(d[p]))
                elif identifier in new_segments:
                    regex.append(
                        lambda _, identifier=identifier: f"(?P={identifier})",
                    )

                else:
                    err = ConfigValueError(
                        f"{at}.format",
                        f'Malformed format; variable segment referenced the identifier "{identifier}" which has not been bound.',
                        v,
                    )
                    raise err
            else:
                if identifier in ancestors.segments:
                    err = ConfigValueError(
                        f"{at}.format",
                        f'Malformed format; variable segment tried to rebind the identifier "{identifier}", which was already bound in a parent.',
                        v,
                    )
                    raise err
                if identifier in new_segments:
                    err = ConfigValueError(
                        f"{at}.format",
                        f'Malformed format; variable segment tried to rebind the identifier "{identifier}", which was already bound in this format.',
                        v,
                    )
                    raise err
                new_segments.append(identifier)
                if segment_type == "*":
                    regex.append(
                        lambda _, identifier=identifier: f"(?P<{identifier}>.+?)",
                    )
                else:
                    # Must be a ## type variable
                    match_len = len(segment_type)
                    regex.append(
                        lambda _, identifier=identifier, match_len=match_len: (
                            f"(?P<{identifier}>[0-9]{{{match_len}}})"
                        ),
                    )

        self.name = (*ancestors.name, name)
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
    type = ""

    def display(self) -> str:
        """Display this particular instance of an error."""
        raise NotImplementedError

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        raise NotImplementedError


@dataclass(frozen=True)
class JDexIssue:
    """A single error detected in the JDex."""

    file: PurePath | None
    type = ""

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
        return f"{self.file!s}\n  matched: {_print_pattern(self.matched_pattern)})"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A file was found that matched the format of an expected child folder.",
            fix="Your format should not mix folders and files that share a naming scheme.",
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
        return f"{self.file!s}\n  has {_pluralize(len(self.children), 'child', 'children')}"

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
        return f"{self.id}:\n    " + "\n    ".join([str(f) for f in self.files])

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
        return f"{self.id}:\n  {self.file!s}"

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
    known_jdex_entries: list[CollectedJDexEntry]
    type: Literal["ID_DIFFERENT_FROM_JDEX"] = "ID_DIFFERENT_FROM_JDEX"

    def display(self) -> str:
        """Display this particular instance of an error."""
        known = "\n".join(
            f"{n.entry}  [from {n.path}]" for n in self.known_jdex_entries
        )
        return f"{self.id}:\n  Folder: {self.file!s}\n  Expected JDex: {self.expected_jdex_entry}\n  Actual JDex:\n{textwrap.indent(known, '    ')}"

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
        return f"{self.file!s}\n  matched: {_print_pattern(self.matched_pattern)})"

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
class JDexIssueInvalidID(JDexIssue):
    """An ID that does not conform to the index spec in a single file JDex."""

    id: str
    entry: str
    entry_type: str
    type: Literal["JDEX_INVALID_ID"] = "JDEX_INVALID_ID"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.id}: {self.entry} is not a valid {self.entry_type} ID"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An index entry in a single file JDex had an ID that wasn't standards compliant.",
            fix='Systems should be like "A01", areas like "10-19", categories like "12", and IDs like "12.34"',
        )


@dataclass(frozen=True)
class JDexIssueOrphan(JDexIssue):
    """An ID in the JDex whose specified parent does not exist."""

    id: str
    entry: str
    parent: str
    type: Literal["JDEX_ORPHAN"] = "JDEX_ORPHAN"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.id}: {self.entry} expected a parent with ID {self.parent} to exist, but none does."

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation='IDs cannot exist "under" IDs that don\'t exist; an ID 11.12 requires a category 11 and an area 10-19.',
            fix="Add any missing categories/areas, or ensure the specified parent is correct.",
        )


@dataclass(frozen=True)
class JDexIssueAmbiguousAncestry(JDexIssue):
    """An ID in the JDex occurred multiple times with different parents."""

    id: str
    entries: list[CollectedJDexEntry]
    type: Literal["JDEX_AMBIGUOUS_ANCESTRY"] = "JDEX_AMBIGUOUS_ANCESTRY"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.id}:\n    " + "\n    ".join(
            [f"Parent {f.parent}:  {f.path}" for f in self.entries],
        )

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="An ID must have exactly one parent, e.g. a work package cannot relate to both ~12.34 and ~12.35",
            fix="This usually occurs due to an accidental duplicate ID. Fix the erroneous entry.",
        )


@dataclass(frozen=True)
class JDexIssueAncestryCycle(JDexIssue):
    """IDs in the JDex had cyclical inheritance."""

    entries: dict[str, list[CollectedJDexEntry]]
    type: Literal["JDEX_ANCESTRY_CYCLE"] = "JDEX_ANCESTRY_CYCLE"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return "Cycle:\n    " + "\n    ".join(
            [
                f"{jid} with parent {es[0].parent}:  {', '.join([str(entry.path) for entry in es])}"
                for jid, es in self.entries.items()
            ],
        )

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="ID's must not have circular inheritance, e.g. two work packages cannot relate to each other. An ID cannot be its own parent.",
            fix="Fix the parentage of the IDs in question to break the cycle.",
        )


@dataclass(frozen=True)
class JDexIssueDuplicateID(JDexIssue):
    """A JDex ID that has been used multiple times."""

    files: tuple[PurePath | None, ...]
    id: str
    type: Literal["JDEX_DUPLICATE_ID"] = "JDEX_DUPLICATE_ID"

    def display(self) -> str:
        """Display this particular instance of an error."""
        return f"{self.id}:\n    " + "\n    ".join([str(f) for f in self.files])

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
        return f"{self.file!s}\n  matched: {_print_pattern(self.matched_pattern)})"

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
        return f"{self.file!s}\n  matched: {_print_pattern(self.matched_pattern)})"

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
        return f"{self.file!s}\n  matched: {_print_pattern(self.matched_pattern)})"

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
        return f"{self.file!s}\n  matched: {_print_pattern(self.matched_pattern)})"

    def explain(self) -> _Explanation:
        """Explain what this error is."""
        return _Explanation(
            explanation="A JDex file was found that matched the format of a forbidden note.",
            fix="You should remove/rename the file in question.",
        )


JDexIssueType = (
    JDexIssueAmbiguousAncestry
    | JDexIssueAncestryCycle
    | JDexIssueArbitraryContentWhereNotAllowed
    | JDexIssueDuplicateID
    | JDexIssueEmptyFolder
    | JDexIssueEncounteredForbiddenFolder
    | JDexIssueEncounteredForbiddenNote
    | JDexIssueFileWhereFolderExpected
    | JDexIssueFolderWhereNoteExpected
    | JDexIssueInvalidID
    | JDexIssueOrphan
)
IssueType = (
    IssueArbitraryContentWhereNotAllowed
    | IssueDuplicateID
    | IssueEmptyFolder
    | IssueEncounteredForbiddenFolder
    | IssueFileWhereFolderExpected
    | IssueFolderShouldBeEmpty
    | IssueIDDifferentFromJDex
    | IssueIDNotInJDex
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
class _CollectedSystemEntry:
    """A file/folder collected by the lint, prior to processing."""

    expected_jdex_entry: str | None
    path: PurePath


@dataclass(frozen=True)
class JDexEntry:
    """An entry in a JDex, including the path to the note that defined it."""

    entry: str
    path: PurePath | None


@dataclass(frozen=True)
class CollectedJDexEntry:
    """An entry in a JDex collected by the lint, prior to processing."""

    entry: str
    parent: str | None
    path: PurePath | None


_CollectedJDex = dict[str, list[CollectedJDexEntry]]


@dataclass
class JDexIDEntry:
    """An ID in a JDex, including any entries that defined it and any children nested under it."""

    entries: list[JDexEntry]
    children: dict[str, JDexIDEntry]


@dataclass(frozen=True)
class JDexLintResults:
    """All errors returned from linting the JDex."""

    errors: list[JDexIssue]
    path: PurePath
    entries: dict[str, JDexIDEntry]


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


def _sort_jdex_error(e: JDexIssue) -> tuple[str, tuple[tuple[str, ...], str], str]:
    # Sort errors alphabetically by type, then by file affected, then by ID, if it exists
    # This is split from _sort_error for type-checking nonsense
    if e.type == "":
        raise NotImplementedError
    return (
        e.type,
        (e.file.parent.parts, e.file.name) if e.file else ((), ""),
        getattr(e, "id", ""),
    )


def _sort_error(e: Issue) -> tuple[str, tuple[tuple[str, ...], str]]:
    # Sort errors alphabetically by type, then by file affected
    # This is split from _sort_jdex_error for type-checking nonsense
    if e.type == "":
        raise NotImplementedError
    return (
        e.type,
        (e.file.parent.parts, e.file.name),
    )


def _sort_jdex_entry(e: CollectedJDexEntry | JDexEntry) -> tuple[str, PurePath]:
    return (e.entry, e.path or PurePath())


def _entry_is_ignored(
    ignored: list[str] | None,
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


def _get_jdex_entries_from_json(
    jdex: ConfigSystemJDex,
    json: dict,
) -> tuple[_CollectedJDex, list[JDexIssue]]:
    accumulated_entries: list[tuple[tuple[str | None | Literal[-1], str], str]] = []
    accumulated_errors: list[JDexIssue] = []
    system_regex = re.compile("[A-Z][0-9][0-9]")
    area_regex = re.compile("(?P<A>[0-9])0-(?P=A)9")
    category_regex = re.compile("([0-9])[0-9]")
    id_regex = re.compile("(([0-9])([0-9]))\\.[0-9]{2}")
    system = None
    for jid, v in json.items():
        built_id: None | tuple[str | None | Literal[-1], str] = None
        entry = jdex.entry.build({"id": jid, "title": v["title"]})
        match v["type"]:
            case "system":
                if system_regex.fullmatch(jid):
                    system = jid
                    built_id = (None, jid)
                else:
                    accumulated_errors.append(
                        JDexIssueInvalidID(
                            None,
                            jid,
                            entry,
                            "system",
                        ),
                    )
            case "area":
                if area_regex.fullmatch(jid):
                    built_id = (-1, jid)
                else:
                    accumulated_errors.append(
                        JDexIssueInvalidID(
                            None,
                            jid,
                            entry,
                            "area",
                        ),
                    )
            case "category":
                match = category_regex.fullmatch(jid)
                if match:
                    built_id = (f"{match.group(1)}0-{match.group(1)}9", jid)
                else:
                    accumulated_errors.append(
                        JDexIssueInvalidID(
                            None,
                            jid,
                            entry,
                            "category",
                        ),
                    )
            case "id":
                match = id_regex.fullmatch(jid)
                if match:
                    built_id = (
                        f"{match.group(2)}{match.group(3)}",
                        jid,
                    )
                else:
                    accumulated_errors.append(
                        JDexIssueInvalidID(
                            None,
                            jid,
                            entry,
                            "id",
                        ),
                    )
            case t:
                accumulated_errors.append(
                    JDexIssueInvalidID(
                        None,
                        jid,
                        entry,
                        f'unknown type: "{t}"',
                    ),
                )

        if built_id is not None:
            accumulated_entries.append((built_id, entry))
    to_return = {}
    for (parent, jid), e in accumulated_entries:
        _insert_append_sorted(
            jid,
            CollectedJDexEntry(e, system if parent == -1 else parent, None),
            to_return,
            key=_sort_jdex_entry,
        )
    return (to_return, accumulated_errors)


def _get_jdex_entries_from_text(
    jdex: ConfigSystemJDex,
    text: str,
) -> tuple[_CollectedJDex, list[JDexIssue]]:
    accumulated_entries: _CollectedJDex = {}
    accumulated_errors: list[JDexIssue] = []
    area_regex = re.compile("^\\s*(?P<A>[0-9])0-(?P=A)9 ([^/\\n]+?)\\s*(?:$|/.*)")
    category_regex = re.compile("^\\s*(([0-9])[0-9]) ([^/\\n]+?)\\s*(?:$|/.*)")
    id_regex = re.compile("^\\s*(([0-9])[0-9])\\.([0-9]{2}) ([^/\\n]+?)\\s*(?:$|/.*)")
    metadata_or_whitespace_regex = re.compile("^\\s*(- .+?)?\\s*(?:$|/.*)")

    for line in text.splitlines():
        match = area_regex.fullmatch(line)
        if match:
            jid = f"{match.group(1)}0-{match.group(1)}9"

            _insert_append_sorted(
                jid,
                CollectedJDexEntry(
                    jdex.entry.build(
                        {"id": jid, "title": match.group(2)},
                    ),
                    None,
                    None,
                ),
                accumulated_entries,
                key=_sort_jdex_entry,
            )
            continue
        match = category_regex.fullmatch(line)
        if match:
            jid = match.group(1)

            _insert_append_sorted(
                jid,
                CollectedJDexEntry(
                    jdex.entry.build(
                        {"id": jid, "title": match.group(3)},
                    ),
                    f"{match.group(2)}0-{match.group(2)}9",
                    None,
                ),
                accumulated_entries,
                key=_sort_jdex_entry,
            )
            continue

        match = id_regex.fullmatch(line)
        if match:
            jid = f"{match.group(1)}.{match.group(3)}"

            _insert_append_sorted(
                jid,
                CollectedJDexEntry(
                    jdex.entry.build(
                        {"id": jid, "title": match.group(4)},
                    ),
                    f"{match.group(1)}",
                    None,
                ),
                accumulated_entries,
                key=_sort_jdex_entry,
            )
            continue
        if not metadata_or_whitespace_regex.fullmatch(line):
            # This doesn't look like something in the standard
            accumulated_errors.append(
                JDexIssueInvalidID(
                    None,
                    "unknown",
                    line.strip(),
                    "unknown",
                ),
            )
    return (accumulated_entries, accumulated_errors)


def _get_jdex_entries_from_file(
    path: Path,
    jdex: ConfigSystemJDex,
) -> tuple[_CollectedJDex, list[JDexIssue]]:
    # Load file
    as_text = Path.read_text(path)
    try:
        return _get_jdex_entries_from_json(jdex, json.loads(as_text))

    except json.JSONDecodeError:
        # This isn't valid JSON, so it must be plaintext
        return _get_jdex_entries_from_text(jdex, as_text)


def _get_jdex_entries_here_or_children(
    ignored: list[str],
    root_path: PurePath,
    bound_segments: dict[str, str],
    path: os.PathLike,
    tier: ConfigJDexTier | ConfigSystemJDex,
) -> tuple[_CollectedJDex, list[JDexIssue]]:
    # Compile regexes for children
    valid_children = [
        (re.compile(c.format.build_regex(bound_segments)), c) for c in tier.children
    ]
    valid_notes = [
        (re.compile(n.format.build_regex(bound_segments)), n) for n in tier.notes
    ]

    accumulated_entries: _CollectedJDex = {}
    accumulated_errors: list[JDexIssue] = []

    has_content = False

    def process_dir_entry(x: os.DirEntry) -> None:
        for child_format, child in valid_children:
            match = child_format.fullmatch(x.name)
            if match:
                if child.format.forbidden:
                    accumulated_errors.append(
                        JDexIssueEncounteredForbiddenFolder(
                            PurePath(x).relative_to(root_path),
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
                            PurePath(x).relative_to(root_path),
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
                    root_path,
                    {**bound_segments, **match.groupdict()},
                    PurePath(x),
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
                                PurePath(x).relative_to(root_path),
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
                                PurePath(x).relative_to(root_path),
                                ContentPattern(
                                    note.format.name,
                                    note.format.raw_format,
                                ),
                            ),
                        )
                        break

                    # Create entry
                    for jid in note.ids:
                        child_id = jid.id.build({**bound_segments, **match.groupdict()})
                        parent_id = (
                            jid.parent.build({**bound_segments, **match.groupdict()})
                            if jid.parent is not None
                            else None
                        )
                        _insert_append_sorted(
                            child_id,
                            CollectedJDexEntry(
                                jid.entry.build(
                                    {**bound_segments, **match.groupdict()},
                                )
                                if jid.entry
                                else x.name,
                                parent_id,
                                PurePath(x).relative_to(root_path),
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
                            PurePath(x).relative_to(root_path),
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

    with os.scandir(path) as contents:
        for x in contents:
            if _entry_is_ignored(ignored, x):
                continue
            has_content = True
            process_dir_entry(x)

    if not has_content:
        # We have a fully empty JDex folder; it shouldn't exist if it's doing nothing.
        accumulated_errors.append(
            JDexIssueEmptyFolder(PurePath(path).relative_to(root_path)),
        )
    return (accumulated_entries, accumulated_errors)


def _process_jdex(
    ignored: list[str],
    jdex: ConfigSystemJDex,
) -> tuple[_CollectedJDex, list[JDexIssue]]:
    # We need to first see if we have a single file, or a folder
    if not getattr(jdex, "entry", False):
        # Normal note-based JDex
        (jdex_entries_by_id, jdex_errors) = _get_jdex_entries_here_or_children(
            ignored + jdex.ignore,
            jdex.path,
            {},
            jdex.path,
            jdex,
        )
    else:
        # Single file JDex
        (jdex_entries_by_id, jdex_errors) = _get_jdex_entries_from_file(
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
    by_id_dict: dict[str, list[_CollectedSystemEntry]],
    ignored: list[str],
    root_path: PurePath,
    bound_segments: dict[str, str],
    path: os.PathLike,
    tier: ConfigSystemRoot | ConfigSystemTier,
) -> tuple[dict[str, list[SystemFolder | SystemFile]], list[Issue]]:
    # Compile regexes for children
    valid_children = [
        (re.compile(c.format.build_regex(bound_segments)), c) for c in tier.children
    ]
    accumulated_errors = []
    accumulated_structure = {}
    has_content = False
    content_in_should_be_empty = []

    def process_dir_entry(x: os.DirEntry) -> None:
        for child_format, child in valid_children:
            match = child_format.fullmatch(x.name)
            if match:
                if child.format.forbidden:
                    accumulated_errors.append(
                        IssueEncounteredForbiddenFolder(
                            PurePath(x).relative_to(root_path),
                            ContentPattern(
                                child.format.name,
                                child.format.raw_format,
                            ),
                        ),
                    )
                    break
                # Is a valid child folder
                child_id = child.id.id.build({**bound_segments, **match.groupdict()})
                if not child.no_jdex_entry:
                    _insert_append_sorted(
                        child_id,
                        _CollectedSystemEntry(
                            child.id.entry.build(
                                {**bound_segments, **match.groupdict()},
                            )
                            if child.id.entry
                            else x.name,
                            PurePath(x).relative_to(root_path),
                        ),
                        by_id_dict,
                        # Sort duplicates by their path, not their JDex entry
                        key=lambda e: e.path,
                    )
                if x.is_file():
                    if child.can_be_file:
                        _insert_append_sorted(
                            child_id,
                            SystemFile(
                                PurePath(x).relative_to(root_path),
                            ),
                            accumulated_structure,
                            key=lambda e: e.path,
                        )
                    else:
                        # This is an error
                        accumulated_errors.append(
                            IssueFileWhereFolderExpected(
                                PurePath(x).relative_to(root_path),
                                ContentPattern(
                                    child.format.name,
                                    child.format.raw_format,
                                ),
                            ),
                        )
                    break

                # Walk child
                (child_structure, child_errors) = _process_system_level_and_children(
                    by_id_dict,
                    ignored,
                    root_path,
                    {**bound_segments, **match.groupdict()},
                    PurePath(x),
                    child,
                )
                _insert_append_sorted(
                    child_id,
                    SystemFolder(
                        PurePath(x).relative_to(root_path),
                        child_structure,
                    ),
                    accumulated_structure,
                    key=lambda e: e.path,
                )
                accumulated_errors.extend(child_errors)
                break
        else:
            # If we got here, it matched no known child/note
            if not getattr(tier, "allow_arbitrary_contents", False):
                # If the tier has no children specified, it should be empty
                if not tier.children:
                    content_in_should_be_empty.append(
                        PurePath(x).relative_to(root_path),
                    )
                else:
                    accumulated_errors.append(
                        IssueArbitraryContentWhereNotAllowed(
                            PurePath(x).relative_to(root_path),
                            tuple(
                                ContentPattern(c.format.name, c.format.raw_format)
                                for c in tier.children
                            ),
                        ),
                    )

    with os.scandir(path) as contents:
        for x in contents:
            if _entry_is_ignored(ignored, x):
                continue
            has_content = True
            process_dir_entry(x)

    if content_in_should_be_empty:
        accumulated_errors.append(
            IssueFolderShouldBeEmpty(
                PurePath(path).relative_to(root_path),
                tuple(content_in_should_be_empty),
            ),
        )
    if not has_content and (
        tier.children or getattr(tier, "allow_arbitrary_contents", False)
    ):
        # We have a fully empty folder; it shouldn't exist if it's doing nothing (unless it should be empty).
        accumulated_errors.append(
            IssueEmptyFolder(PurePath(path).relative_to(root_path)),
        )
    return (accumulated_structure, accumulated_errors)


def _process_system_root(
    ignored: list[str],
    root: ConfigSystemRoot,
    jdex: None | _CollectedJDex,
) -> tuple[dict[str, list[SystemFolder | SystemFile]], list[Issue]]:
    by_id: dict[str, list[_CollectedSystemEntry]] = {}
    (root_structure, root_errors) = _process_system_level_and_children(
        by_id,
        ignored + root.ignore,
        root.path,
        {},
        root.path,
        root,
    )

    # Check for duplicate IDs
    duplicate_id_errors = [
        IssueDuplicateID(fs[0].path, tuple([f.path for f in fs]), jid)
        for jid, fs in by_id.items()
        if len(fs) != 1
    ]

    # If we have a JDex, we can do some additional checks
    id_errors = []
    if jdex is not None:
        for jid, fs in by_id.items():
            if jid not in jdex:
                id_errors.append(IssueIDNotInJDex(fs[0].path, jid))
            else:
                jdex_entries = [n.entry for n in jdex[jid]]
                id_errors.extend(
                    IssueIDDifferentFromJDex(
                        f.path,
                        jid,
                        f.expected_jdex_entry,
                        jdex[jid],
                    )
                    for f in fs
                    if f.expected_jdex_entry
                    and f.expected_jdex_entry not in jdex_entries
                )

    return (root_structure, root_errors + duplicate_id_errors + id_errors)


def lint_system(config: Config) -> LintResults:
    """Given a valid jdlint config, lint the specified system and return results."""
    jdex_errors = []
    jdex_entries: _CollectedJDex = {}
    if config.system.jdex:
        (jdex_entries, jdex_errors) = _process_jdex(
            config.linter.ignore,
            config.system.jdex,
        )
        # We need to assemble a tree structure for the JDex, since we only have dependencies
        safe_entries: dict[tuple[str | None, str], JDexIDEntry] = {}
        has_children: dict[str, set[str]] = {}

        def go() -> dict[str, JDexIDEntry]:
            starting_size = len(safe_entries)
            for pid, jid in tuple(safe_entries.keys()):
                if jid not in has_children:
                    entry = safe_entries.pop((pid, jid))
                    if pid is None:
                        # this is a top level entry
                        safe_entries[(None, jid)] = entry
                        continue
                    possible_parents = [
                        (grandparent, parent)
                        for (grandparent, parent) in safe_entries
                        if parent == pid
                    ]
                    match len(possible_parents):
                        case 1:
                            key = possible_parents[0]
                            parent = safe_entries[key]
                            parent.children[jid] = entry
                            safe_entries[key] = parent
                        case 0:
                            # ID is an orphan
                            jdex_errors.extend(
                                JDexIssueOrphan(e.path, jid, e.entry, pid)
                                for e in entry.entries
                            )
                        case _:
                            # Parentage is ambiguous; this should not be able to happen, since we've checked for it already
                            raise NotImplementedError
                    remaining_children = has_children.pop(pid)
                    remaining_children.remove(jid)
                    if remaining_children:
                        has_children[pid] = remaining_children
            if has_children:
                if len(safe_entries) < starting_size:
                    go()
                else:
                    # We have cycles
                    while True:
                        # Get an ID that is not top level
                        pid, jid = next(
                            ((k, v) for k, v in safe_entries if k is not None),
                            (None, None),
                        )
                        if jid is None:
                            # All cycles reported
                            break
                        cycle = {
                            jid: [
                                CollectedJDexEntry(e.entry, pid, e.path)
                                for e in safe_entries.pop((pid, jid)).entries
                            ],
                        }

                        def get_next(
                            cycle: dict[str, list[CollectedJDexEntry]],
                            next_parent: str,
                        ) -> None:
                            gp, p = next(
                                ((gp, p) for gp, p in safe_entries if p == next_parent),
                                (None, None),
                            )
                            if p is not None:
                                cycle[next_parent] = [
                                    CollectedJDexEntry(e.entry, gp, e.path)
                                    for e in safe_entries.pop((gp, p)).entries
                                ]
                                if gp is not None:
                                    get_next(cycle, gp)

                        if pid is not None:
                            get_next(cycle, pid)
                        jdex_errors.append(
                            JDexIssueAncestryCycle(
                                # Sort dict keys
                                next(iter(cycle[key] for key in sorted(cycle.keys())))[
                                    0
                                ].path,
                                {k: cycle[k] for k in sorted(cycle.keys())},
                            ),
                        )

            return {jid: e for (_, jid), e in safe_entries.items()}

        for jid, es in jdex_entries.items():
            # We need to collect these by parentage first
            by_parent: dict[str | None, list[CollectedJDexEntry]] = {}
            for e in es:
                _insert_append_sorted(e.parent, e, by_parent, key=_sort_jdex_entry)
            if len(by_parent) == 1:
                (pid, entries) = by_parent.popitem()
                safe_entries[(pid, jid)] = JDexIDEntry(
                    [JDexEntry(e.entry, e.path) for e in entries],
                    {},
                )

                if pid is not None:
                    children = has_children.get(pid, set())
                    children.add(jid)
                    has_children[pid] = children
            else:
                # Ambiguous parentage
                jdex_errors.append(JDexIssueAmbiguousAncestry(es[0].path, jid, es))
        jdex_results = go()

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
            jdex_results,
        )
        if config.system.jdex
        else None,
        roots,
        ignored_errors + ignored_jdex_errors,
    )


def _pluralize(num: int, word: str, weird_plural: str | None = None) -> str:
    if num == 1:
        return f"{num!s} {word}"
    if weird_plural is None:
        return f"{num!s} {word}s"
    return f"{num!s} {weird_plural}"


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
                total_errs = sum(len(errs) for errs in jdex_errs_by_type.values())
                print(  # noqa: T201
                    f"{'':=^80}\n{'JDex Errors Found:':^80}\n{_pluralize(total_errs, 'instance') + '; ' + _pluralize(len(jdex_errs_by_type), 'kind'):^80}\n{'':=^80}\n",
                )
                for errs in jdex_errs_by_type.values():
                    first_j_err = next(iter(errs))  # Just get the first error
                    explanation = first_j_err.explain()
                    print(  # noqa: T201
                        f"{first_j_err.type + ' (' + str(len(errs)) + ')':^80}\n{explanation.explanation}\n---",
                    )
                    print(  # noqa: T201
                        textwrap.indent(
                            "\n".join(
                                [e.display() for e in errs],
                            ),
                            "  ",
                        ),
                    )
                    print(f"---\n{explanation.fix}\n")  # noqa: T201

        # Print file errors if any
        if any(r.errors for r in results.roots.values()):
            any_errors = True
            for location, root in results.roots.items():
                errs_by_type: dict[IssueType, list[Issue]] = {}
                if root.errors:
                    errs_by_type = {}
                    for e in root.errors:
                        _insert_append_sorted(e.type, e, errs_by_type, key=_sort_error)
                    total_errs = sum(len(errs) for errs in errs_by_type.values())
                    print(  # noqa: T201
                        f"{'':=^80}\n{location + ' Errors Found:':^80}\n{_pluralize(total_errs, 'instance') + '; ' + _pluralize(len(errs_by_type), 'kind'):^80}\n{'':=^80}\n",
                    )
                    for errs in errs_by_type.values():
                        first_err = next(iter(errs))  # Just get the first error
                        explanation = first_err.explain()
                        print(  # noqa: T201
                            f"{first_err.type + ' (' + str(len(errs)) + ')':^80}\n{explanation.explanation}\n---",
                        )
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
