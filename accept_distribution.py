"""Perform final, non-publishing acceptance of built JSForm distributions."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from verify_distribution import verify


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"


class DistributionAcceptanceError(RuntimeError):
    """Report a failed isolated-package acceptance check."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(command: list[str], *, environment: dict[str, str] | None = None) -> None:
    result = subprocess.run(command, cwd=ROOT, env=environment, check=False)
    if result.returncode:
        raise DistributionAcceptanceError(
            f"Acceptance command failed with exit code {result.returncode}."
        )


def accept(python: str = sys.executable) -> tuple[Path, Path, Path]:
    """Verify, install, and smoke-test the current wheel and source archive."""
    wheel, source, _version = verify(DIST)
    sample = ROOT / "examples" / "JSFormSample"

    with tempfile.TemporaryDirectory(prefix="jsform-distribution-") as temporary:
        target = Path(temporary) / "installed"
        _run([
            python, "-m", "pip", "install", "--no-deps", "--target",
            str(target), str(wheel),
        ])
        environment = dict(os.environ)
        environment.update({
            "JSFORM_ACCEPT_TARGET": str(target),
            "JSFORM_ACCEPT_SAMPLE": str(sample),
        })
        smoke = (
            "import os,sys;"
            "sys.path[:0]=[os.environ['JSFORM_ACCEPT_TARGET'],os.environ['JSFORM_ACCEPT_SAMPLE']];"
            "import JSForm,app;"
            "assert JSForm.__version__;"
            "assert str(JSForm.__file__).startswith(os.environ['JSFORM_ACCEPT_TARGET']);"
            "assert app.JSForm is JSForm;"
            "print('installed_sample_import=true version='+JSForm.__version__)"
        )
        _run([python, "-I", "-c", smoke], environment=environment)

    checksums = DIST / "SHA256SUMS.txt"
    checksums.write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in (wheel, source)),
        encoding="ascii",
    )
    return wheel, source, checksums


def main(argv: list[str] | None = None) -> int:
    """Run distribution acceptance without publishing or changing the version."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable, help="Python used for isolated installation.")
    arguments = parser.parse_args(argv)
    wheel, source, checksums = accept(arguments.python)
    print("distribution_accepted=true")
    print(f"wheel={wheel}")
    print(f"source_archive={source}")
    print(f"checksums={checksums}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
