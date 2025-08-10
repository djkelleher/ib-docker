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

    # Auto-detect container memory if JAVA_HEAP_SIZE not set
    java_heap_size = os.getenv("JAVA_HEAP_SIZE")
    if not java_heap_size:
        try:
            with open("/sys/fs/cgroup/memory/memory.limit_in_bytes", "r") as f:
                mem_limit = int(f.read().strip())
                if mem_limit < 9223372036854775807:  # Not unlimited
                    mem_mb = mem_limit // (1024 * 1024)

                    # Smarter heap allocation based on container memory
                    # IB Gateway/TWS typically needs 1-2GB for normal operation
                    # More memory helps with multiple charts/data streams
                    if mem_mb <= 2048:  # 2GB or less
                        # Use 75% for very constrained environments
                        java_heap_size = str(int(mem_mb * 0.75))
                    elif mem_mb <= 4096:  # 2-4GB
                        # Use 60% to leave room for OS and other processes
                        java_heap_size = str(int(mem_mb * 0.6))
                    elif mem_mb <= 8192:  # 4-8GB
                        # Use 50% - plenty for IB and system
                        java_heap_size = str(int(mem_mb * 0.5))
                    else:  # > 8GB
                        # Cap at 4GB - IB rarely needs more than this
                        # Using more can actually cause longer GC pauses
                        java_heap_size = str(min(4096, int(mem_mb * 0.4)))

                    print(
                        f"Auto-detected container memory: {mem_mb}MB, setting heap to {java_heap_size}MB"
                    )
                else:
                    # Default for unlimited memory
                    java_heap_size = "2048"
        except Exception as e:
            # Default fallback
            print(f"Could not detect memory: {e}")
            java_heap_size = "1536"  # Conservative default

    # Calculate initial heap size (Xms)
    # Start with smaller initial heap to reduce startup time
    # but not too small to avoid excessive heap growth operations
    heap_size_int = int(java_heap_size)
    if heap_size_int <= 1024:
        initial_heap = heap_size_int // 2  # 50% for small heaps
    elif heap_size_int <= 2048:
        initial_heap = 512  # Fixed 512MB for medium heaps
    else:
        initial_heap = 768  # Fixed 768MB for larger heaps (IB's default)

    template_path = Path.home() / "vmoptions.j2"
    # Load and render the vmoptions template
    template_content = template_path.read_text()
    # Parse custom JVM options from environment if provided
    custom_opts_env = os.getenv("CUSTOM_JVM_OPTS", "")
    custom_opts = []
    if custom_opts_env:
        custom_opts = [opt.strip() for opt in custom_opts_env.split() if opt.strip()]

    # Simple string replacement for template variables
    vmoptions_content = template_content.replace("{{ max_heap }}", java_heap_size)
    vmoptions_content = vmoptions_content.replace(
        "{{ initial_heap }}", str(initial_heap)
    )

    # Handle custom options
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

    # Clean up template file after use
    if template_path.exists():
        template_path.unlink()


def check_container_settings_initialized():
    flag_file = Path.home() / "init_container_vars"
    if not flag_file.exists():
        print("Container settings already initialized (flag file not found)")
        return
    ibc_ini_file = Path(os.environ["IBC_PATH"]) / "ibc.ini"
    ibc_ini_file.write_text(sub_env_vars(ibc_ini_file.read_text()))

    # Configure JVM options once during initialization
    set_java_vmoptions()

    flag_file.unlink()


if __name__ == "__main__":
    check_container_settings_initialized()
