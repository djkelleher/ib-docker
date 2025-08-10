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
    """Configure JVM options for IB Gateway/TWS"""
    program = os.environ["PROGRAM"]
    ib_release_dir = Path(os.environ["IB_RELEASE_DIR"])
    vmoptions_file = ib_release_dir / f"{program}.vmoptions"

    java_heap_size = os.getenv("JAVA_HEAP_SIZE")
    if not java_heap_size:
        try:
            with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r") as f:
                mem_limit = int(f.read().strip())
                if mem_limit < 9223372036854775807:  # Not unlimited
                    mem_mb = mem_limit // (1024 * 1024)
                    if mem_mb <= 2048:
                        java_heap_size = str(int(mem_mb * 0.75))
                    elif mem_mb <= 4096:
                        java_heap_size = str(int(mem_mb * 0.6))
                    elif mem_mb <= 8192:
                        java_heap_size = str(int(mem_mb * 0.5))
                    else:
                        java_heap_size = str(min(4096, int(mem_mb * 0.4)))
                    print(
                        f"Auto-detected container memory: {mem_mb}MB, setting heap to {java_heap_size}MB"
                    )
                else:
                    java_heap_size = "2048"
        except Exception as e:  # noqa: BLE001
            print(f"Could not detect memory: {e}")
            java_heap_size = "1536"

    heap_size_int = int(java_heap_size)
    if heap_size_int <= 1024:
        initial_heap = heap_size_int // 2
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
        if custom_opts:
            custom_section = "# Custom options\n" + "\n".join(custom_opts)
        else:
            custom_section = ""
        vmoptions_content = vmoptions_content.replace(
            "{% if custom_opts %}\n# Custom options\n{% for opt in custom_opts %}\n{{ opt }}\n{% endfor %}\n{% endif %}",
            custom_section,
        )
        vmoptions_file.write_text(vmoptions_content)
        print(
            f"Updated vmoptions file with optimized settings (heap={java_heap_size}MB, initial={initial_heap}MB)"
        )
        print(f"VM Options written to: {vmoptions_file}")
        template_path.unlink(missing_ok=True)
    else:
        print("VM options template not found; skipping vmoptions generation")


def main():
    ibc_ini_path = Path(os.environ["IBC_PATH"]) / "ibc.ini"
    try:
        content = ibc_ini_path.read_text()
    except FileNotFoundError:
        print(f"IBC ini not found at {ibc_ini_path}")
        return

    if "${" in content:  # Needs substitution
        print("Expanding environment variables in ibc.ini")
        new_content = sub_env_vars(content)
        ibc_ini_path.write_text(new_content)
    else:
        print("ibc.ini already expanded; skipping substitution")

    # Always ensure JVM options file exists / updated each start (cheap & idempotent)
    set_java_vmoptions()


if __name__ == "__main__":
    main()
