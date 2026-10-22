# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Report it privately through GitHub's advisory form:
<https://github.com/jjjake/internetarchive/security/advisories/new>.
If that is not an option, email jake@archive.org.

Include the version (`ia --version`), how to reproduce, and what an attacker
gains. You should hear back within a week. Once a fix is released the advisory
is published with credit to the reporter unless you ask otherwise.

## Supported versions

Fixes go into the latest release only. `ia` and the `internetarchive` library
have no long-term-support branches; upgrading is the fix.

## Scope

This policy covers the `internetarchive` Python package, the `ia` command, and
the `ia` pex binary published to <https://archive.org/details/ia-pex>.
Vulnerabilities in archive.org itself go to <https://archive.org/about/contact.php>.

## Dependencies

Dependabot alerts and a weekly `uv audit` run watch the lockfile. The pex
binary bundles its dependencies, so a dependency advisory that affects the
`ia` binary gets a new release rather than waiting for the next feature
release.
