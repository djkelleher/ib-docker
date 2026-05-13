import ast
import hashlib
import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CI_PATH = REPO_ROOT / "ci.py"
INIT_SETTINGS_PATH = REPO_ROOT / "build" / "programs" / "init_container_settings.py"
IB_UTILS_PATH = REPO_ROOT / "build" / "programs" / "ib_utils.sh"
ENTRYPOINT_PATH = REPO_ROOT / "build" / "programs" / "entrypoint.sh"
START_VNC_PATH = REPO_ROOT / "build" / "programs" / "start_vnc.sh"
START_XVFB_PATH = REPO_ROOT / "build" / "programs" / "start_xvfb.sh"
START_IBC_PATH = REPO_ROOT / "build" / "programs" / "start_ibc.sh"
DOCKERFILE_PATH = REPO_ROOT / "build" / "Dockerfile"
BUILD_DOCKERIGNORE_PATH = REPO_ROOT / "build" / ".dockerignore"
VMOPTIONS_TEMPLATE_PATH = REPO_ROOT / "build" / "config" / "vmoptions.j2"
SUPERVISORD_CONF_PATH = REPO_ROOT / "build" / "config" / "supervisord.conf"
DOCKER_COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"
IBC_TEMPLATE_PATH = REPO_ROOT / "build" / "config" / "ibc.ini"
README_PATH = REPO_ROOT / "README.md"
GATEWAY_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "build_gateway.yml"
TWS_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "build_tws.yml"


def load_init_settings() -> ModuleType:
    """Load init_container_settings.py from its runtime script location."""
    spec = importlib.util.spec_from_file_location(
        "init_container_settings", INIT_SETTINGS_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_ci_module(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load ci.py with a lightweight PyGithub stub for local unit tests."""
    github_module = types.ModuleType("github")

    class Github:
        """Minimal stand-in for PyGithub's client class."""

        def __init__(self, token: str) -> None:
            self.token = token

        def get_repo(self, repo_name: str) -> str:
            return repo_name

    github_module.Github = Github
    monkeypatch.setitem(sys.modules, "github", github_module)
    spec = importlib.util.spec_from_file_location("ci", CI_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ci"] = module
    spec.loader.exec_module(module)
    return module


def run_bash(script: str) -> subprocess.CompletedProcess[str]:
    """Run a bash snippet and return its completed process."""
    return subprocess.run(
        ["bash", "-eu", "-o", "pipefail", "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )


def run_bash_unchecked(script: str) -> subprocess.CompletedProcess[str]:
    """Run a bash snippet without raising for a non-zero exit code."""
    return subprocess.run(
        ["bash", "-eu", "-o", "pipefail", "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )


def create_ib_release_dir(path: Path, app_name: str) -> None:
    """Create the minimal installer layout required by runtime path checks."""
    (path / "jars").mkdir(parents=True)
    executable_path = path / app_name
    executable_path.write_text("#!/bin/sh\n")
    executable_path.chmod(0o755)
    (path / f"{app_name}.vmoptions").write_text("-Xmx256m\n")
    if app_name == "ibgateway":
        (path / "tws.vmoptions").write_text("-Xmx256m\n")


def create_ibc_dir(path: Path) -> None:
    """Create the minimal IBC layout required by runtime path checks."""
    scripts_dir = path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    ibc_start_path = scripts_dir / "ibcstart.sh"
    ibc_start_path.write_text("#!/bin/sh\n")
    ibc_start_path.chmod(0o755)


def fake_sha256_fetch(url: str) -> str:
    """Return a deterministic checksum sidecar for a fake release asset URL."""
    asset_name = Path(url).name
    installer_name = asset_name.removesuffix(".sha256")
    digest = hashlib.sha256(installer_name.encode()).hexdigest()
    return f"{digest} {installer_name}\n"


def fake_release_asset_fetch(url: str, as_text: bool = True) -> str | bytes:
    """Return fake release asset bytes or matching checksum sidecars."""
    asset_name = Path(url).name
    if asset_name.endswith(".sha256"):
        return fake_sha256_fetch(url)
    content = asset_name.encode()
    if as_text:
        return content.decode()
    return content


@pytest.fixture(name="init_settings")
def fixture_init_settings() -> ModuleType:
    """Return the init_container_settings module."""
    return load_init_settings()


@pytest.fixture(autouse=True)
def fixture_runtime_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Provide image defaults that most runtime validation tests assume."""
    default_ibc_path = tmp_path / "runtime-defaults" / "opt" / "ibc"
    create_ibc_dir(default_ibc_path)
    monkeypatch.setenv("IBC_PATH", str(default_ibc_path))
    monkeypatch.setenv("IBC_VERSION", "3.23.0")


def test_env_substitution_uses_defaults_for_empty_values(
    init_settings: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Shell-style defaults should apply when an env var is unset or empty."""
    monkeypatch.delenv("TRADING_MODE", raising=False)
    monkeypatch.setenv("FIX", "")
    monkeypatch.setenv("IB_USER", "")

    rendered = init_settings.sub_env_vars(
        "TradingMode=${TRADING_MODE:-paper}\n"
        "FIX=${FIX:-no}\n"
        "IbLoginId=${IB_USER}\n"
    )

    assert rendered == "TradingMode=paper\nFIX=no\nIbLoginId=\n"


def test_ibc_template_defaults_match_documented_runtime_defaults(
    init_settings: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Documented runtime defaults should render even when env vars are absent."""
    for var_name in [
        "TWOFA_EXIT_INTERVAL",
        "READ_ONLY_API",
        "BYPASS_WARNING",
        "SAVE_TWS_SETTINGS",
    ]:
        monkeypatch.delenv(var_name, raising=False)

    rendered = init_settings.sub_env_vars(IBC_TEMPLATE_PATH.read_text())

    assert "SecondFactorAuthenticationExitInterval=60" in rendered
    assert "ReadOnlyApi=no" in rendered
    assert "BypassOrderPrecautions=yes" in rendered
    assert "BypassNoOverfillProtectionPrecaution=yes" in rendered
    assert "SaveTwsSettingsAt=Every 30 mins" in rendered


def test_python_required_env_fails_with_clear_error(
    init_settings: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Python startup config should not fail with a raw KeyError."""
    monkeypatch.delenv("IBC_INI", raising=False)

    with pytest.raises(RuntimeError, match="Required environment variable IBC_INI"):
        init_settings.require_env("IBC_INI")


def test_python_required_directory_fails_with_clear_error(
    init_settings: ModuleType, tmp_path: Path
) -> None:
    """Python startup config should not fail with a raw file write error."""
    missing_path = tmp_path / "opt" / "tws" / "stable"

    with pytest.raises(RuntimeError, match="IB release directory does not exist"):
        init_settings.require_directory(missing_path, "IB release")


def test_python_required_directory_rejects_relative_paths(
    init_settings: ModuleType,
) -> None:
    """Python startup config should not accept relative release paths."""
    with pytest.raises(RuntimeError, match="must be an absolute path"):
        init_settings.require_directory(Path("opt/tws/stable"), "IB release")


def test_python_absolute_path_validation_rejects_relative_paths(
    init_settings: ModuleType,
) -> None:
    """Python startup config should validate path-like env values consistently."""
    with pytest.raises(RuntimeError, match="IBC_INI must be an absolute path"):
        init_settings.require_absolute_path(Path("ibc.ini"), "IBC_INI")


def test_python_release_dir_defaults_from_program_and_release(
    init_settings: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Python startup config should mirror the shell default release directory."""
    monkeypatch.setenv("IB_RELEASE", "stable")
    monkeypatch.delenv("IB_RELEASE_DIR", raising=False)

    assert init_settings.resolve_ib_release_dir("tws", tmp_path / "opt") == (
        tmp_path / "opt" / "tws" / "stable"
    )


def test_python_release_dir_default_requires_release(
    init_settings: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Python startup config should fail clearly when default release is unset."""
    monkeypatch.delenv("IB_RELEASE", raising=False)
    monkeypatch.delenv("IB_RELEASE_DIR", raising=False)

    with pytest.raises(RuntimeError, match="Required environment variable IB_RELEASE"):
        init_settings.resolve_ib_release_dir("tws")


def test_python_tws_settings_path_rejects_existing_file(
    init_settings: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Python runtime validation should reject file-valued TWS_SETTINGS_PATH early."""
    settings_path = tmp_path / "tws_settings"
    settings_path.write_text("not a directory")
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_path))

    with pytest.raises(RuntimeError, match="TWS_SETTINGS_PATH is not a directory"):
        init_settings.tws_settings_path()


def test_python_initializer_cli_reports_errors_without_traceback() -> None:
    """The runtime config command should print actionable errors without tracebacks."""
    result = subprocess.run(
        [sys.executable, str(INIT_SETTINGS_PATH)],
        check=False,
        capture_output=True,
        text=True,
        env={},
    )

    assert result.returncode == 1
    assert result.stderr == "ERROR: Required environment variable PROGRAM is not set\n"
    assert "Traceback" not in result.stderr


def test_python_initializer_reports_filesystem_errors_without_traceback(
    init_settings: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Runtime config filesystem errors should use the same concise CLI format."""

    def fail_main() -> None:
        raise OSError("disk is full")

    monkeypatch.setattr(init_settings, "main", fail_main)

    assert init_settings.run() == 1
    captured = capsys.readouterr()
    assert captured.err == "ERROR: disk is full\n"
    assert "Traceback" not in captured.err


def test_gateway_ibc_path_resolves_to_parent_expected_by_ibc(tmp_path: Path) -> None:
    """Gateway IBC startup should find /opt/ibgateway/<release> without fallback."""
    release_dir = tmp_path / "opt" / "ibgateway" / "stable"
    create_ib_release_dir(release_dir, "ibgateway")

    result = run_bash(
        f"""
        source "{IB_UTILS_PATH}"
        PROGRAM=ibgateway
        IB_RELEASE=stable
        IB_RELEASE_DIR="{release_dir}"
        release_dir="$(resolve_ib_release_dir)"
        resolve_ibc_tws_path "$release_dir"
        """
    )

    assert result.stdout.strip().endswith(f"{os.sep}opt")


def test_tws_ibc_path_resolves_to_product_dir_expected_by_ibc(tmp_path: Path) -> None:
    """TWS IBC startup should find /opt/tws/<release>."""
    release_dir = tmp_path / "opt" / "tws" / "stable"
    create_ib_release_dir(release_dir, "tws")

    result = run_bash(
        f"""
        source "{IB_UTILS_PATH}"
        PROGRAM=tws
        IB_RELEASE=stable
        IB_RELEASE_DIR="{release_dir}"
        release_dir="$(resolve_ib_release_dir)"
        resolve_ibc_tws_path "$release_dir"
        """
    )

    assert result.stdout.strip().endswith(f"{os.sep}opt{os.sep}tws")


def test_ibc_release_version_comes_from_resolved_release_dir(tmp_path: Path) -> None:
    """Custom release dirs should keep IBC's version argument aligned with the path."""
    release_dir = tmp_path / "opt" / "tws" / "10.45.1e"
    create_ib_release_dir(release_dir, "tws")

    result = run_bash(
        f"""
        source "{IB_UTILS_PATH}"
        PROGRAM=tws
        IB_RELEASE=stable
        IB_RELEASE_DIR="{release_dir}"
        release_dir="$(resolve_ib_release_dir)"
        ib_release_version_from_dir "$release_dir"
        """
    )

    assert result.stdout.strip() == "10.45.1e"


def test_gateway_ibc_path_rejects_parent_not_named_ibgateway(tmp_path: Path) -> None:
    """Gateway custom release dirs must match the path shape IBC reconstructs."""
    release_dir = tmp_path / "opt" / "gateway" / "stable"
    create_ib_release_dir(release_dir, "ibgateway")

    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        PROGRAM=ibgateway
        IB_RELEASE=stable
        IB_RELEASE_DIR="{release_dir}"
        release_dir="$(resolve_ib_release_dir)"
        resolve_ibc_tws_path "$release_dir"
        """
    )

    assert result.returncode == 1
    assert "must be nested under an ibgateway directory" in result.stdout


def test_release_dir_validation_rejects_incomplete_installer_layout(
    tmp_path: Path,
) -> None:
    """Runtime should fail early if a custom release path is missing product files."""
    release_dir = tmp_path / "opt" / "ibgateway" / "stable"
    (release_dir / "jars").mkdir(parents=True)

    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        PROGRAM=ibgateway
        IB_RELEASE=stable
        IB_RELEASE_DIR="{release_dir}"
        resolve_ib_release_dir
        """
    )

    assert result.returncode == 1
    assert "Expected executable" in result.stdout


def test_gateway_release_dir_requires_compatibility_vmoptions(tmp_path: Path) -> None:
    """Gateway startup should fail clearly if IBC's tws.vmoptions file is missing."""
    release_dir = tmp_path / "opt" / "ibgateway" / "stable"
    create_ib_release_dir(release_dir, "ibgateway")
    (release_dir / "tws.vmoptions").unlink()

    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        PROGRAM=ibgateway
        IB_RELEASE_DIR="{release_dir}"
        resolve_ib_release_dir
        """
    )

    assert result.returncode == 1
    assert "Expected Gateway compatibility vmoptions file" in result.stdout


def test_shell_product_validation_rejects_unsupported_program() -> None:
    """Shared shell helpers should fail explicitly on unsupported products."""
    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        PROGRAM=desktop
        ib_product_executable
        """
    )

    assert result.returncode == 1
    assert "Unsupported IB program: desktop" in result.stdout


def test_ensure_env_fails_with_clear_error() -> None:
    """Strict-mode scripts should report missing required env names clearly."""
    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        unset IB_RELEASE
        ensure_env IB_RELEASE
        """
    )

    assert result.returncode == 1
    assert "Required environment variable IB_RELEASE is not set" in result.stdout


def test_ensure_absolute_path_rejects_relative_values() -> None:
    """Runtime paths passed across scripts should not depend on cwd."""
    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        IBC_PATH=opt/ibc
        ensure_absolute_path IBC_PATH
        """
    )

    assert result.returncode == 1
    assert "IBC_PATH must be an absolute path: opt/ibc" in result.stdout


def test_ensure_executable_file_fails_clearly(tmp_path: Path) -> None:
    """Runtime script checks should fail before invoking missing executables."""
    missing_path = tmp_path / "ibc" / "scripts" / "ibcstart.sh"
    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        ensure_executable_file "{missing_path}" "IBC start script"
        """
    )

    assert result.returncode == 1
    assert "IBC start script is missing or not executable" in result.stdout


def test_ensure_file_fails_clearly(tmp_path: Path) -> None:
    """Runtime file checks should report the missing path before handoff."""
    missing_path = tmp_path / "ibc.ini"
    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        ensure_file "{missing_path}" "IBC config"
        """
    )

    assert result.returncode == 1
    assert "IBC config is missing" in result.stdout


def test_wait_for_x_server_requires_home_before_xauth_setup() -> None:
    """Strict-mode X startup should fail clearly when HOME is missing."""
    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        unset HOME
        wait_for_x_server
        """
    )

    assert result.returncode == 1
    assert "Required environment variable HOME is not set" in result.stdout
    assert "unbound variable" not in result.stderr


def test_wait_for_x_server_rejects_invalid_display_before_timeout() -> None:
    """X client startup should fail clearly for malformed DISPLAY values."""
    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        HOME=/tmp
        DISPLAY=not-a-display
        wait_for_x_server
        """
    )

    assert result.returncode == 1
    assert "Invalid DISPLAY value: not-a-display" in result.stdout
    assert "failed to start within 60 seconds" not in result.stdout


def test_release_dir_default_requires_release_without_nounset() -> None:
    """Default release dir construction should fail clearly if IB_RELEASE is unset."""
    result = run_bash_unchecked(
        f"""
        set -u
        source "{IB_UTILS_PATH}"
        PROGRAM=tws
        unset IB_RELEASE
        unset IB_RELEASE_DIR
        resolve_ib_release_dir
        """
    )

    assert result.returncode == 1
    assert "Required environment variable IB_RELEASE is not set" in result.stdout


def test_release_dir_validation_rejects_relative_custom_path(tmp_path: Path) -> None:
    """IBC path resolution should not pass relative install paths downstream."""
    release_dir = tmp_path / "opt" / "tws" / "stable"
    create_ib_release_dir(release_dir, "tws")

    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        cd "{tmp_path}"
        PROGRAM=tws
        IB_RELEASE_DIR="opt/tws/stable"
        resolve_ib_release_dir
        """
    )

    assert result.returncode == 1
    assert "must be an absolute path" in result.stdout


def test_ibc_startup_defaults_and_validates_runtime_choices() -> None:
    """IBC startup choices should be normalized before they are passed to IBC."""
    default_result = run_bash(
        f"""
        source "{IB_UTILS_PATH}"
        unset TRADING_MODE
        unset TWOFA_TIMEOUT_ACTION
        ib_trading_mode
        ib_twofa_timeout_action
        """
    )
    invalid_mode = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        TRADING_MODE=demo
        ib_trading_mode
        """
    )
    invalid_action = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        TWOFA_TIMEOUT_ACTION=wait
        ib_twofa_timeout_action
        """
    )

    assert default_result.stdout.splitlines() == ["paper", "exit"]
    assert invalid_mode.returncode == 1
    assert "Unsupported TRADING_MODE: demo" in invalid_mode.stdout
    assert invalid_action.returncode == 1
    assert "Unsupported TWOFA_TIMEOUT_ACTION: wait" in invalid_action.stdout


def test_python_runtime_choice_validation_matches_shell_defaults(
    init_settings: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Python startup validation should accept the same defaults as shell startup."""
    monkeypatch.delenv("TRADING_MODE", raising=False)
    monkeypatch.delenv("TWOFA_TIMEOUT_ACTION", raising=False)

    init_settings.validate_runtime_choices()

    monkeypatch.setenv("TRADING_MODE", "")
    monkeypatch.setenv("TWOFA_TIMEOUT_ACTION", "")
    init_settings.validate_runtime_choices()

    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("TWOFA_TIMEOUT_ACTION", "restart")
    init_settings.validate_runtime_choices()


def test_x_display_number_strips_screen_suffix() -> None:
    """X11 artifact paths should use the display number, not the screen suffix."""
    result = run_bash(
        f"""
        source "{IB_UTILS_PATH}"
        x_display_number ":1.0"
        x_display_number "localhost:2.1"
        """
    )

    assert result.stdout.splitlines() == ["1", "2"]


def test_x_display_number_rejects_invalid_display() -> None:
    """Invalid display values should fail before cleanup derives bad paths."""
    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        x_display_number "not-a-display"
        """
    )

    assert result.returncode == 1
    assert "Invalid DISPLAY value" in result.stdout


def test_x_server_display_rejects_client_style_display() -> None:
    """Xvfb startup should fail clearly for DISPLAY values it cannot serve."""
    valid_result = run_bash(
        f"""
        source "{IB_UTILS_PATH}"
        x_server_display ":1.0"
        """
    )
    invalid_result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        x_server_display "localhost:2.1"
        """
    )

    assert valid_result.stdout.strip() == ":1.0"
    assert invalid_result.returncode == 1
    assert "Invalid X server DISPLAY value" in invalid_result.stdout


def test_entrypoint_uses_display_specific_x_cleanup() -> None:
    """Entrypoint cleanup should match the normalized display path handling."""
    content = ENTRYPOINT_PATH.read_text()

    assert 'DISPLAY="$(x_server_display "${DISPLAY:-:1}")"' in content
    assert 'display_no="$(x_display_number "$DISPLAY")"' in content
    assert 'xvfb_pattern="$(x_display_process_pattern Xvfb "$DISPLAY")"' in content
    assert 'x11vnc_pattern="$(x_display_process_pattern x11vnc "$DISPLAY")"' in content
    assert "rm -rf /tmp/.X*-lock" not in content
    assert "rm -rf /tmp/.X11-unix/*" not in content
    assert 'rm -f "/tmp/.X${display_no}-lock"' in content
    assert 'rm -f "/tmp/.X11-unix/X${display_no}"' in content


def test_entrypoint_rejects_client_style_display_before_cleanup() -> None:
    """Entrypoint cleanup should only operate on local X server displays."""
    content = ENTRYPOINT_PATH.read_text()

    validation = content.index('DISPLAY="$(x_server_display "${DISPLAY:-:1}")"')
    cleanup = content.index("cleanup_x_server", validation)

    assert validation < cleanup
    assert 'DISPLAY="${DISPLAY:-:1}"' not in content


def test_xvfb_cleanup_is_display_specific() -> None:
    """Xvfb startup should not kill unrelated Xvfb processes on other displays."""
    content = START_XVFB_PATH.read_text()

    assert 'DISPLAY="$(x_server_display "${DISPLAY:-:1}")"' in content
    assert "ensure_absolute_path HOME" in content
    assert 'xvfb_pattern="$(x_display_process_pattern Xvfb "$DISPLAY")"' in content
    assert 'pkill -9 -f "$xvfb_pattern"' in content
    assert 'pkill -9 -f "Xvfb.*${DISPLAY}"' not in content
    assert 'pkill -9 -f "Xvfb" 2>/dev/null || true' not in content


def test_x_display_process_pattern_uses_normalized_display_number() -> None:
    """Process cleanup regexes should not use raw DISPLAY as regex input."""
    result = run_bash(
        f"""
        source "{IB_UTILS_PATH}"
        x_display_process_pattern Xvfb ":1.0"
        x_display_process_pattern x11vnc "localhost:2.1"
        """
    )

    assert result.stdout.splitlines() == [
        "Xvfb.*:1([[:space:].]|$)",
        "x11vnc.*:2([[:space:].]|$)",
    ]


def test_x_screen_dimension_defaults_and_validates() -> None:
    """Xvfb screen dimensions should fail before invoking Xvfb with bad args."""
    default_result = run_bash(
        f"""
        source "{IB_UTILS_PATH}"
        unset VNC_SCREEN_DIMENSION
        x_screen_dimension
        """
    )
    custom_result = run_bash(
        f"""
        source "{IB_UTILS_PATH}"
        VNC_SCREEN_DIMENSION=1920x1080x24
        x_screen_dimension
        """
    )
    invalid_result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        VNC_SCREEN_DIMENSION=1920x0x24
        x_screen_dimension
        """
    )

    assert default_result.stdout.strip() == "1600x1200x24"
    assert custom_result.stdout.strip() == "1920x1080x24"
    assert invalid_result.returncode == 1
    assert "Invalid VNC_SCREEN_DIMENSION" in invalid_result.stdout


def test_vnc_port_defaults_and_validates() -> None:
    """VNC should support per-service host-network ports."""
    default_result = run_bash(
        f"""
        source "{IB_UTILS_PATH}"
        unset VNC_PORT
        vnc_port
        """
    )
    custom_result = run_bash(
        f"""
        source "{IB_UTILS_PATH}"
        VNC_PORT=5901
        vnc_port
        """
    )
    invalid_result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        VNC_PORT=70000
        vnc_port
        """
    )

    assert default_result.stdout.strip() == "5900"
    assert custom_result.stdout.strip() == "5901"
    assert invalid_result.returncode == 1
    assert "Invalid VNC_PORT" in invalid_result.stdout


def test_vnc_password_is_not_passed_on_process_command_line() -> None:
    """VNC password should not remain in x11vnc argv or inherited env."""
    content = START_VNC_PATH.read_text()

    assert '-passwd "$VNC_PWD"' not in content
    assert '-passwdfile "$vnc_password_file"' in content
    assert '-rfbport "$vnc_listen_port"' in content
    assert 'chmod 600 "$vnc_password_file"' in content
    assert "unset VNC_PWD" in content
    assert "cleanup_vnc_password_file" in content
    assert 'rm -f "$path"' in content
    assert "trap 'cleanup_vnc_password_file \"$vnc_password_file\"' EXIT" in content
    assert 'trap \'stop_vnc "$vnc_password_file" "$vnc_pid"\' TERM INT' in content
    assert 'wait "$vnc_pid"' in content


def test_vnc_startup_requires_home_before_xauth_setup() -> None:
    """VNC startup should validate HOME before using it for X authority files."""
    content = START_VNC_PATH.read_text()

    validation = content.index("ensure_absolute_path HOME")
    xauth = content.index('export XAUTHORITY="$HOME/.Xauthority"')

    assert validation < xauth


def test_ibc_startup_rejects_file_tws_settings_path_before_mkdir() -> None:
    """IBC startup should not leak mkdir errors for file-valued settings paths."""
    content = START_IBC_PATH.read_text()
    validation = content.index('ensure_directory_path "$TWS_SETTINGS_PATH"')
    mkdir_call = content.index('mkdir -p "$TWS_SETTINGS_PATH"')

    assert validation < mkdir_call

    result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        settings_path="$(mktemp)"
        ensure_directory_path "$settings_path" "TWS settings path"
        """
    )

    assert result.returncode == 1
    assert "TWS settings path is not a directory" in result.stdout


def test_startup_scripts_use_strict_shell_mode() -> None:
    """Startup scripts should fail on setup errors instead of continuing."""
    for script_path in [
        ENTRYPOINT_PATH,
        START_IBC_PATH,
        START_VNC_PATH,
        START_XVFB_PATH,
    ]:
        content = script_path.read_text()
        assert content.startswith("#!/bin/bash\nset -euo pipefail\n")


def test_vnc_password_optional_under_strict_shell_mode() -> None:
    """Unset VNC_PWD should still disable VNC without tripping nounset."""
    content = START_VNC_PATH.read_text()

    assert "if [[ -z ${VNC_PWD:-} ]]; then" in content


def test_shell_ibc_version_defaults_and_validates() -> None:
    """Shell startup should reject runtime IBC versions Docker would not build."""
    valid_result = run_bash(
        f"""
        source "{IB_UTILS_PATH}"
        IBC_VERSION=3.23.0
        ibc_version
        """
    )
    invalid_result = run_bash_unchecked(
        f"""
        source "{IB_UTILS_PATH}"
        IBC_VERSION=3.23
        ibc_version
        """
    )

    assert valid_result.stdout.strip() == "3.23.0"
    assert invalid_result.returncode == 1
    assert "IBC_VERSION must look like 3.23.0" in invalid_result.stdout


def test_ibc_startup_requires_absolute_runtime_paths() -> None:
    """IBC startup should validate paths before passing them to IBC."""
    content = START_IBC_PATH.read_text()

    assert 'ibc_version="$(ibc_version)"' in content
    assert "ensure_env IBC_VERSION" not in content
    assert 'IB_RELEASE="$(ib_release_version_from_dir "$IB_RELEASE_DIR")"' in content
    assert "ensure_absolute_path IBC_PATH" in content
    assert "ensure_absolute_path IBC_INI" in content
    assert (
        'ensure_executable_file "${IBC_PATH}/scripts/ibcstart.sh" "IBC start script"'
        in content
    )
    assert 'ensure_file "$IBC_INI" "IBC config"' in content
    assert "ensure_absolute_path HOME" in content
    assert "ensure_absolute_path TWS_SETTINGS_PATH" in content


def test_gateway_vmoptions_updates_primary_and_compatibility_files(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gateway runtime initialization should not leave stale tws.vmoptions behind."""
    home = tmp_path / "home" / "ibuser"
    release_dir = tmp_path / "opt" / "ibgateway" / "stable"
    home.mkdir(parents=True)
    create_ib_release_dir(release_dir, "ibgateway")
    template_path = home / "vmoptions.j2"
    template_path.write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "ibgateway")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(home / "custom_settings"))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1g")
    monkeypatch.setenv("CUSTOM_JVM_OPTS", "-Dcustom=true '-Dquoted=value with spaces'")

    init_settings.set_java_vmoptions()

    primary_content = (release_dir / "ibgateway.vmoptions").read_text()
    compatibility_content = (release_dir / "tws.vmoptions").read_text()
    assert primary_content == compatibility_content
    assert "-Xmx1024m" in primary_content
    assert "-Xms512m" in primary_content
    assert f"-DjtsConfigDir={home / 'custom_settings'}" in primary_content
    assert "-Dcustom=true" in primary_content
    assert "-Dquoted=value with spaces" in primary_content
    assert template_path.exists()


def test_gateway_layout_validation_requires_compatibility_vmoptions(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Python runtime validation should match Gateway startup layout checks."""
    home = tmp_path / "home" / "ibuser"
    release_dir = tmp_path / "opt" / "ibgateway" / "stable"
    home.mkdir(parents=True)
    create_ib_release_dir(release_dir, "ibgateway")
    (release_dir / "tws.vmoptions").unlink()
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "ibgateway")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(home / "tws_settings"))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")

    with pytest.raises(RuntimeError, match="expected vmoptions file"):
        init_settings.set_java_vmoptions()

    assert (release_dir / "ibgateway.vmoptions").read_text() == "-Xmx256m\n"
    assert not (release_dir / "tws.vmoptions").exists()


def test_tws_vmoptions_updates_tws_file_only(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TWS runtime initialization should write the TWS vmoptions file."""
    home = tmp_path / "home" / "ibuser"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    create_ib_release_dir(release_dir, "tws")
    template_path = home / "vmoptions.j2"
    template_path.write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(home / "tws_settings"))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "2048")

    init_settings.set_java_vmoptions()

    vmoptions_content = (release_dir / "tws.vmoptions").read_text()
    assert "-Xmx2048m" in vmoptions_content
    assert "-Xms512m" in vmoptions_content
    assert not (release_dir / "ibgateway.vmoptions").exists()


def test_vmoptions_generation_defaults_tws_settings_path_to_home(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Python vmoptions generation should match start_ibc's settings path default."""
    home = tmp_path / "home" / "ibuser"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    create_ib_release_dir(release_dir, "tws")
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.delenv("TWS_SETTINGS_PATH", raising=False)
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")

    init_settings.set_java_vmoptions()

    vmoptions_content = (release_dir / "tws.vmoptions").read_text()
    assert f"-DjtsConfigDir={home / 'tws_settings'}" in vmoptions_content


def test_vmoptions_generation_rejects_directory_template_path(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """VM options generation should fail clearly when vmoptions.j2 is a directory."""
    home = tmp_path / "home" / "ibuser"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    create_ib_release_dir(release_dir, "tws")
    (home / "vmoptions.j2").mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(home / "tws_settings"))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")

    with pytest.raises(RuntimeError, match="VM options template is not a file"):
        init_settings.set_java_vmoptions()

    assert (release_dir / "tws.vmoptions").read_text() == "-Xmx256m\n"


def test_vmoptions_generation_rejects_missing_release_dir(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bad IB_RELEASE_DIR should fail before writing product vmoptions files."""
    home = tmp_path / "home" / "ibuser"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(home / "tws_settings"))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")

    with pytest.raises(RuntimeError, match="IB release directory does not exist"):
        init_settings.set_java_vmoptions()

    assert not release_dir.exists()


def test_vmoptions_generation_rejects_incomplete_release_layout(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Direct vmoptions generation should validate the release layout too."""
    home = tmp_path / "home" / "ibuser"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    (release_dir / "jars").mkdir(parents=True)
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(home / "tws_settings"))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")

    with pytest.raises(RuntimeError, match="expected executable"):
        init_settings.set_java_vmoptions()

    assert not (release_dir / "tws.vmoptions").exists()


def test_main_rejects_missing_release_dir_before_rendering_configs(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bad IB_RELEASE_DIR should not rewrite runtime configs first."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("IbLoginId=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "new-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")
    monkeypatch.setenv("TIME_ZONE", "America/New_York")

    with pytest.raises(RuntimeError, match="IB release directory does not exist"):
        init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=old\n"
    assert jts_ini.read_text() == "TimeZone=old\n"


def test_main_rejects_missing_credentials_before_rendering_configs(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing IB credentials should fail before rendering blank login config."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    create_ib_release_dir(release_dir, "tws")

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("IbLoginId=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.delenv("IB_USER", raising=False)
    monkeypatch.setenv("IB_PASSWORD", "paper-password")

    with pytest.raises(RuntimeError, match="Required environment variable IB_USER"):
        init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=old\n"
    assert jts_ini.read_text() == "TimeZone=old\n"


def test_main_rejects_missing_ibc_version_before_rendering_configs(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing IBC metadata should fail before rendering runtime config files."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    create_ib_release_dir(release_dir, "tws")

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("IbLoginId=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "new-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")
    monkeypatch.delenv("IBC_VERSION")

    with pytest.raises(RuntimeError, match="Required environment variable IBC_VERSION"):
        init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=old\n"
    assert jts_ini.read_text() == "TimeZone=old\n"


def test_main_rejects_invalid_ibc_version_before_rendering_configs(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runtime IBC version overrides should match Docker build validation."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    create_ib_release_dir(release_dir, "tws")

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("IbLoginId=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "new-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")
    monkeypatch.setenv("IBC_VERSION", "3.23")

    with pytest.raises(ValueError, match="IBC_VERSION must look like 3.23.0"):
        init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=old\n"
    assert jts_ini.read_text() == "TimeZone=old\n"


def test_main_rejects_gateway_release_dir_shape_before_rendering_configs(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Python startup validation should match IBC's Gateway path reconstruction."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "gateway" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    create_ib_release_dir(release_dir, "ibgateway")

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("IbLoginId=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "ibgateway")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "new-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")
    monkeypatch.setenv("TIME_ZONE", "America/New_York")

    with pytest.raises(
        RuntimeError, match="must be nested under an ibgateway directory"
    ):
        init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=old\n"
    assert jts_ini.read_text() == "TimeZone=old\n"
    assert (release_dir / "ibgateway.vmoptions").read_text() == "-Xmx256m\n"


def test_main_rejects_incomplete_release_layout_before_rendering_configs(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An incomplete IB release should be caught before config mutation."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    (release_dir / "jars").mkdir(parents=True)

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("IbLoginId=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "new-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")
    monkeypatch.setenv("TIME_ZONE", "America/New_York")

    with pytest.raises(RuntimeError, match="expected executable"):
        init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=old\n"
    assert jts_ini.read_text() == "TimeZone=old\n"


def test_main_rejects_invalid_custom_jvm_opts_before_rendering_configs(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid custom JVM option quoting should not allow partial config rewrites."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    create_ib_release_dir(release_dir, "tws")

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("IbLoginId=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "new-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")
    monkeypatch.setenv("TIME_ZONE", "America/New_York")
    monkeypatch.setenv("CUSTOM_JVM_OPTS", "'unterminated")

    with pytest.raises(ValueError, match="CUSTOM_JVM_OPTS is invalid"):
        init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=old\n"
    assert jts_ini.read_text() == "TimeZone=old\n"
    assert (release_dir / "tws.vmoptions").read_text() == "-Xmx256m\n"


def test_main_rejects_invalid_java_heap_before_rendering_configs(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid heap settings should fail before any runtime config mutation."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    create_ib_release_dir(release_dir, "tws")

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("IbLoginId=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "not-a-size")
    monkeypatch.setenv("IB_USER", "new-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")
    monkeypatch.setenv("TIME_ZONE", "America/New_York")

    with pytest.raises(ValueError, match="JAVA_HEAP_SIZE"):
        init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=old\n"
    assert jts_ini.read_text() == "TimeZone=old\n"
    assert (release_dir / "tws.vmoptions").read_text() == "-Xmx256m\n"


def test_main_rejects_invalid_trading_mode_before_rendering_configs(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid trading mode should not be rendered into IBC config first."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    create_ib_release_dir(release_dir, "tws")

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("TradingMode=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text(
        "TradingMode=${TRADING_MODE:-paper}\n"
    )
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "new-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")
    monkeypatch.setenv("TRADING_MODE", "demo")

    with pytest.raises(ValueError, match="Unsupported TRADING_MODE: demo"):
        init_settings.main()

    assert ibc_ini.read_text() == "TradingMode=old\n"
    assert jts_ini.read_text() == "TimeZone=old\n"
    assert (release_dir / "tws.vmoptions").read_text() == "-Xmx256m\n"


def test_main_rejects_invalid_twofa_timeout_action_before_rendering_configs(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid 2FA timeout action should fail before partial config rewrites."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    create_ib_release_dir(release_dir, "tws")

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("IbLoginId=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "new-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")
    monkeypatch.setenv("TWOFA_TIMEOUT_ACTION", "wait")

    with pytest.raises(ValueError, match="Unsupported TWOFA_TIMEOUT_ACTION: wait"):
        init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=old\n"
    assert jts_ini.read_text() == "TimeZone=old\n"
    assert (release_dir / "tws.vmoptions").read_text() == "-Xmx256m\n"


def test_main_rejects_relative_config_paths_before_rendering(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Relative config paths should not be expanded under an implicit cwd."""
    home = tmp_path / "home" / "ibuser"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    create_ib_release_dir(release_dir, "tws")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", "ibc.ini")
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(home / "tws_settings"))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "paper-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")

    with pytest.raises(RuntimeError, match="IBC_INI must be an absolute path"):
        init_settings.main()

    assert not (tmp_path / "ibc.ini").exists()


def test_main_rejects_relative_ibc_path_before_template_lookup(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Relative IBC_PATH should not control fallback template lookup."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_ini = tmp_path / "ibc" / "ibc.ini"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    create_ib_release_dir(release_dir, "tws")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_PATH", "opt/ibc")
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "paper-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")

    with pytest.raises(RuntimeError, match="IBC_PATH must be an absolute path"):
        init_settings.main()

    assert not ibc_ini.exists()


def test_main_rejects_missing_ibc_path_before_rendering_configs(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Missing IBC install paths should fail before config files are rewritten."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    create_ib_release_dir(release_dir, "tws")

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("IbLoginId=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.delenv("IBC_PATH", raising=False)
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "new-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")

    with pytest.raises(RuntimeError, match="Required environment variable IBC_PATH"):
        init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=old\n"
    assert jts_ini.read_text() == "TimeZone=old\n"


def test_main_rejects_incomplete_ibc_layout_before_rendering_configs(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bad IBC_PATH should not rewrite runtime configs before start_ibc fails."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    broken_ibc_path = tmp_path / "opt" / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    broken_ibc_path.mkdir(parents=True)
    create_ib_release_dir(release_dir, "tws")

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("IbLoginId=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_PATH", str(broken_ibc_path))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "new-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")

    with pytest.raises(RuntimeError, match="IBC layout is invalid"):
        init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=old\n"
    assert jts_ini.read_text() == "TimeZone=old\n"


def test_vmoptions_paths_rejects_unsupported_program(
    init_settings: ModuleType, tmp_path: Path
) -> None:
    """Python vmoptions generation should fail before writing unknown product files."""
    with pytest.raises(ValueError, match="Unsupported PROGRAM"):
        init_settings.vmoptions_paths("desktop", tmp_path)


def test_python_release_dir_rejects_unsupported_program_before_release_lookup(
    init_settings: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release path resolution should not ask for IB_RELEASE for unknown products."""
    monkeypatch.delenv("IB_RELEASE", raising=False)
    monkeypatch.delenv("IB_RELEASE_DIR", raising=False)

    with pytest.raises(ValueError, match="Unsupported PROGRAM: desktop"):
        init_settings.resolve_ib_release_dir("desktop")


def test_runtime_validation_rejects_unsupported_program_before_credentials(
    init_settings: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup validation should report a bad PROGRAM before unrelated env gaps."""
    monkeypatch.setenv("PROGRAM", "desktop")
    monkeypatch.delenv("IB_USER", raising=False)
    monkeypatch.delenv("IB_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="Unsupported PROGRAM: desktop"):
        init_settings.validate_runtime_environment()


def test_vmoptions_generation_rejects_unsupported_program_before_release_lookup(
    init_settings: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct vmoptions generation should fail on product name before path lookup."""
    monkeypatch.setenv("PROGRAM", "desktop")
    monkeypatch.delenv("IB_RELEASE", raising=False)
    monkeypatch.delenv("IB_RELEASE_DIR", raising=False)
    monkeypatch.delenv("HOME", raising=False)

    with pytest.raises(ValueError, match="Unsupported PROGRAM: desktop"):
        init_settings.set_java_vmoptions()


def test_main_renders_ini_files_from_templates_each_start(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Runtime config should be regenerated from templates when env values change."""
    home = tmp_path / "home" / "ibuser"
    settings_dir = tmp_path / "settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    settings_dir.mkdir()
    ibc_dir.mkdir()
    create_ib_release_dir(release_dir, "tws")

    ibc_ini = ibc_dir / "ibc.ini"
    jts_ini = settings_dir / "jts.ini"
    ibc_ini.write_text("IbLoginId=old\n")
    jts_ini.write_text("TimeZone=old\n")
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    jts_ini.with_suffix(".ini.template").write_text("TimeZone=${TIME_ZONE:-UTC}\n")
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "first-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")
    monkeypatch.setenv("TIME_ZONE", "America/New_York")

    init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=first-user\n"
    assert jts_ini.read_text() == "TimeZone=America/New_York\n"

    monkeypatch.setenv("IB_USER", "second-user")
    monkeypatch.setenv("TIME_ZONE", "UTC")

    init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=second-user\n"
    assert jts_ini.read_text() == "TimeZone=UTC\n"
    assert ibc_ini.with_suffix(".ini.template").read_text() == "IbLoginId=${IB_USER}\n"


def test_main_defaults_tws_settings_path_to_home(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Python config generation should use the same default settings dir as start_ibc."""
    home = tmp_path / "home" / "ibuser"
    default_settings_dir = home / "tws_settings"
    ibc_dir = tmp_path / "ibc"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    ibc_dir.mkdir()
    create_ib_release_dir(release_dir, "tws")

    ibc_ini = ibc_dir / "ibc.ini"
    ibc_ini.with_suffix(".ini.template").write_text("IbLoginId=${IB_USER}\n")
    default_settings_dir.mkdir()
    (default_settings_dir / "jts.ini.template").write_text(
        "TimeZone=${TIME_ZONE:-UTC}\n"
    )
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "tws")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_INI", str(ibc_ini))
    monkeypatch.delenv("TWS_SETTINGS_PATH", raising=False)
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "paper-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")
    monkeypatch.setenv("TIME_ZONE", "America/New_York")

    init_settings.main()

    assert ibc_ini.read_text() == "IbLoginId=paper-user\n"
    assert (
        default_settings_dir / "jts.ini"
    ).read_text() == "TimeZone=America/New_York\n"


def test_render_config_template_bootstraps_existing_placeholder_config(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Existing placeholder configs should become templates if no template exists yet."""
    config_path = tmp_path / "ibc.ini"
    template_path = config_path.with_suffix(".ini.template")
    config_path.write_text("IbLoginId=${IB_USER}\n")
    monkeypatch.setenv("IB_USER", "paper-user")

    init_settings.render_config_template(template_path, config_path, "ibc.ini")

    assert config_path.read_text() == "IbLoginId=paper-user\n"
    assert template_path.read_text() == "IbLoginId=${IB_USER}\n"


def test_render_config_template_preserves_existing_expanded_custom_config(
    init_settings: ModuleType, tmp_path: Path
) -> None:
    """Fallback templates should not clobber an existing custom config file."""
    config_path = tmp_path / "custom" / "ibc.ini"
    fallback_template_path = tmp_path / "defaults" / "ibc.ini.template"
    config_path.parent.mkdir()
    fallback_template_path.parent.mkdir()
    config_path.write_text("IbLoginId=custom-user\n")
    fallback_template_path.write_text("IbLoginId=${IB_USER}\n")

    init_settings.render_config_template(
        config_path.with_suffix(".ini.template"),
        config_path,
        "ibc.ini",
        fallback_template_path,
    )

    assert config_path.read_text() == "IbLoginId=custom-user\n"
    assert not config_path.with_suffix(".ini.template").exists()


def test_render_config_template_does_not_create_unused_template_parent(
    init_settings: ModuleType, tmp_path: Path
) -> None:
    """Expanded custom configs should not create unused template directories."""
    config_path = tmp_path / "runtime" / "ibc.ini"
    template_path = tmp_path / "templates" / "ibc.ini.template"
    config_path.parent.mkdir()
    config_path.write_text("IbLoginId=custom-user\n")

    init_settings.render_config_template(template_path, config_path, "ibc.ini")

    assert config_path.read_text() == "IbLoginId=custom-user\n"
    assert not template_path.parent.exists()


def test_render_config_template_creates_separate_template_parent(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Template bootstrapping should not assume template and output share a parent."""
    template_path = tmp_path / "templates" / "ibc.ini.template"
    config_path = tmp_path / "runtime" / "ibc.ini"
    config_path.parent.mkdir()
    config_path.write_text("IbLoginId=${IB_USER}\n")
    monkeypatch.setenv("IB_USER", "paper-user")

    init_settings.render_config_template(template_path, config_path, "ibc.ini")

    assert config_path.read_text() == "IbLoginId=paper-user\n"
    assert template_path.read_text() == "IbLoginId=${IB_USER}\n"


def test_render_config_template_rejects_directory_output_path(
    init_settings: ModuleType, tmp_path: Path
) -> None:
    """Config rendering should fail clearly when the output path is a directory."""
    template_path = tmp_path / "templates" / "ibc.ini.template"
    output_path = tmp_path / "runtime" / "ibc.ini"
    template_path.parent.mkdir()
    template_path.write_text("IbLoginId=${IB_USER}\n")
    output_path.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="ibc.ini output is not a file"):
        init_settings.render_config_template(template_path, output_path, "ibc.ini")

    assert template_path.read_text() == "IbLoginId=${IB_USER}\n"


def test_render_config_template_rejects_directory_fallback_template(
    init_settings: ModuleType, tmp_path: Path
) -> None:
    """Fallback config bootstrapping should reject directory template paths clearly."""
    template_path = tmp_path / "runtime" / "ibc.ini.template"
    output_path = tmp_path / "runtime" / "ibc.ini"
    fallback_template_path = tmp_path / "defaults" / "ibc.ini.template"
    fallback_template_path.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="ibc.ini fallback template is not a file"):
        init_settings.render_config_template(
            template_path,
            output_path,
            "ibc.ini",
            fallback_template_path,
        )

    assert not output_path.parent.exists()


def test_main_bootstraps_custom_config_paths_from_default_templates(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Custom runtime config paths should be created from bundled templates."""
    home = tmp_path / "home" / "ibuser"
    default_settings_dir = home / "tws_settings"
    custom_settings_dir = tmp_path / "custom" / "settings"
    default_ibc_dir = tmp_path / "opt" / "ibc"
    custom_ibc_ini = tmp_path / "custom" / "ibc" / "custom.ini"
    release_dir = tmp_path / "opt" / "ibgateway" / "stable"
    default_settings_dir.mkdir(parents=True)
    create_ibc_dir(default_ibc_dir)
    create_ib_release_dir(release_dir, "ibgateway")

    default_ibc_template = default_ibc_dir / "ibc.ini.template"
    default_jts_template = default_settings_dir / "jts.ini.template"
    default_ibc_template.write_text("IbLoginId=${IB_USER}\n")
    default_jts_template.write_text("TimeZone=${TIME_ZONE:-UTC}\n")
    (home / "vmoptions.j2").write_text(VMOPTIONS_TEMPLATE_PATH.read_text())

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PROGRAM", "ibgateway")
    monkeypatch.setenv("IB_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("IBC_PATH", str(default_ibc_dir))
    monkeypatch.setenv("IBC_INI", str(custom_ibc_ini))
    monkeypatch.setenv("TWS_SETTINGS_PATH", str(custom_settings_dir))
    monkeypatch.setenv("JAVA_HEAP_SIZE", "1024m")
    monkeypatch.setenv("IB_USER", "custom-user")
    monkeypatch.setenv("IB_PASSWORD", "paper-password")
    monkeypatch.setenv("TIME_ZONE", "America/New_York")

    init_settings.main()

    custom_jts_ini = custom_settings_dir / "jts.ini"
    assert custom_ibc_ini.read_text() == "IbLoginId=custom-user\n"
    assert custom_jts_ini.read_text() == "TimeZone=America/New_York\n"
    assert (
        custom_ibc_ini.with_suffix(".ini.template").read_text()
        == default_ibc_template.read_text()
    )
    assert (
        custom_jts_ini.with_suffix(".ini.template").read_text()
        == default_jts_template.read_text()
    )
    assert (release_dir / "ibgateway.vmoptions").exists()


def test_java_heap_size_rejects_invalid_values(init_settings: ModuleType) -> None:
    """Invalid heap values should fail before writing broken vmoptions."""
    with pytest.raises(ValueError, match="JAVA_HEAP_SIZE"):
        init_settings.parse_memory_mb("2gb")


def test_auto_java_heap_size_has_safe_minimum(
    init_settings: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tiny cgroup limits should not render zero or near-zero max heap values."""
    monkeypatch.delenv("JAVA_HEAP_SIZE", raising=False)
    monkeypatch.setattr(init_settings, "detect_memory_mb", lambda: 128)

    assert init_settings.calculate_java_heap_size() == "256"


def test_initial_heap_never_exceeds_max_heap(init_settings: ModuleType) -> None:
    """Small explicit heap values should still render a valid Xms/Xmx pair."""
    assert init_settings.calculate_initial_heap_size("64m") == 64
    assert init_settings.calculate_initial_heap_size("256m") == 128


def test_supervisor_config_uses_supported_startup_coordination() -> None:
    """Supervisor config should avoid unsupported dependency keys."""
    content = SUPERVISORD_CONF_PATH.read_text()

    assert "depends_on" not in content
    assert "[program:settings]" not in content
    assert "[unix_http_server]" in content
    assert "serverurl=unix:///tmp/supervisor.sock" in content


def test_dockerfile_healthcheck_uses_supervisor_service_status() -> None:
    """Healthcheck should fail when IBC is not running under supervisord."""
    content = DOCKERFILE_PATH.read_text()

    assert "--start-period=180s" in content
    assert "supervisorctl status xvfb ibc" in content
    assert "grep -Eq '^xvfb[[:space:]]+RUNNING'" in content
    assert "grep -Eq '^ibc[[:space:]]+RUNNING'" in content
    assert "pgrep -f supervisord" not in content


def test_dockerfile_validates_build_args_before_downloads() -> None:
    """Builds should reject invalid products/releases before installer downloads."""
    content = DOCKERFILE_PATH.read_text()
    first_validation = content.index("Unsupported PROGRAM")
    first_download = content.index("wget -q -O /ib.sh")

    assert first_validation < first_download
    assert "Unsupported RELEASE" in content
    assert "IB installer artifacts are only supported with ARCH=x64" in content
    assert "VERSION must be NULL or a packaged IB version" in content
    assert "VERSION must look like 10.45.1e or be NULL" in content
    assert "grep -Eqz '^[0-9]+[.][0-9]+[.][0-9]+[a-z]?$'" in content
    assert "'^[0-9]+[.][0-9]+[.][0-9]+[a-z]?$'" in content
    assert "IBC_VERSION must not be empty" in content
    assert "IBC_VERSION must look like 3.23.0" in content
    assert "grep -Eqz '^[0-9]+[.][0-9]+[.][0-9]+$'" in content
    assert "'^[0-9]+[.][0-9]+[.][0-9]+$'" in content


def test_dockerfile_build_arg_regexes_reject_embedded_newlines() -> None:
    """Docker build arg validation should consume the whole value, not one line."""
    version_result = run_bash_unchecked(
        """
        VERSION=$'10.45.1e\\nbad'
        printf '%s' "$VERSION" | grep -Eqz '^[0-9]+[.][0-9]+[.][0-9]+[a-z]?$'
        """
    )
    ibc_result = run_bash_unchecked(
        """
        IBC_VERSION=$'3.23.0\\nbad'
        printf '%s' "$IBC_VERSION" | grep -Eqz '^[0-9]+[.][0-9]+[.][0-9]+$'
        """
    )

    assert version_result.returncode == 1
    assert ibc_result.returncode == 1


def test_dockerfile_arg_defaults_do_not_include_inline_comments() -> None:
    """Direct Docker builds should not parse explanatory comments as ARG defaults."""
    content = DOCKERFILE_PATH.read_text()

    assert "ARG PROGRAM=ibgateway       #" not in content
    assert "ARG RELEASE=stable          #" not in content
    assert "ARG ARCH=x64                #" not in content
    assert "\nARG PROGRAM=ibgateway\n" in content
    assert "\nARG RELEASE=stable\n" in content
    assert "\nARG ARCH=x64\n" in content


def test_dockerfile_verifies_ibc_start_script_during_build() -> None:
    """Builds should fail if the IBC archive does not contain the runtime entrypoint."""
    content = DOCKERFILE_PATH.read_text()

    assert 'find "$IBC_PATH" -type f -name "*.sh" -exec chmod u+x {} +' in content
    assert 'test -x "$IBC_PATH/scripts/ibcstart.sh"' in content
    assert (
        "chmod -R u+x ${IBC_PATH}/*.sh ${IBC_PATH}/scripts/*.sh || true" not in content
    )


def test_dockerfile_requires_release_checksum_to_reference_installer() -> None:
    """Packaged release builds should reject mismatched checksum sidecars."""
    content = DOCKERFILE_PATH.read_text()

    checksum_file = content.index('CHECKSUM_FILE="$(sed -E')
    checksum_validation = content.index('if [ "$CHECKSUM_FILE" != "$FILE" ]; then')
    checksum_check = content.index('sha256sum --strict --check "/$FILE.sha256"')
    installer_move = content.index('mv "/$FILE" /ib.sh')

    assert checksum_file < checksum_validation < checksum_check < installer_move
    assert "Checksum sidecar does not reference expected file $FILE" in content
    assert "sha256sum --check" not in content


def test_release_workflows_validate_tag_format_before_build_args() -> None:
    """Release workflows should reject malformed tags before passing build args."""
    for workflow_path in [GATEWAY_WORKFLOW_PATH, TWS_WORKFLOW_PATH]:
        content = workflow_path.read_text()
        validation = content.index("Release tag must look like")
        release_type = content.index('release_type="${release_name%%-*}"')
        docker_build = content.index("docker/build-push-action")

        assert validation < release_type < docker_build
        assert "^(stable|latest|beta)-[0-9]+[.][0-9]+[.][0-9]+[a-z]?$" in content
        assert """"$release_name" == *$'\\n'*""" in content
        assert """"$release_name" == *$'\\r'*""" in content


def test_release_workflow_tag_guard_rejects_trailing_newline() -> None:
    """Workflow tag validation should not accept newline-tainted manual inputs."""
    valid_result = run_bash(
        """
        release_name="stable-10.45.1e"
        tag_pattern='^(stable|latest|beta)-[0-9]+[.][0-9]+[.][0-9]+[a-z]?$'
        if [[ "$release_name" == *$'\\n'* ]] ||
           [[ "$release_name" == *$'\\r'* ]] ||
           [[ ! "$release_name" =~ $tag_pattern ]]; then
          exit 1
        fi
        """
    )
    invalid_result = run_bash_unchecked(
        """
        release_name=$'stable-10.45.1e\\n'
        tag_pattern='^(stable|latest|beta)-[0-9]+[.][0-9]+[.][0-9]+[a-z]?$'
        if [[ "$release_name" == *$'\\n'* ]] ||
           [[ "$release_name" == *$'\\r'* ]] ||
           [[ ! "$release_name" =~ $tag_pattern ]]; then
          exit 1
        fi
        """
    )

    assert valid_result.returncode == 0
    assert invalid_result.returncode == 1


def test_release_workflows_require_major_minor_tag() -> None:
    """Release workflows should not push an empty major/minor Docker tag."""
    for workflow_path in [GATEWAY_WORKFLOW_PATH, TWS_WORKFLOW_PATH]:
        content = workflow_path.read_text()
        extraction = content.index("major_minor_version=$(echo")
        validation = content.index("Could not extract major/minor version")
        output = content.index("major_minor_version=$major_minor_version")

        assert extraction < validation < output
        assert 'if [ -z "$major_minor_version" ]; then' in content


def test_release_workflows_quote_github_output_path() -> None:
    """Workflow parsing should still write outputs if runner paths contain spaces."""
    for workflow_path in [GATEWAY_WORKFLOW_PATH, TWS_WORKFLOW_PATH]:
        content = workflow_path.read_text()

        assert '>> "$GITHUB_OUTPUT"' in content
        assert ">> $GITHUB_OUTPUT" not in content


def test_release_workflows_require_manual_tag_input() -> None:
    """Manual release builds should not allow an empty tag input in the UI."""
    for workflow_path in [GATEWAY_WORKFLOW_PATH, TWS_WORKFLOW_PATH]:
        content = workflow_path.read_text()
        tag_input = content.index("tag_name:")
        tag_required = content.index("required: true", tag_input)
        parse_step = content.index("release_name=")

        assert tag_input < tag_required < parse_step
        assert "required: false" not in content


def test_release_workflows_do_not_publish_broad_beta_aliases() -> None:
    """Beta builds should not overwrite broad major or major/minor Docker tags."""
    for workflow_path, image_name in [
        (GATEWAY_WORKFLOW_PATH, "ib-gateway"),
        (TWS_WORKFLOW_PATH, "ib-tws"),
    ]:
        content = workflow_path.read_text()

        assert 'major_version="${version%%.*}"' in content
        assert "Could not extract major version" in content
        assert "major_version=$major_version" in content
        assert "outputs.release_type != 'beta'" in content
        assert "outputs.release_type == 'latest'" in content
        assert f"format('{{0}}/{image_name}:{{1}}'" in content


def test_release_workflows_run_after_release_assets_are_published() -> None:
    """Release-triggered builds should not start before packaged assets are uploaded."""
    for workflow_path in [GATEWAY_WORKFLOW_PATH, TWS_WORKFLOW_PATH]:
        content = workflow_path.read_text()

        assert "release:\n      types: [published]" in content
        assert "types: [created]" not in content


def test_ci_module_does_not_read_secrets_at_import_time() -> None:
    """CI helpers should be importable without runtime-only secret environment."""
    tree = ast.parse(CI_PATH.read_text())
    top_level_nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Expr))
    ]

    for node in top_level_nodes:
        source = ast.get_source_segment(CI_PATH.read_text(), node)
        assert source is not None
        assert 'os.environ["GITHUB_TOKEN"]' not in source
        assert 'os.environ["DOCKERHUB_USERNAME"]' not in source
        assert 'os.environ["DOCKERHUB_TOKEN"]' not in source
        assert "downloads_dir.mkdir" not in source


def test_ci_validates_release_tags_before_building() -> None:
    """CI build helpers should reject malformed release tags before image builds."""
    content = CI_PATH.read_text()

    assert "BUILD_VERSION_RE = re.compile" in content
    assert "RELEASE_TAG_RE = re.compile" in content
    assert "latest|stable|beta" in content
    assert "def parse_release_tag(tag_name: str) -> GitHubRelease:" in content
    assert 'raise ValueError(f"Invalid release tag: {tag_name}")' in content
    assert (
        "releases: list[IBRelease | GitHubRelease] = [parse_release_tag(tag)]"
        in content
    )


def test_ci_parse_release_tag_rejects_invalid_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release tag validation should run before any build side effects."""
    ci_module = load_ci_module(monkeypatch)

    parsed = ci_module.parse_release_tag("stable-10.45.1e")

    assert parsed.release == "stable"
    assert parsed.build_version == "10.45.1e"
    with pytest.raises(ValueError, match="Invalid release tag"):
        ci_module.parse_release_tag("ibgateway-stable-10.45.1e")
    with pytest.raises(ValueError, match="Invalid release tag"):
        ci_module.parse_release_tag("stable-10.45.1e\n")


def test_ci_ib_release_rejects_invalid_program_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduled release metadata should not build URLs for unknown products."""
    ci_module = load_ci_module(monkeypatch)

    with pytest.raises(ValueError, match="Unsupported PROGRAM: desktop"):
        ci_module.IBRelease(release="stable", program="desktop")


def test_ci_ib_release_rejects_invalid_scheduled_channel_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduled release metadata should not build URLs for unknown channels."""
    ci_module = load_ci_module(monkeypatch)

    with pytest.raises(ValueError, match="Unsupported scheduled RELEASE: beta"):
        ci_module.IBRelease(release="beta", program="ibgateway")


def test_ci_validates_upstream_build_versions_before_release_tags() -> None:
    """Release creation should reject unexpected upstream buildVersion strings."""
    content = CI_PATH.read_text()

    assert (
        "def release_meta_value(release_meta: dict[str, Any], key: str, source: str)"
        in content
    )
    assert "def parse_build_version(version: str, source: str) -> str:" in content
    assert "if not BUILD_VERSION_RE.fullmatch(version):" in content
    assert "Invalid IB build version from {source}: {version}" in content
    assert (
        'release_meta_value(\n                self.release_meta,\n                "buildVersion",'
        in content
    )
    assert "return parse_build_version(" in content
    assert 'version = parse_build_version(version, "Docker image build")' in content


def test_ci_parse_build_version_rejects_invalid_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build version validation should reject strings that would make bad tags."""
    ci_module = load_ci_module(monkeypatch)

    assert ci_module.parse_build_version("10.45.1e", "test") == "10.45.1e"
    with pytest.raises(ValueError, match="Invalid IB build version"):
        ci_module.parse_build_version("10.45", "test")
    with pytest.raises(ValueError, match="Invalid IB build version"):
        ci_module.parse_build_version("10.45.1e\n", "test")


def test_ci_validates_upstream_build_timestamps_before_release_notes() -> None:
    """Release notes should not fail with raw timestamp parsing errors."""
    content = CI_PATH.read_text()

    assert "def parse_build_datetime(value: str, source: str) -> datetime:" in content
    assert "return datetime.fromisoformat(value.strip())" in content
    assert "Invalid IB build datetime from {source}: {value}" in content
    assert (
        'release_meta_value(\n                self.release_meta,\n                "buildDateTime",'
        in content
    )
    assert "return parse_build_datetime(" in content


def test_ci_parse_build_datetime_rejects_invalid_timestamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release note timestamp validation should report its source clearly."""
    ci_module = load_ci_module(monkeypatch)

    parsed = ci_module.parse_build_datetime("2026-05-12T13:45:00", "test metadata")

    assert parsed.isoformat() == "2026-05-12T13:45:00"
    with pytest.raises(
        ValueError, match="Invalid IB build datetime from test metadata"
    ):
        ci_module.parse_build_datetime("not-a-date", "test metadata")


def test_ci_metadata_parser_rejects_missing_or_non_string_values() -> None:
    """Release metadata parsing should not assume upstream JSON shape blindly."""
    content = CI_PATH.read_text()

    assert (
        "def parse_release_meta(content: str, source: str) -> dict[str, Any]:"
        in content
    )
    assert "return parse_release_meta(resp, url)" in content
    assert "except json.JSONDecodeError as exc:" in content
    assert "json.JSONDecoder().raw_decode(metadata_content)" in content
    assert "Invalid release metadata JSON from {source}: {exc}" in content
    assert "Unexpected trailing release metadata content from {source}" in content
    assert "Release metadata from {source} must be a JSON object" in content
    assert 'raise RuntimeError(f"Missing {key} from {source}") from exc' in content
    assert "if not isinstance(value, str):" in content
    assert 'raise ValueError(f"Invalid {key} from {source}: {value}")' in content
    assert "return value.strip()" in content


def test_ci_parse_release_meta_rejects_invalid_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upstream version metadata should fail clearly when the JSON is malformed."""
    ci_module = load_ci_module(monkeypatch)

    assert ci_module.parse_release_meta(
        'callback({"buildVersion": "10.45.1e"})', "test-url"
    ) == {"buildVersion": "10.45.1e"}
    assert ci_module.parse_release_meta(
        'ibgatewaystable_callback({"buildVersion":"10.45.1e",'
        '"buildDateTime":"20260507 05:00:06"});',
        "test-url",
    ) == {"buildVersion": "10.45.1e", "buildDateTime": "20260507 05:00:06"}
    with pytest.raises(RuntimeError, match="Could not parse release metadata"):
        ci_module.parse_release_meta("no json here", "test-url")
    with pytest.raises(RuntimeError, match="Invalid release metadata JSON"):
        ci_module.parse_release_meta('callback({"buildVersion": })', "test-url")
    with pytest.raises(RuntimeError, match="Unexpected trailing release metadata"):
        ci_module.parse_release_meta(
            'callback({"buildVersion": "10.45.1e"}); {}', "test-url"
        )
    with pytest.raises(RuntimeError, match="must be a JSON object"):
        ci_module.parse_release_meta("[1, 2, 3]", "test-url")


def test_ci_release_meta_value_rejects_missing_or_non_string_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release metadata extraction should fail before raw indexing errors leak."""
    ci_module = load_ci_module(monkeypatch)

    assert (
        ci_module.release_meta_value(
            {"buildVersion": " 10.45.1e "}, "buildVersion", "test"
        )
        == "10.45.1e"
    )
    with pytest.raises(RuntimeError, match="Missing buildVersion from test"):
        ci_module.release_meta_value({}, "buildVersion", "test")
    with pytest.raises(ValueError, match="Invalid buildVersion from test"):
        ci_module.release_meta_value({"buildVersion": 1045}, "buildVersion", "test")


def test_ci_release_discovery_skips_unsupported_tags() -> None:
    """Daily release discovery should tolerate old or unrelated GitHub release tags."""
    content = CI_PATH.read_text()

    assert "release = parse_release_tag(gh_release.tag_name)" in content
    assert "Skipping release with unsupported tag: %s" in content
    assert "gh_release.tag_name" in content
    assert "if not release_has_required_assets(gh_release, release):" in content
    assert "continue" in content


def test_ci_find_latest_releases_skips_unsupported_and_beta_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scheduled release discovery should return latest/stable only."""
    ci_module = load_ci_module(monkeypatch)

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name
            self.browser_download_url = f"https://example.test/{name}"

    class FakeRelease:
        def __init__(self, tag_name: str) -> None:
            self.tag_name = tag_name
            self.draft = False

        def get_assets(self) -> list[FakeAsset]:
            release = ci_module.parse_release_tag(self.tag_name)
            return [
                FakeAsset(name)
                for name in ci_module.expected_release_asset_names(release)
            ]

    class FakeRepo:
        def get_releases(self) -> list[FakeRelease]:
            return [
                FakeRelease("ibgateway-stable-10.43.1"),
                FakeRelease("beta-10.46.1"),
                FakeRelease("stable-10.45.1e"),
                FakeRelease("latest-10.46.1"),
                FakeRelease("latest-10.45.2"),
            ]

    monkeypatch.setattr(ci_module, "get_gh_repo", lambda: FakeRepo())
    monkeypatch.setattr(ci_module, "fetch", fake_release_asset_fetch)

    releases = ci_module.find_latest_github_releases()

    assert releases == [
        ci_module.GitHubRelease(release="stable", build_version="10.45.1e"),
        ci_module.GitHubRelease(release="latest", build_version="10.46.1"),
    ]


def test_ci_release_discovery_skips_releases_with_missing_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incomplete GitHub releases should not block a retry on the next run."""
    ci_module = load_ci_module(monkeypatch)

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name
            self.browser_download_url = f"https://example.test/{name}"

    class FakeRelease:
        def __init__(self, tag_name: str, asset_names: set[str]) -> None:
            self.tag_name = tag_name
            self.asset_names = asset_names
            self.draft = False

        def get_assets(self) -> list[FakeAsset]:
            return [FakeAsset(name) for name in self.asset_names]

    class FakeRepo:
        def get_releases(self) -> list[FakeRelease]:
            stable_release = ci_module.GitHubRelease(
                release="stable", build_version="10.45.1e"
            )
            latest_release = ci_module.GitHubRelease(
                release="latest", build_version="10.46.1"
            )
            incomplete_stable_assets = {
                "ibgateway-stable-10.45.1e-standalone-linux-x64.sh"
            }
            return [
                FakeRelease("stable-10.45.1e", incomplete_stable_assets),
                FakeRelease(
                    "latest-10.46.1",
                    ci_module.expected_release_asset_names(latest_release),
                ),
                FakeRelease(
                    "stable-10.45.1e",
                    ci_module.expected_release_asset_names(stable_release),
                ),
            ]

    monkeypatch.setattr(ci_module, "get_gh_repo", lambda: FakeRepo())
    monkeypatch.setattr(ci_module, "fetch", fake_release_asset_fetch)

    releases = ci_module.find_latest_github_releases()

    assert releases == [
        ci_module.GitHubRelease(release="latest", build_version="10.46.1"),
        ci_module.GitHubRelease(release="stable", build_version="10.45.1e"),
    ]


def test_ci_release_discovery_skips_mismatched_checksum_sidecars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed checksum sidecars should not make a broken release look complete."""
    ci_module = load_ci_module(monkeypatch)

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name
            self.browser_download_url = f"https://example.test/{name}"

    class FakeRelease:
        def __init__(self, tag_name: str) -> None:
            self.tag_name = tag_name
            self.draft = False

        def get_assets(self) -> list[FakeAsset]:
            release = ci_module.parse_release_tag(self.tag_name)
            return [
                FakeAsset(name)
                for name in ci_module.expected_release_asset_names(release)
            ]

    class FakeRepo:
        def get_releases(self) -> list[FakeRelease]:
            return [
                FakeRelease("latest-10.46.1"),
                FakeRelease("latest-10.45.2"),
                FakeRelease("stable-10.45.1e"),
            ]

    def fake_fetch(url: str, as_text: bool = True) -> str | bytes:
        asset_name = Path(url).name
        if asset_name == "ibgateway-latest-10.46.1-standalone-linux-x64.sh.sha256":
            return f"{'0' * 64} wrong-file.sh\n"
        return fake_release_asset_fetch(url, as_text=as_text)

    monkeypatch.setattr(ci_module, "get_gh_repo", lambda: FakeRepo())
    monkeypatch.setattr(ci_module, "fetch", fake_fetch)

    releases = ci_module.find_latest_github_releases()

    assert releases == [
        ci_module.GitHubRelease(release="latest", build_version="10.45.2"),
        ci_module.GitHubRelease(release="stable", build_version="10.45.1e"),
    ]


def test_ci_release_discovery_skips_stale_checksum_sidecars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checksum sidecars should match both filename and installer content."""
    ci_module = load_ci_module(monkeypatch)

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name
            self.browser_download_url = f"https://example.test/{name}"

    class FakeRelease:
        def __init__(self, tag_name: str) -> None:
            self.tag_name = tag_name
            self.draft = False

        def get_assets(self) -> list[FakeAsset]:
            release = ci_module.parse_release_tag(self.tag_name)
            return [
                FakeAsset(name)
                for name in ci_module.expected_release_asset_names(release)
            ]

    class FakeRepo:
        def get_releases(self) -> list[FakeRelease]:
            return [
                FakeRelease("latest-10.46.1"),
                FakeRelease("latest-10.45.2"),
                FakeRelease("stable-10.45.1e"),
            ]

    def fake_fetch(url: str, as_text: bool = True) -> str | bytes:
        asset_name = Path(url).name
        if asset_name == "ibgateway-latest-10.46.1-standalone-linux-x64.sh.sha256":
            return f"{'0' * 64} ibgateway-latest-10.46.1-standalone-linux-x64.sh\n"
        return fake_release_asset_fetch(url, as_text=as_text)

    monkeypatch.setattr(ci_module, "get_gh_repo", lambda: FakeRepo())
    monkeypatch.setattr(ci_module, "fetch", fake_fetch)

    releases = ci_module.find_latest_github_releases()

    assert releases == [
        ci_module.GitHubRelease(release="latest", build_version="10.45.2"),
        ci_module.GitHubRelease(release="stable", build_version="10.45.1e"),
    ]


def test_ci_release_discovery_skips_unfetchable_installer_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Installer fetch failures during checksum validation should not abort discovery."""
    ci_module = load_ci_module(monkeypatch)

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name
            self.browser_download_url = f"https://example.test/{name}"

    class FakeRelease:
        def __init__(self, tag_name: str) -> None:
            self.tag_name = tag_name
            self.draft = False

        def get_assets(self) -> list[FakeAsset]:
            release = ci_module.parse_release_tag(self.tag_name)
            return [
                FakeAsset(name)
                for name in ci_module.expected_release_asset_names(release)
            ]

    class FakeRepo:
        def get_releases(self) -> list[FakeRelease]:
            return [
                FakeRelease("latest-10.46.1"),
                FakeRelease("latest-10.45.2"),
                FakeRelease("stable-10.45.1e"),
            ]

    def fake_fetch(url: str, as_text: bool = True) -> str | bytes:
        asset_name = Path(url).name
        if (
            asset_name == "ibgateway-latest-10.46.1-standalone-linux-x64.sh"
            and not as_text
        ):
            raise RuntimeError("download failed")
        return fake_release_asset_fetch(url, as_text=as_text)

    monkeypatch.setattr(ci_module, "get_gh_repo", lambda: FakeRepo())
    monkeypatch.setattr(ci_module, "fetch", fake_fetch)

    releases = ci_module.find_latest_github_releases()

    assert releases == [
        ci_module.GitHubRelease(release="latest", build_version="10.45.2"),
        ci_module.GitHubRelease(release="stable", build_version="10.45.1e"),
    ]


def test_ci_release_discovery_skips_draft_releases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Complete draft releases should remain repairable instead of blocking retries."""
    ci_module = load_ci_module(monkeypatch)

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name
            self.browser_download_url = f"https://example.test/{name}"

    class FakeRelease:
        def __init__(self, tag_name: str, draft: bool) -> None:
            self.tag_name = tag_name
            self.draft = draft

        def get_assets(self) -> list[FakeAsset]:
            release = ci_module.parse_release_tag(self.tag_name)
            return [
                FakeAsset(name)
                for name in ci_module.expected_release_asset_names(release)
            ]

    class FakeRepo:
        def get_releases(self) -> list[FakeRelease]:
            return [
                FakeRelease("latest-10.46.1", True),
                FakeRelease("latest-10.45.2", False),
                FakeRelease("stable-10.45.1e", False),
            ]

    monkeypatch.setattr(ci_module, "get_gh_repo", lambda: FakeRepo())
    monkeypatch.setattr(ci_module, "fetch", fake_release_asset_fetch)

    releases = ci_module.find_latest_github_releases()

    assert releases == [
        ci_module.GitHubRelease(release="latest", build_version="10.45.2"),
        ci_module.GitHubRelease(release="stable", build_version="10.45.1e"),
    ]


def test_ci_scheduled_release_discovery_ignores_beta_tags() -> None:
    """Daily release checks should still discover latest and stable when beta exists."""
    content = CI_PATH.read_text()

    assert "Skipping draft release during scheduled release discovery" in content
    assert 'if release.release == "beta":' in content
    assert "Skipping beta release during scheduled release discovery" in content
    assert content.index('if release.release == "beta":') < content.index(
        "if release.release not in releases:"
    )


def test_ci_shared_release_tags_require_both_products() -> None:
    """Shared release tags should not be created with only one product artifact."""
    content = CI_PATH.read_text()

    assert "created_releases = []" in content
    assert (
        "release_programs = {ib_release.program for ib_release in ib_releases}"
        in content
    )
    assert 'release_programs != {"ibgateway", "tws"}' in content
    assert (
        "Skipping %s-%s release until both Gateway and TWS artifacts are available"
        in content
    )
    assert "ThreadPoolExecutor(max_workers=len(ib_releases))" in content
    assert "ThreadPoolExecutor(max_workers=len(new_releases))" not in content
    assert "created_releases.extend(ib_releases)" in content
    assert "return created_releases" in content


def test_ci_build_platforms_match_workflow_support() -> None:
    """Manual CI image builds should not attempt unsupported TWS arm64 builds."""
    ci_content = CI_PATH.read_text()
    gateway_workflow = GATEWAY_WORKFLOW_PATH.read_text()
    tws_workflow = TWS_WORKFLOW_PATH.read_text()

    assert (
        'if program == "ibgateway":\n        return "linux/amd64,linux/arm64"'
        in ci_content
    )
    assert 'if program == "tws":\n        return "linux/amd64"' in ci_content
    assert '"--platform",\n        platforms,' in ci_content
    assert "platforms: linux/amd64,linux/arm64" in gateway_workflow
    assert "platforms: linux/amd64\n" in tws_workflow
    assert "platforms: linux/amd64,linux/arm64" not in tws_workflow


def test_ci_build_tags_use_dockerhub_namespace() -> None:
    """Manual CI image pushes should target the configured DockerHub namespace."""
    content = CI_PATH.read_text()

    assert 'dockerhub_username = require_env("DOCKERHUB_USERNAME")' in content
    assert "def docker_image_repository(program: str) -> str:" in content
    assert 'return "ib-gateway"' in content
    assert 'return "ib-tws"' in content
    assert "image_repository = docker_image_repository(program)" in content
    assert 'image_name = f"{dockerhub_username}/{image_repository}"' in content


def test_ci_build_validates_release_channel_and_product_before_docker() -> None:
    """Manual CI builds should fail clearly for invalid direct-call build params."""
    content = CI_PATH.read_text()

    assert (
        "def parse_release_channel(release: str, source: str) -> ReleaseChannel:"
        in content
    )
    assert "Invalid IB release channel from {source}: {release}" in content
    assert 'release = parse_release_channel(release, "Docker image build")' in content
    assert "image_repository = docker_image_repository(program)" in content
    assert "platforms = docker_platforms(program)" in content
    assert content.index(
        "image_repository = docker_image_repository(program)"
    ) < content.index('dockerhub_username = require_env("DOCKERHUB_USERNAME")')
    assert 'raise ValueError(f"Unsupported PROGRAM: {program}")' in content


def test_ci_build_image_rejects_bad_program_before_secret_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid product builds should not be hidden by missing DockerHub secrets."""
    ci_module = load_ci_module(monkeypatch)
    monkeypatch.delenv("DOCKERHUB_USERNAME", raising=False)

    with pytest.raises(ValueError, match="Unsupported PROGRAM: desktop"):
        ci_module.build_image(("desktop", "stable", "10.45.1e"))


def test_ci_build_image_uses_argv_and_expected_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manual CI builds should pass exact buildx argv without shell splitting."""
    ci_module = load_ci_module(monkeypatch)
    captured: dict[str, object] = {}

    def fake_run(
        cmd: list[str],
        capture_output: bool,
        check: bool,
        text: bool,
        cwd: str,
    ) -> object:
        captured["cmd"] = cmd
        captured["capture_output"] = capture_output
        captured["check"] = check
        captured["text"] = text
        captured["cwd"] = cwd
        return ci_module.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setenv("DOCKERHUB_USERNAME", "demo")
    monkeypatch.setattr(ci_module, "run", fake_run)

    ci_module.build_image(("ibgateway", "latest", "10.45.1e"))

    assert captured["cmd"] == [
        "docker",
        "buildx",
        "build",
        "--platform",
        "linux/amd64,linux/arm64",
        "--build-arg",
        "PROGRAM=ibgateway",
        "--build-arg",
        "RELEASE=latest",
        "--build-arg",
        "VERSION=10.45.1e",
        "-t",
        "demo/ib-gateway:latest",
        "-t",
        "demo/ib-gateway:10.45.1e",
        "-t",
        "demo/ib-gateway:10.45",
        "-t",
        "demo/ib-gateway:10",
        "--push",
        ".",
    ]
    assert captured["capture_output"] is True
    assert captured["check"] is False
    assert captured["text"] is True
    assert captured["cwd"] == str(REPO_ROOT / "build")


def test_ci_docker_tags_do_not_give_beta_broad_aliases() -> None:
    """Manual CI builds should match workflow beta tag behavior."""
    content = CI_PATH.read_text()

    assert "def docker_tags(release: str, version: str) -> list[str]:" in content
    assert "tags = [release, version]" in content
    assert 'if release != "beta":' in content
    assert 'tags.append(f"{major}.{minor}")' in content
    assert 'if release == "latest":' in content
    assert "tags.append(major)" in content
    assert "tags = docker_tags(release, version)" in content


def test_ci_docker_tags_match_release_channel_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Docker tag generation should avoid broad aliases for beta releases."""
    ci_module = load_ci_module(monkeypatch)

    assert ci_module.docker_tags("beta", "10.45.1e") == ["beta", "10.45.1e"]
    assert ci_module.docker_tags("stable", "10.45.1e") == [
        "stable",
        "10.45.1e",
        "10.45",
    ]
    assert ci_module.docker_tags("latest", "10.45.1e") == [
        "latest",
        "10.45.1e",
        "10.45",
        "10",
    ]
    with pytest.raises(ValueError, match="Invalid IB release channel"):
        ci_module.docker_tags("preview", "10.45.1e")


def test_ci_download_and_fetch_errors_are_fatal() -> None:
    """Release automation should not continue after failed network operations."""
    content = CI_PATH.read_text()

    assert 'raise RuntimeError(f"Error fetching URL {url}: {exc}") from exc' in content
    assert (
        'raise RuntimeError(f"Error downloading file {url}: {exc}") from exc' in content
    )
    assert 'logger.info(f"Error fetching URL' not in content
    assert 'logger.info(f"Error downloading file' not in content


def test_ci_downloads_are_atomic_and_nonempty() -> None:
    """Release downloads should not reuse partial or empty cached assets."""
    content = CI_PATH.read_text()

    assert (
        "def download(url: str, save_path: Path, overwrite: bool = False) -> None:"
        in content
    )
    assert "not overwrite and not os.getenv" in content
    assert "save_path.parent.mkdir(parents=True, exist_ok=True)" in content
    assert 'require_download_file(save_path, "Existing download path")' in content
    assert 'require_download_file(temporary_path, "Temporary download path")' in content
    assert "save_path.stat().st_size > 0" in content
    assert "Existing download is empty" in content
    assert (
        'temporary_path = save_path.with_suffix(save_path.suffix + ".tmp")' in content
    )
    assert "urlretrieve(url, temporary_path)" in content
    assert 'raise RuntimeError("downloaded file is empty")' in content
    assert "temporary_path.replace(save_path)" in content
    assert "temporary_path.unlink()" in content


def test_ci_download_creates_parent_and_replaces_atomically(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Direct downloads should not require callers to create target directories."""
    ci_module = load_ci_module(monkeypatch)
    save_path = tmp_path / "nested" / "installer.sh"

    def fake_urlretrieve(url: str, filename: Path) -> None:
        assert url == "https://example.test/installer.sh"
        filename.write_text("installer")

    monkeypatch.setattr(ci_module, "urlretrieve", fake_urlretrieve)

    ci_module.download("https://example.test/installer.sh", save_path)

    assert save_path.read_text() == "installer"
    assert not save_path.with_suffix(".sh.tmp").exists()


def test_ci_download_rejects_directory_cache_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Corrupted cache directories should not be treated as valid downloads."""
    ci_module = load_ci_module(monkeypatch)
    save_path = tmp_path / "downloads" / "installer.sh"
    save_path.mkdir(parents=True)

    def fail_urlretrieve(url: str, filename: Path) -> None:
        raise AssertionError("directory cache path should fail before download")

    monkeypatch.setattr(ci_module, "urlretrieve", fail_urlretrieve)

    with pytest.raises(RuntimeError, match="Existing download path is not a file"):
        ci_module.download("https://example.test/installer.sh", save_path)


def test_ci_download_rejects_directory_targets_when_overwriting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Release downloads should fail before fetching when the target is a directory."""
    ci_module = load_ci_module(monkeypatch)
    save_path = tmp_path / "downloads" / "installer.sh"
    save_path.mkdir(parents=True)

    def fail_urlretrieve(url: str, filename: Path) -> None:
        raise AssertionError("directory target should fail before download")

    monkeypatch.setattr(ci_module, "urlretrieve", fail_urlretrieve)

    with pytest.raises(RuntimeError, match="Existing download path is not a file"):
        ci_module.download(
            "https://example.test/installer.sh", save_path, overwrite=True
        )


def test_ci_download_rejects_file_parent_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Download setup should fail clearly when the parent path is a file."""
    ci_module = load_ci_module(monkeypatch)
    parent_path = tmp_path / "downloads"
    parent_path.write_text("not a directory")
    save_path = parent_path / "installer.sh"

    def fail_urlretrieve(url: str, filename: Path) -> None:
        raise AssertionError("unexpected download")

    monkeypatch.setattr(ci_module, "urlretrieve", fail_urlretrieve)

    with pytest.raises(RuntimeError, match="Download parent path is not a directory"):
        ci_module.download("https://example.test/installer.sh", save_path)


def test_ci_download_rejects_directory_temp_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A stale temp directory should fail clearly instead of leaking an OSError."""
    ci_module = load_ci_module(monkeypatch)
    save_path = tmp_path / "downloads" / "installer.sh"
    temp_path = save_path.with_suffix(".sh.tmp")
    temp_path.mkdir(parents=True)

    def fail_urlretrieve(url: str, filename: Path) -> None:
        raise AssertionError("temp directory path should fail before download")

    monkeypatch.setattr(ci_module, "urlretrieve", fail_urlretrieve)

    with pytest.raises(RuntimeError, match="Temporary download path is not a file"):
        ci_module.download("https://example.test/installer.sh", save_path)


def test_ci_download_rejects_temp_directory_created_by_downloader(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Downloader-created temp directories should not mask cleanup errors."""
    ci_module = load_ci_module(monkeypatch)
    save_path = tmp_path / "downloads" / "installer.sh"

    def fake_urlretrieve(url: str, filename: Path) -> None:
        filename.mkdir()

    monkeypatch.setattr(ci_module, "urlretrieve", fake_urlretrieve)

    with pytest.raises(RuntimeError, match="Temporary download path is not a file"):
        ci_module.download("https://example.test/installer.sh", save_path)


def test_ci_download_release_file_creates_nested_download_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Release downloads should work when the configured cache path is nested."""
    ci_module = load_ci_module(monkeypatch)
    captured: dict[str, object] = {}

    class FakeIBRelease:
        build_version = "10.45.1e"
        download_url = (
            "https://download.example/ibgateway-stable-standalone-linux-x64.sh"
        )

    def fake_download(url: str, file: Path, overwrite: bool = False) -> None:
        captured["url"] = url
        captured["file"] = file
        captured["overwrite"] = overwrite
        file.write_text("installer")

    monkeypatch.setattr(ci_module, "downloads_dir", tmp_path / "cache" / "downloads")
    monkeypatch.setattr(ci_module, "download", fake_download)

    file_path = ci_module.download_release_file(FakeIBRelease())

    assert captured["url"] == FakeIBRelease.download_url
    assert file_path == (
        tmp_path
        / "cache"
        / "downloads"
        / "ibgateway-stable-10.45.1e-standalone-linux-x64.sh"
    )
    assert captured["file"] == file_path
    assert captured["overwrite"] is True
    assert file_path.read_text() == "installer"


def test_ci_download_release_file_rejects_unexpected_installer_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Release downloads should not silently publish unversioned installer names."""
    ci_module = load_ci_module(monkeypatch)
    monkeypatch.setattr(ci_module, "downloads_dir", tmp_path / "downloads")

    class FakeIBRelease:
        build_version = "10.45.1e"
        download_url = "https://download.example/ibgateway-stable-linux-x64.sh"

    def fail_download(url: str, file: Path, overwrite: bool = False) -> None:
        raise AssertionError("unexpected download")

    monkeypatch.setattr(ci_module, "download", fail_download)

    with pytest.raises(RuntimeError, match="expected '-standalone-' marker"):
        ci_module.download_release_file(FakeIBRelease())


def test_ci_download_release_file_rejects_file_downloads_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Release downloads should fail clearly when downloads_dir is a file."""
    ci_module = load_ci_module(monkeypatch)
    downloads_path = tmp_path / "downloads"
    downloads_path.write_text("not a directory")
    monkeypatch.setattr(ci_module, "downloads_dir", downloads_path)

    class FakeIBRelease:
        build_version = "10.45.1e"
        download_url = "https://download.example/tws-stable-standalone-linux-x64.sh"

    def fail_download(url: str, file: Path, overwrite: bool = False) -> None:
        raise AssertionError("unexpected download")

    monkeypatch.setattr(ci_module, "download", fail_download)

    with pytest.raises(RuntimeError, match="Downloads path is not a directory"):
        ci_module.download_release_file(FakeIBRelease())


def test_ci_download_release_file_refreshes_cached_assets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Release automation should not bless stale cached installers with new hashes."""
    ci_module = load_ci_module(monkeypatch)
    monkeypatch.setattr(ci_module, "downloads_dir", tmp_path)
    cached_file = tmp_path / "tws-latest-10.46.1-standalone-linux-x64.sh"
    cached_file.write_text("stale installer")

    class FakeIBRelease:
        build_version = "10.46.1"
        download_url = "https://download.example/tws-latest-standalone-linux-x64.sh"

    def fake_urlretrieve(url: str, filename: Path) -> None:
        assert url == FakeIBRelease.download_url
        filename.write_text("fresh installer")

    monkeypatch.setattr(ci_module, "urlretrieve", fake_urlretrieve)

    file_path = ci_module.download_release_file(FakeIBRelease())

    assert file_path == cached_file
    assert file_path.read_text() == "fresh installer"


def test_ci_download_rejects_empty_files_and_removes_temp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Empty direct downloads should not leave a cacheable artifact behind."""
    ci_module = load_ci_module(monkeypatch)
    save_path = tmp_path / "downloads" / "empty.sh"

    def fake_urlretrieve(url: str, filename: Path) -> None:
        filename.write_text("")

    monkeypatch.setattr(ci_module, "urlretrieve", fake_urlretrieve)

    with pytest.raises(RuntimeError, match="downloaded file is empty"):
        ci_module.download("https://example.test/empty.sh", save_path)

    assert not save_path.exists()
    assert not save_path.with_suffix(".sh.tmp").exists()


def test_ci_sha256_assets_are_line_oriented() -> None:
    """Generated sha256 sidecars should be valid line-oriented checksum files."""
    content = CI_PATH.read_text()

    assert "def write_sha256_file(file: Path) -> Path:" in content
    assert "def release_asset_names(gh_release: Any) -> set[str]:" in content
    assert "def upload_release_asset(" in content
    assert "existing_asset_names: set[str] | None = None" in content
    assert "hash_file = write_sha256_file(file)" in content
    assert (
        'f"{hashlib.sha256(file.read_bytes()).hexdigest()} {file.name}\\n"' in content
    )


def test_ci_write_sha256_file_creates_sidecar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Checksum sidecar generation should be deterministic and line-oriented."""
    ci_module = load_ci_module(monkeypatch)
    asset_path = tmp_path / "ibgateway-stable-10.45.1e-standalone-linux-x64.sh"
    asset_path.write_text("installer")

    hash_path = ci_module.write_sha256_file(asset_path)

    assert hash_path == asset_path.with_suffix(".sh.sha256")
    assert (
        hash_path.read_text()
        == "9c0d294c05fc1d88d698034609bb81c0c69196327594e4c69d2915c80fd9850c "
        "ibgateway-stable-10.45.1e-standalone-linux-x64.sh\n"
    )


def test_ci_write_sha256_file_rejects_directory_asset_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Checksum generation should fail clearly when the asset path is a directory."""
    ci_module = load_ci_module(monkeypatch)
    asset_path = tmp_path / "ibgateway-stable-10.45.1e-standalone-linux-x64.sh"
    asset_path.mkdir()

    with pytest.raises(RuntimeError, match="Release asset path is not a file"):
        ci_module.write_sha256_file(asset_path)

    assert not asset_path.with_suffix(".sh.sha256").exists()


def test_ci_write_sha256_file_rejects_directory_sidecar_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Checksum generation should not write through a stale sidecar directory."""
    ci_module = load_ci_module(monkeypatch)
    asset_path = tmp_path / "tws-stable-10.45.1e-standalone-linux-x64.sh"
    asset_path.write_text("installer")
    sidecar_path = asset_path.with_suffix(".sh.sha256")
    sidecar_path.mkdir()

    with pytest.raises(RuntimeError, match="Checksum sidecar path is not a file"):
        ci_module.write_sha256_file(asset_path)


def test_ci_parse_sha256_sidecar_rejects_malformed_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Remote checksum sidecars should be line-oriented and filename-scoped."""
    ci_module = load_ci_module(monkeypatch)

    digest = "a" * 64

    assert ci_module.parse_sha256_sidecar(
        f"{digest} *ibgateway-stable-10.45.1e-standalone-linux-x64.sh\n",
        "test-url",
    ) == (digest, "ibgateway-stable-10.45.1e-standalone-linux-x64.sh")
    assert ci_module.parse_sha256_sidecar(
        f"{digest}\ttws-stable-10.45.1e-standalone-linux-x64.sh\n",
        "test-url",
    ) == (digest, "tws-stable-10.45.1e-standalone-linux-x64.sh")
    with pytest.raises(RuntimeError, match="expected one line"):
        ci_module.parse_sha256_sidecar(
            f"{digest} file.sh\n{digest} other.sh\n", "test-url"
        )
    with pytest.raises(RuntimeError, match="malformed checksum"):
        ci_module.parse_sha256_sidecar("not-a-digest file.sh\n", "test-url")
    with pytest.raises(RuntimeError, match="Invalid sha256 sidecar"):
        ci_module.parse_sha256_sidecar(f"{digest} nested/file.sh\n", "test-url")
    with pytest.raises(RuntimeError, match="Invalid sha256 sidecar"):
        ci_module.parse_sha256_sidecar(f"{digest} nested\\file.sh\n", "test-url")


def test_ci_upload_release_asset_uploads_asset_and_checksum(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Release asset uploads should include the installer and checksum sidecar."""
    ci_module = load_ci_module(monkeypatch)
    asset_path = tmp_path / "tws-stable-10.45.1e-standalone-linux-x64.sh"
    asset_path.write_text("installer")
    uploads: list[tuple[str, str, str]] = []

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name
            self.browser_download_url = f"https://example.test/{name}"

    class FakeRelease:
        def get_assets(self) -> list[FakeAsset]:
            return []

        def upload_asset(self, path: str, label: str, name: str) -> None:
            uploads.append((path, label, name))

    ci_module.upload_release_asset(FakeRelease(), asset_path)

    checksum_path = asset_path.with_suffix(".sh.sha256")
    assert uploads == [
        (str(asset_path), asset_path.name, asset_path.name),
        (str(checksum_path), checksum_path.name, checksum_path.name),
    ]
    assert checksum_path.exists()


def test_ci_upload_release_asset_repairs_missing_checksum_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Incomplete releases should upload sidecars without duplicating installers."""
    ci_module = load_ci_module(monkeypatch)
    asset_path = tmp_path / "ibgateway-stable-10.45.1e-standalone-linux-x64.sh"
    asset_path.write_text("installer")
    checksum_path = asset_path.with_suffix(".sh.sha256")
    uploads: list[tuple[str, str, str]] = []

    class FakeRelease:
        def upload_asset(self, path: str, label: str, name: str) -> None:
            uploads.append((path, label, name))

    ci_module.upload_release_asset(
        FakeRelease(),
        asset_path,
        existing_asset_names={asset_path.name},
    )

    assert uploads == [(str(checksum_path), checksum_path.name, checksum_path.name)]
    assert checksum_path.exists()


def test_ci_upload_release_asset_updates_shared_existing_asset_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Repeated uploads with a shared asset set should not duplicate assets."""
    ci_module = load_ci_module(monkeypatch)
    asset_path = tmp_path / "tws-stable-10.45.1e-standalone-linux-x64.sh"
    asset_path.write_text("installer")
    checksum_path = asset_path.with_suffix(".sh.sha256")
    existing_asset_names: set[str] = set()
    uploads: list[str] = []

    class FakeRelease:
        def upload_asset(self, path: str, label: str, name: str) -> None:
            uploads.append(name)
            assert Path(path).name == name
            assert label == name

    ci_module.upload_release_asset(
        FakeRelease(), asset_path, existing_asset_names=existing_asset_names
    )
    ci_module.upload_release_asset(
        FakeRelease(), asset_path, existing_asset_names=existing_asset_names
    )

    assert uploads == [asset_path.name, checksum_path.name]
    assert existing_asset_names == {asset_path.name, checksum_path.name}


def test_ci_invalid_checksum_assets_include_orphaned_sidecars(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repair should replace sidecars that exist before their installer asset."""
    ci_module = load_ci_module(monkeypatch)
    release = ci_module.GitHubRelease(release="stable", build_version="10.45.1e")

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name
            self.browser_download_url = f"https://example.test/{name}"

    class FakeRelease:
        def get_assets(self) -> list[FakeAsset]:
            return [
                FakeAsset("ibgateway-stable-10.45.1e-standalone-linux-x64.sh.sha256")
            ]

    monkeypatch.setattr(ci_module, "fetch", fake_release_asset_fetch)

    assert ci_module.invalid_release_checksum_asset_names(FakeRelease(), release) == {
        "ibgateway-stable-10.45.1e-standalone-linux-x64.sh.sha256"
    }


def test_ci_release_repair_replaces_installers_with_missing_checksum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Repair should not upload a fresh checksum for an unchecked remote installer."""
    ci_module = load_ci_module(monkeypatch)
    release = ci_module.GitHubRelease(release="stable", build_version="10.45.1e")

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name
            self.browser_download_url = f"https://example.test/{name}"

    class FakeRelease:
        def get_assets(self) -> list[FakeAsset]:
            return [
                FakeAsset("ibgateway-stable-10.45.1e-standalone-linux-x64.sh"),
            ]

    monkeypatch.setattr(ci_module, "fetch", fake_release_asset_fetch)

    assert ci_module.release_asset_names_to_replace(FakeRelease(), release) == {
        "ibgateway-stable-10.45.1e-standalone-linux-x64.sh"
    }


def test_ci_delete_release_assets_ignores_already_absent_assets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Release repair should tolerate assets removed between listing and deletion."""
    ci_module = load_ci_module(monkeypatch)
    deleted_assets: list[str] = []

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name

        def delete_asset(self) -> bool:
            deleted_assets.append(self.name)
            return True

    class FakeRelease:
        def get_assets(self) -> list[FakeAsset]:
            return [FakeAsset("present.sh")]

    ci_module.delete_release_assets(FakeRelease(), {"missing.sh", "present.sh"})

    assert deleted_assets == ["present.sh"]


def test_ci_create_github_releases_repairs_existing_incomplete_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Published release repair should reuse the tag and dispatch image builds."""
    ci_module = load_ci_module(monkeypatch)
    dispatched_tags: list[str] = []
    deleted_assets: list[str] = []

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name

    class FakeGitHubRelease:
        def __init__(self, tag_name: str, asset_names: set[str]) -> None:
            self.tag_name = tag_name
            self.asset_names = asset_names
            self.draft = False
            self.uploads: list[str] = []

        def get_assets(self) -> list[FakeAsset]:
            return [FakeAsset(name) for name in self.asset_names]

        def upload_asset(self, path: str, label: str, name: str) -> None:
            self.uploads.append(name)
            self.asset_names.add(name)
            assert Path(path).name == name
            assert label == name

        def update_release(
            self, name: str, message: str, draft: bool
        ) -> "FakeGitHubRelease":
            raise AssertionError(
                "published incomplete release should not be republished"
            )

    existing_release = FakeGitHubRelease(
        "stable-10.45.1e",
        {
            "ibgateway-stable-10.45.1e-standalone-linux-x64.sh",
            "ibgateway-stable-10.45.1e-standalone-linux-x64.sh.sha256",
        },
    )

    class FakeRepo:
        def get_releases(self) -> list[FakeGitHubRelease]:
            return [existing_release]

        def create_git_release(
            self, tag: str, name: str, message: str, draft: bool
        ) -> FakeGitHubRelease:
            raise AssertionError(f"unexpected release creation for {tag}")

    class FakeIBRelease:
        def __init__(self, release: str, program: str) -> None:
            self.release = release
            self.program = program
            self.build_version = "10.46.1" if release == "latest" else "10.45.1e"
            self.description = f"{program} {release} {self.build_version}"

    def fake_download_release_file(ib_release: FakeIBRelease) -> Path:
        file_path = (
            tmp_path
            / f"{ib_release.program}-{ib_release.release}-{ib_release.build_version}"
            "-standalone-linux-x64.sh"
        )
        file_path.write_text(ib_release.description)
        return file_path

    monkeypatch.setattr(ci_module, "get_gh_repo", lambda: FakeRepo())
    monkeypatch.setattr(
        ci_module,
        "find_latest_github_releases",
        lambda: [ci_module.GitHubRelease(release="latest", build_version="10.46.1")],
    )
    monkeypatch.setattr(ci_module, "IBRelease", FakeIBRelease)
    monkeypatch.setattr(ci_module, "download_release_file", fake_download_release_file)
    monkeypatch.setattr(
        ci_module,
        "invalid_release_checksum_asset_names",
        lambda gh_release, release: {
            "ibgateway-stable-10.45.1e-standalone-linux-x64.sh.sha256"
        },
    )

    monkeypatch.setattr(
        ci_module,
        "delete_release_assets",
        lambda gh_release, asset_names: deleted_assets.extend(sorted(asset_names)),
    )
    monkeypatch.setattr(
        ci_module,
        "dispatch_build_workflows",
        lambda gh_repo, tag: dispatched_tags.append(tag),
    )

    created_releases = ci_module.create_github_releases()

    assert [
        (release.program, release.release, release.build_version)
        for release in created_releases
    ] == [
        ("ibgateway", "stable", "10.45.1e"),
        ("tws", "stable", "10.45.1e"),
    ]
    assert sorted(existing_release.uploads) == [
        "ibgateway-stable-10.45.1e-standalone-linux-x64.sh",
        "ibgateway-stable-10.45.1e-standalone-linux-x64.sh.sha256",
        "tws-stable-10.45.1e-standalone-linux-x64.sh",
        "tws-stable-10.45.1e-standalone-linux-x64.sh.sha256",
    ]
    assert deleted_assets == [
        "ibgateway-stable-10.45.1e-standalone-linux-x64.sh",
        "ibgateway-stable-10.45.1e-standalone-linux-x64.sh.sha256",
    ]
    assert dispatched_tags == ["stable-10.45.1e"]


def test_ci_create_github_releases_publishes_after_asset_upload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """New GitHub releases should stay draft until all installer assets are present."""
    ci_module = load_ci_module(monkeypatch)
    events: list[str] = []

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name

    class FakeGitHubRelease:
        def __init__(self, tag_name: str) -> None:
            self.tag_name = tag_name
            self.draft = True
            self.asset_names: set[str] = set()

        def get_assets(self) -> list[FakeAsset]:
            return [FakeAsset(name) for name in self.asset_names]

        def upload_asset(self, path: str, label: str, name: str) -> None:
            events.append(f"upload:{name}")
            self.asset_names.add(name)
            assert Path(path).name == name
            assert label == name

        def update_release(
            self, name: str, message: str, draft: bool
        ) -> "FakeGitHubRelease":
            expected_asset_names = ci_module.expected_release_asset_names(
                ci_module.GitHubRelease(release="latest", build_version="10.46.1")
            )
            assert name == "latest-10.46.1"
            assert "ibgateway latest 10.46.1" in message
            assert "tws latest 10.46.1" in message
            assert draft is False
            assert self.asset_names == expected_asset_names
            events.append("publish:latest-10.46.1")
            self.draft = False
            return self

    created_gh_releases: list[FakeGitHubRelease] = []

    class FakeRepo:
        def get_releases(self) -> list[FakeGitHubRelease]:
            return []

        def create_git_release(
            self, tag: str, name: str, message: str, draft: bool
        ) -> FakeGitHubRelease:
            assert tag == "latest-10.46.1"
            assert name == tag
            assert "ibgateway latest 10.46.1" in message
            assert draft is True
            gh_release = FakeGitHubRelease(tag)
            created_gh_releases.append(gh_release)
            events.append(f"create-draft:{tag}")
            return gh_release

    class FakeIBRelease:
        def __init__(self, release: str, program: str) -> None:
            self.release = release
            self.program = program
            self.build_version = "10.46.1" if release == "latest" else "10.45.1e"
            self.description = f"{program} {release} {self.build_version}"

    def fake_download_release_file(ib_release: FakeIBRelease) -> Path:
        file_path = (
            tmp_path
            / f"{ib_release.program}-{ib_release.release}-{ib_release.build_version}"
            "-standalone-linux-x64.sh"
        )
        file_path.write_text(ib_release.description)
        return file_path

    monkeypatch.setattr(ci_module, "get_gh_repo", lambda: FakeRepo())
    monkeypatch.setattr(
        ci_module,
        "find_latest_github_releases",
        lambda: [ci_module.GitHubRelease(release="stable", build_version="10.45.1e")],
    )
    monkeypatch.setattr(ci_module, "IBRelease", FakeIBRelease)
    monkeypatch.setattr(ci_module, "download_release_file", fake_download_release_file)
    monkeypatch.setattr(ci_module, "fetch", fake_release_asset_fetch)

    created_releases = ci_module.create_github_releases()

    assert [
        (release.program, release.release, release.build_version)
        for release in created_releases
    ] == [
        ("ibgateway", "latest", "10.46.1"),
        ("tws", "latest", "10.46.1"),
    ]
    assert len(created_gh_releases) == 1
    assert created_gh_releases[0].draft is False
    assert events[0] == "create-draft:latest-10.46.1"
    assert events[-1] == "publish:latest-10.46.1"


def test_ci_create_github_releases_publishes_existing_complete_draft(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A complete draft from a failed prior run should be published on retry."""
    ci_module = load_ci_module(monkeypatch)
    latest_release = ci_module.GitHubRelease(release="latest", build_version="10.46.1")

    class FakeAsset:
        def __init__(self, name: str) -> None:
            self.name = name
            self.browser_download_url = f"https://example.test/{name}"

    class FakeGitHubRelease:
        def __init__(self) -> None:
            self.tag_name = "latest-10.46.1"
            self.draft = True
            self.asset_names = ci_module.expected_release_asset_names(latest_release)
            self.uploads: list[str] = []
            self.published = False

        def get_assets(self) -> list[FakeAsset]:
            return [FakeAsset(name) for name in self.asset_names]

        def upload_asset(self, path: str, label: str, name: str) -> None:
            self.uploads.append(name)

        def update_release(
            self, name: str, message: str, draft: bool
        ) -> "FakeGitHubRelease":
            assert name == self.tag_name
            assert "ibgateway latest 10.46.1" in message
            assert "tws latest 10.46.1" in message
            assert draft is False
            self.draft = False
            self.published = True
            return self

    draft_release = FakeGitHubRelease()

    class FakeRepo:
        def get_releases(self) -> list[FakeGitHubRelease]:
            return [draft_release]

        def create_git_release(
            self, tag: str, name: str, message: str, draft: bool
        ) -> FakeGitHubRelease:
            raise AssertionError(f"unexpected release creation for {tag}")

    class FakeIBRelease:
        def __init__(self, release: str, program: str) -> None:
            self.release = release
            self.program = program
            self.build_version = "10.46.1" if release == "latest" else "10.45.1e"
            self.description = f"{program} {release} {self.build_version}"

    def fake_download_release_file(ib_release: FakeIBRelease) -> Path:
        file_path = (
            tmp_path
            / f"{ib_release.program}-{ib_release.release}-{ib_release.build_version}"
            "-standalone-linux-x64.sh"
        )
        file_path.write_text(ib_release.description)
        return file_path

    monkeypatch.setattr(ci_module, "get_gh_repo", lambda: FakeRepo())
    monkeypatch.setattr(
        ci_module,
        "find_latest_github_releases",
        lambda: [ci_module.GitHubRelease(release="stable", build_version="10.45.1e")],
    )
    monkeypatch.setattr(ci_module, "IBRelease", FakeIBRelease)
    monkeypatch.setattr(ci_module, "download_release_file", fake_download_release_file)
    monkeypatch.setattr(ci_module, "fetch", fake_release_asset_fetch)

    created_releases = ci_module.create_github_releases()

    assert [
        (release.program, release.release, release.build_version)
        for release in created_releases
    ] == [
        ("ibgateway", "latest", "10.46.1"),
        ("tws", "latest", "10.46.1"),
    ]
    assert draft_release.uploads == []
    assert draft_release.published is True


def test_ci_dispatch_build_workflows_raises_when_dispatch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow dispatch failures should fail the release repair run."""
    ci_module = load_ci_module(monkeypatch)

    class FakeWorkflow:
        def create_dispatch(self, ref: str, inputs: dict[str, str]) -> bool:
            assert ref == "main"
            assert inputs == {"tag_name": "stable-10.45.1e"}
            return False

    class FakeRepo:
        def get_workflow(self, workflow_name: str) -> FakeWorkflow:
            assert workflow_name == "build_gateway.yml"
            return FakeWorkflow()

    with pytest.raises(RuntimeError, match="Could not dispatch build_gateway.yml"):
        ci_module.dispatch_build_workflows(FakeRepo(), "stable-10.45.1e")


def test_ci_dispatch_build_workflows_runs_both_product_builds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Published release repair should trigger both product image workflows."""
    ci_module = load_ci_module(monkeypatch)
    workflow_dispatches: list[tuple[str, str, dict[str, str]]] = []

    class FakeWorkflow:
        def __init__(self, workflow_name: str) -> None:
            self.workflow_name = workflow_name

        def create_dispatch(self, ref: str, inputs: dict[str, str]) -> bool:
            workflow_dispatches.append((self.workflow_name, ref, inputs))
            return True

    class FakeRepo:
        def get_workflow(self, workflow_name: str) -> FakeWorkflow:
            return FakeWorkflow(workflow_name)

    ci_module.dispatch_build_workflows(FakeRepo(), "stable-10.45.1e")

    assert workflow_dispatches == [
        ("build_gateway.yml", "main", {"tag_name": "stable-10.45.1e"}),
        ("build_tws.yml", "main", {"tag_name": "stable-10.45.1e"}),
    ]


def test_ci_docker_build_failures_are_fatal() -> None:
    """CI image builds should fail when docker buildx returns a non-zero status."""
    content = CI_PATH.read_text()

    assert "if res.returncode != 0:" in content
    assert (
        'raise RuntimeError(f"Docker image build failed with exit code {res.returncode}")'
        in content
    )
    assert "check=False" in content
    assert "cmd.split()" not in content


def test_ci_consumes_parallel_worker_results() -> None:
    """Parallel release automation should propagate worker exceptions."""
    content = CI_PATH.read_text()

    assert "list(executor.map(upload, files))" in content
    assert "partial(\n                upload_release_asset," in content
    assert "dispatch_build_workflows(gh_repo, tag)" in content
    assert "list(executor.map(build_image, params))" in content
    assert "\n            executor.map(lambda file:" not in content
    assert "\n            executor.map(build_image, params)\n" not in content


def test_ci_build_images_expands_shared_releases_to_both_products(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shared GitHub release tags should build both Gateway and TWS images."""
    ci_module = load_ci_module(monkeypatch)
    built_params: list[tuple[str, str, str]] = []

    def fake_build_image(params: tuple[str, str, str]) -> None:
        built_params.append(params)

    monkeypatch.setattr(ci_module, "build_image", fake_build_image)

    ci_module.build_images(
        [ci_module.GitHubRelease(release="stable", build_version="10.45.1e")]
    )

    assert built_params == [
        ("ibgateway", "stable", "10.45.1e"),
        ("tws", "stable", "10.45.1e"),
    ]


def test_ci_build_images_parallel_consumes_worker_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parallel image builds should surface exceptions from build workers."""
    ci_module = load_ci_module(monkeypatch)

    def fake_build_image(params: tuple[str, str, str]) -> None:
        raise RuntimeError(f"boom: {params[0]}")

    monkeypatch.setattr(ci_module, "build_image", fake_build_image)

    with pytest.raises(RuntimeError, match="boom: ibgateway"):
        ci_module.build_images(
            [ci_module.GitHubRelease(release="stable", build_version="10.45.1e")],
            parallel=True,
        )


def test_release_workflow_uses_only_release_check_requirements() -> None:
    """Daily release checks should not require unused DockerHub secrets."""
    content = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text()

    assert 'python-version: "3.12"' in content
    assert 'python-version: "3.11"' not in content
    assert "pip install pygithub\n" in content
    assert "pip install pygithub docker jinja2" not in content
    assert "GITHUB_TOKEN: ${{ secrets.GH_PAT }}" in content
    assert "DOCKERHUB_USERNAME" not in content
    assert "DOCKERHUB_TOKEN" not in content


def test_build_context_ignores_generated_python_artifacts() -> None:
    """The build context should not include local Python cache artifacts."""
    ignored_patterns = set(BUILD_DOCKERIGNORE_PATH.read_text().splitlines())

    assert "__pycache__/" in ignored_patterns
    assert "*.py[cod]" in ignored_patterns
    assert ".pytest_cache/" in ignored_patterns


def test_compose_passes_documented_env_to_runtime_services() -> None:
    """Documented .env settings should reach containers without requiring env_file."""
    content = DOCKER_COMPOSE_PATH.read_text()

    assert "env_file:" not in content
    for env_name in [
        "ACCEPT_NON_BROKERAGE_WARNING",
        "READ_ONLY_API",
        "TIME_ZONE",
        "TWOFA_TIMEOUT_ACTION",
        "AUTO_RESTART_TIME",
        "AUTO_LOGOFF_TIME",
        "COLD_RESTART_TIME",
        "BYPASS_WARNING",
        "SAVE_TWS_SETTINGS",
        "RELOGIN_AFTER_TWOFA_TIMEOUT",
        "TWOFA_EXIT_INTERVAL",
        "JAVA_HEAP_SIZE",
        "CUSTOM_JVM_OPTS",
    ]:
        assert content.count(f"{env_name}: ${{{env_name}") == 2


def test_compose_timezone_default_matches_image_default() -> None:
    """Compose should not silently change the image timezone default."""
    compose_content = DOCKER_COMPOSE_PATH.read_text()
    env_example_content = (REPO_ROOT / ".env.example").read_text()

    assert compose_content.count("TIME_ZONE: ${TIME_ZONE:-UTC}") == 2
    assert "TIME_ZONE=UTC" in env_example_content


def test_compose_requires_credentials_before_startup() -> None:
    """Compose should fail fast when required IB credentials are missing."""
    content = DOCKER_COMPOSE_PATH.read_text()

    assert content.count("IB_USER: ${IB_USER:?IB_USER is required}") == 2
    assert content.count("IB_PASSWORD: ${IB_PASSWORD:?IB_PASSWORD is required}") == 2


def test_env_example_does_not_bypass_required_credentials() -> None:
    """The example env file should still trigger compose's required credential checks."""
    env_example = ENV_EXAMPLE_PATH.read_text().splitlines()

    assert "IB_USER=" in env_example
    assert "IB_PASSWORD=" in env_example
    assert "IB_USER=your_ib_username" not in env_example
    assert "IB_PASSWORD=your_ib_password" not in env_example


def test_compose_uses_distinct_vnc_ports_for_host_network_services() -> None:
    """Enabling VNC on both compose services should not collide on host networking."""
    content = DOCKER_COMPOSE_PATH.read_text()

    assert "VNC_PORT: ${VNC_PORT:-5900}" in content
    assert "VNC_PORT: ${TWS_VNC_PORT:-5901}" in content


def test_readme_gateway_access_ports_match_trading_modes() -> None:
    """README should not point paper users at the live Gateway API port."""
    content = README_PATH.read_text()

    assert "`localhost:4002` for paper trading" in content
    assert "`localhost:4001` for live trading" in content
    assert "`localhost:4001` (paper:" not in content
