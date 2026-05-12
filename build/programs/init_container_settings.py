#!/usr/bin/env python3

import os
import re
from pathlib import Path

VARS_REG = re.compile(r"\$\{([a-zA-Z_][\w]*)(?::-(.*?))?\}")
CUSTOM_OPTS_BLOCK = """{% if custom_opts %}
# Custom options
{% for opt in custom_opts %}
{{ opt }}
{% endfor %}
{% endif %}"""


def sub_env_vars(txt: str) -> str:
    def replace_match(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2) or ""
        return os.getenv(var_name, default)

    return VARS_REG.sub(replace_match, txt)


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


def calculate_java_heap_size() -> str:
    """Return the configured or memory-derived maximum Java heap size."""
    java_heap_size = os.getenv("JAVA_HEAP_SIZE")
    if java_heap_size:
        return java_heap_size

    mem_mb = detect_memory_mb()
    if mem_mb is None:
        print("Memory limit unlimited/undetectable; using default heap 2048MB")
        return "2048"

    if mem_mb <= 2048:
        java_heap_size = str(int(mem_mb * 0.75))
    elif mem_mb <= 4096:
        java_heap_size = str(int(mem_mb * 0.6))
    elif mem_mb <= 8192:
        java_heap_size = str(int(mem_mb * 0.5))
    else:
        java_heap_size = str(min(4096, int(mem_mb * 0.4)))

    print(f"Detected cgroup memory: {mem_mb}MB; heap={java_heap_size}MB")
    return java_heap_size


def calculate_initial_heap_size(java_heap_size: str) -> int:
    """Return the initial Java heap size for a maximum heap size."""
    heap_size_int = int(java_heap_size)
    if heap_size_int <= 1024:
        return max(128, heap_size_int // 2)
    if heap_size_int <= 2048:
        return 512
    return 768


def vmoptions_paths(program: str, ib_release_dir: Path) -> list[Path]:
    """Return every vmoptions file IBC may use for the installed program."""
    names = [f"{program}.vmoptions"]
    if program == "ibgateway":
        names.append("tws.vmoptions")
    return [ib_release_dir / name for name in names]


def render_vmoptions(
    template_content: str,
    java_heap_size: str,
    initial_heap: int,
    custom_opts: list[str],
) -> str:
    """Render the lightweight vmoptions template."""
    vmoptions_content = template_content.replace("{{ max_heap }}", java_heap_size)
    vmoptions_content = vmoptions_content.replace(
        "{{ initial_heap }}", str(initial_heap)
    )
    custom_section = (
        ("# Custom options\n" + "\n".join(custom_opts)) if custom_opts else ""
    )
    return vmoptions_content.replace(CUSTOM_OPTS_BLOCK, custom_section)


def set_java_vmoptions() -> None:
    """Configure JVM options for IB Gateway/TWS with robust cgroup memory detection."""
    program = os.environ["PROGRAM"]
    ib_release_dir = Path(os.environ["IB_RELEASE_DIR"])
    java_heap_size = calculate_java_heap_size()
    initial_heap = calculate_initial_heap_size(java_heap_size)

    template_path = Path.home() / "vmoptions.j2"
    if template_path.exists():
        template_content = template_path.read_text()
        custom_opts_env = os.getenv("CUSTOM_JVM_OPTS", "")
        custom_opts = [opt.strip() for opt in custom_opts_env.split() if opt.strip()]
        vmoptions_content = render_vmoptions(
            template_content, java_heap_size, initial_heap, custom_opts
        )
        for vmoptions_file in vmoptions_paths(program, ib_release_dir):
            vmoptions_file.write_text(vmoptions_content)
            print(
                "Updated vmoptions file "
                f"(heap={java_heap_size}MB, initial={initial_heap}MB) -> {vmoptions_file}"
            )
    else:
        print("VM options template not found; skipping vmoptions generation")


def expand_ini_file(path: Path, label: str) -> None:
    """Expand environment variables in an ini file if it exists."""
    try:
        content = path.read_text()
    except FileNotFoundError:
        print(f"{label} not found at {path}; skipping env expansion")
        return

    if "${" in content:
        print(f"Expanding environment variables in {label}")
        path.write_text(sub_env_vars(content))
    else:
        print(f"{label} has no variables to expand; skipping")


def main() -> None:
    ibc_ini_path = Path(os.environ["IBC_PATH"]) / "ibc.ini"
    expand_ini_file(ibc_ini_path, "ibc.ini")

    jts_ini_path = Path.home() / "tws_settings" / "jts.ini"
    expand_ini_file(jts_ini_path, "jts.ini")

    set_java_vmoptions()


if __name__ == "__main__":
    main()
