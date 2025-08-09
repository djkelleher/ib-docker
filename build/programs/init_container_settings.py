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


def check_container_settings_initialized():
    flag_file = Path.home() / "init_container_vars"
    if not flag_file.exists():
        print("Container settings already initialized (flag file not found)")
        return
    ibc_ini_file = Path(os.environ["IBC_PATH"]) / "ibc.ini"
    ibc_ini_file.write_text(sub_env_vars(ibc_ini_file.read_text()))
    # --- handle JAVA_HEAP_SIZE in VM options ---
    # TODO: include IB_VMOPTIONS
    ib_vmoptions = os.getenv("IB_VMOPTIONS")
    java_heap = os.getenv("JAVA_HEAP_SIZE")
    if java_heap and ib_vmoptions:
        # read, replace, write
        ib_vmoptions = Path(ib_vmoptions)
        ib_vmoptions.write_text(
            ib_vmoptions.read_text().replace("-Xmx768m", f"-Xmx{java_heap}m")
        )
        print(f"Java heap size set to {java_heap}m")

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
        "enable_socat": should_enable_socat(),
        "enable_ssh_tunnel": should_enable_ssh_tunnel(),
    }
    print(
        f"Configuring supervisord with: UI={bool(template_vars['supervisord_ui_port'])}, "
        f"SOCAT={template_vars['enable_socat']}, SSH={template_vars['enable_ssh_tunnel']}"
    )

    # Render template
    template_content = supervisord_template_path.read_text()
    template = Template(template_content)
    rendered_config = template.render(**template_vars)

    # Write rendered config
    Path("/etc/supervisor/conf.d/supervisord.conf").write_text(rendered_config)
    supervisord_template_path.unlink()
    print("supervisord.conf generated from template")


def should_enable_socat():
    """Determine if socat should be enabled based on environment variables"""
    enable_socat = os.getenv("ENABLE_SOCAT", "yes").lower()
    ssh_tunnel = os.getenv("SSH_TUNNEL", "").lower()

    if enable_socat == "no":
        return False
    if ssh_tunnel == "yes":  # SSH tunnel only mode
        return False
    return True  # Default enabled for 'both' mode or standard mode


def should_enable_ssh_tunnel():
    """Determine if SSH tunnel should be enabled based on environment variables"""
    ssh_tunnel = os.getenv("SSH_TUNNEL", "").lower()
    return ssh_tunnel in ["yes", "both"]


if __name__ == "__main__":
    check_container_settings_initialized()
