# Security Policy

## Reporting a Vulnerability

Do not open a public issue for suspected vulnerabilities, leaked credentials, or
account-specific trading information.

Report security concerns through GitHub Security Advisories for this repository.
Include the affected image, tag or commit, reproduction steps, and any relevant
logs with credentials redacted.

## Supported Versions

Security fixes are made on the `main` branch and published through the normal
image release workflow. Users should run current image tags and rebuild pinned
deployments regularly.

## Trust Model

These images bundle Interactive Brokers software, IBC, Java runtime components,
and Linux packages. Treat the resulting image as a privileged trading-session
runtime:

- pass IB credentials with `IB_USER_FILE` and `IB_PASSWORD_FILE` when possible;
- do not expose VNC beyond trusted networks;
- prefer SSH tunneling or local-only binding for GUI access;
- keep persistent TWS settings volumes private because upstream software may
  write account-specific state there.
