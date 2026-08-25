"""Validate JSForm wheel and source-distribution release artifacts."""

from __future__ import annotations

import argparse
import email.parser
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


REQUIRED_WHEEL_SUFFIXES = {
    "JSForm/__init__.py",
    "JSForm/Forms/frmJSForm.json",
    "JSForm/menu_builder.py",
    "JSForm/menu_commands.py",
    "JSForm/menu_definition.py",
    "JSForm/schema/menu_definition_schema.json",
    "JSForm/schema/unified_schema.json",
    "JSForm/standard_commands.py",
}
REQUIRED_SDIST_SUFFIXES = {
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "Documentation/DEVELOPMENT.md",
    "Documentation/PUBLIC_API.md",
    "examples/JSFormSample/app.py",
    "examples/JSFormSample/Menus/main.menu.json",
    "examples/JSFormSample/README.md",
    "tests/test_versioning.py",
}
FORBIDDEN_WHEEL_PARTS = {
    "BackupDB", "DevelopmentTesting", "Log.txt", "__pycache__", "tests",
}


class DistributionVerificationError(RuntimeError):
    """Report a release artifact that violates the package contract."""


def _single(directory: Path, pattern: str) -> Path:
    matches = sorted(directory.glob(pattern))
    if len(matches) != 1:
        raise DistributionVerificationError(
            f"Expected one {pattern} artifact in {directory}; found {len(matches)}."
        )
    return matches[0]


def _has_suffix(names: set[str], suffix: str) -> bool:
    return any(name == suffix or name.endswith("/" + suffix) for name in names)


def verify_wheel(path: Path) -> tuple[str, str]:
    """Validate wheel contents and return its distribution name and version."""
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        missing = sorted(item for item in REQUIRED_WHEEL_SUFFIXES if item not in names)
        if missing:
            raise DistributionVerificationError(f"Wheel is missing: {missing}")
        for name in names:
            parts = set(PurePosixPath(name).parts)
            if parts & FORBIDDEN_WHEEL_PARTS:
                raise DistributionVerificationError(f"Wheel contains forbidden file: {name}")
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise DistributionVerificationError("Wheel must contain exactly one METADATA file.")
        metadata = email.parser.BytesParser().parsebytes(archive.read(metadata_names[0]))
    name = metadata.get("Name", "")
    version = metadata.get("Version", "")
    if name != "jsform-desktop" or not version:
        raise DistributionVerificationError(
            f"Unexpected wheel identity: name={name!r}, version={version!r}."
        )
    return name, version


def verify_sdist(path: Path) -> None:
    """Validate that the source archive contains development and sample material."""
    with tarfile.open(path, "r:gz") as archive:
        names = {member.name for member in archive.getmembers() if member.isfile()}
    missing = sorted(item for item in REQUIRED_SDIST_SUFFIXES if not _has_suffix(names, item))
    if missing:
        raise DistributionVerificationError(f"Source archive is missing: {missing}")
    forbidden = [name for name in names if "DevelopmentTesting" in name or name.endswith("/Log.txt")]
    if forbidden:
        raise DistributionVerificationError(f"Source archive contains forbidden files: {forbidden}")


def verify(directory: Path) -> tuple[Path, Path, str]:
    """Validate the single wheel and source archive in *directory*."""
    wheel = _single(directory, "*.whl")
    sdist = _single(directory, "*.tar.gz")
    _name, version = verify_wheel(wheel)
    verify_sdist(sdist)
    return wheel, sdist, version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default="dist", type=Path)
    args = parser.parse_args(argv)
    wheel, sdist, version = verify(args.directory.resolve())
    print(f"distribution_verified=true version={version}")
    print(f"wheel={wheel}")
    print(f"source_archive={sdist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
