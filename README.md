# jdlint

Ensure that your [Johnny Decimal](https://johnnydecimal.com/) system is neat and
clean.

* [jdlint](#jdlint)
  * [Installation/Requirements](#installationrequirements)
  * [Usage](#usage)
    * [With a JDex/Index](#with-a-jdexindex)
      * [JDex Formats](#jdex-formats)
      * [Alternative Layout for the Standard Zeros](#alternative-layout-for-the-standard-zeros)
    * [Ignoring Files](#ignoring-files)
    * [Disabling Specific Rules](#disabling-specific-rules)
    * [I Am A Robot And Want Something Machine-Readable](#i-am-a-robot-and-want-something-machine-readable)
  * [File Errors](#file-errors)
    * [`AREA_DIFFERENT_FROM_JDEX`](#area_different_from_jdex)
    * [`AREA_NOT_IN_JDEX`](#area_not_in_jdex)
    * [`CATEGORY_DIFFERENT_FROM_JDEX`](#category_different_from_jdex)
    * [`CATEGORY_IN_WRONG_AREA`](#category_in_wrong_area)
    * [`CATEGORY_NOT_IN_JDEX`](#category_not_in_jdex)
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
  * [JDex Errors](#jdex-errors)
    * [`JDEX_AREA_HEADER_DIFFERENT_FROM_AREA`](#jdex_area_header_different_from_area)
    * [`JDEX_AREA_HEADER_WITHOUT_AREA`](#jdex_area_header_without_area)
    * [`JDEX_CATEGORY_IN_WRONG_AREA`](#jdex_category_in_wrong_area)
    * [`JDEX_DUPLICATE_AREA`](#jdex_duplicate_area)
    * [`JDEX_DUPLICATE_AREA_HEADER`](#jdex_duplicate_area_header)
    * [`JDEX_DUPLICATE_CATEGORY`](#jdex_duplicate_category)
    * [`JDEX_DUPLICATE_ID`](#jdex_duplicate_id)
    * [`JDEX_FILE_OUTSIDE_CATEGORY`](#jdex_file_outside_category)
    * [`JDEX_ID_IN_WRONG_CATEGORY`](#jdex_id_in_wrong_category)
    * [`JDEX_INVALID_AREA_NAME`](#jdex_invalid_area_name)
    * [`JDEX_INVALID_CATEGORY_NAME`](#jdex_invalid_category_name)
    * [`JDEX_INVALID_ID_NAME`](#jdex_invalid_id_name)
  * [Why Doesn't This Check For-](#why-doesnt-this-check-for-)
  * [Acknowledgements](#acknowledgements)

## Installation/Requirements

Install a fairly recent version of
[Python 3](https://www.python.org/downloads/); `jdlint` is tested to work on
Python 3.10 and up. Python 3.9 and earlier is not supported.

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

#### JDex Formats

This supports three possible JDex formats:

* Single file, as specified [here](https://github.com/johnnydecimal/index-spec).
  Note that strict adherence to the spec is not checked, because I personally do
  not use this method and am lazy, so don't expect linter errors for your JDex
  if you use this format.
* Nested files in folders, e.g.

```text
.
└── 00-09 System
    └── 01 System Stuff
        ├── 01.02 A Name.md
        └── 01.03 Another ID.md
```

* Flat files, e.g.

```tree
.
├── 00.00 System Area Management.md
├── 01.00 System Stuff Category Management.md
├── 01.02 A Name.md
└── 01.03 Another ID.md
```

Note that in the flat case, `N0.00` is taken as the JDex entry for area `N0-N9`,
and `AC.00` is taken as the JDex entry for category `AC`.

In all cases, any `.md` file extension will be stripped, should one exist.

A trailing `area management` or `category management` or `index` will also be
stripped, if one exists, to derive the "canonical" name for the area/category.

For example:

* `10.00 Life Admin`
* `10.00 Life Admin.md`
* `10.00 Life Admin Area Management`
* `10.00 Life Admin Index`
* `10.00 Life Admin Area Management Index.md`

are all equivalent, and will lead to `jdlint` expecting an area named
`10-19 Life Admin` in your files.

#### Alternative Layout for the Standard Zeros

For a more complete treatment of this topic, see the original post
[here](https://forum.johnnydecimal.com/t/the-standard-zeros/1558/12).

This moves the expected area management zeros into the system management area.
For example, the management category for area `10-19` will be category `01`,
instead of the typical `10`. This increases the available number of categories
per area and makes greater use of the reserved `00-09` area.

To specify that you're using this format, pass `jdlint` the `--altzeros` flag.

This causes two changes in behavior if you are using the flat files JDex
structure:

* The linter will treat `10.00` as the note for category `10`, and `01.00` as
  the note for area `10-19`, etc.
* The area management notes (`0N.00`) will additionally create categories in the
  `00-09` area, for those standard zeros.
* The linter will check for optional "header" files. This is not an official
  Johnny Decimal thing, just something I use to visually separate notes in the
  JDex. They are named e.g. `10. Life Admin` for the `10-19 Life Admin` area.

  ![An image showing how `40. Improvement` nicely shows `20.00 Education` as nested under it.](images/header_note.png)

  If you don't use them, there will be no complaints from the linter; it just
  ensures their names stay in sync with the area if they do already exist.

### Ignoring Files

You may have files outside of IDs that have to be there; if so, you can ignore
them, e.g.

```bash
./jdlint.py ~/Documents --ignore .st*
```

This option supports some basic glob-style patterns. (It uses
[`PurePath.match()`](https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.match).)

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

These are errors that can be generated for your files. Some of them require you
passing your JDex via the `--jdex` argument to be detected.

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

### `CATEGORY_NOT_IN_JDEX`

A category without a corresponding JDex entry, e.g.

```text
.
├── files
│   └── 00-09 System
│       └── 01 System Stuff      <-- This category has no corresponding entry in the JDex
│           ├── 01.02 An ID
│           └── 01.03 Another ID
└── jdex
    ├── 00.00 System.md
    ├── 01.00 An ID.md
    └── 01.03 Another ID.md
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
        ├── 01.11 An ID   <-- 01.11 has been used twice!
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
├── files
│   └── 00-09 System
│       └── 01 System Stuff
│           ├── 01.02 A Naem     <-- This is a typo, oops!
│           ├── 01.03 Another ID
│           └── 01.04 An ID
└── jdex
    ├── 00.00 System.md
    ├── 01.00 System Stuff.md
    ├── 01.02 A Name.md
    ├── 01.03 Another ID.md
    └── 01.04 An ID.md
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

## JDex Errors

These are errors that are only generated with the `--jdex` argument and concern
the state of your JDex, not your organized files.

### `JDEX_AREA_HEADER_DIFFERENT_FROM_AREA`

An (optional) area header with a differently-named JDex entry, e.g.

```text
jdex
├── 00.00 System Area Management.md
├── 01.00 Life Admin Area Management.md
├── 01.03 Area Standard Zero.md
├── 10. Life Adminn.md                  <-- This is a typo, oops!
├── 10.00 Me, Myself, and I.md
└── 10.02 An ID.md
```

### `JDEX_AREA_HEADER_WITHOUT_AREA`

An (optional) area header without any corresponding JDex entry, e.g.

```text
jdex
├── 00.00 System Area Management.md
├── 01.00 Life Admin Area Management.md
├── 01.03 Area Standard Zero.md
├── 10. Life Admin.md
├── 10.00 Me, Myself, and I.md
├── 10.02 An ID.md
└── 20. Digital Stuff.md                <- There is no corresponding area
```

### `JDEX_CATEGORY_IN_WRONG_AREA`

A JDex category that, by its number, has been put in the wrong area, e.g.

```text
jdex
└── 00-09 System
    ├── 01 System Stuff
    │   └── 01.00 An ID
    └── 11 Whoops       <-- This is in the wrong area
        └── 11.01 Inbox
```

### `JDEX_DUPLICATE_AREA`

A JDex area that has been used multiple times, e.g.

```text
jdex
├── 00-09 An Area           <-- 00-09 has been used twice!
│   └── 01 A Category
│       └── 01.00 An ID
└── 00-09 A Reuse           <-- 00-09 has been used twice!
    └── 02 Another Category
        └── 02.00 An ID
```

### `JDEX_DUPLICATE_AREA_HEADER`

An (optional) area header that has been used multiple times, e.g.

```text
jdex
├── 00.00 System Area Management.md
├── 01.00 An Area.md
├── 01.03 Area Standard Zero.md
├── 10. An Area.md                   <-- These are both for 10-19
├── 10. A Reuse.md                   <-- These are both for 10-19
├── 10.00 Me, Myself, and I.md
└── 10.02 An ID.md
```

### `JDEX_DUPLICATE_CATEGORY`

A JDex category that has been used multiple times, e.g.

```text
jdex
└── 00-09 System
    ├── 01 A Category        <-- 01 has been used twice!
    │   └── 01.00 An ID
    └── 01 A Reuse           <-- 01 has been used twice!
        └── 01.02 Another ID
```

### `JDEX_DUPLICATE_ID`

A JDex ID that has been used multiple times, e.g.

```text
jdex
└── 00-09 System
    └── 01 System Stuff
        ├── 01.11 An ID   <-- 01.11 has been used twice!
        └── 01.11 A Reuse <-- 01.11 has been used twice!
```

### `JDEX_FILE_OUTSIDE_CATEGORY`

A file that is located at the area or category level in a nested JDex, e.g.

```text
jdex
├── 00-09 System
│   ├── 01 System Stuff
│   │   ├── 01.02 A Name.md
│   │   └── 01.03 Another ID.md
│   └── Nor here                <-- Both of these should only be in categories
└── Not here                    <--
```

### `JDEX_ID_IN_WRONG_CATEGORY`

A JDex ID that, by its number, has been put in the wrong category in a nested
structure, e.g.

```text
jdex
└── 00-09 System
    └── 01 System Stuff
        ├── 01.00 An ID
        └── 02.01 Whoops <-- This is in the wrong category
```

### `JDEX_INVALID_AREA_NAME`

A directory was found at the area level in the JDex that doesn't begin with
`00-09` or the like, e.g.

```text
jdex
├── 00-09 System
│   └── 01 System Stuff
│       └── 01.02 An ID
├── 10-18 Malformed     <-- This has numbers that were typo'd.
└── No ID               <-- This doesn't have numbers at all
```

### `JDEX_INVALID_CATEGORY_NAME`

A directory was found at the category level in the JDex that doesn't begin with
`11` or the like, e.g.

```text
jdex
└── 00-09 System
    ├── 01 System Stuff
    │   └── 01.02 An ID
    ├── 2 Malformed     <-- This has numbers that were typo'd.
    └── No ID           <-- This doesn't have numbers at all
```

### `JDEX_INVALID_ID_NAME`

A JDEx note was found at the ID level that doesn't begin with `11.12` or the
like, e.g.

```text
.
└── 00-09 System
    └── 01 System Stuff
        ├── 01.00 An ID
        ├── 01.1 Malformed <-- This has numbers that were typo'd.
        └── No ID          <-- This doesn't have numbers at all
```

## Why Doesn't This Check For-

Because I didn't think of it. Open an issue and maybe it will get added!

## Acknowledgements

This project has no formal affiliation with the Johnny Decimal system. The
license for said system may be found
[here](https://johnnydecimal.com/00-09-site-administration/01-about/01.02-licence/).
