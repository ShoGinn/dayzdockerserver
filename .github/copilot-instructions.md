# Copilot Instructions

Follow the root `AGENTS.md`; it is the sole canonical repository guidance. Do not duplicate or
override its architecture, security invariants, dependency policy, or verification commands here.

In particular, preserve the four-service Compose architecture, native `linux/amd64` DayZ and
SteamCMD requirements, intentional server host networking, Unix-socket permissions, fail-closed
authentication, confined 512 KiB log tails, unprivileged runtime containers, locked dependencies,
and zero-fixable-CVE release gate. Python uses `ty==0.0.65` as its sole type checker and Ruff's
annotation rules. Add regression tests for security defects and behavioral changes.
