# jdlint

Ensure that your [Johnny Decimal](https://johnnydecimal.com/) system is neat and clean.

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

## Why Doesn't This Check For-

Because I didn't think of it.  Open an issue and maybe it will get added!

## Acknowledgements

This project has no formal affiliation with the Johnny Decimal system.  The
license for said system may be found
[here](https://johnnydecimal.com/00-09-site-administration/01-about/01.02-licence/).
