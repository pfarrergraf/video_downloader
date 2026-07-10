package de.classydl.app

import android.content.Context
import android.content.Intent
import android.net.Uri

/**
 * Stores only the public partner slug received through the narrowly scoped
 * /claim/<slug> Android App Link. No customer identity or browsing history is
 * stored. Referrals expire after the same 180-day window used by the website.
 */
object AffiliateReferral {
    private const val PREFS_NAME = "classydl_prefs"
    private const val PREFS_SLUG_KEY = "affiliate_partner_slug"
    private const val PREFS_CAPTURED_AT_KEY = "affiliate_partner_captured_at"
    private const val ATTRIBUTION_WINDOW_MS = 180L * 24 * 60 * 60 * 1000
    private val VALID_SLUG = Regex("^[a-z0-9][a-z0-9-]{1,47}$")
    private val ALLOWED_HOSTS = setOf("downloadthat.pages.dev", "downloadthat.gaistreich.com")

    fun capture(context: Context, intent: Intent?): Boolean {
        if (intent?.action != Intent.ACTION_VIEW) return false
        val uri = intent.data ?: return false
        val host = uri.host ?: return false
        if (uri.scheme != "https" || host !in ALLOWED_HOSTS) return false
        val segments = uri.pathSegments
        if (segments.size != 2 || segments[0] != "claim") return false
        val slug = segments[1].lowercase()
        if (!VALID_SLUG.matches(slug)) return false

        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(PREFS_SLUG_KEY, slug)
            .putLong(PREFS_CAPTURED_AT_KEY, System.currentTimeMillis())
            .apply()
        return true
    }

    /**
     * Converts only DownloadThat's own pricing link into the partner route.
     * All unrelated outbound URLs remain byte-for-byte unchanged.
     */
    fun rewritePricingUrl(context: Context, original: Uri): Uri {
        val host = original.host ?: return original
        if (original.scheme != "https" || host !in ALLOWED_HOSTS) return original
        val isPricing = original.fragment == "pricing" || original.path == "/pricing"
        if (!isPricing) return original

        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val slug = prefs.getString(PREFS_SLUG_KEY, null) ?: return original
        val capturedAt = prefs.getLong(PREFS_CAPTURED_AT_KEY, 0L)
        if (!VALID_SLUG.matches(slug) || capturedAt <= 0L ||
            System.currentTimeMillis() - capturedAt > ATTRIBUTION_WINDOW_MS
        ) {
            prefs.edit().remove(PREFS_SLUG_KEY).remove(PREFS_CAPTURED_AT_KEY).apply()
            return original
        }

        return Uri.parse("https://downloadthat.pages.dev/p/$slug?buy=1")
    }
}
