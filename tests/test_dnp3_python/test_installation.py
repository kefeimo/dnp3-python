import os
import platform
import subprocess
import sys

import pytest


def run_subprocess(command, env=None):
    """Helper function to run subprocess commands"""
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env
    )
    if result.returncode != 0:
        pytest.fail(f"Command failed with error: {result.stderr}")
    return result.stdout


def test_installation():
    python_version = platform.python_version()
    package_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))

    # Create virtual environment
    venv_path = os.path.join(package_path, f"env{python_version}")
    run_subprocess(["python", "-m", "venv", venv_path])

    # Activate the environment and install the package
    env = os.environ.copy()
    env["PATH"] = os.path.join(venv_path, "bin") + os.pathsep + env["PATH"]
    if sys.platform == "win32":
        env["PATH"] = os.path.join(venv_path, "Scripts") + os.pathsep + env["PATH"]

    # Install the package
    run_subprocess(
        [
            os.path.join(
                venv_path,
                "bin",
                "python" if sys.platform != "win32" else "python.exe",
            ),
            os.path.join(package_path, "setup.py"),
            "install",
        ],
        env=env,
    )

    # Check if the package is installed correctly
    output = run_subprocess(
        [
            os.path.join(
                venv_path,
                "bin",
                "python" if sys.platform != "win32" else "python.exe",
            ),
            "-c",
            "import dnp3_python; print(dnp3_python)",
        ],
        env=env,
    )
    print(f"{output=}")
    assert "dnp3_python" in output
