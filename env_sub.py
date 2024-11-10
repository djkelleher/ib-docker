import argparse
import os
import re
import sys


def create_options():
    parser = argparse.ArgumentParser(
        description="Rewrites input to output expanding environment variables"
    )
    parser.add_argument(
        "-g",
        "--greedy-defaults",
        action="store_true",
        help="allow expansion of undefined variable defaults",
    )
    parser.add_argument(
        "-v",
        "--variable",
        action="append",
        help="restrict expansion to named variables only",
        metavar="VAR",
    )
    parser.add_argument(
        "-p",
        "--prefix",
        default="${",
        help="set the expansion prefix marker (default: ${)",
        metavar="PREFIX",
    )
    parser.add_argument(
        "-s",
        "--suffix",
        default="}",
        help="set the expansion suffix marker (default: })",
        metavar="SUFFIX",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version="1.0",
        help="print the version and exit",
    )
    return parser


def print_usage(program):
    print(f"Usage: {program} [options]")
    print()
    print("Rewrites input to output expanding environment variables")
    print()
    print("NOTE: Only ${ENV_VAR} and ${ENV_VAR-default value} are supported")
    print("      (and you are on your own if your default value needs to include")
    print("      a } character)")
    print()


def main():
    parser = create_options()
    args = parser.parse_args()

    prefix = args.prefix
    suffix = args.suffix
    greedy = (
        re.compile(
            rf"{re.escape(prefix)}[a-zA-Z_][a-zA-Z0-9_]*:?-(.*?)" + re.escape(suffix)
        )
        if args.greedy_defaults
        else None
    )

    if args.variable:
        vars = {}
        for var_name in args.variable:
            vars[var_name] = (
                re.compile(
                    rf"{re.escape(prefix)}{var_name}((:?-)(.*?))??" + re.escape(suffix)
                ),
                os.getenv(var_name),
            )
    else:
        vars = {
            key: (
                re.compile(
                    rf"{re.escape(prefix)}{key}((:?-)(.*?))??" + re.escape(suffix)
                ),
                os.getenv(key),
            )
            for key in os.environ
        }

    for line in sys.stdin:
        out = line.strip()
        for var_name, (regex, value) in vars.items():
            out = regex.sub(lambda match: handle_match(match, value), out)

        if greedy:
            out = greedy.sub(lambda match: match.group(1) or "", out)

        sys.stdout.write(out + "\n")
        sys.stdout.flush()


def handle_match(caps, val):
    if caps.group(2):
        if caps.group(2) == ":-":
            return val if val and val.strip() else caps.group(3) or ""
        else:
            return val or caps.group(3) or ""
    else:
        return val or caps.group(0)


if __name__ == "__main__":
    main()
    main()
