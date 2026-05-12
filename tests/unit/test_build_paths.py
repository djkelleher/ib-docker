import ast
import importlib.util
import os
import subprocess
import sys
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


@pytest.fixture(name="init_settings")
def fixture_init_settings() -> ModuleType:
    """Return the init_container_settings module."""
    return load_init_settings()


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


def test_entrypoint_uses_display_specific_x_cleanup() -> None:
    """Entrypoint cleanup should match the normalized display path handling."""
    content = ENTRYPOINT_PATH.read_text()

    assert 'display_no="$(x_display_number "$DISPLAY")"' in content
    assert 'xvfb_pattern="$(x_display_process_pattern Xvfb "$DISPLAY")"' in content
    assert 'x11vnc_pattern="$(x_display_process_pattern x11vnc "$DISPLAY")"' in content
    assert "rm -rf /tmp/.X*-lock" not in content
    assert "rm -rf /tmp/.X11-unix/*" not in content
    assert 'rm -f "/tmp/.X${display_no}-lock"' in content
    assert 'rm -f "/tmp/.X11-unix/X${display_no}"' in content


def test_xvfb_cleanup_is_display_specific() -> None:
    """Xvfb startup should not kill unrelated Xvfb processes on other displays."""
    content = START_XVFB_PATH.read_text()

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


def test_vnc_startup_requires_home_before_xauth_setup() -> None:
    """VNC startup should validate HOME before using it for X authority files."""
    content = START_VNC_PATH.read_text()

    validation = content.index("ensure_absolute_path HOME")
    xauth = content.index('export XAUTHORITY="$HOME/.Xauthority"')

    assert validation < xauth


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


def test_ibc_startup_requires_absolute_runtime_paths() -> None:
    """IBC startup should validate paths before passing them to IBC."""
    content = START_IBC_PATH.read_text()

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


def test_vmoptions_paths_rejects_unsupported_program(
    init_settings: ModuleType, tmp_path: Path
) -> None:
    """Python vmoptions generation should fail before writing unknown product files."""
    with pytest.raises(ValueError, match="Unsupported PROGRAM"):
        init_settings.vmoptions_paths("desktop", tmp_path)


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
    default_ibc_dir.mkdir(parents=True)
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
    assert "'^[0-9]+[.][0-9]+[.][0-9]+[a-z]?$'" in content
    assert "IBC_VERSION must not be empty" in content
    assert "IBC_VERSION must look like 3.23.0" in content
    assert "'^[0-9]+[.][0-9]+[.][0-9]+$'" in content


def test_dockerfile_verifies_ibc_start_script_during_build() -> None:
    """Builds should fail if the IBC archive does not contain the runtime entrypoint."""
    content = DOCKERFILE_PATH.read_text()

    assert 'find "$IBC_PATH" -type f -name "*.sh" -exec chmod u+x {} +' in content
    assert 'test -x "$IBC_PATH/scripts/ibcstart.sh"' in content
    assert (
        "chmod -R u+x ${IBC_PATH}/*.sh ${IBC_PATH}/scripts/*.sh || true" not in content
    )


def test_release_workflows_validate_tag_format_before_build_args() -> None:
    """Release workflows should reject malformed tags before passing build args."""
    for workflow_path in [GATEWAY_WORKFLOW_PATH, TWS_WORKFLOW_PATH]:
        content = workflow_path.read_text()
        validation = content.index("Release tag must look like")
        release_type = content.index('release_type="${release_name%%-*}"')
        docker_build = content.index("docker/build-push-action")

        assert validation < release_type < docker_build
        assert "^(stable|latest|beta)-[0-9]+[.][0-9]+[.][0-9]+[a-z]?$" in content


def test_release_workflows_require_major_minor_tag() -> None:
    """Release workflows should not push an empty major/minor Docker tag."""
    for workflow_path in [GATEWAY_WORKFLOW_PATH, TWS_WORKFLOW_PATH]:
        content = workflow_path.read_text()
        extraction = content.index("major_minor_version=$(echo")
        validation = content.index("Could not extract major/minor version")
        output = content.index("major_minor_version=$major_minor_version")

        assert extraction < validation < output
        assert 'if [ -z "$major_minor_version" ]; then' in content


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


def test_ci_validates_upstream_build_versions_before_release_tags() -> None:
    """Release creation should reject unexpected upstream buildVersion strings."""
    content = CI_PATH.read_text()

    assert "def parse_build_version(version: str, source: str) -> str:" in content
    assert "if not BUILD_VERSION_RE.match(version):" in content
    assert "Invalid IB build version from {source}: {version}" in content
    assert "return parse_build_version(" in content
    assert 'self.release_meta["buildVersion"].strip()' in content


def test_ci_release_discovery_skips_unsupported_tags() -> None:
    """Daily release discovery should tolerate old or unrelated GitHub release tags."""
    content = CI_PATH.read_text()

    assert "release = parse_release_tag(gh_release.tag_name)" in content
    assert "Skipping release with unsupported tag: %s" in content
    assert "gh_release.tag_name" in content
    assert "continue" in content


def test_ci_scheduled_release_discovery_ignores_beta_tags() -> None:
    """Daily release checks should still discover latest and stable when beta exists."""
    content = CI_PATH.read_text()

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
    assert 'f"{dockerhub_username}/"' in content
    assert '"ibgateway": "ib-gateway"' in content
    assert '"tws": "ib-tws"' in content


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

    assert "save_path.stat().st_size > 0" in content
    assert "Existing download is empty" in content
    assert (
        'temporary_path = save_path.with_suffix(save_path.suffix + ".tmp")' in content
    )
    assert "urlretrieve(url, temporary_path)" in content
    assert 'raise RuntimeError("downloaded file is empty")' in content
    assert "temporary_path.replace(save_path)" in content
    assert "temporary_path.unlink()" in content


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

    assert "list(executor.map(upload_release_file, files))" in content
    assert "list(executor.map(build_image, params))" in content
    assert "\n            executor.map(upload_release_file, files)\n" not in content
    assert "\n            executor.map(build_image, params)\n" not in content


def test_release_workflow_uses_only_release_check_requirements() -> None:
    """Daily release checks should not require unused DockerHub secrets."""
    content = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text()

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
