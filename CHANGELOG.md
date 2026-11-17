# Fork releases

## v2.11.1

Based on upstream main at 6a73a2d9e590f0cc7684036ca8fbf26812ceca0a (after v2.11.0).

- Add an authenticated browser dashboard for TV-code pairing, configuration,
  channel whitelists, and JSON import/export.
- Use the current upstream pairing helper and playback client.
- Validate configuration before an atomic save. Apply valid updates without
  restarting containers; retain working settings when an external update is invalid.
- Run worker and dashboard as a non-root user with health checks, read-only
  root filesystems, and no Docker socket access.
- Publish matching amd64 and arm64 worker/dashboard images.
