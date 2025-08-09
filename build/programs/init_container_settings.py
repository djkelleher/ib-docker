#!/usr/bin/env python3

import os
import re
from pathlib import Path

from jinja2 import Template

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
    ib_release_dir = os.environ["IB_RELEASE_DIR"]
    vmoptions_file = Path(ib_release_dir) / f"{program}.vmoptions"

    if not vmoptions_file.exists():
        print(f"Warning: vmoptions file not found at {vmoptions_file}")
        return

    # Backup original file
    backup_file = vmoptions_file.with_suffix(".vmoptions.original")
    if not backup_file.exists():
        backup_file.write_text(vmoptions_file.read_text())
        print(f"Backed up original vmoptions to {backup_file}")

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

    # Write optimized vmoptions
    vmoptions_content = f"""# Memory settings
-Xmx{java_heap_size}m
-Xms{initial_heap}m

# Garbage Collection
-XX:+UseG1GC
-XX:MaxGCPauseMillis=200
-XX:+ParallelRefProcEnabled

# Container support
-XX:+UnlockExperimentalVMOptions
-XX:+UseContainerSupport
-XX:MaxRAMPercentage=75.0

# Performance
-XX:+UseStringDeduplication
-XX:+OptimizeStringConcat

# GUI and stability
-Djava.awt.headless=false
-Dsun.java2d.xrender=false
-Dsun.java2d.pmoffscreen=false
-Dsun.java2d.uiScale=1.0
-Dswing.boldMetal=false

# WebKit/JavaFX stability
-Dcom.sun.webkit.useHTML5MediaPlayer=false
-Dprism.order=sw
-Dprism.verbose=false

# Network
-Djava.net.preferIPv4Stack=true
-Djava.security.egd=file:/dev/./urandom

# Crash prevention
-XX:+ExitOnOutOfMemoryError
-XX:ErrorFile=/tmp/hs_err_pid%p.log

# IB specific
-Dinstaller.uuid=/home/ibuser
-DjtsConfigDir=/home/ibuser/tws_settings
"""

    vmoptions_file.write_text(vmoptions_content)
    print(f"Updated vmoptions file with optimized settings (heap={java_heap_size}MB)")
    print(f"VM Options written to: {vmoptions_file}")


def check_container_settings_initialized():
    flag_file = Path.home() / "init_container_vars"
    if not flag_file.exists():
        print("Container settings already initialized (flag file not found)")
        return
    ibc_ini_file = Path(os.environ["IBC_PATH"]) / "ibc.ini"
    ibc_ini_file.write_text(sub_env_vars(ibc_ini_file.read_text()))

    # Configure JVM options once during initialization
    set_java_vmoptions()

    # --- handle supervisord inet_http_server configuration ---
    configure_supervisord_web_interface()

    flag_file.unlink()


def configure_supervisord_web_interface():
    """Configure supervisord using Jinja2 template with environment variables"""
    supervisord_template_path = Path.home() / "supervisord.conf.j2"
    if not supervisord_template_path.exists():
        print("supervisord.conf.j2 template not found, skipping configuration")
        return

    # Prepare template variables from environment
    template_vars = {
        "supervisord_ui_port": os.getenv("SUPERVISORD_UI_PORT"),
        "supervisord_ui_user": os.getenv("SUPERVISORD_UI_USER", "admin"),
        "supervisord_ui_pass": os.getenv("SUPERVISORD_UI_PASS", "admin"),
    }
    print(
        f"Configuring supervisord with: UI={bool(template_vars['supervisord_ui_port'])}"
    )

    # Render template
    template_content = supervisord_template_path.read_text()
    template = Template(template_content)
    rendered_config = template.render(**template_vars)

    # Write rendered config
    Path("/etc/supervisor/conf.d/supervisord.conf").write_text(rendered_config)
    supervisord_template_path.unlink()
    print("supervisord.conf generated from template")


if __name__ == "__main__":
    check_container_settings_initialized()
