#!/usr/bin/env python3

import os
import re
import shlex
import sys
from pathlib import Path

VARS_REG = re.compile(r"\$\{([a-zA-Z_][\w]*)(?::-(.*?))?\}")
IBC_VERSION_REG = re.compile(r"^[0-9]+[.][0-9]+[.][0-9]+$")
CUSTOM_OPTS_BLOCK = """{% if custom_opts %}
# Custom options
{% for opt in custom_opts %}
{{ opt }}
{% endfor %}
{% endif %}"""
MIN_AUTO_HEAP_MB = 256


def require_env(name: str) -> str:
    """Return a required environment value or fail with a clear message."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def require_absolute_path(path: Path, label: str) -> None:
    """Fail with a clear message when a required runtime path is relative."""
    if not path.is_absolute():
        raise RuntimeError(f"{label} must be an absolute path: {path}")


def validate_env_choice(
    name: str, allowed_values: tuple[str, ...], default: str
) -> str:
    """Return a supported runtime choice, applying the same default as shell startup."""
    value = os.environ.get(name) or default
    if value not in allowed_values:
        allowed = ", ".join(allowed_values)
        raise ValueError(f"Unsupported {name}: {value}. Expected one of: {allowed}")
    return value


def require_directory(path: Path, label: str) -> None:
    """Fail with a clear message when a required runtime directory is missing."""
    require_absolute_path(path, f"{label} directory")
    if not path.is_dir():
        raise RuntimeError(f"{label} directory does not exist: {path}")


def require_directory_path(path: Path, label: str) -> None:
    """Fail when an existing runtime path is not a directory."""
    if path.exists() and not path.is_dir():
        raise RuntimeError(f"{label} is not a directory: {path}")


def require_creatable_directory_path(path: Path, label: str) -> None:
    """Fail when a directory path cannot be created because an ancestor is a file."""
    for directory_path in (path, *path.parents):
        if directory_path.exists():
            if not directory_path.is_dir():
                raise RuntimeError(f"{label} is not a directory: {directory_path}")
            return


def require_file_path(path: Path, label: str) -> None:
    """Fail when an existing runtime path is not a regular file."""
    if path.exists() and not path.is_file():
        raise RuntimeError(f"{label} is not a file: {path}")


def home_path() -> Path:
    """Return the required runtime home directory."""
    home = Path(require_env("HOME"))
    require_directory(home, "HOME")
    return home


def tws_settings_path() -> Path:
    """Return the TWS settings path, matching the shell startup default."""
    raw_path = os.environ.get("TWS_SETTINGS_PATH")
    if raw_path:
        settings_path = Path(raw_path)
    else:
        settings_path = home_path() / "tws_settings"
    require_absolute_path(settings_path, "TWS_SETTINGS_PATH")
    require_directory_path(settings_path, "TWS_SETTINGS_PATH")
    return settings_path


def sub_env_vars(txt: str) -> str:
    def replace_match(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2) or ""
        env_value = os.getenv(var_name)
        if env_value:
            return env_value
        return default

    return VARS_REG.sub(replace_match, txt)


def render_config_template(
    template_path: Path,
    output_path: Path,
    label: str,
    fallback_template_path: Path | None = None,
) -> None:
    """Render an environment-expanded config from a persistent template."""
    require_absolute_path(output_path, f"{label} output")
    require_creatable_directory_path(output_path.parent, f"{label} output parent")
    require_creatable_directory_path(template_path.parent, f"{label} template parent")
    require_file_path(output_path, f"{label} output")
    require_file_path(template_path, f"{label} template")
    if fallback_template_path is not None:
        require_file_path(fallback_template_path, f"{label} fallback template")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        template_content = template_path.read_text()
    except FileNotFoundError:
        try:
            current_content = output_path.read_text()
        except FileNotFoundError:
            if fallback_template_path is None or not fallback_template_path.exists():
                print(f"{label} template not found at {template_path}; skipping")
                return

            template_content = fallback_template_path.read_text()
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(template_content)
            output_path.write_text(sub_env_vars(template_content))
            print(f"Rendered {label} from {fallback_template_path} -> {output_path}")
            return

        if "${" not in current_content:
            print(f"{label} template not found and existing config is already expanded")
            return

        template_content = current_content
        template_path.parent.mkdir(parents=True, exist_ok=True)
        template_path.write_text(template_content)

    output_path.write_text(sub_env_vars(template_content))
    print(f"Rendered {label} from {template_path} -> {output_path}")


def detect_memory_mb() -> int | None:
    """Detect the container memory limit in megabytes."""
    cg2 = Path("/sys/fs/cgroup/memory.max")
    if cg2.exists():
        val = cg2.read_text().strip()
        if val == "max":
            return None
        try:
            return int(val) // (1024 * 1024)
        except ValueError:
            return None

    cg1 = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    if cg1.exists():
        try:
            raw = int(cg1.read_text().strip())
        except ValueError:
            return None

        if raw > (1 << 42):
            return None
        return raw // (1024 * 1024)

    return None


def parse_memory_mb(value: str) -> int:
    """Parse a memory value as megabytes, supporting m and g suffixes."""
    normalized = value.strip().lower()
    if normalized.endswith("m"):
        multiplier = 1
        number = normalized[:-1]
    elif normalized.endswith("g"):
        multiplier = 1024
        number = normalized[:-1]
    else:
        multiplier = 1
        number = normalized

    try:
        memory_mb = int(number) * multiplier
    except ValueError as exc:
        raise ValueError(
            f"JAVA_HEAP_SIZE must be a whole number of MB, or use an m/g suffix: {value}"
        ) from exc

    if memory_mb <= 0:
        raise ValueError(f"JAVA_HEAP_SIZE must be greater than zero: {value}")

    return memory_mb


def calculate_java_heap_size() -> str:
    """Return the configured or memory-derived maximum Java heap size."""
    java_heap_size = os.getenv("JAVA_HEAP_SIZE")
    if java_heap_size:
        return str(parse_memory_mb(java_heap_size))

    mem_mb = detect_memory_mb()
    if mem_mb is None:
        print("Memory limit unlimited/undetectable; using default heap 2048MB")
        return "2048"

    if mem_mb <= 2048:
        java_heap_size = int(mem_mb * 0.75)
    elif mem_mb <= 4096:
        java_heap_size = int(mem_mb * 0.6)
    elif mem_mb <= 8192:
        java_heap_size = int(mem_mb * 0.5)
    else:
        java_heap_size = min(4096, int(mem_mb * 0.4))

    java_heap_size = max(MIN_AUTO_HEAP_MB, java_heap_size)
    print(f"Detected cgroup memory: {mem_mb}MB; heap={java_heap_size}MB")
    return str(java_heap_size)


def calculate_initial_heap_size(java_heap_size: str) -> int:
    """Return the initial Java heap size for a maximum heap size."""
    heap_size_int = parse_memory_mb(java_heap_size)
    if heap_size_int <= 1024:
        return min(heap_size_int, max(128, heap_size_int // 2))
    if heap_size_int <= 2048:
        return 512
    return 768


def vmoptions_names(program: str) -> list[str]:
    """Return vmoptions filenames for a supported IB product."""
    if program == "ibgateway":
        return ["ibgateway.vmoptions", "tws.vmoptions"]
    if program == "tws":
        return ["tws.vmoptions"]
    raise ValueError(f"Unsupported PROGRAM: {program}")


def vmoptions_paths(program: str, ib_release_dir: Path) -> list[Path]:
    """Return every vmoptions file IBC may use for the installed program."""
    return [ib_release_dir / name for name in vmoptions_names(program)]


def resolve_ib_release_dir(program: str, install_root: Path = Path("/opt")) -> Path:
    """Return the configured or default IB release directory."""
    vmoptions_names(program)
    raw_release_dir = os.environ.get("IB_RELEASE_DIR")
    if raw_release_dir:
        return Path(raw_release_dir)

    release = require_env("IB_RELEASE")
    return install_root / program / release


def custom_jvm_opts() -> list[str]:
    """Parse custom JVM options from the environment."""
    custom_opts_env = os.getenv("CUSTOM_JVM_OPTS", "")
    try:
        return shlex.split(custom_opts_env)
    except ValueError as exc:
        raise ValueError(f"CUSTOM_JVM_OPTS is invalid: {exc}") from exc


def validate_java_heap_size() -> None:
    """Validate configured Java heap size before rendering config files."""
    java_heap_size = os.getenv("JAVA_HEAP_SIZE")
    if java_heap_size:
        parse_memory_mb(java_heap_size)


def validate_runtime_choices() -> None:
    """Validate runtime choices that shell startup also normalizes."""
    validate_env_choice("TRADING_MODE", ("paper", "live"), "paper")
    validate_env_choice("TWOFA_TIMEOUT_ACTION", ("exit", "restart"), "exit")


def validate_ibc_version(value: str) -> None:
    """Validate the IBC version string inherited from the image build."""
    if not IBC_VERSION_REG.fullmatch(value):
        raise ValueError(f"IBC_VERSION must look like 3.23.0: {value}")


def validate_ib_release_layout(program: str, ib_release_dir: Path) -> None:
    """Validate the installed IB product layout before mutating runtime config."""
    require_directory(ib_release_dir, "IB release")
    if ib_release_dir.parent.name != program:
        article = "an" if program == "ibgateway" else "a"
        raise RuntimeError(
            "IB release directory is invalid: "
            f"{program} release directory must be nested under {article} {program} "
            f"directory: {ib_release_dir}"
        )
    executable_path = ib_release_dir / program
    jars_path = ib_release_dir / "jars"
    expected_vmoptions_paths = vmoptions_paths(program, ib_release_dir)

    if not jars_path.is_dir():
        raise RuntimeError(f"IB release directory is invalid: expected {jars_path}")
    if not executable_path.is_file():
        raise RuntimeError(
            f"IB release directory is invalid: expected executable {executable_path}"
        )
    if not os.access(executable_path, os.X_OK):
        raise RuntimeError(
            f"IB release directory is invalid: executable is not runnable {executable_path}"
        )
    for vmoptions_path in expected_vmoptions_paths:
        if not vmoptions_path.is_file():
            raise RuntimeError(
                "IB release directory is invalid: "
                f"expected vmoptions file {vmoptions_path}"
            )


def validate_ibc_layout(ibc_path: Path) -> None:
    """Validate the installed IBC layout before mutating runtime config."""
    require_absolute_path(ibc_path, "IBC_PATH")
    if not ibc_path.is_dir():
        raise RuntimeError(f"IBC directory does not exist: {ibc_path}")
    ibc_start_path = ibc_path / "scripts" / "ibcstart.sh"
    if not ibc_start_path.is_file():
        raise RuntimeError(f"IBC layout is invalid: expected {ibc_start_path}")
    if not os.access(ibc_start_path, os.X_OK):
        raise RuntimeError(
            f"IBC layout is invalid: start script is not runnable {ibc_start_path}"
        )


def validate_runtime_environment() -> None:
    """Validate runtime settings that should prevent config generation."""
    program = require_env("PROGRAM")
    vmoptions_names(program)
    require_env("IB_USER")
    require_env("IB_PASSWORD")
    validate_ibc_version(require_env("IBC_VERSION"))
    validate_ibc_layout(Path(require_env("IBC_PATH")))
    validate_ib_release_layout(program, resolve_ib_release_dir(program))
    require_absolute_path(Path(require_env("IBC_INI")), "IBC_INI")
    home_path()
    tws_settings_path()
    custom_jvm_opts()
    validate_java_heap_size()
    validate_runtime_choices()


def render_vmoptions(
    template_content: str,
    java_heap_size: str,
    initial_heap: int,
    tws_settings_path: Path,
    custom_opts: list[str],
) -> str:
    """Render the lightweight vmoptions template."""
    vmoptions_content = template_content.replace("{{ max_heap }}", java_heap_size)
    vmoptions_content = vmoptions_content.replace(
        "{{ initial_heap }}", str(initial_heap)
    )
    vmoptions_content = vmoptions_content.replace(
        "{{ tws_settings_path }}", str(tws_settings_path)
    )
    custom_section = (
        ("# Custom options\n" + "\n".join(custom_opts)) if custom_opts else ""
    )
    return vmoptions_content.replace(CUSTOM_OPTS_BLOCK, custom_section)


def set_java_vmoptions() -> None:
    """Configure JVM options for IB Gateway/TWS with robust cgroup memory detection."""
    program = require_env("PROGRAM")
    vmoptions_names(program)
    ib_release_dir = resolve_ib_release_dir(program)
    settings_path = tws_settings_path()
    validate_ib_release_layout(program, ib_release_dir)
    java_heap_size = calculate_java_heap_size()
    initial_heap = calculate_initial_heap_size(java_heap_size)

    template_path = home_path() / "vmoptions.j2"
    if template_path.exists():
        require_file_path(template_path, "VM options template")
        template_content = template_path.read_text()
        vmoptions_content = render_vmoptions(
            template_content,
            java_heap_size,
            initial_heap,
            settings_path,
            custom_jvm_opts(),
        )
        for vmoptions_file in vmoptions_paths(program, ib_release_dir):
            vmoptions_file.write_text(vmoptions_content)
            print(
                "Updated vmoptions file "
                f"(heap={java_heap_size}MB, initial={initial_heap}MB) -> {vmoptions_file}"
            )
    else:
        print("VM options template not found; skipping vmoptions generation")


def main() -> None:
    validate_runtime_environment()

    ibc_ini_path = Path(require_env("IBC_INI"))
    default_ibc_dir = Path(os.environ.get("IBC_PATH", str(ibc_ini_path.parent)))
    default_ibc_template_path = default_ibc_dir / "ibc.ini.template"
    render_config_template(
        ibc_ini_path.with_suffix(".ini.template"),
        ibc_ini_path,
        "ibc.ini",
        default_ibc_template_path,
    )

    settings_path = tws_settings_path()
    jts_ini_path = settings_path / "jts.ini"
    default_jts_template_path = home_path() / "tws_settings" / "jts.ini.template"
    render_config_template(
        jts_ini_path.with_suffix(".ini.template"),
        jts_ini_path,
        "jts.ini",
        default_jts_template_path,
    )

    set_java_vmoptions()


def run() -> int:
    """Run runtime config initialization from the command line."""
    try:
        main()
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
