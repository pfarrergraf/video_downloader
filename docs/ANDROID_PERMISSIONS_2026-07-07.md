# Android permission additions — owner approval record (2026-07-07)

Per the permission guardrail in `CLAUDE.md`, dangerous/new manifest
permissions require explicit written approval from the repository owner.

## Approved on 2026-07-07 (in-session confirmation by the owner)

The owner was asked: *"Downloads sollen weiterlaufen, wenn die App in den
Hintergrund geht, mit Fortschritts-/Fertig-Benachrichtigung (wie bei
Seal/YTDLnis). Dafür braucht die App neue Android-Berechtigungen:
FOREGROUND_SERVICE, FOREGROUND_SERVICE_DATA_SYNC (beide harmlos/install-time)
und POST_NOTIFICATIONS (Laufzeit-Abfrage beim Nutzer). Genehmigst du diese
drei?"* — Answer: **"Ja, alle drei genehmigen"**.

| Permission | Protection level | Why it's needed |
|---|---|---|
| `android.permission.FOREGROUND_SERVICE` | normal (install-time) | `DownloadService` hosts the embedded Python server + download queue as a foreground service so downloads survive the user switching apps or turning the screen off. Without it, Android kills the process and every in-flight download with it (the pre-2026-07 behavior). |
| `android.permission.FOREGROUND_SERVICE_DATA_SYNC` | normal (install-time) | Required on API 34+ to start a foreground service with `foregroundServiceType="dataSync"` — the canonical type for user-initiated transfers. |
| `android.permission.POST_NOTIFICATIONS` | dangerous (runtime, API 33+) | Makes the download-progress notification and the tappable "Download fertig" notification visible. Requested **contextually once, right after the user's first download starts** (never at app launch); a denial is respected permanently and the app degrades gracefully (service still runs, no visible notifications). |

Additional manifest changes that are NOT permissions (listed for
transparency):

- `<service android:name=".DownloadService" android:exported="false" android:foregroundServiceType="dataSync"/>` — not exported; nothing outside the app can start it.
- `ACTION_SEND` intent-filter + `launchMode="singleTask"` on `MainActivity` (2026-07-07, share-target feature) — an intent-filter is not a permission.

Unchanged, per the guardrail: `android:allowBackup="false"` stays; the app
still requests **no** access to contacts, SMS, location, camera, microphone,
storage beyond its own scoped directories, or any other user data.
