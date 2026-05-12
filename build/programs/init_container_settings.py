#!/usr/bin/env python3

import os
import re
import shlex
import sys
from pathlib import Path

VARS_REG = re.compile(r"\$\{([a-zA-Z_][\w]*)(?::-(.*?))?\}")
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


def require_directory(path: Path, label: str) -> None:
    """Fail with a clear message when a required runtime directory is missing."""
    if not path.is_dir():
        raise RuntimeError(f"{label} directory does not exist: {path}")


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
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        template_content = template_path.read_text()
    except FileNotFoundError:
        if fallback_template_path is not None and fallback_template_path.exists():
            template_content = fallback_template_path.read_text()
            template_path.write_text(template_content)
            output_path.write_text(sub_env_vars(template_content))
            print(f"Rendered {label} from {fallback_template_path} -> {output_path}")
            return

        try:
            current_content = output_path.read_text()
        except FileNotFoundError:
            print(f"{label} template not found at {template_path}; skipping")
            return

        if "${" not in current_content:
            print(f"{label} template not found and existing config is already expanded")
            return

        template_content = current_content
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


def validate_runtime_environment() -> None:
    """Validate runtime settings that should prevent config generation."""
    program = require_env("PROGRAM")
    vmoptions_names(program)
    require_directory(Path(require_env("IB_RELEASE_DIR")), "IB release")


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
    ib_release_dir = Path(require_env("IB_RELEASE_DIR"))
    tws_settings_path = Path(require_env("TWS_SETTINGS_PATH"))
    require_directory(ib_release_dir, "IB release")
    java_heap_size = calculate_java_heap_size()
    initial_heap = calculate_initial_heap_size(java_heap_size)

    template_path = Path.home() / "vmoptions.j2"
    if template_path.exists():
        template_content = template_path.read_text()
        custom_opts_env = os.getenv("CUSTOM_JVM_OPTS", "")
        custom_opts = shlex.split(custom_opts_env)
        vmoptions_content = render_vmoptions(
            template_content,
            java_heap_size,
            initial_heap,
            tws_settings_path,
            custom_opts,
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

    tws_settings_path = Path(require_env("TWS_SETTINGS_PATH"))
    jts_ini_path = tws_settings_path / "jts.ini"
    default_jts_template_path = Path.home() / "tws_settings" / "jts.ini.template"
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
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
