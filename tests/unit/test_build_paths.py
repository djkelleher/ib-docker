import importlib.util
import os
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INIT_SETTINGS_PATH = REPO_ROOT / "build" / "programs" / "init_container_settings.py"
IB_UTILS_PATH = REPO_ROOT / "build" / "programs" / "ib_utils.sh"
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
    (release_dir / "jars").mkdir(parents=True)

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
    (release_dir / "jars").mkdir(parents=True)

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


def test_supervisor_config_uses_supported_startup_coordination() -> None:
    """Supervisor config should avoid unsupported dependency keys."""
    content = SUPERVISORD_CONF_PATH.read_text()

    assert "depends_on" not in content
    assert "[program:settings]" not in content
    assert "[unix_http_server]" in content
    assert "serverurl=unix:///tmp/supervisor.sock" in content
