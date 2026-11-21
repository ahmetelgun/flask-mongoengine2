"""Nox tool configuration file."""

import shutil
from pathlib import Path

import nox

nox.options.sessions = "latest", "lint", "documentation_tests"
nox.options.default_venv_backend = "uv|virtualenv"

PYTHON_VERSIONS = ["3.10", "3.11", "3.12", "3.13", "3.14"]
DB_VERSION = "8.0"
# Lowest supported versions and latest allowed versions.
DEPENDENCY_SETS = {
    "minimum": ["Flask==3.1.0", "mongoengine==0.29.1", "pymongo==4.18.3"],
    "latest": ["Flask>=3.1.0", "mongoengine>=0.29.1,<0.30", "pymongo>=4.18.3,<5"],
}


def base_install(session, deps, toolbar):
    """Create basic environment setup for tests and linting."""
    extra = "toolbar,dev" if toolbar else "dev"
    session.install(*DEPENDENCY_SETS[deps], "-e", f".[{extra}]")
    return session


@nox.session(python="3.13")
def lint(session):
    """Run linting check locally."""
    session.install("pre-commit")
    session.run("pre-commit", "run", "-a")


@nox.session(python=PYTHON_VERSIONS)
@nox.parametrize("deps", list(DEPENDENCY_SETS))
@nox.parametrize("toolbar", [True, False])
def ci_cd_tests(session, deps, toolbar):
    """Run test suite with pytest into ci_cd (no docker)."""
    session = base_install(session, deps, toolbar)
    session.run("pytest", *session.posargs)


def _run_in_docker(session):
    session.run(
        "docker",
        "run",
        "--name",
        "nox_docker_test",
        "-p",
        "27017:27017",
        "-d",
        f"mongo:{DB_VERSION}",
        external=True,
    )
    try:
        session.run("pytest", *session.posargs)
    finally:
        session.run_always("docker", "rm", "-fv", "nox_docker_test", external=True)


@nox.session(python=PYTHON_VERSIONS)
@nox.parametrize("deps", list(DEPENDENCY_SETS))
@nox.parametrize("toolbar", [True, False])
def full_tests(session, deps, toolbar):
    """Run tests locally with docker and complete support matrix."""
    session = base_install(session, deps, toolbar)
    _run_in_docker(session)


@nox.session(python=PYTHON_VERSIONS)
@nox.parametrize("toolbar", [True, False])
def latest(session, toolbar):
    """Run minimum tests for checking minimum code quality."""
    session = base_install(session, "latest", toolbar)
    if session.interactive:
        _run_in_docker(session)
    else:
        session.run("pytest", *session.posargs)


@nox.session(python="3.13")
def documentation_tests(session):
    """Run documentation tests."""
    return docs(session, batch_run=True)


@nox.session(python="3.13")
def docs(session, batch_run: bool = False):
    """Build the documentation or serve documentation interactively."""
    shutil.rmtree(Path("docs").joinpath("_build"), ignore_errors=True)
    session.install("-r", "docs/requirements.txt")
    session.install("-e", ".[toolbar]")
    session.cd("docs")
    sphinx_args = ["-b", "html", "-W", ".", "_build/html"]

    if not session.interactive or batch_run:
        sphinx_cmd = "sphinx-build"
    else:
        sphinx_cmd = "sphinx-autobuild"
        sphinx_args.extend(
            [
                "--open-browser",
                "--port",
                "9812",
                "--watch",
                "../*.md",
                "--watch",
                "../*.rst",
                "--watch",
                "../*.py",
                "--watch",
                "../flask_mongoengine2",
            ]
        )

    session.run(sphinx_cmd, *sphinx_args)
