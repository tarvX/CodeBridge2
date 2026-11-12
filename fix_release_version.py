from pathlib import Path
import sys


ROOT = Path.cwd()
WORKFLOWS_DIR = ROOT / ".github" / "workflows"

MARKER = "# CODEBRIDGE_VERSION_PREBUILD_CHECK"

INSERTION = """          python ../../scripts/sync_version.py
          # CODEBRIDGE_VERSION_PREBUILD_CHECK
          python - <<'PY'
          import importlib
          import json
          import sys
          from pathlib import Path

          # Force Python to load the project source, not an installed copy.
          sys.path.insert(0, str(Path("src").resolve()))

          package = json.loads(
              Path("../../package.json").read_text(encoding="utf-8")
          )
          expected = package["version"]

          version_module = importlib.import_module("codebridge._version")

          actual = version_module.__version__
          module_path = Path(version_module.__file__).resolve()

          print(f"Expected version: {expected}")
          print(f"Actual version:   {actual}")
          print(f"Version module:   {module_path}")

          if actual != expected:
              raise SystemExit(
                  f"Version mismatch: expected {expected}, got {actual}"
              )

          print("Version metadata is ready for PyInstaller.")
          PY
"""


def fail(message):
    print(f"ERROR: {message}")
    sys.exit(1)


def main():
    if not (ROOT / "package.json").is_file():
        fail("Run this script from the CodeBridge project root.")

    if not WORKFLOWS_DIR.is_dir():
        fail(".github/workflows directory not found.")

    candidates = []

    for path in list(WORKFLOWS_DIR.glob("*.yml")) + list(
        WORKFLOWS_DIR.glob("*.yaml")
    ):
        content = path.read_text(encoding="utf-8")

        if (
            "Sync version and build binary" in content
            and "pyinstaller --onefile" in content
        ):
            candidates.append(path)

    if len(candidates) != 1:
        fail(
            "Expected exactly one desktop release workflow, "
            f"found {len(candidates)}."
        )

    workflow = candidates[0]
    content = workflow.read_text(encoding="utf-8")

    if MARKER in content:
        print("The version fix is already present. No changes made.")
        return

    target = "          python -m pip install ."

    if content.count(target) != 1:
        fail(
            "Could not uniquely locate 'python -m pip install .' "
            "in the release workflow."
        )

    if content.index(target) > content.index("pyinstaller --onefile"):
        fail("Unexpected build command order.")

    backup = workflow.with_suffix(workflow.suffix + ".bak")

    if backup.exists():
        fail(f"Backup already exists: {backup}")

    # Preserve original workflow before modifying it.
    backup.write_text(content, encoding="utf-8")

    # Recreate _version.py after pip install, because setup.py
    # may remove the generated file during package installation.
    updated = content.replace(
        target,
        target + "\n" + INSERTION.rstrip("\n"),
        1,
    )

    workflow.write_text(updated, encoding="utf-8")

    print("\nSUCCESS")
    print(f"Modified: {workflow.relative_to(ROOT)}")
    print(f"Backup:   {backup.relative_to(ROOT)}")
    print("\nThe build now:")
    print("1. Installs the Python package.")
    print("2. Regenerates _version.py.")
    print("3. Verifies the imported version against package.json.")
    print("4. Runs PyInstaller only if the version is correct.")


if __name__ == "__main__":
    main()