# ADR-003: Transfer-scoped foreground service

Status: Accepted for 1.0.4.2

## Decision

The loopback HTTP runtime is process-owned and may run while the app UI is
visible without a `dataSync` foreground service. The Python download execution
gate is closed by default on Android. A user transfer obtains a bounded lease:
foreground promotion, runtime readiness and entitlement convergence must all
succeed before queue execution is opened.

## Consequences

- Opening the app, search or library does not itself create a download FGS.
- Share, WebView, native search, retry and recovery use the same transfer gate.
- Foreground loss and promotion failure fail closed; an active visible FGS may
  continue after the Activity is removed from Recents.
- Empty queues close execution, remove the notification and stop the transfer
  service; playback remains a separate `mediaPlayback` service.

Permission purpose and historical context are documented in
[Android permissions](../../../ANDROID_PERMISSIONS_2026-07-07.md). The current
behavior still requires API 34/35 emulator and real-device verification before
release.

