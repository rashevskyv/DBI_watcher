from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
import sys

import requests

FILE_HEADER = ";LANGUAGES\n\n"
ENTRY_TEMPLATE = (
    "[{lang_long}]\n"
    "catch_errors\n"
    "download https://github.com/rashevskyv/DBIPatcher/releases/latest/download/DBI.{version}.{lang_short}.nro /switch/DBI/DBI_new.nro\n"
    "mv /switch/DBI/DBI_new.nro /switch/DBI/DBI.nro\n"
)
CONFIG_FILENAME = "config.ini"
DEFAULT_STATE_FILE = Path("state.json")
DEFAULT_LANG_MAP_FILE = Path("languages.json")
DEFAULT_OUTPUT_DIR = Path("output")
GITHUB_RELEASES_API = "https://api.github.com/repos/rashevskyv/DBIPatcher/releases/latest"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, payload: dict) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def fetch_latest_release() -> dict:
    response = requests.get(GITHUB_RELEASES_API, timeout=30)
    response.raise_for_status()
    return response.json()


def parse_assets(assets: list[dict]) -> tuple[str, list[str]]:
    version = None
    languages: list[str] = []
    for asset in assets:
        name = asset.get("name", "")
        lower_name = name.lower()
        if not lower_name.startswith("dbi.") or not lower_name.endswith(".nro"):
            continue
        parts = name.split(".")
        if len(parts) != 4:
            continue
        _, asset_version, lang_code, _ = parts
        if version is None:
            version = asset_version
        elif version != asset_version:
            raise ValueError(
                f"Inconsistent versions in assets: expected {version}, got {asset_version} from {name}"
            )
        languages.append(lang_code)
    if version is None or not languages:
        raise ValueError("No DBI assets found in the latest release")
    languages.sort()
    return version, languages


def render_config_ini(
    version: str, languages: list[str], lang_map: dict[str, str]
) -> tuple[str, list[str]]:
    rendered: list[tuple[str, str, str]] = []
    for lang_code in languages:
        long_name = lang_map.get(lang_code, lang_code)
        block = ENTRY_TEMPLATE.format(
            lang_long=long_name,
            version=version,
            lang_short=lang_code,
        ).rstrip()
        rendered.append((long_name.casefold(), lang_code, block))
    rendered.sort(key=lambda item: (item[0], item[1]))

    blocks: list[str] = [FILE_HEADER.rstrip()]
    ordered_codes: list[str] = []
    for _, lang_code, block in rendered:
        blocks.append(block)
        ordered_codes.append(lang_code)

    content = "\n\n".join(blocks)
    if not content.endswith("\n"):
        content += "\n"
    return content, ordered_codes


def clear_output_dir(output_dir: Path) -> None:
    for entry in output_dir.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def update_state(
    state_path: Path,
    release_id: int,
    tag_name: str,
    version: str,
    languages: list[str],
) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    state_payload = {
        "last_release_id": release_id,
        "last_tag": tag_name,
        "last_version": version,
        "languages": languages,
        "updated_at": now_iso,
    }
    save_json(state_path, state_payload)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Watch DBIPatcher releases and build Ultrahand config.ini archive"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to store generated artifacts",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
        help="Path to store release tracking state",
    )
    parser.add_argument(
        "--languages",
        type=Path,
        default=DEFAULT_LANG_MAP_FILE,
        help="JSON file with language mapping",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration even if release was already processed",
    )
    args = parser.parse_args()

    lang_map = load_json(args.languages)
    if not lang_map:
        print(f"Language mapping file is empty or missing: {args.languages}", file=sys.stderr)
        return 1

    state = load_json(args.state_file)
    try:
        release = fetch_latest_release()
    except requests.HTTPError as err:
        print(f"Failed to query GitHub releases: {err}", file=sys.stderr)
        return 1

    release_id = release.get("id")
    if release_id is None:
        print("Latest release payload does not contain an id", file=sys.stderr)
        return 1

    if state.get("last_release_id") == release_id and not args.force:
        print("Latest release was already processed. Use --force to rebuild.")
        return 0

    try:
        version, languages = parse_assets(release.get("assets", []))
    except ValueError as err:
        print(str(err), file=sys.stderr)
        return 1

    config_content, ordered_codes = render_config_ini(version, languages, lang_map)

    release_tag = release.get("tag_name", f"dbi-{version}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    clear_output_dir(args.output_dir)

    config_path = args.output_dir / CONFIG_FILENAME
    config_path.write_text(config_content, encoding="utf-8")

    update_state(args.state_file, release_id, release_tag, version, ordered_codes)

    print(f"Prepared package for release {release_tag} with version {version}.")
    print(f"Languages: {', '.join(ordered_codes)}")
    print(f"config.ini: {config_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())