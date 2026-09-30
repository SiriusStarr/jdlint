#!/usr/bin/env python3

#
# Copyright © 2026 SiriusStarr
#
# This code is made available under the terms of the GNU General Public License v3.0
# You should have received a copy of this license along with this code.
# If not, a copy is available here: https://www.gnu.org/licenses/gpl-3.0.en.html
#

"""Script to check for common issues with a Johnny Decimal system."""

from __future__ import annotations

import argparse
import contextlib
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


class JDConfigError(Exception):
    """An error in the JD config."""

    def __init__(self, path: Path, message: str) -> None:
        """Create a config error, given a message."""
        super().__init__(f"Issue with JD config file at {path}. {message}")


class JDConfigMissingError(JDConfigError):
    """The specified JD config file was not found."""

    def __init__(self, path: Path) -> None:
        """Create a missing file error, given the path."""
        super().__init__(path, "JD_CONFIG was set, but no file was found.")


class JDConfigJsonError(JDConfigError):
    """The specified JD config file was not valid JSON."""

    def __init__(self, path: Path, message: str) -> None:
        """Create an invalid JSON error, given the decode message."""
        super().__init__(path, f"The file was not valid JSON. {message}")


class JDConfigFormatError(JDConfigError):
    """The specified JD config file was not valid."""

    def __init__(self, path: Path, message: str) -> None:
        """Create an invalid format error, given the  message."""
        super().__init__(path, f"The file was not valid. {message}")


class JDConfigVersionError(JDConfigError):
    """The specified JD config file was an unknown/unspecified version."""

    def __init__(self, path: Path) -> None:
        """Create a version error for the JD config."""
        super().__init__(
            path,
            "The file did not specify a version or was an unsupported version. Supported versions: 1",
        )


class JDConfigMissingKeyError(JDConfigError):
    """A missing key in the JD config."""

    def __init__(self, path: Path, key: str) -> None:
        """Create a missing key error."""
        super().__init__(
            path,
            f"Required key {key} not found.",
        )


class JDConfigTypeError(JDConfigError):
    """A value with the wrong type in the JD config."""

    def __init__(self, path: Path, key: str, expected: str, got: str) -> None:
        """Create a type error, given the key it occurs at, the expected type, and the actual type."""
        super().__init__(
            path,
            f"Key {key} was the wrong type.  Expected: {expected}  Got: {got}",
        )


class JDConfigValueError(JDConfigError):
    """A bad value in the JD config."""

    def __init__(self, path: Path, key: str, issue: str, got: str) -> None:
        """Create a value error, given the key it occurs at, the issue with the value, and the actual value."""
        super().__init__(
            path,
            f"Key {key} was a bad value.  Got: {got}  Issue: {issue}",
        )


class JDConfigConflictError(JDConfigError):
    """A conflict in the JD config."""

    def __init__(self, path: Path, key: str, issue: str) -> None:
        """Create a conflict error, given the key it occurs at and the issue."""
        super().__init__(path, f"Conflict in JD config at key {key}.  Issue: {issue}")


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


def _pop_nonempty_str(
    at: str,
    attr: str,
    from_file: dict,
    template: _Template | None,
) -> str:
    return _pop_nonempty_str_with_binds(at, attr, from_file, template)[0]


def _pop_nonempty_str_with_binds(
    at: str,
    attr: str,
    from_file: dict,
    template: _Template | None,
) -> tuple[str, dict[str, str] | None]:
    """Given a parent location, a mandatory attribute to get, and data, return it.

    If the template is used, return the template as well (for binds).
    """
    if attr in from_file:
        val = from_file.pop(attr)
        binds = None
    elif template and attr in template.vals:
        val = template.vals[attr]
        binds = template.binds
    else:
        err = ConfigMissingKeyError(f"{at}.{attr}")
        raise err
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
    return (val, binds)


def _pop_default_false_bool(
    at: str,
    attr: str,
    from_file: dict,
    template: _Template | None,
) -> bool:
    """Get a boolean at the specified attribute, defaulting to false, or fail."""
    val = False
    if attr in from_file:
        val = from_file.pop(attr)
    elif template:
        val = template.vals.get(attr, False)
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
    template: _Template | None,
    *,
    default_empty: bool = True,
) -> tuple[list, list]:
    """Get a list at the specified attribute, defaulting to [], or fail."""
    is_template = False
    if attr in from_file:
        val = from_file.pop(attr)
    elif template and attr in template.vals:
        val = template.vals[attr]
        is_template = True
    elif default_empty:
        val = []
    else:
        err = ConfigMissingKeyError(f"{at}.{attr}")
        raise err
    if not isinstance(val, list):
        err = ConfigTypeError(
            f"{at}.{attr}",
            "list",
            type(val).__name__,
        )
        raise err
    if is_template:
        return ([], val)
    return (val, [])


C = TypeVar("C")


def _recurse(
    process: Callable[[int, dict | _Template], C],
    at: str,
    attr: str,
    from_file: dict,
    template: _Template | None,
) -> list[C]:
    (cs, template_cs) = _pop_list(
        at,
        attr,
        from_file,
        template,
    )
    if template_cs:
        return [process(i, _Template(t, {})) for i, t in enumerate(template_cs)]
    return [process(i, v) for i, v in enumerate(cs)]


def _pop_list_of_strings(
    at: str,
    attr: str,
    from_file: dict,
    template: _Template | None,
    *,
    default_empty: bool = True,
) -> list[str]:
    """Get a list of strings at .ignore or fail, defaulting to []."""
    (val, template_val) = _pop_list(
        at,
        attr,
        from_file,
        template,
        default_empty=default_empty,
    )
    for i, r in enumerate(val):
        if not isinstance(r, str):
            err = ConfigTypeError(f"{at}.{attr}[{i}]", "str", type(r).__name__)
            raise err
    # Strings never matter whether they came from template or not, so just return whichever
    return val + template_val


class JDConfigSystem:
    """A system loaded from the JD config format."""

    def __init__(self, path: Path, at: str, from_file: dict) -> None:
        """Create and validate a system."""

        def get_nonempty_str(attr: str) -> str:
            if attr not in from_file:
                err = JDConfigMissingKeyError(path, f"{at}.{attr}")
                raise err
            val = from_file.pop(attr)
            if not isinstance(val, str):
                err = JDConfigTypeError(
                    path,
                    f"{at}.{attr}",
                    "str",
                    type(val).__name__,
                )
                raise err
            if val == "":
                err = JDConfigValueError(
                    path,
                    f"{at}.{attr}",
                    "Must not be empty.",
                    val,
                )
                raise err
            return val

        self.id = get_nonempty_str("sys")
        self.name = get_nonempty_str("title")
        self.root = Path(get_nonempty_str("root")).expanduser()
        # Validate path is good
        if not self.root.is_dir():
            err = JDConfigValueError(
                path,
                f"{at}.root",
                "Root path isn't a folder that exists!",
                str(self.root),
            )
            raise err
        if "jdex" in from_file:
            self.jdex = Path(get_nonempty_str("jdex")).expanduser()
            # Validate path is good
            if not self.jdex.is_dir():
                err = JDConfigValueError(
                    path,
                    f"{at}.jdex",
                    "JDex path isn't a folder that exists!",
                    str(self.jdex),
                )
                raise err

        self.default = from_file.get("default", False)
        if not isinstance(self.default, bool):
            err = JDConfigTypeError(
                jd_path,
                f"{at}.default",
                "bool",
                type(self.default).__name__,
            )
            raise err


class ConfigSystemRoot:
    """A root of a JD system to check for correctness, e.g. ~/Documents."""

    def __init__(
        self,
        templates: ConfigTemplates,
        at: str,
        default_structure: list[ConfigSystemTier],
        from_file: dict,
    ) -> None:
        """Create a valid configuration given a loaded section of a config file."""
        template = templates.get_template(at, from_file)
        self.name = _pop_nonempty_str(
            at,
            "name",
            from_file,
            template,
        )
        self.path = Path(
            _pop_nonempty_str(
                at,
                "path",
                from_file,
                template,
            ),
        ).expanduser()
        self.ignore = _pop_list_of_strings(
            at,
            "ignore",
            from_file,
            template,
        )

        # Validate path is good
        if not self.path.is_dir():
            err = ConfigValueError(
                f"{at}.path",
                "Root path isn't a folder that exists!",
                str(self.path),
            )
            raise err

        # Load specialized structure, if any
        self.children = _recurse(
            lambda i, v: ConfigSystemTier(
                templates,
                f"{at}.children[{i}]",
                ConfigFormatAncestorInfo((), ()),
                v,
            ),
            at,
            "children",
            from_file,
            template,
        )
        if not self.children:
            if default_structure:
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

    def __init__(
        self,
        jd_config: JDConfigSystem | None,
        templates: ConfigTemplates,
        at: str,
        from_file: dict,
    ) -> None:
        """Create a valid configuration given a loaded section of a config file."""
        template = templates.get_template(at, from_file)
        # Acquire and set defaults
        try:
            self.path = Path(
                _pop_nonempty_str(
                    at,
                    "path",
                    from_file,
                    template,
                ),
            ).expanduser()

        except ConfigMissingKeyError:
            if jd_config:
                # Note, we've already expanded user on this
                self.path = jd_config.jdex
            else:
                raise
        self.ignore = _pop_list_of_strings(
            at,
            "ignore",
            from_file,
            template,
        )

        try:
            note_extension = _pop_nonempty_str(
                at,
                "note_extension",
                from_file,
                template,
            )
        except ConfigMissingKeyError:
            # This is fine, it's an optional key
            note_extension = None

        self.children = _recurse(
            lambda i, v: ConfigJDexTier(
                templates,
                f"{at}.children[{i}]",
                ConfigFormatAncestorInfo((), ()),
                v,
                note_extension=note_extension,
            ),
            at,
            "children",
            from_file,
            template,
        )

        self.notes = _recurse(
            lambda i, v: ConfigJDexNotes(
                templates,
                f"{at}.notes[{i}]",
                ConfigFormatAncestorInfo((), ()),
                v,
                note_extension=note_extension,
            ),
            at,
            "notes",
            from_file,
            template,
        )

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
            if self.children or self.notes or self.ignore or note_extension:
                err = ConfigConflictError(
                    at,
                    "Single file JDexes must not specify children or notes or ignore or note_extension!",
                )
                raise err
            # Load format
            self.entry = ConfigStaticFormat(
                f"{at}.entry",
                # This is the default info made available to a file JDex
                ConfigFormatAncestorInfo(("Single File JDex",), ("id", "title")),
                _pop_nonempty_str_with_binds(
                    at,
                    "entry",
                    from_file,
                    template,
                ),
            )
        elif not self.children and not self.notes:
            err = ConfigValueError(
                at,
                "JDex must specify at least one child folder or note.",
                "[]",
            )
            raise err
        _report_extra_keys(at, from_file, tuple(self.__dict__.keys()))


class ConfigLinter:
    """Valid configuration for the linter."""

    def __init__(self, from_file: dict) -> None:
        """Create a valid configuration given a loaded linter section of a config file."""
        # Acquire and set defaults
        self.disable_rules = _pop_list_of_strings(
            "linter",
            "disable_rules",
            from_file,
            None,
        )
        self.json_output = _pop_default_false_bool(
            "linter",
            "json_output",
            from_file,
            None,
        )
        self.ignore_environment = _pop_default_false_bool(
            "linter",
            "ignore_environment",
            from_file,
            None,
        )
        self.ignore = _pop_list_of_strings(
            "linter",
            "ignore",
            from_file,
            None,
        )

        # Validate
        for r in self.disable_rules:
            if r in [e.type for e in typing.get_args(AnyIssueType)]:
                continue
            err = ConfigValueError("linter.disable_rules", "not a valid rule name", r)
            raise err

        _report_extra_keys("linter", from_file, tuple(self.__dict__.keys()))


class ConfigSystem:
    """Valid configuration for the JD system."""

    def __init__(
        self,
        jd_config: JDConfigSystem | None,
        templates: ConfigTemplates,
        at: str,
        sys_id: str | None,
        from_file: dict,
    ) -> None:
        """Create a valid configuration given a loaded system section of a config file."""
        self.id = sys_id

        try:
            self.name = _pop_nonempty_str(
                at,
                "name",
                from_file,
                None,
            )
        except ConfigMissingKeyError:
            if jd_config:
                self.name = jd_config.name
            elif sys_id:
                # Name is mandatory for non-default systems
                raise

        default = from_file.pop("default", {})

        default_structure = _recurse(
            lambda i, v: ConfigSystemTier(
                templates,
                f"{at}.default.children[{i}]",
                ConfigFormatAncestorInfo((), ()),
                v,
            ),
            f"{at}.default",
            "children",
            default,
            templates.get_template(f"{at}.default", default),
        )

        self.roots = [
            ConfigSystemRoot(
                templates,
                f"{at}.roots[{i}]",
                default_structure,
                v,
            )
            for i, v in enumerate(
                _pop_list(f"{at}", "roots", from_file, None)[0],
            )
        ]

        accum_names = {}
        accum_paths = {}
        for root in self.roots:
            if root.name in accum_names:
                err = ConfigConflictError(
                    f"{at}.roots",
                    f"System root names must be unique. {root.name} occurs multiple times.",
                )
                raise err
            if root.path in accum_paths:
                err = ConfigConflictError(
                    f"{at}.roots",
                    f"System root paths must be unique. {root.path} occurs multiple times.",
                )
                raise err
        if jd_config and not any(root.path == jd_config.root for root in self.roots):
            # We need to add the root path from the JD config, if it wasn't already in
            self.roots.append(
                ConfigSystemRoot(
                    templates,
                    "from JD config file",
                    default_structure,
                    {"path": str(jd_config.root), "name": "from JD config file"},
                ),
            )
        if not self.roots:
            err = ConfigValueError(
                f"{at}.roots",
                "At least one root must be specified!",
                "[]",
            )
            raise err

        if "jdex" in from_file:
            self.jdex = ConfigSystemJDex(
                jd_config,
                templates,
                f"{at}.jdex",
                from_file.pop("jdex"),
            )
        else:
            self.jdex = None

        _report_extra_keys(f"{at}", from_file, tuple(self.__dict__.keys()))


class ConfigStaticFormat:
    """Configuration for how to assign a static ID or JDex note."""

    # A valid variable segment of an ID format
    variable_static_segment_re = re.compile(r"=([A-Za-z]+)")

    def __init__(
        self,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        str_and_binds: tuple[str, dict[str, str] | None],
    ) -> None:
        """Create a valid format given a string from a config file."""
        (format_str, binds) = str_and_binds
        # Validate
        if format_str.count("/") % 2 != 0:
            raise ConfigValueError(
                at,
                "Malformed format; there must be an even number of / characters. You have an extra/are missing one.",
                format_str,
            )

        build = []

        for i, v in enumerate(format_str.split("/")):
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
                if binds and match.group(1) in binds:
                    # Bind made this a literal segment
                    bind = binds[match.group(1)]
                    build.append(lambda _, v=bind: v)
                elif match.group(1) in ancestors.segments:
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
        template: _Template | None,
        *,
        supports_parent: bool,
    ) -> None:
        """Create a valid ID given a loaded section of a config file."""
        # Expanding templates is done at the layer above
        self.id = ConfigStaticFormat(
            f"{at}.id",
            ancestors,
            _pop_nonempty_str_with_binds(
                at,
                "id",
                from_file,
                template,
            ),
        )
        if supports_parent:
            try:
                self.parent = ConfigStaticFormat(
                    f"{at}.parent",
                    ancestors,
                    _pop_nonempty_str_with_binds(
                        at,
                        "parent",
                        from_file,
                        template,
                    ),
                )
            except ConfigMissingKeyError:
                self.parent = None

        try:
            self.entry = ConfigStaticFormat(
                f"{at}.entry",
                ancestors,
                _pop_nonempty_str_with_binds(
                    at,
                    "entry",
                    from_file,
                    template,
                ),
            )
        except ConfigMissingKeyError:
            self.entry = None

        _report_extra_keys(at, from_file, tuple(self.__dict__.keys()))


class ConfigJDexNotes:
    """Configuration for how JDex notes are formatted."""

    def __init__(
        self,
        templates: ConfigTemplates,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        load: dict | _Template,
        *,
        note_extension: str | None,
    ) -> None:
        """Create a valid note format given a loaded section of a config file."""
        if isinstance(load, _Template):
            from_file = {}
            template = templates.subtemplate(at, load)
        else:
            from_file = load
            template = templates.get_template(at, load)

        # Compile Format
        self.format = ConfigFormat(
            at,
            ancestors,
            from_file,
            template,
            note_extension=note_extension,
        )

        self.extension = note_extension

        try:
            self.ids = [
                ConfigID(at, self.format, from_file, template, supports_parent=True)
            ]
        except ConfigMissingKeyError:
            self.ids = []

        (cs, template_cs) = _pop_list(
            at, "ids", from_file, template, default_empty=True
        )
        if template_cs:
            self.ids.extend(
                ConfigID(
                    f"{at}.ids[{i}]",
                    self.format,
                    {},
                    templates.subtemplate(f"{at}.ids[{i}]", _Template(t, {})),
                    supports_parent=True,
                )
                for i, t in enumerate(template_cs)
            )
        else:
            self.ids.extend(
                ConfigID(
                    f"{at}.ids[{i}]",
                    self.format,
                    v,
                    templates.get_template(f"{at}.ids[{i}]", v),
                    supports_parent=True,
                )
                for i, v in enumerate(cs)
            )
        if not self.ids and not self.format.forbidden:
            err = ConfigMissingKeyError(f"{at}.ids")
            raise err

        _report_extra_keys(at, from_file, tuple(self.__dict__.keys()))


class ConfigFolderTier:
    """A tier of a JD system, e.g. a Category, whether in the JDex or the system itself."""

    def __init__(
        self,
        templates: ConfigTemplates,
        child_class: Callable,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        from_file: dict,
        template: _Template | None,
    ) -> None:
        """Create a valid tier given a loaded section of a config file."""
        # Note that we have already gotten any template that exists at this level, so we don't need to do it here
        # Acquire and set defaults
        self.allow_arbitrary_contents = _pop_default_false_bool(
            at,
            "allow_arbitrary_contents",
            from_file,
            template,
        )

        # Compile Format & Children
        self.format = ConfigFormat(
            at,
            ancestors,
            from_file,
            template,
            note_extension=None,
        )

        self.children = _recurse(
            lambda i, v: child_class(
                templates,
                f"{at}.children[{i}]",
                self.format,
                v,
            ),
            at,
            "children",
            from_file,
            template,
        )

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
        templates: ConfigTemplates,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        load: dict | _Template,
    ) -> None:
        """Create a valid tier given a loaded section of a config file."""
        if isinstance(load, _Template):
            from_file = {}
            template = templates.subtemplate(at, load)
        else:
            from_file = load
            template = templates.get_template(at, load)
        # Acquire and set defaults

        self.can_be_file = _pop_default_false_bool(
            at,
            "can_be_file",
            from_file,
            template,
        )
        self.no_jdex_entry = _pop_default_false_bool(
            at,
            "no_jdex_entry",
            from_file,
            template,
        )

        # Call the folder tier stuff
        super().__init__(
            templates,
            ConfigSystemTier,
            at,
            ancestors,
            from_file,
            template,
        )

        self.id = ConfigID(
            at,
            self.format,
            from_file,
            template,
            supports_parent=False,
        )

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
        templates: ConfigTemplates,
        at: str,
        ancestors: ConfigFormatAncestorInfo,
        load: dict | _Template,
        *,
        note_extension: str | None,
    ) -> None:
        """Create a valid tier given a loaded section of a config file."""
        if isinstance(load, _Template):
            from_file = {}
            template = templates.subtemplate(at, load)
        else:
            from_file = load
            template = templates.get_template(at, load)

        # Call the folder tier stuff
        super().__init__(
            templates,
            lambda t, at, an, lo: ConfigJDexTier(
                t,
                at,
                an,
                lo,
                note_extension=note_extension,
            ),
            at,
            ancestors,
            from_file,
            template,
        )

        self.notes = _recurse(
            lambda i, v: ConfigJDexNotes(
                templates,
                f"{at}.notes[{i}]",
                self.format,
                v,
                note_extension=note_extension,
            ),
            at,
            "notes",
            from_file,
            template,
        )

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
        template: _Template | None,
        *,
        note_extension: str | None = None,
    ) -> None:
        """Create a valid format given a string from a config file."""
        name = _pop_nonempty_str(
            at,
            "name",
            from_file,
            template,
        )
        (self.raw_format, binds) = _pop_nonempty_str_with_binds(
            at,
            "format",
            from_file,
            template,
        )
        self.forbidden = _pop_default_false_bool(
            at,
            "forbidden",
            from_file,
            template,
        )

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

        def handle_literal(v: str) -> None:
            # Literal segment
            regex.append(lambda _, v=v: re.escape(v))

        for i, v in enumerate(self.raw_format.split("/")):
            if i % 2 == 0:
                handle_literal(v)
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

            if binds and identifier in binds:
                if segment_type == "=":
                    handle_literal(binds[identifier])

                else:
                    # Bind made this a literal segment, not variable
                    new_segments.append(identifier)
                    bind = binds[identifier]
                    regex.append(
                        lambda _, identifier=identifier, bind=bind: (
                            f"(?P<{identifier}>{re.escape(bind)})"
                        ),
                    )
                continue

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
            elif identifier in ancestors.segments:
                if binds is not None:
                    # We're in a template, so convert it to a bound segment
                    p = identifier
                    regex.append(lambda d, p=p: re.escape(d[p]))
                else:
                    err = ConfigValueError(
                        f"{at}.format",
                        f'Malformed format; variable segment tried to rebind the identifier "{identifier}", which was already bound in a parent.',
                        v,
                    )
                    raise err
            elif identifier in new_segments:
                err = ConfigValueError(
                    f"{at}.format",
                    f'Malformed format; variable segment tried to rebind the identifier "{identifier}", which was already bound in this format.',
                    v,
                )
                raise err
            else:
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

        if note_extension:
            # Literal segment
            regex.append(lambda _, v=note_extension: re.escape(v))

        self.name = (*ancestors.name, name)
        self.segments = ancestors.segments + tuple(new_segments)
        self.build_regex = lambda d: "".join([f(d) for f in regex])


@dataclass(frozen=True)
class _Template:
    """A template loaded in the config."""

    vals: dict[str, typing.Any]
    binds: dict[str, str]


class ConfigTemplates:
    """Valid templates for jdlint."""

    def __init__(self, config_file_path: Path, from_file: dict) -> None:
        """Attempt to load templates from loaded TOML."""
        # Load and validate templates
        templates = from_file.pop("template", {})
        if not isinstance(templates, dict):
            err = ConfigTypeError(
                "template",
                "dict",
                type(templates).__name__,
            )
            raise err
        imports = templates.pop("imports", [])
        if not isinstance(imports, list):
            err = ConfigTypeError(
                "template.imports",
                "list",
                type(imports).__name__,
            )
            raise err
        for k, v in templates.items():
            if not isinstance(v, dict):
                err = ConfigTypeError(
                    f"template.{k}",
                    "dict",
                    type(v).__name__,
                )
                raise err
        imported = {}
        with contextlib.chdir(config_file_path.parent):
            for i, f in reversed(list(enumerate(imports))):
                if not isinstance(f, str):
                    err = ConfigTypeError(
                        f"template.imports[{i}]",
                        "string",
                        type(f).__name__,
                    )
                    raise err
                as_path = Path(f).expanduser()
                if not as_path.is_file():
                    err = ConfigValueError(
                        f"template.imports[{i}]",
                        "Template import path isn't a file that exists!",
                        str(as_path),
                    )
                    raise err

                with Path.open(as_path, "rb") as import_file:
                    to_import = tomllib.load(import_file)

                for k, v in to_import.items():
                    if not isinstance(v, dict):
                        err = ConfigTypeError(
                            f"template.{k}",
                            "dict",
                            type(v).__name__,
                        )
                        raise err
                imported |= to_import

        self.templates = imported | templates

    def get_template(self, at: str, from_file: dict) -> _Template | None:
        """Get a template specified by the loaded data structure, if it specifies one."""
        try:
            template_name = _pop_nonempty_str(
                f"{at}.template",
                "template",
                from_file,
                None,
            )
            return_keys = self.templates.get(template_name, {})
            if not return_keys:
                err = ConfigValueError(
                    f"{at}.template",
                    f"The specified template could not be found or was completely empty; check your spelling, maybe? Known templates are: {', '.join(sorted(self.templates.keys()))}",
                    template_name,
                )
                raise err
        except ConfigMissingKeyError:
            # This is fine, no need to have a template
            return None

        binds = from_file.pop("bind") if "bind" in from_file else {}
        if not isinstance(binds, dict):
            err = ConfigTypeError(
                f"{at}.bind",
                "dict",
                type(binds).__name__,
            )
            raise err
        for k, v in binds.items():
            if not isinstance(v, str):
                err = ConfigTypeError(
                    f"{at}.bind.{k}",
                    "str",
                    type(v).__name__,
                )
                raise err
        return self._subtemplate_recurse(
            at,
            [template_name],
            _Template(return_keys, binds),
        )

    def _subtemplate_recurse(
        self,
        at: str,
        inside: list[str],
        template: _Template,
    ) -> _Template:
        """Get a template inside of a template, if it specifies one, and merge them."""
        try:
            template_name = _pop_nonempty_str(
                f"{at}.template",
                "template",
                {},
                template,
            )
            if template_name in inside:
                # Infinite recursion
                err = ConfigValueError(
                    f"{at}.template",
                    f"Infinite template recursion encountered. Ancestry: {inside}",
                    template_name,
                )
                raise err
            return_keys = self.templates.get(template_name, {})
            if not return_keys:
                err = ConfigValueError(
                    f"{at}.template",
                    f"The specified template could not be found or was completely empty; check your spelling, maybe? Known templates are: {', '.join(sorted(self.templates.keys()))}",
                    template_name,
                )
                raise err
        except ConfigMissingKeyError:
            # This is fine, no need to have a template; return the input one
            return template

        binds = template.vals.get("bind", {})
        if not isinstance(binds, dict):
            err = ConfigTypeError(
                f"{at}.bind",
                "dict",
                type(binds).__name__,
            )
            raise err
        for k, v in binds.items():
            if not isinstance(v, str):
                err = ConfigTypeError(
                    f"{at}.bind.{k}",
                    "str",
                    type(v).__name__,
                )
                raise err

        inside.append(template_name)
        subtemp = self._subtemplate_recurse(at, inside, _Template(return_keys, binds))
        # We have to merge keys and binds; as always, the deeper you are the lower priority
        return _Template(subtemp.vals | template.vals, subtemp.binds | template.binds)

    def subtemplate(self, at: str, template: _Template) -> _Template:
        """Resolve templating within the current template, if necessary."""
        return self._subtemplate_recurse(at, [], template)


class Config:
    """Valid config for jdlint."""

    def __init__(
        self,
        config_file_path: Path,
        jd_config: dict[str, JDConfigSystem],
        from_file: dict,
    ) -> None:
        """Attempt to create a valid config from loaded TOML."""
        templates = ConfigTemplates(config_file_path, from_file)

        self.linter = ConfigLinter(from_file.pop("linter", {}))

        if "system" not in from_file:
            err = ConfigMissingKeyError("system")
            raise err

        if not isinstance(from_file["system"], list):
            try:
                sys_id = _pop_nonempty_str(
                    "system",
                    "id",
                    from_file["system"],
                    None,
                )
            except ConfigMissingKeyError:
                sys_id = None
            if sys_id:
                jd_sys = jd_config.get(sys_id)
            else:
                jd_sys = None
                defaults = [v for v in jd_config.values() if v.default]
                if defaults:
                    jd_sys = defaults[0]
                    sys_id = jd_sys.id
            self.system: dict[str, ConfigSystem] | ConfigSystem = ConfigSystem(
                jd_sys,
                templates,
                "system",
                sys_id,
                from_file.pop("system"),
            )
        else:
            self.system = {}
            for i, sys in enumerate(from_file.pop("system")):
                if not isinstance(sys, dict):
                    err = ConfigTypeError(
                        f"system[{i}]",
                        "dict",
                        type(sys).__name__,
                    )
                    raise err
                sys_id = _pop_nonempty_str(
                    f"system[{i}]",
                    "id",
                    sys,
                    None,
                )
                if sys_id in self.system:
                    # Duplicate system ID!
                    err = ConfigConflictError(
                        f"system[{i}].id",
                        f"The id {sys_id} was specified for more than one system!",
                    )
                    raise err

                self.system[sys_id] = ConfigSystem(
                    jd_config.get(sys_id),
                    templates,
                    f"system[{i}]",
                    sys_id,
                    sys,
                )

        _report_extra_keys("", from_file, ("linter", "system", "template"))


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
class SystemInfo:
    """Info about which system was linted (if multiple)."""

    id: str
    name: str


@dataclass(frozen=True)
class LintResults:
    """All errors returned from linting files, as well as the JDex and filesystems structures."""

    jdex: JDexLintResults | None
    roots: dict[str, RootLintResults]
    system: SystemInfo | None
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
    accumulated_entries: list[tuple[tuple[str | Literal[-1] | None, str], str]] = []
    accumulated_errors: list[JDexIssue] = []
    system_regex = re.compile("[A-Z][0-9][0-9]")
    area_regex = re.compile("(?P<A>[0-9])0-(?P=A)9")
    category_regex = re.compile("([0-9])[0-9]")
    id_regex = re.compile("(([0-9])([0-9]))\\.[0-9]{2}")
    system = None
    for jid, v in json.items():
        built_id: tuple[str | Literal[-1] | None, str] | None = None
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
                        if jid.entry:
                            entry = jid.entry.build(
                                {**bound_segments, **match.groupdict()},
                            )
                        else:
                            entry = x.name
                            if note.extension:
                                entry = entry.removesuffix(note.extension)
                        _insert_append_sorted(
                            child_id,
                            CollectedJDexEntry(
                                entry,
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
    jdex: _CollectedJDex | None,
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


def lint_system(linter: ConfigLinter, system: ConfigSystem) -> LintResults:
    """Given a valid jdlint config, lint the specified system and return results."""
    jdex_errors = []
    jdex_entries: _CollectedJDex = {}
    if system.jdex:
        (jdex_entries, jdex_errors) = _process_jdex(linter.ignore, system.jdex)
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
    for root in system.roots:
        (root_structure, root_errors) = _process_system_root(
            linter.ignore,
            root,
            jdex_entries if system.jdex else None,
        )
        ignored_errors += sum(1 for e in root_errors if e.type in linter.disable_rules)
        root_errors = [e for e in root_errors if e.type not in linter.disable_rules]
        roots[root.name] = RootLintResults(
            sorted(root_errors, key=_sort_error),
            root.path,
            root_structure,
        )

    ignored_jdex_errors = sum(1 for e in jdex_errors if e.type in linter.disable_rules)

    return LintResults(
        JDexLintResults(
            sorted(
                [e for e in jdex_errors if e.type not in linter.disable_rules],
                key=_sort_jdex_error,
            ),
            system.jdex.path,
            jdex_results,
        )
        if system.jdex
        else None,
        roots,
        SystemInfo(system.id, system.name) if system.id else None,
        ignored_errors + ignored_jdex_errors,
    )


def lint_all_systems(config: Config) -> dict[str, LintResults] | LintResults:
    """Given a valid jdlint config, lint all contained systems and return results."""
    if isinstance(config.system, ConfigSystem):
        if config.system.id:
            return {config.system.id: lint_system(config.linter, config.system)}
        return lint_system(config.linter, config.system)
    return {
        sysID: lint_system(config.linter, sys) for sysID, sys in config.system.items()
    }


def _pluralize(num: int, word: str, weird_plural: str | None = None) -> str:
    if num == 1:
        return f"{num!s} {word}"
    if weird_plural is None:
        return f"{num!s} {word}s"
    return f"{num!s} {weird_plural}"


def _print_results(results: LintResults) -> None:
    """Print lint results in a human-readable fashion; returns true if errors, false if none."""
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
        for location, root in results.roots.items():
            if root.errors:
                errs_by_type: dict[IssueType, list[Issue]] = {}
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


def load_jd_config(jd_path: Path) -> dict[str, JDConfigSystem]:
    """Load the official JD config format from a path."""
    as_text = Path.read_text(jd_path)
    try:
        jd_config = json.loads(as_text)
    except json.JSONDecodeError as e:
        err = JDConfigJsonError(jd_path, str(e))
        raise err from None
    if not isinstance(jd_config, dict):
        raise JDConfigFormatError(jd_path, "Top level was not an object.")
    if jd_config.get("version", None) != 1:
        raise JDConfigVersionError(jd_path)
    if "systems" not in jd_config:
        raise JDConfigMissingKeyError(jd_path, "systems")
    jd_sys_list = jd_config["systems"]
    if not isinstance(jd_sys_list, list):
        raise JDConfigTypeError(jd_path, "systems", "list", type(jd_sys_list).__name__)
    jd_systems: dict[str, JDConfigSystem] = {}
    for i, system in enumerate(jd_sys_list):
        if not isinstance(system, dict):
            raise JDConfigTypeError(
                jd_path,
                f"systems[{i}]",
                "object",
                type(system).__name__,
            )

        s = JDConfigSystem(jd_path, f"systems[{i}]", system)
        if s.id in jd_systems:
            # Duplicate system ID!
            err = JDConfigConflictError(
                jd_path,
                f"systems[{i}].sys",
                f"The id {s.id} was specified for more than one system!",
            )
            raise err
        if s.default and [v for v in jd_systems.values() if v.default]:
            err = JDConfigConflictError(
                jd_path,
                f"systems[{i}].default",
                "A previous system was already specified as the default!",
            )
            raise err
        jd_systems[s.id] = s

    return jd_systems


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
    parser.add_argument(
        "-p",
        "--pure",
        dest="pure",
        action="store_const",
        const=True,
        help="Ignore any environment configuration, e.g. JD_CONFIG or ~/.jd/config.json; useful if you want to fully specify configuration in jdlint.toml.",
    )

    args = parser.parse_args()

    jd_systems = {}
    if not args.pure:
        jd_env = os.getenv("JD_CONFIG")
        if not jd_env:
            jd_path = Path("~", ".jd", "config.json").expanduser()
        else:
            jd_path = Path(jd_env)
        if jd_path.is_file():
            jd_systems = load_jd_config(jd_path)

        elif jd_env:
            err = JDConfigMissingError(jd_path)
            raise err

    with Path.open(args.config, "rb") as config_file:
        config = Config(Path(args.config), jd_systems, tomllib.load(config_file))

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
    results = lint_all_systems(config)

    any_errors = False

    def _check_errors(res: LintResults) -> bool:
        return bool(
            (res.jdex and res.jdex.errors) or any(r.errors for r in res.roots.values()),
        )

    if isinstance(results, LintResults):
        any_errors = _check_errors(results)
        # Dump to JSON if asked
        if config.linter.json_output:
            json.dump(
                results,
                sys.stdout,
                cls=_EnhancedJSONEncoder,
            )
        else:
            _print_results(results)
    else:
        any_errors = any(_check_errors(sys) for sys in results.values())
        # Dump to JSON if asked
        if config.linter.json_output:
            json.dump(
                results,
                sys.stdout,
                cls=_EnhancedJSONEncoder,
            )
        else:
            for sys_id, res in results.items():
                print(  # noqa: T201
                    f"{'':=^80}\n{f'System: {f'{res.system.name} [{res.system.id}]' if res.system else sys_id}':^80}\n{'':=^80}\n",
                )
                any_errors = _print_results(res) or any_errors

    if any_errors:
        # Exit unhappily
        sys.exit(1)

    if not config.linter.json_output:
        print("Everything looks good!")  # noqa: T201
    sys.exit(0)
