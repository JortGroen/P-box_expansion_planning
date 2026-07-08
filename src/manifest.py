"""Manifest utilities for reproducible experiment outputs.

The manifest is intentionally small at E0. Later ExperimentRunner work can add
runtime fields without changing the checksum helpers tested here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from importlib import metadata
from pathlib import Path
from typing import Iterable, Mapping, Sequence

DEFAULT_PACKAGES: tuple[str, ...] = (
    "numpy",
    "pandas",
    "scipy",
    "numba",
    "pandapower",
    "simbench",
    "lightsim2grid",
    "pytest",
    "hypothesis",
    "matplotlib",
)


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 hex digest for a file."""
    digest = hashlib.sha256()
    file_path = Path(path)
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def config_hash(config_path: str | Path) -> str:
    """Return the SHA-256 digest of a version-controlled config file."""
    return sha256_file(config_path)


def git_commit_hash(repo_root: str | Path = ".") -> str | None:
    """Return the current git commit hash, or None when unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(repo_root),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def collect_package_versions(packages: Iterable[str] = DEFAULT_PACKAGES) -> dict[str, str | None]:
    """Collect installed package versions without importing heavy packages."""
    versions: dict[str, str | None] = {}
    for package in packages:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def checksum_outputs(paths: Iterable[str | Path]) -> dict[str, str]:
    """Return checksums keyed by POSIX-style relative path strings."""
    checksums: dict[str, str] = {}
    for path in paths:
        output_path = Path(path)
        if not output_path.is_file():
            raise FileNotFoundError(f"Output does not exist or is not a file: {output_path}")
        checksums[output_path.as_posix()] = sha256_file(output_path)
    return dict(sorted(checksums.items()))


def build_manifest(
    *,
    config_path: str | Path,
    seeds: Mapping[str, int | str],
    output_paths: Sequence[str | Path] = (),
    repo_root: str | Path = ".",
    packages: Iterable[str] = DEFAULT_PACKAGES,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Build a deterministic manifest dictionary.

    Parameters
    ----------
    config_path:
        Path to the version-controlled configuration file.
    seeds:
        Named random seeds used by the run.
    output_paths:
        Files produced by the run. The manifest file itself should not be
        included.
    repo_root:
        Repository root used to resolve the git commit hash.
    packages:
        Package names to record with installed versions.
    extra:
        Optional runner-owned metadata. Avoid timestamps in tests that need
        bit-identical manifests.
    """
    manifest: dict[str, object] = {
        "schema_version": 1,
        "git_commit": git_commit_hash(repo_root),
        "config_path": Path(config_path).as_posix(),
        "config_hash": config_hash(config_path),
        "seeds": dict(sorted(seeds.items())),
        "package_versions": collect_package_versions(packages),
        "output_checksums": checksum_outputs(output_paths),
    }
    if extra:
        manifest["extra"] = dict(sorted(extra.items()))
    return manifest


def write_manifest(
    output_dir: str | Path,
    *,
    config_path: str | Path,
    seeds: Mapping[str, int | str],
    output_paths: Sequence[str | Path] = (),
    repo_root: str | Path = ".",
    packages: Iterable[str] = DEFAULT_PACKAGES,
    extra: Mapping[str, object] | None = None,
) -> Path:
    """Write `manifest.json` to an output directory and return its path."""
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(
        config_path=config_path,
        seeds=seeds,
        output_paths=output_paths,
        repo_root=repo_root,
        packages=packages,
        extra=extra,
    )
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def _parse_seed(seed_values: Sequence[str]) -> dict[str, int | str]:
    seeds: dict[str, int | str] = {}
    for raw in seed_values:
        if "=" not in raw:
            raise ValueError(f"Seed must use name=value syntax: {raw}")
        name, value = raw.split("=", 1)
        try:
            seeds[name] = int(value)
        except ValueError:
            seeds[name] = value
    return seeds


def main(argv: Sequence[str] | None = None) -> int:
    """Command-line entrypoint for manifest smoke checks."""
    parser = argparse.ArgumentParser(description="Write a manifest for existing outputs.")
    parser.add_argument("config_path")
    parser.add_argument("output_dir")
    parser.add_argument("--seed", action="append", default=["root=0"])
    parser.add_argument("--output", action="append", default=[])
    args = parser.parse_args(argv)

    write_manifest(
        args.output_dir,
        config_path=args.config_path,
        seeds=_parse_seed(args.seed),
        output_paths=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

