# jdlint [N14.0001]

Ensure that your [Johnny Decimal](https://johnnydecimal.com/) system is neat and
clean.

* [jdlint \[N14.0001\]](#jdlint-n140001)
  * [Installation/Requirements](#installationrequirements)
  * [Usage](#usage)
  * [Config File](#config-file)
  * [Ignoring Files](#ignoring-files)
  * [Disabling Specific Rules](#disabling-specific-rules)
  * [I Am a Robot and Want Something Machine-Readable](#i-am-a-robot-and-want-something-machine-readable)
  * [Errors](#errors)
    * [`ARBITRARY_CONTENT_WHERE_NOT_ALLOWED`](#arbitrary_content_where_not_allowed)
    * [`DUPLICATE_ID`](#duplicate_id)
    * [`EMPTY_FOLDER`](#empty_folder)
    * [`ENCOUNTERED_FORBIDDEN_FOLDER`](#encountered_forbidden_folder)
    * [`FILE_WHERE_FOLDER_EXPECTED`](#file_where_folder_expected)
    * [`FOLDER_SHOULD_BE_EMPTY`](#folder_should_be_empty)
    * [`ID_NOT_IN_JDEX`](#id_not_in_jdex)
    * [`ID_DIFFERENT_FROM_JDEX`](#id_different_from_jdex)
  * [JDex Errors](#jdex-errors)
    * [`JDEX_ARBITRARY_CONTENT_WHERE_NOT_ALLOWED`](#jdex_arbitrary_content_where_not_allowed)
    * [`JDEX_DUPLICATE_ID`](#jdex_duplicate_id)
    * [`JDEX_EMPTY_FOLDER`](#jdex_empty_folder)
    * [`JDEX_ENCOUNTERED_FORBIDDEN_FOLDER`](#jdex_encountered_forbidden_folder)
    * [`JDEX_ENCOUNTERED_FORBIDDEN_NOTE`](#jdex_encountered_forbidden_note)
    * [`JDEX_FILE_WHERE_FOLDER_EXPECTED`](#jdex_file_where_folder_expected)
    * [`JDEX_FOLDER_WHERE_NOTE_EXPECTED`](#jdex_folder_where_note_expected)
  * [Does This Modify My Files?](#does-this-modify-my-files)
  * [Why Doesn't This Check For-](#why-doesnt-this-check-for-)
  * [This Doesn't Work with My System Because-](#this-doesnt-work-with-my-system-because-)
  * [Acknowledgments](#acknowledgments)

## Installation/Requirements

Install a fairly recent version of
[Python 3](https://www.python.org/downloads/); `jdlint` is tested to work on
Python 3.11 and up.

That's it! There are no other dependencies.

`jdlint` should work on Linux, macOS, or Windows.

## Usage

The script itself is executable (you should be able to just run `./jdlint.py`),
or you can explicitly point python at it, like `python3 jdlint.py`.

You'll need to provide it wit a config file. By default, it looks for
`jdlint.toml` in the working directory; you may specify a different config file
with the `-c` flag, e.g.

```bash
./jdlint.py -c ~/my_jdlint_config.toml
```

Everything the script needs is specified in the config file.

## Config File

Several config files are provided in this repository, matching the various
JDex/JD standards. You can of course customize it to your liking.

It's recommended you read the [Config README](./configs/README.md) for
information on the format, and check out the provided example configs in that
folder, which are (hopefully) well-documented. If you have questions/need help,
please feel free to poke me on the JD Discord.

## Ignoring Files

If you wish to ignore files/folders, patterns can be added globally to
`linter.ignore`, to a single root's `.ignore`, or to `system.jdex.ignore`.

Additionally, you can ignore them just for one run with:

```bash
./jdlint.py --ignore .st*
```

This option may be specified more than once.

This option supports some basic glob-style patterns. (It uses
[`PurePath.match()`](https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.match).)

## Disabling Specific Rules

If you wish to disable a specific rule, it can be added globally to
`linter.disable_rules`.

Additionally, you can ignore them just for one run with:

```bash
./jdlint.py --disable DUPLICATE_ID
```

This option may be specified more than once.

## I Am a Robot and Want Something Machine-Readable

Either set `linter.json_output = true` in the config file, or force JSON output
just once with the flag:

```bash
./jdlint.py --json
```

Note that these JSON results additionally contain complete information about the
structure of your system that jdlint had to scan, if that information if of use
to you. This structure only returns portions of the system that are at least
possibly valid; it will not return forbidden files/folders, or files where
folders are required, for example.

## Errors

These are errors that can be generated for your files; some of them may require
the JDex to determine.

### `ARBITRARY_CONTENT_WHERE_NOT_ALLOWED`

A file or folder was found that didn't match you specified format, e.g.

```text
.
├── 10-19 Life
│   ├── 11 Me, Myself, & I
│   │   ├── 11.11 Me
│   │   ├── 11.12 Myself
│   │   └── Not An Id       <-- These don't belong here
│   └── 21 You              <-- These don't belong here
└── Stuff                   <-- These don't belong here
```

### `DUPLICATE_ID`

An ID that has been used multiple times, e.g.

```text
.
├── 00-09 System             <-- 00-09 has been used twice!
│   ├── 01 System Stuff        <-- 01 has been used twice!
│   │   ├── 01.11 An ID          <-- 01.11 has been used twice!
│   │   └── 01.11 A Reuse        <-- 01.11 has been used twice!
│   └── 01 A Reuse             <-- 01 has been used twice!
│       └── 01.02 Another ID
└── 00-09 A Reuse            <-- 00-09 has been used twice!
    └── 02 Another Category
        └── 02.00 An ID
```

### `EMPTY_FOLDER`

A completely empty folder was found; you shouldn't have folders that clutter
things up if they aren't actually serving a purpose.

```text
.
├── 00-09 System
│   ├── 01 System Stuff
│   │   └── 01.11 Empty    <-- These are all empty folders (just suppose there's no content it here)
│   └── 02 Empty Category  <-- These are all empty folders
└── 10-19 Empty Area       <-- These are all empty folders
```

### `ENCOUNTERED_FORBIDDEN_FOLDER`

A folder that was specified as forbidden in the config was encountered. (These
can be used to ensure that naming schemes are followed.)

```text
.
└── 10-19 Life
    └── 11 Me, Myself, & I
        ├── 11.01 Meh         <-- This should be called AC.01 Inbox
        └── 11.11 Me
```

### `FILE_WHERE_FOLDER_EXPECTED`

A file was found with the name of something that should have been a folder.

```text
.
└── 10-19 Life
    ├── 11 Me, Myself, & I
    │   ├── 11.11 Me
    │   ├── 11.12 Myself
    │   └── 11.13 I
    └── 12 You              <-- This is a file that looks like a category folder
```

### `FOLDER_SHOULD_BE_EMPTY`

A folder that should be empty per the config (e.g. inboxes and headers) wasn't.

```text
.
└── 10-19 Life
    └── 11 Me, Myself, & I
        ├── 11.01 Inbox       <-- These shouldn't have files in them
        │   └── Some file
        ├── 11.10 ■ The Me's  <-- These shouldn't have files in them
        │   └── Some file
        └── 11.11 Me
```

### `ID_NOT_IN_JDEX`

An ID without a corresponding JDex entry, e.g.

```text
.
├── files
│   └── 00-09 System              <-- This Area has no corresponding entry in the JDex
│       └── 01 System Stuff       <-- This Category has no corresponding entry in the JDex
│           ├── 01.02 Missing ID  <-- This ID has no corresponding entry in the JDex
│           └── 01.03 Another ID
└── jdex
    └── 01.03 Another ID.md
```

### `ID_DIFFERENT_FROM_JDEX`

An ID with a differently-named JDex entry, e.g.

```text
├── files
│   └── 00-09 Systm               <-- This is a typo, oops!
│       └── 01 System Stuf        <-- This is a typo, oops!
│           ├── 01.02 A Naem      <-- This is a typo, oops!
│           ├── 01.03 Another ID
│           └── 01.04 An ID
└── jdex
    ├── 00.00 System.md
    ├── 01.00 System Stuff.md
    ├── 01.02 A Name.md
    ├── 01.03 Another ID.md
    └── 01.04 An ID.md
```

## JDex Errors

These are errors that are only generated about the state of your JDex, not your
files.

    | JDexIssueEncounteredForbiddenFolder
    | JDexIssueEncounteredForbiddenNote

### `JDEX_ARBITRARY_CONTENT_WHERE_NOT_ALLOWED`

A file or folder was found that didn't match you specified format, e.g.

```text
.
├── 10-19 Life
│   ├── 11 Me, Myself, & I
│   │   ├── 11.11 Me.md
│   │   ├── 11.12 Myself.md
│   │   └── Not An Id.md    <-- These don't belong here
│   └── 21 You              <-- These don't belong here
└── Stuff                   <-- These don't belong here
```

### `JDEX_DUPLICATE_ID`

An ID that has been used multiple times, e.g.

```text
.
├── 01.11 An ID.md     <-- 01.11 has been used twice!
└── 01.11 A Reuse.md   <-- 01.11 has been used twice!
```

### `JDEX_EMPTY_FOLDER`

A completely empty folder was found; you shouldn't have folders that clutter
things up if they aren't actually serving a purpose.

```text
.
├── 00-09 System
│   ├── 01 System Stuff
│   │   └── 01.11 Me.md
│   └── 02 Empty Category  <-- These are all empty folders
└── 10-19 Empty Area       <-- These are all empty folders
```

### `JDEX_ENCOUNTERED_FORBIDDEN_FOLDER`

A folder that was specified as forbidden in the config was encountered. (These
can be used to ensure that naming schemes are followed.)

```text
.
└── 10-19 Life
    └── 11 Me, Myself, & I
        └── 11.00 Meh         <-- This should be called AC.00 Index
            └── 11.11 Me.md
```

### `JDEX_ENCOUNTERED_FORBIDDEN_NOTE`

A note that was specified as forbidden in the config was encountered. (These can
be used to ensure that naming schemes are followed.)

```text
.
└── 10-19 Life
    └── 11 Me, Myself, & I
        ├── 11.01 Meh.md         <-- This should be called AC.01 Inbox
        └── 11.11 Me.md
```

### `JDEX_FILE_WHERE_FOLDER_EXPECTED`

A file was found with the name of something that should have been a folder.

```text
.
└── 10-19 Life
    ├── 11 Me, Myself, & I
    │   ├── 11.11 Me.md
    │   ├── 11.12 Myself.md
    │   └── 11.13 I.md
    └── 12 You              <-- This is a file that looks like a category folder
```

### `JDEX_FOLDER_WHERE_NOTE_EXPECTED`

A folder was found with the name of something that should have been a file.

```text
.
└── 10-19 Life
    ├── 11 Me, Myself, & I
        ├── 11.11 Me.md
        ├── 11.12 Myself.md
        └── 11.13 I.md             <-- This is a file that looks like a category folder
            └── Some file
```

## Does This Modify My Files?

No. jdlint makes no changes to your files; you have to fix the problems it finds
yourself. We also think that's a good thing.

## Why Doesn't This Check For-

Because we didn't think of it. Open an issue and maybe it will get added.

## This Doesn't Work with My System Because-

Open an issue, and if it's reasonable, we can try to support it.

## Acknowledgments

This project has no formal affiliation with the Johnny Decimal system. The
license for said system may be found
[here](https://johnnydecimal.com/support/about-legal/licence/).
