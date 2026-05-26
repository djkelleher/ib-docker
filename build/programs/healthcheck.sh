#!/bin/bash
set -euo pipefail

supervisorctl status xvfb ibc |
	awk '/^xvfb[[:space:]]+RUNNING/{xvfb=1} /^ibc[[:space:]]+RUNNING/{ibc=1} END{exit !(xvfb && ibc)}'

xset q >/dev/null 2>&1
