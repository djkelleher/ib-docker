import importlib.util
import os
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INIT_SETTINGS_PATH = REPO_ROOT / "build" / "programs" / "init_container_settings.py"
IB_UTILS_PATH = REPO_ROOT / "build" / "programs" / "ib_utils.sh"
ENTRYPOINT_PATH = REPO_ROOT / "build" / "programs" / "entrypoint.sh"
START_VNC_PATH = REPO_ROOT / "build" / "programs" / "start_vnc.sh"
START_XVFB_PATH = REPO_ROOT / "build" / "programs" / "start_xvfb.sh"
DOCKERFILE_PATH = REPO_ROOT / "build" / "Dockerfile"
BUILD_DOCKERIGNORE_PATH = REPO_ROOT / "build" / ".dockerignore"
VMOPTIONS_TEMPLATE_PATH = REPO_ROOT / "build" / "config" / "vmoptions.j2"
SUPERVISORD_CONF_PATH = REPO_ROOT / "build" / "config" / "supervisord.conf"


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


def test_vnc_password_is_not_passed_on_process_command_line() -> None:
    """VNC password should not remain in x11vnc argv or inherited env."""
    content = START_VNC_PATH.read_text()

    assert '-passwd "$VNC_PWD"' not in content
    assert '-passwdfile "$vnc_password_file"' in content
    assert 'chmod 600 "$vnc_password_file"' in content
    assert "unset VNC_PWD" in content


def test_gateway_vmoptions_updates_primary_and_compatibility_files(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gateway runtime initialization should not leave stale tws.vmoptions behind."""
    home = tmp_path / "home" / "ibuser"
    release_dir = tmp_path / "opt" / "ibgateway" / "stable"
    home.mkdir(parents=True)
    release_dir.mkdir(parents=True)
    (release_dir / "ibgateway.vmoptions").write_text("-Xmx256m\n")
    (release_dir / "tws.vmoptions").write_text("-Xmx256m\n")
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


def test_tws_vmoptions_updates_tws_file_only(
    init_settings: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TWS runtime initialization should write the TWS vmoptions file."""
    home = tmp_path / "home" / "ibuser"
    release_dir = tmp_path / "opt" / "tws" / "stable"
    home.mkdir(parents=True)
    release_dir.mkdir(parents=True)
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
    release_dir.mkdir(parents=True)

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
    release_dir.mkdir(parents=True)

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


def test_dockerfile_validates_build_args_before_downloads() -> None:
    """Builds should reject invalid products/releases before installer downloads."""
    content = DOCKERFILE_PATH.read_text()
    first_validation = content.index("Unsupported PROGRAM")
    first_download = content.index("wget -q -O /ib.sh")

    assert first_validation < first_download
    assert "Unsupported RELEASE" in content
    assert "Versioned release artifacts are only available for ARCH=x64" in content


def test_build_context_ignores_generated_python_artifacts() -> None:
    """The build context should not include local Python cache artifacts."""
    ignored_patterns = set(BUILD_DOCKERIGNORE_PATH.read_text().splitlines())

    assert "__pycache__/" in ignored_patterns
    assert "*.py[cod]" in ignored_patterns
    assert ".pytest_cache/" in ignored_patterns
