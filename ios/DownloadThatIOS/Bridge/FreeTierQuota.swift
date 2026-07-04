import Foundation

/// Tracks the free tier's rolling-window download quota locally on-device, mirroring
/// video_downloader/web/server.py's _recent_job_count/FREE_DAILY_DOWNLOAD_LIMIT
/// semantics (3 downloads per rolling 24h window, not a calendar day) - there's no
/// shared Python process on iOS to hold that state, so this reimplements just the
/// counting rule natively.
///
/// The server counts a job the moment it's queued (pending/in_progress/completed all
/// count; only cancelled/failed don't - "a user isn't punished for a source that
/// didn't work out"). iOS downloads happen synchronously per item with no concurrent
/// multi-connection race to guard against, so recording only on success reproduces the
/// same steady-state behavior more simply: a slot is checked before starting and
/// spent only once a download actually succeeds.
enum FreeTierQuota {
    static let dailyLimit = AppConfig.freeDailyDownloadLimit
    static let windowHours = 24

    private static let defaultsKey = "com.gaistreich.downloadthat.recentDownloadTimestamps"

    static func remainingSlots() -> Int {
        max(0, dailyLimit - recentCount())
    }

    static func hasSlotAvailable() -> Bool {
        recentCount() < dailyLimit
    }

    static func recordSuccessfulDownload() {
        var timestamps = prunedTimestamps()
        timestamps.append(Date().timeIntervalSince1970)
        UserDefaults.standard.set(timestamps, forKey: defaultsKey)
    }

    private static func recentCount() -> Int {
        prunedTimestamps().count
    }

    private static func prunedTimestamps() -> [Double] {
        let cutoff = Date().timeIntervalSince1970 - Double(windowHours) * 3600
        let stored = UserDefaults.standard.array(forKey: defaultsKey) as? [Double] ?? []
        return stored.filter { $0 >= cutoff }
    }
}
