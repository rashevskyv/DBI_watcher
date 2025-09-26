# DBI Watcher

Utility that polls the latest release of [DBIPatcher](https://github.com/rashevskyv/DBIPatcher) and produces a ready-to-use `config.ini` archive for Ultrahand packages. The script mirrors the behaviour of `unpack_translation`, but applies the DBI specific template and skips repacking translation zips.

## Prerequisites

* Python 3.9+
* `pip install -r requirements.txt`

## Running

```
python main.py
```

By default the script writes:

* `output/<tag>/config.ini` with language blocks built from the release assets (sorted alphabetically by language name)
* `output/<tag>/metadata.json` with basic release information
* `output/dbi_<version>_<tag>.zip` containing the config and metadata
* `state.json` that records the latest processed release id

Use `--force` to rebuild artifacts even if the latest release was already recorded. `--output-dir`, `--state-file`, and `--languages` let you change paths.

## Updating the language mapping

Language names originate from `languages.json`. Extend or tweak this file if new locale identifiers appear in future releases; missing codes fall back to the short identifier.