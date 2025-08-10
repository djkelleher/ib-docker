#!/usr/bin/env python3

import os
import re
from pathlib import Path

vars_reg = re.compile(r"\$\{([a-zA-Z_][\w]*)(?::-(.*?))?\}")


def sub_env_vars(txt: str) -> str:
    for match in vars_reg.finditer(txt):
        var_name = match.group(1)
        default = match.group(2) or ""
        var_value = os.getenv(var_name, default)
        txt = txt.replace(match.group(), var_value)
    return txt


def set_java_vmoptions():
    """Configure JVM options for IB Gateway/TWS with robust cgroup memory detection."""
    program = os.environ["PROGRAM"]
    ib_release_dir = Path(os.environ["IB_RELEASE_DIR"])
    vmoptions_file = ib_release_dir / f"{program}.vmoptions"

    def detect_memory_mb() -> int | None:
        # cgroup v2
        cg2 = Path("/sys/fs/cgroup/memory.max")
        if cg2.exists():
            val = cg2.read_text().strip()
            if val == "max":
                return None
            try:
                mb = int(val) // (1024 * 1024)
                return mb
            except ValueError:
                return None
        # cgroup v1
        cg1 = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
        if cg1.exists():
            try:
                raw = int(cg1.read_text().strip())
                # Treat absurdly huge limits (> 4TB) as unlimited
                if raw > (1 << 42):  # 4 TB threshold
                    return None
                return raw // (1024 * 1024)
            except Exception:  # noqa: BLE001
                return None
        return None

    java_heap_size = os.getenv("JAVA_HEAP_SIZE")
    if not java_heap_size:
        mem_mb = detect_memory_mb()
        if mem_mb is None:
            # Unlimited or undetectable: default to 2048MB
            java_heap_size = "2048"
            print("Memory limit unlimited/undetectable; using default heap 2048MB")
        else:
            if mem_mb <= 2048:
                java_heap_size = str(int(mem_mb * 0.75))
            elif mem_mb <= 4096:
                java_heap_size = str(int(mem_mb * 0.6))
            elif mem_mb <= 8192:
                java_heap_size = str(int(mem_mb * 0.5))
            else:
                java_heap_size = str(min(4096, int(mem_mb * 0.4)))
            print(f"Detected cgroup memory: {mem_mb}MB; heap={java_heap_size}MB")

    heap_size_int = int(java_heap_size)
    if heap_size_int <= 1024:
        initial_heap = max(128, heap_size_int // 2)
    elif heap_size_int <= 2048:
        initial_heap = 512
    else:
        initial_heap = 768

    template_path = Path.home() / "vmoptions.j2"
    if template_path.exists():
        template_content = template_path.read_text()
        custom_opts_env = os.getenv("CUSTOM_JVM_OPTS", "")
        custom_opts = [opt.strip() for opt in custom_opts_env.split() if opt.strip()]
        vmoptions_content = template_content.replace("{{ max_heap }}", java_heap_size)
        vmoptions_content = vmoptions_content.replace(
            "{{ initial_heap }}", str(initial_heap)
        )
        custom_section = (
            ("# Custom options\n" + "\n".join(custom_opts)) if custom_opts else ""
        )
        vmoptions_content = vmoptions_content.replace(
            "{% if custom_opts %}\n# Custom options\n{% for opt in custom_opts %}\n{{ opt }}\n{% endfor %}\n{% endif %}",
            custom_section,
        )
        vmoptions_file.write_text(vmoptions_content)
        print(
            f"Updated vmoptions file (heap={java_heap_size}MB, initial={initial_heap}MB) -> {vmoptions_file}"
        )
        template_path.unlink(missing_ok=True)
    else:
        print("VM options template not found; skipping vmoptions generation")


def main():
    ibc_ini_path = Path(os.environ["IBC_PATH"]) / "ibc.ini"
    try:
        content = ibc_ini_path.read_text()
    except FileNotFoundError:
        print(f"IBC ini not found at {ibc_ini_path}")
        content = None
    if content is not None:
        if "${" in content:
            print("Expanding environment variables in ibc.ini")
            new_content = sub_env_vars(content)
            ibc_ini_path.write_text(new_content)
        else:
            print("ibc.ini already expanded; skipping substitution")

    # Also expand variables in jts.ini (TWS settings)
    jts_ini_path = Path.home() / "tws_settings" / "jts.ini"
    if jts_ini_path.exists():
        jts_content = jts_ini_path.read_text()
        if "${" in jts_content:
            print("Expanding environment variables in jts.ini")
            jts_new = sub_env_vars(jts_content)
            jts_ini_path.write_text(jts_new)
        else:
            print("jts.ini has no variables to expand; skipping")
    else:
        print(f"jts.ini not found at {jts_ini_path}; skipping env expansion")

    # Always ensure JVM options file exists / updated each start (cheap & idempotent)
    set_java_vmoptions()


if __name__ == "__main__":
    main()
