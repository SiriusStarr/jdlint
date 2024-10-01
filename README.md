# jdlint

Ensure that your [Johnny Decimal](https://johnnydecimal.com/) system is neat and
clean.

* [jdlint](#jdlint)
  * [Installation/Requirements](#installationrequirements)
  * [Usage](#usage)
    * [With a JDex/Index](#with-a-jdexindex)
    * [Ignoring Files](#ignoring-files)
    * [Disabling Specific Rules](#disabling-specific-rules)
    * [I Am A Robot And Want Something Machine-Readable](#i-am-a-robot-and-want-something-machine-readable)
  * [File Errors](#file-errors)
    * [`AREA_DIFFERENT_FROM_JDEX`](#area_different_from_jdex)
    * [`AREA_NOT_IN_JDEX`](#area_not_in_jdex)
    * [`CATEGORY_DIFFERENT_FROM_JDEX`](#category_different_from_jdex)
    * [`CATEGORY_IN_WRONG_AREA`](#category_in_wrong_area)
    * [`DUPLICATE_AREA`](#duplicate_area)
    * [`DUPLICATE_CATEGORY`](#duplicate_category)
    * [`DUPLICATE_ID`](#duplicate_id)
    * [`FILE_OUTSIDE_ID`](#file_outside_id)
    * [`ID_DIFFERENT_FROM_JDEX`](#id_different_from_jdex)
    * [`ID_IN_WRONG_CATEGORY`](#id_in_wrong_category)
    * [`ID_NOT_IN_JDEX`](#id_not_in_jdex)
    * [`INVALID_AREA_NAME`](#invalid_area_name)
    * [`INVALID_CATEGORY_NAME`](#invalid_category_name)
    * [`INVALID_ID_NAME`](#invalid_id_name)
    * [`NONEMPTY_INBOX`](#nonempty_inbox)
  * [Why Doesn't This Check For-](#why-doesnt-this-check-for-)
  * [Acknowledgements](#acknowledgements)

## Installation/Requirements

Install a fairly recent version of [Python 3](https://www.python.org/downloads/)
(`jdlint` was developed using `3.11.8`).

That's it! There are no other dependencies.

## Usage

The script itself is executable (you should be able to just run `./jdlint.py`),
or you can explicitly point python at it, like `python3 jdlint.py`.

You'll need to pass the script the root folder of your JD-organized file system,
e.g.

```bash
./jdlint.py ~/Documents
```

### With a JDex/Index

If you have your JDex/Index stored as files, you can improve the number of
detected issues by passing that root path along as well, e.g.

```bash
./jdlint.py --jdex ~/"Knowledge/00.00 📇 System Index" ~/Documents
```

### Ignoring Files

You may have files outside of IDs that have to be there; if so, you can ignore
them, e.g.

```bash
./jdlint.py ~/Documents --ignore .stfolder .stignore
```

### Disabling Specific Rules

Maybe you disagree with a specific issue detected by this linter or have reason
to break the rules. If so, you can disable a rule, e.g.

```bash
./jdlint.py ~/Documents --disable NONEMPTY_INBOX
```

### I Am A Robot And Want Something Machine-Readable

Ask nicely for JSON output instead!

```bash
./jdlint.py ~/Documents --json
```

## File Errors

### `AREA_DIFFERENT_FROM_JDEX`

An area with a differently-named JDex entry, e.g.

```text
.
├── files
│   └── 00-09 Systme             <-- This is a typo, oops!
│       └── 01 System Stuff
│           ├── 01.00 An ID
│           ├── 01.02 A Name
│           └── 01.03 Another ID
└── jdex
    └── 00-09 System
        └── 01 System Stuff
            ├── 01.00 An ID.md
            ├── 01.02 A Name.md
            └── 01.03 Another ID.md
```

### `AREA_NOT_IN_JDEX`

An area without a corresponding JDex entry, e.g.

```text
.
├── files
│   ├── 00-09 System
│   │   └── 01 System Stuff
│   │       ├── 01.02 A Name
│   │       └── 01.03 Another ID
│   └── 10-19 Oops               <-- This area has no corresponding entry in the JDex/index
│       └── 11 Cat
│           └── 11.12 ID
└──jdex
    ├── 00.00 System.md
    ├── 01.00 System Stuff.md
    ├── 01.02 A Name.md
    ├── 01.03 Another ID.md
    ├── 11.00 Cat.md
    └── 11.12 ID.md
```

### `CATEGORY_DIFFERENT_FROM_JDEX`

A category with a differently-named JDex entry, e.g.

```text
.
├── files
│   └── 00-09 System
│       └── 01 System Stuf          <-- This is a typo, oops!
│           ├── 01.00 An ID
│           │   └── Other File
│           ├── 01.02 A Name
│           └── 01.03 Another ID
└── jdex
    └── 00-09 System
        └── 01 System Stuff
            ├── 01.00 An ID.md
            ├── 01.02 A Name.md
            └── 01.03 Another ID.md
```

### `CATEGORY_IN_WRONG_AREA`

A category that, by its number, has been put in the wrong area, e.g.

```text
.
└── 00-09 System
    ├── 01 System Stuff
    │   └── 01.00 An ID
    └── 11 Whoops       <-- This is in the wrong area
        └── 11.01 Inbox
```

### `DUPLICATE_AREA`

An area that has been used multiple times, e.g.

```text
.
├── 00-09 An Area           <-- 00-09 has been used twice!
│   └── 01 A Category
│       └── 01.00 An ID
└── 00-09 A Reuse           <-- 00-09 has been used twice!
    └── 02 Another Category
        └── 02.00 An ID
```

### `DUPLICATE_CATEGORY`

A category that has been used multiple times, e.g.

```text
.
└── 00-09 System
    ├── 01 A Category        <-- 01 has been used twice!
    │   └── 01.00 An ID
    └── 01 A Reuse           <-- 01 has been used twice!
        └── 01.02 Another ID
```

### `DUPLICATE_ID`

An ID that has been used multiple times, e.g.

```text
.
└── 00-09 System
    └── 01 System Stuff
        ├── 01.11 An ID
        └── 01.11 A Reuse <-- 01.11 has been used twice!
```

### `FILE_OUTSIDE_ID`

A file that is located somewhere higher up than in an ID folder, e.g.

```text
.
├── 00-09 System
│   ├── 01 System Stuff
│   │   ├── 01.00 An ID
│   │   └── File Outside Id   <--
│   └── File Outside Category <-- All of these should only be in IDs
└── File Outside Area         <--
```

Use the `--ignore FILE_NAME` option if you have files that *have* to be there,
e.g. `.stignore` is you use Syncthing.

### `ID_DIFFERENT_FROM_JDEX`

An ID with a differently-named JDex entry, e.g.

```text
.
├── files
│   └── 00-09 System
│       └── 01 System Stuff
│           ├── 01.00 An ID
│           ├── 01.02 A Naem     <-- This is a typo, oops!
│           └── 01.03 Another ID
└── jdex
    ├── 01.00 An ID.md
    ├── 01.02 A Name.md
    └── 01.03 Another ID.md
```

### `ID_IN_WRONG_CATEGORY`

An ID that, by its number, has been put in the wrong category, e.g.

```text
.
└── 00-09 System
    └── 01 System Stuff
        ├── 01.00 An ID
        └── 11.01 Whoops <-- This is in the wrong category
```

### `ID_NOT_IN_JDEX`

An ID without a corresponding JDex entry, e.g.

```text
.
├── files
│   └── 00-09 System
│       └── 01 System Stuff
│           ├── 01.00 An ID
│           ├── 01.02 Missing ID <-- This ID has no corresponding entry in the JDex/index
│           └── 01.03 Another ID
└── jdex
    ├── 01.00 An ID.md
    └── 01.03 Another ID.md
```

### `INVALID_AREA_NAME`

A directory was found at the area level that doesn't begin with `00-09` or the
like, e.g.

```text
.
├── 00-09 System
│   └── 01 System Stuff
│       └── 01.00 An ID
├── 10-18 Malformed     <-- This has numbers that were typo'd.
└── No ID               <-- This doesn't have numbers at all
```

### `INVALID_CATEGORY_NAME`

A directory was found at the category level that doesn't begin with `11` or the
like, e.g.

```text
.
└── 00-09 System
    ├── 01 System Stuff
    │   └── 01.00 An ID
    ├── 2 Malformed     <-- This has numbers that were typo'd.
    └── No ID           <-- This doesn't have numbers at all
```

### `INVALID_ID_NAME`

A directory was found at the ID level that doesn't begin with `11.12` or the
like, e.g.

```text
.
└── 00-09 System
    └── 01 System Stuff
        ├── 01.00 An ID
        ├── 01.1 Malformed <-- This has numbers that were typo'd.
        └── No ID          <-- This doesn't have numbers at all
```

### `NONEMPTY_INBOX`

An inbox (AC.01) that contains items, e.g.

```text
.
└── 01 System Stuff
    ├── 01.01 Inbox
    │   └── This is something you meant to sort that you never got around to...
    └── 01.11 An ID
```

## Why Doesn't This Check For-

Because I didn't think of it. Open an issue and maybe it will get added!

## Acknowledgements

This project has no formal affiliation with the Johnny Decimal system. The
license for said system may be found
[here](https://johnnydecimal.com/00-09-site-administration/01-about/01.02-licence/).
