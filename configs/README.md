# jdlint.toml

* [jdlint.toml](#jdlinttoml)
  * [Introduction](#introduction)
  * [On TOML](#on-toml)
  * [JDex Structure](#jdex-structure)
    * [Notes on Disk](#notes-on-disk)
    * [Single File](#single-file)
    * [None](#none)
    * ["SiriusStarr"](#siriusstarr)
  * [Formats](#formats)
    * [Literal Segments](#literal-segments)
    * [Variable Segments](#variable-segments)
      * [Numeric Segments](#numeric-segments)
      * [Wildcard Segments](#wildcard-segments)
    * [Bound Segments](#bound-segments)
    * [Segment Identifiers](#segment-identifiers)
  * [Templates](#templates)
    * [Template Imports](#template-imports)
    * [Template Functionality](#template-functionality)
    * [Template Example](#template-example)
    * [Standard Templates](#standard-templates)
  * [Full Config Specification](#full-config-specification)
    * [`linter`](#linter)
    * [`system`](#system)
      * [`system.id`](#systemid)
      * [`system.name`](#systemname)
      * [`system.jdex`](#systemjdex)
        * [JDex `*.children` Tier](#jdex-children-tier)
        * [JDex `*.notes`](#jdex-notes)
        * [JDex `*.notes.ids`](#jdex-notesids)
      * [`system.roots`](#systemroots)
        * [Root `*.children` Tier](#root-children-tier)
      * [`system.default`](#systemdefault)
    * [`template`](#template)
      * [`system.imports`](#systemimports)
    * [`system.TEMPLATE_NAME`](#systemtemplate_name)

## Introduction

This folder has some example configs for jdlint. They are (hopefully)
well-documented with comments and demonstrate the full range of capabilities.

You're strongly encouraged to read through the entirety of one of the configs

Please note that you **must** edit whichever config you choose, as you'll need
to set the path to your files and JDex and such. These are things that vary from
computer to computer based on OS, personal preference, etc.

## On TOML

jdlint is configured using the TOML format, a human-readable configuration file
format. If you're unfamiliar with it, it will likely be helpful to read up on
its (simple) syntax a bit.

At a bare minimum, you will want to understand
[tables](https://toml.io/en/v1.1.0#table) and
[arrays of tables](https://toml.io/en/v1.1.0#array-of-tables), as their syntax
is slightly unintuitive/confusing. Make certain while editing the configuration
that you use the correct number of square brackets: `[name]` to specify a single
thing vs `[[name]]` to specify one thing in a list; if you get an error like
"expected a list, got a dict", you probably messed this up.

Similarly, if you get errors telling you that you can't overwrite values, you
probably have an extra level of nesting. For example,

```toml
[[a.children.children]]
something = 0
[[a.children.children]]
something = 1
```

will throw an error about being unable to overwrite a value, if you haven't
defined

```toml
[[a.children]]
```

before it, since each of those tries to implicitly create its ancestors.

## JDex Structure

### Notes on Disk

[Partially-nested](./partially_nested_jdex.toml) should work mostly
out-of-the-box with the Life Admin System or Small Business System. You'll need
to set your paths if they're different (e.g. you don't use emoji, or your root
isn't at `~/Documents`), and there are one or two features that are turned on to
demonstrate the existence of certain options.

[Fully-nested](./fully_nested_jdex.toml) and [flat](./flat_jdex.toml) JDexes no
longer have "canon" downloads available for them, so they will likely need more
tweaking to make work.

### Single File

jdlint supports the official index specification as defined
[here](https://github.com/johnnydecimal/index-spec).

[JSON JDex](./json_jdex.toml) and [Plaintext JDex](./plaintext_jdex.toml)
demonstrate loading from (respectively) the JSON and plaintext standards.

If you have your JDex stored in e.g. some database, but are capable of getting
them exported to the JSON standard, this will allow you to still use jdlint.

Note that this format is extremely restrictive to the exact standard, as the
standard lacks expressiveness for alternative formats.

### None

[No JDex](./no_jdex.toml) is exactly what it says on the label; this is
generally an inferior mode to run jdlint in, since it many checks are
impossible, but it may be necessary depending on how you store your JDex.

### "SiriusStarr"

[SiriusStarr](./SiriusStarr.toml) is an example config for a very nonstandard
system that showcases the ability of jdlint to adapt to flexible system
structures. Probably don't look at it if you're running a very standard JD
system, but if you're trying to fit an odd system of your own, it might be
helpful to look at, as well as demonstrating more advanced usage to e.g. ensure
standardized naming of the standard zeros.

## Formats

This section provides an overview of the simple markup used for defining the
format of folders and notes by jdlint. A format can consist of three different
segments: literal segments, variable segments, and bound segments.

### Literal Segments

Literal segments match exactly what you type. For example, the format
`format = "My Note.md"` will match a file or folder called exactly `My Note.md`
and nothing else.

### Variable Segments

Variable segments, on the other hand, can match a range of values. They are
delimited with `/`, since the slash character cannot appear in filenames
anyways. There are two different kinds, numeric segments and wildcard segments.

#### Numeric Segments

Numeric Segments match an exact number of digits and are denoted by one or more
`#` symbols, followed by the name to bind the match to.

For example, `format = "/##AC/./#Tens/0"` will match all of the following:

* `00.10`
* `19.70`
* `99.20`

It will *not* match the following:

* `0.10` – (Too few leading digits; matches exactly 2)
* `999.10` – (Too many leading digits; matches exactly 2)
* `19.710` – (Too many digits after the decimal; matches exactly 1 followed by
  a 0)

#### Wildcard Segments

Wildcard segments match 1 or more of *any* character and are denoted by the `*`
symbol, followed by the name to bind the match to.

For example, `format = "12.35 /*Name/.md"` will match all of the following:

* `12.35 A.md`
* `12.35 This is a long title woooooo.md`
* `12.35 This title with 1946 digits and 🐦️ emoji.md`

It will *not* match the following:

* `12.35A.md` – (Missing the literal space before the variable segment)
* `12.35 A.m` – (Missing the `d` on the end of the literal `.md`)
* `12.35 .md` – (Wildcard segments must match at least 1 character, not nothing)

**Note:** If you know regex, this is equivalent to `.+?` under the hood, i.e.
lazily matching one or more character.

### Bound Segments

Bound segments refer to variable segments that were defined earlier in the
format **or in an ancestor format** (e.g. a parent folder). They match exactly
the content that matched the variable segment the first time. They are delimited
with `/` and denoted by `=` followed by the alphabetic name of the variable
segment they reference.

For example, you can define an area folder with
`format = "/#A/0-/=A/9 /*Name/"`, which will match all of the following:

* `00-09 System`
* `90-99 Archive Stuff`
* `10-19 Life Admin`

It will *not* match the following:

* `00-19 System` – (`A` is bound to be `0` by the first match, which means the
  `1` does not then match it)

Alternately, assuming we are defining a child folder of the above area format,
we could define a category folder with: `format = "/=A//#C/ /*CategoryName/"`
Note that this refers to the variable segment `A`, which isn't defined in this
format but rather in its ancestor. This would then match:

```text
.
├── 00-09 System
│   └── 01 System Stuff
└── 10-19 Life
    └── 11 Me, Myself, & I
```

It will *not* match:

```text
.
├── 00-09 System
│   └── 11 Me, Myself, & I    <--- "A" is bound to 0
└── 10-19 Life
    └── 01 System Stuff       <--- "A" is bound to 1
```

### Segment Identifiers

The names used to define variable segments and refer to them in bound segments
must consist only of letters. They may not be reused, since it would be
ambiguous what a bound segment referred to then (this will throw an error if you
try).

## Templates

`jdlint` supports some limited templating to reduce verbosity of repeated
structure. Please note that these are an advanced feature and can easily lead to
very confusing error messages if you are not careful.

Templates can be used anywhere that expects tiers of folders or notes, namely
`jdex`, `system.default`, `system.roots`, or anywhere within their children.

Templates are also valid **within templates**, allowing you to easily make a
copy of a template with one key overridden or the like. Infinitely recursive
templates are, of course, an error (though you can use a template in its own
descendants, if it does not cause infinite recursion).

### Template Imports

The key `imports` is reserved and cannot be used as a template name. Instead, it
takes a list of TOML files to import for templates. Templates imported in this
way are equivalent to those defined locally in the file. In imported files,
templates should be defined as top-level keys, without the `template` prefix. If
a template is defined with the same name in multiple imports, the earlier in the
list takes precedence. If a template is defined in imports and also locally, the
local definition takes precedence.

Note that **imports with relative paths are resolved relative to the config
file**, not relative to the current working directory.

### Template Functionality

A template is just a TOML table with any number of keys. `jdlint` does not
eagerly check it for validity (nor for excess keys). As such, you may use a
template in a location even if it contains keys that would not be valid there
(such as defining `notes` in a system folder).

To use a template, simply set the key `template` to the name of the desired
template. Any keys not specified will be checked from the template instead. This
allows you to override template keys at the site they are applied.

Note that **variable segment binds within templates will be automatically
converted to bound segments if their identifier has already been bound** in an
ancestor (rather than this being an error).

You may also set the key `bind` alongside any template to specify how variable
segments within the template should be reassigned to literal values.

### Template Example

```toml
[system]
[[system.roots]]
name = "Files"
path = "~/Documents"

[system.jdex]
path = "~/JDex"
template = "standard_jdex"

[system.default]
template = "standard_system"

[template]
imports = ["./standard_templates.toml"]

[template.standard_jdex]
[[template.standard_jdex.children]]
template = "area_folder"

[[template.standard_jdex.children.children]]
template = "category_folder"
children = [] # No ID folders in the JDex; this overrides the usual `children` key

[template.standard_system]
[[template.standard_system.children]]
template = "area_folder"

[[template.standard_system.children.children]]
# It doesn't matter that `notes` is defined, it will just be ignored
template = "category_folder"
```

where `standard_templates.toml` contains:

```toml
[area_folder]
name = "Area"
format = "/#A/0-/=A/9 /*Area/"
id = "/=A/0-/=A/9"

[category_folder]
name = "Category"
format = "/=A//#C/ /*Category/"
id = "/=A//=C/"
children = [{ template = "id_folder" }]
notes = [{ template = "area_note" }, { template = "category_note" }, { template = "id_note" }]

[id_folder]
name = "ID"
format = "/=A//=C/./##ID/ /*IDName/"
id = "/=A//=C/./=ID/"
can_be_file = true
allow_arbitrary_contents = true

[area_note]
name = "JDex Area Note"
format = "/=A/0.00 /*Name/.md"

[[area_note.ids]]
id = "/=A/0-/=A/9"
entry = "/=A/0-/=A/9 /=Name/"

[[area_note.ids]]
id = "/=A/0"
parent = "/=A/0-/=A/9"
entry = "/=A/0 /=Name/"

[[area_note.ids]]
id = "/=A/0.00"
parent = "/=A/0"
entry = "/=A/0.00 /=Name/"

[category_note]
name = "JDex Category Note"
format = "/=A//=C/.00 /*Name/.md"

[[category_note.ids]]
id = "/=A//=C/"
parent = "/=A/0-/=A/9"
entry = "/=A//=C/ /=Name/"

[[category_note.ids]]
id = "/=A//=C/.00"
parent = "/=A//=C/"
entry = "/=A//=C/.00 /=Name/"

[id_note]
name = "JDex Id Note"
format = "/=A//=C/./##ID/ /*Name/.md"

[[id_note.ids]]
id = "/=A//=C/./=ID/"
parent = "/=A//=C/"
entry = "/=A//=C/./=ID/ /=Name/"
```

### Standard Templates

Some generally-useful "standards-compliant" templates are provided in
[standard_templates.toml](./standard_templates.toml); feel free to use these in
your own configs, but make certain you understand what's being specified in
them.

If you have additions/corrections to these, please make a PR or open an issue.

## Full Config Specification

This section describes all available keys that can be specified; as always,
refer to the example configs if something is confusing.

### `linter`

General linter behavior.

* `linter.disable_rules` – A (default empty) list of strings that are the names
  of rules to not report errors for. Names of rules are in SCREAMING_SNAKE_CASE
  and are all listed in [the readme](../README.md). Note that the total number
  of ignored errors *is* reported, so you won't forget about them entirely.
  Ignored errors will not cause the script to exit 1 instead of 0 (don't worry
  about what that means if you don't understand).
* `linter.json_output` – Boolean, defaults to false. If true, report in
  machine-readable JSON instead of printing results. If you don't already know
  why you'd want that, you don't want it.
* `linter.ignore_environment` – Boolean, defaults to false. If true, ignore any
  [JD configuration](https://johnnydecimal.com/jdhq/configuration) present.
* `linter.ignore` – A (default empty) list of strings to ignore as files or
  folders across the JDex and all locations. Supports glob patterns, so you can
  do `"*.jpg"` to ignore all files that end with `.jpg`, for example. (It uses
  [`PurePath.match()`](https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.match)
  under the hood, so refer to that for details.)

### `system`

Configuration of your exact JD system.

Note that this can either be a single object *or* a list of systems, depending
on whether you are linting multiple systems or not. In general, you should
prefer it being a list, but the single object is provided for backwards
compatibility.

#### `system.id`

The ID of the system. Optional when specifying only a single system. This ID
must match one specified via the
[JD configuration standard](https://johnnydecimal.com/jdhq/configuration) if you
are using it.

#### `system.name`

The name/description of the system. Optional when specifying only a single
system.

#### `system.jdex`

Configuration for the JDex of your system. This whole section can be omitted if
you don't have one, though you'll lose the ability to check for many types of
errors.

* `system.jdex.path` – A string, specifying the path to the JDex. If you have a
  JSON or plaintext JDex (per
  [the standard](https://github.com/johnnydecimal/index-spec)), this can just be
  the path to it, and you can leave the rest of `system.jdex` empty except for
  `system.jdex.entry`. If you use notes, this should be the path to where that
  structure begins.
* `system.jdex.entry` – If and only if you have a single-file JDex, this format
  specifies how to build an expected entry name from the information in the
  JDex. Two bound segments are available, `/=id/` and `/=title`. Typically, it
  should be `"/=id/ /=title/"`, but you may use this to e.g. replace the space
  that normally comes between an ID and its title with an underscore by setting
  it to `"/=id/_/=title/"`.
* `system.jdex.ignore` – Like `linter.ignore`, but only for the JDex structure.
  You might want this to be `[".obsidian", ".trash"]`, for example. Not relevant
  to single file JDexes.
* `system.jdex.note_extension` – A string to append to all `*.notes.format`
  within the JDex. This is optional, but allows reusing the same formats for
  folders and notes. Note that this extension will also be stripped off when
  generating converting filenames to an `entry`, e.g. `11.01 Inbox.md` will
  create `11.01 Inbox`.
* `system.jdex.children` – A list of top-level folders expected in the JDex; see
  below for the expected format. Not relevant to single file JDexes.
* `system.jdex.notes` – A list of top-level notes expected in the JDex; see
  below for the expected format. Not relevant to single file JDexes.
* `system.jdex.template` – Optionally, a string specifying a template to apply.
* `system.jdex.bind` – A table with keys that are
  [segment identifiers](#segment-identifiers) and values that are strings to
  bind them to.

##### JDex `*.children` Tier

This is a "level" of folder in the JDex, e.g. Areas.

* `*.children.allow_arbitrary_contents` – Boolean, default false. If false,
  jdlint will report anything within this tier of folders that does not match
  either its `.children` or `.notes`. Set this to true if you expect the folder
  to contain unstructured/arbitrary stuff (like a terminal ID folder).
* `*.children.children` – An (empty by default) list of more folder tiers
  expected within this folder; for example, if you're defining an area folder at
  `system.jdex.children`, `system.jdex.children.children` should define category
  folders.
* `*.children.notes` – An (empty by default) list of files expected within this
  folder; these files are what actually "create" known IDs in the system. Note
  that, despite being called "notes", the only requirement is that they be
  files.
* `*.children.name` – A string that specifies what to call this level of folder
  in error messages.
* `*.children.format` – A string that specifies the expected format of the
  folders at this tier. See [formats](#formats) for details.
* `*.children.forbidden` – A boolean, default false. If true, forbid the
  existence of anything that matches this format, reporting its existence as an
  error. You can do this to define, for example, how a standard zero should
  *not* be named.
* `*.children.template` – Optionally, a string specifying a template to apply.
* `*.children.bind` – A table with keys that are
  [segment identifiers](#segment-identifiers) and values that are strings to
  bind them to.

##### JDex `*.notes`

This specifies a format of notes in the JDex that define IDs. Note that a note
can define multiple IDs.

* `*.notes.name` – A string that specifies what to call these notes in error
  messages.
* `*.notes.format` – A string that specifies the expected format of the notes.
  See [formats](#formats) for details.
* `*.notes.forbidden` – A boolean, default false. If true, forbid the existence
  of anything that matches this format, reporting its existence as an error. You
  can do this to define, for example, how a standard zero should *not* be named.
* `*.notes.id`, `*.notes.entry`, `*.notes.parent` – Optional. If set, these
  behave identically as if they were a single entry in `*.notes.ids`.
* `*.notes.ids` – A list of IDs that this note "creates" (i.e. specifies as
  known to exist). This usually should just be one, but some notes (`10.00`, for
  example) might create e.g. an Area ID `10-19`, a Category ID `10`, and an ID
  `10.00`.
* `*.notes.template` – Optionally, a string specifying a template to apply.
* `*.notes.bind` – A table with keys that are
  [segment identifiers](#segment-identifiers) and values that are strings to
  bind them to.

##### JDex `*.notes.ids`

* `*notes.ids.id` – A string that specifies the ID created by the note, e.g.
  `"/=A//=C/./=ID/"` See [formats](#formats) for details.
* `*.notes.ids.entry` – A string that specifies the entry (expected file/folder
  name) created by the note, e.g. `"/=A//=C/./=ID/ /=Name/"`. See
  [formats](#formats) for details. If not specified, the filename is used
  instead, with `note_extension` stripped if it has been set.
* `*.notes.ids.parent` – A string that specifies the ID this ID is nested
  *under*. For instance, for the ID `"/=A//=C/./=ID/"`, its parent should be
  `"/=A//=C/"`. This can be used to detect orphans, e.g. IDs that are missing a
  category, or work packages that reference an ID that doesn't exist.
* `*.ids.template` – Optionally, a string specifying a template to apply.
* `*.ids.bind` – A table with keys that are
  [segment identifiers](#segment-identifiers) and values that are strings to
  bind them to.

#### `system.roots`

A list of root directories to check. These contain your actual "stuff".

* `system.roots.name` – A string that specifies the name to refer to this root
  by in error messages and such.
* `system.roots.path` – A string that specifies the path to the root of the,
  well, of the root. This is the folder in which jdlint will begin confirming
  the structure, e.g. `"~/Documents"`.
* `system.roots.ignore` – Like `linter.ignore`, but only for this root. You
  might want this to be `[".stfolder"]` if you use Syncthing, for example
* `system.roots.children` – A list of top-level folders expected in this root;
  see below for the expected format.
* `system.roots.template` – Optionally, a string specifying a template to apply.
* `system.roots.bind` – A table with keys that are
  [segment identifiers](#segment-identifiers) and values that are strings to
  bind them to.

##### Root `*.children` Tier

This is a "level" of folder in the root, e.g. Areas.

* `*.children.allow_arbitrary_contents` – Boolean, default false. If false,
  jdlint will report anything within this tier of folders that does not match
  its `.children`. Set this to true if you expect the folder to contain
  unstructured/arbitrary stuff (like a terminal ID folder).
* `*.children.children` – An (empty by default) list of more folder tiers
  expected within this folder; for example, if you're defining an area folder at
  `system.roots.children`, `system.roots.children.children` should define
  category folders.
* `*.children.name` – A string that specifies what to call this level of folder
  in error messages.
* `*.children.format` – A string that specifies the expected format of the
  folders at this tier. See [formats](#formats) for details.
* `*children.id` – A string that specifies the ID of this folder, e.g.
  `"/=A//=C/./=ID/"`. jdlint will check that a corresponding JDex entry exists.
  See [formats](#formats) for details.
* `*.children.entry` – A string that specifies the JDex entry (ID and name)
  expected by this folder, e.g. `"/=A//=C/./=ID/ /=Name/"`. jdlint will check
  that a corresponding JDex entry exists. See [formats](#formats) for details.
  If not specified, the filename is used instead.
* `*.children.forbidden` – A boolean, default false. If true, forbid the
  existence of anything that matches this format, reporting its existence as an
  error. You can do this to define, for example, how a standard zero should
  *not* be named.
* `*.children.can_be_file` – Boolean, default false. If false, jdlint will
  report any files that match this format as errors; set it to true if you want
  to e.g. allow terminal IDs that are files along with folders.
* `*.children.no_jdex_entry` – Boolean, default false. If false, jdlint will
  report as an error if you do not have a matching entry for this ID defined in
  the JDex. Set it to true if you happen to just have a folder that you don't
  care about matching to an ID (e.g. maybe `W0000-W9999 Work Packages`).
* `*.children.template` – Optionally, a string specifying a template to apply.
* `*.children.bind` – A table with keys that are
  [segment identifiers](#segment-identifiers) and values that are strings to
  bind them to.

#### `system.default`

Configuration for the folder structure of your system. This section applies to
all roots that do not specify their own `.children`. This can be omitted if you
are just going to specify the children of each root separately.

* `system.default.children` – A list of top-level folders expected in all roots
  that don't specify their own; this follows the same format as the
  root-specific children specified above.
* `system.default.template` – Optionally, a string specifying a template to
  apply.
* `system.default.bind` – A table with keys that are
  [segment identifiers](#segment-identifiers) and values that are strings to
  bind them to.

### `template`

Optionally, templates that may be used.

#### `system.imports`

A list of files to import the top-level keys of as templates; this is reserved
and cannot be used as a template name.

### `system.TEMPLATE_NAME`

Defining this creates the template `TEMPLATE_NAME`.

* `system.TEMPLATE_NAME.template` – Optionally, a string specifying a template
  to apply.
* `system.TEMPLATE_NAME.bind` – A table with keys that are
  [segment identifiers](#segment-identifiers) and values that are strings to
  bind them to.
* `system.TEMPLATE_NAME.*` – Any keys defined here are what is copied to the
  location a template is applied; note that extra keys will just be ignored, so
  it's okay to specify otherwise invalid keys.
