#!/usr/bin/env python3

import os
import re
from pathlib import Path

vars_reg = re.compile(r"\$\{([a-zA-Z_][\w]*)(?::-(.*?))?\}")


def sub_env_vars(txt: str) -> str:
    for match in vars_reg.finditer(txt):
        var_name = match.group(1)
        default = match.group(2)
        txt = txt.replace(match.group(), os.getenv(var_name, default))
    return txt


def check_container_settings_initialized():
    flag_file = Path("/init_container_vars")
    if not flag_file.exists():
        return
    program = os.getenv("PROGRAM")
    if program == "ibgateway":
        ib_ini_file = Path(f"/opt/ibgateway/{os.environ['IB_RELEASE']}/jts.ini")
    elif program == "tws":
        ib_ini_file = Path("/Jts/stable/jts.ini")
    else:
        raise RuntimeError(f"Unknown program: {program}. Valid options: ibgateway, tws")
    ib_ini_file.write_text(sub_env_vars(ib_ini_file.read_text()))
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
    flag_file.unlink()


if __name__ == "__main__":
    check_container_settings_initialized()
