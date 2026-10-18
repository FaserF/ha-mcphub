import glob
import os
import re
import subprocess
import sys


def run_cmd(cmd: list[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def find_manifest():
    matches = glob.glob("custom_components/*/manifest.json")
    return matches[0] if matches else "custom_components/omniroute/manifest.json"


def main():
    # Set encoding to UTF-8
    sys.stdout.reconfigure(encoding="utf-8")

    release_type = os.environ.get("RELEASE_TYPE", "beta")
    bump_level = os.environ.get("BUMP_LEVEL", "patch")

    manifest_path = find_manifest()

    # 1. Dry run get next version
    # Run version_manager.py bump and then restore files
    version = run_cmd(
        [
            sys.executable,
            ".github/scripts/version_manager.py",
            "bump",
            "--type",
            release_type,
            "--level",
            bump_level,
        ]
    )
    # Revert modified files to keep clean state
    for path in [manifest_path, "pyproject.toml"]:
        try:
            run_cmd(["git", "checkout", "--", path])
        except Exception:  # noqa: BLE001
            pass

    print(f"Calculated Version: {version}")
    tag = f"v{version}"
    is_prerelease = "false" if release_type == "stable" else "true"

    # Extract base version without suffixes (e.g. 2.3.1 from 2.3.1b1)
    base_version = version
    base_match = re.match(r"^(\d+\.\d+\.\d+)", version)
    if base_match:
        base_version = base_match.group(1)

    # 2. Determine changelog base tag (previous tag to diff against)
    changelog_from = ""
    changelog_label = "initial release — full history"

    # Get all tags matching SemVer pattern
    try:
        raw_tags = run_cmd(
            ["git", "tag", "-l", "[0-9]*", "v[0-9]*", "--sort=-v:refname"]
        ).splitlines()
    except Exception:
        raw_tags = []

    tags = [t.strip() for t in raw_tags if t.strip()]

    if release_type == "stable":
        # Diff against the previous stable tag (ignore beta/rc tags)
        for t in tags:
            clean = t.lstrip("v")
            if re.match(r"^\d+\.\d+\.\d+$", clean) and clean != version:
                changelog_from = t
                changelog_label = f"changes since {t}"
                break
    else:
        # Beta release: diff against the immediately preceding tag of any kind
        for t in tags:
            clean = t.lstrip("v")
            if clean != version:
                changelog_from = t
                changelog_label = f"changes since {t}"
                break

    print(f"Base tag for changelog: {changelog_from or 'none (full history)'}")

    # Set GitHub Actions output
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"version={version}\n")
            f.write(f"tag={tag}\n")
            f.write(f"base_version={base_version}\n")
            f.write(f"is_prerelease={is_prerelease}\n")
            f.write(f"changelog_from={changelog_from}\n")
            f.write(f"changelog_label={changelog_label}\n")


if __name__ == "__main__":
    main()
