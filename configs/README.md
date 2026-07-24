# jdlint.toml

* [jdlint.toml](#jdlinttoml)
  * [Introduction](#introduction)
  * [LAS/SBS](#lassbs)
  * ["SiriusStarr"](#siriusstarr)
  * [Formats](#formats)
    * [Literal Segments](#literal-segments)
    * [Variable Segments](#variable-segments)
      * [Numeric Segments](#numeric-segments)
      * [Wildcard Segments](#wildcard-segments)
    * [Bound Segments](#bound-segments)
    * [Segment Identifiers](#segment-identifiers)

## Introduction

This folder has some example configs for jdlint. They are (hopefully)
well-documented with comments and demonstrate the full range of capabilities.

You're strongly encouraged to read through the entirety of one of the configs

## LAS/SBS

[Partially-nested](./partially_nested_jdex.toml) should work mostly
out-of-the-box with the Life Admin System or Small Business System. You'll need
to set your paths, and there are one or two features that are turned on to
demonstrate the existence of certain options.

[Fully-nested](./fully_nested_jdex.toml) and [flat](./flat_jdex.toml) JDex's no
longer have "canon" downloads available for them, so they will likely need more
tweaking to make work.

[No JDex](./no_jdex.toml) is exactly what it says on the label; this is
generally an inferior mode to run jdlint in, since it many checks are
impossible, but it may be necessary depending on how you store your JDex.

## "SiriusStarr"

[SiriusStarr](./SiriusStarr.toml) is an example config for a very non-standard
system that showcases the ability of jdlint to adapt to flexible system
structures. Probably don't look at it if you're running a very standard JD
system, but if you're trying to fit an odd system of your own, it might be
helpful to look at.

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

* `0.10` -- (Too few leading digits; matches exactly 2)
* `999.10` -- (Too many leading digits; matches exactly 2)
* `19.710` -- (Too many digits after the decimal; matches exactly 1 followed by
  a 0)

#### Wildcard Segments

Wildcard segments match 1 or more of *any* character and are denoted by the `*`
symbol, followed by the name to bind the match to.

For example, `format = "12.35 /*Name/.md"` will match all of the following:

* `12.35` A.md
* `12.35` This is a long title woooooo.md
* `12.35` This title with 1946 digits and 🐦️ emoji.md

It will *not* match the following:

* `12.35A.md` -- (Missing the literal space before the variable segment)
* `12.35 A.m` -- (Missing the `d` on the end of the literal `.md`)
* `12.35 .md` -- (Wildcard segments must match at least 1 character, not
  nothing)

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

* `00-19 System` -- (`A` is bound to be `0` by the first match, which means the
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
