# Changelog

* [Changelog](#changelog)
  * [`v3.1.0`](#v310)
  * [`v3.0.0`](#v300)
  * [`v2.0.1`](#v201)
  * [`v2.0.0`](#v200)
  * [`v1.0.1`](#v101)
  * [`v1.0.0`](#v100)

## `v3.1.0`

* ✨ – Templates! Make your configs shorter. My personal config got ~45% shorter
  (and way easier to read), while actually becoming more thorough. Do note that
  these should be considered an "advanced" feature; make sure you understand how
  configs work before using them, as it's very easy to end up with some very
  arcane error messages. Some standards-compliant ones are available
  [here](./configs/standard_templates.toml) for use in your own configs.
* ✨ – The config key `system` can now be a list instead of a single entry,
  allowing a single config file to specify multiple systems. If doing so, the
  new `system.id` and `system.name` keys are mandatory.
* ✨ – The linter now reads `JD_CONFIG` (and checks the default location at
  `~/.jd/config.json`) for a
  [JD configuration file](https://johnnydecimal.com/jdhq/configuration). If such
  a file exists, it can substitute for the equivalent keys in a `system` (namely
  `name`, root path, and JDex path). If `system` is a single item without an ID,
  the default system specified in the config format will be used.
* ✨ – `notes` in the JDex can now set `id`, `entry`, and `parent` directly on
  themselves if they only need to specify a single ID. This is especially useful
  when combined with templates. Configuration via the old `ids` list still works
  (and is necessary to create multiple IDs from one note).
* ✨ – A new `system.jdex.note_extension` key. Set it to `".md"` and you can
  drop that from the formats of all your notes. This is especially powerful when
  combined with templates, since folder and note formats become interchangeable.
  This extension will also be stripped when generating entries from filenames
  (i.e. `11.01 Inbox.md` will generate the entry `11.01 Inbox`).
* 🛠️ – Invalid keys at the top level are now reported as errors (like they are
  elsewhere). *Technically* this is a **breaking change**, but shame on you if
  it is.
* 🛠️ – A system with zero roots is now an error, since it was previously kind of
  worthless. *Technically* this is a **breaking change**, but shame on you if it
  is.
* 🛠️ – A (non-single file) JDex with neither children nor notes is now an error,
  since it was previously kind of worthless. *Technically* this is a **breaking
  change**, but shame on you if it is.
* 🐛 – Exit code is now correctly set with JSON output. Previously, script
  always exited successfully if JSON output was used.

## `v3.0.0`

Please note that this introduces **breaking changes** to the config file format.

* 🚨 – Renamed `jdex_entry` to just `entry` for consistency; you will need to
  update this name if you used the old key name.
* 🚨 – Removed the `jdex_entry` key from notes; you could previously specify it
  and it did…exactly nothing, so probably no one did. No changes are necessary
  if you didn't specify that.
* ✨ – Added the `parent` key to JDex entries to allow checking for orphans; go
  add this to your configs to enable orphan checking. This allows you to
  guarantee work packages only associate with IDs that actually exist, for
  example.
* 🛠️ – Better handling of IDs in single file JDexes; invalid IDs that do not
  match the standard are now reported instead of being silently ignored.
* 📚 – Significantly improved documentation of the configuration format
  (hopefully). All available settings are now fully-documented in the
  [config readme](./configs/README.md).
* 📚 – Spell Johnny's name correctly, whoops, sorry.

## `v2.0.1`

* 🐛 – Improved handling of multiline comments in plaintext JDexes. Previously,
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
* Supports the plaintext and JSON standards defined by Johnny
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

* 🚸 – Group errors of the same type when printing, so the header and footer
  aren't unnecessarily repeated. This does not affect JSON output.

## `v1.0.0`

Initial release.
