"""Setup file for backward compatibility with setuptools, not supported PEP 660."""
from setuptools import setup


def myversion():
    from setuptools_scm.version import (
        SEMVER_MINOR,
        guess_next_simple_semver,
        release_branch_semver_version,
    )

    def my_release_branch_semver_version(version):
        v = release_branch_semver_version(version)
        if v == version.format_next_version(
            guess_next_simple_semver, retain=SEMVER_MINOR
        ):
            return version.format_next_version(
                guess_next_simple_semver, fmt="{guessed}", retain=SEMVER_MINOR
            )
        return v

    return {
        "version_scheme": my_release_branch_semver_version,
        "local_scheme": "no-local-version",
    }


setup(use_scm_version=myversion)
