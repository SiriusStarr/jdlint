# Changelog

* [Changelog](#changelog)
  * [`v2.0.1`](#v201)
  * [`v2.0.0`](#v200)
  * [`v1.0.1`](#v101)
  * [`v1.0.0`](#v100)

## `v2.0.1`

* 🐛 -- Improved handling of multiline comments in plaintext JDexes. Previously,
  commented-out IDs could be erroneously detected.

## `v2.0.0`

* This release brings support for essentially arbitrary systems. If you have the
  concept of an index, IDs, and files, it probably can be made to work for you.
* This is a much less "out of the box" solution now, since it relies on a config
  file that fully defines the format in use. There are pre-made example configs
  that should work mostly out of the box if your system is "normal", but they'll
  still need a bit of tweaking. (v1 is still available in the v1 branch if you'd
  rather keep using that, but it won't be developed further)
* The upside to this is the aforementioned support of basically any system. If
  it can't support yours, let me know, and we can probably make it work.
* Also, now you can easily, repeatably lint multiple different locations (notes,
  files, dropbox), with different ignore lists (and even different structures!)
  per location.
* Supports the plaintext and JSON standards defined by Johhny
  (https://github.com/johnnydecimal/index-spec), so if you keep your JDex in a
  database but can get them out in that format, you can still use it.
* JSON output still is a thing, but now also spits out your full system/index
  structure, if you'd like to ingest that for use in another tool. If there's
  some information that the tool doesn't yet return that would be helpful, let
  me know, because I probably have access to it and just need to add it.
* Use headers? Done, we can check that you don't put files there. Use WPs? We
  support it. ETE? Can do. No spaces? Sure. Something crazy like mine? Still
  works.
* More delightful printing of errors.

## `v1.0.1`

* 🚸 -- Group errors of the same type when printing, so the header and footer
  aren't unnecessarily repeated. This does not affect JSON output.

## `v1.0.0`

Initial release.
