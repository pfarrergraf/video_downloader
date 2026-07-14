package de.classydl.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LicenseCachePolicyTest {
    @Test fun validAtExactly72Hours() {
        assertTrue(LicenseCachePolicy.isInsideGrace(1_000L, 1_000L + EntitlementStore.OFFLINE_GRACE_MS))
    }

    @Test fun expiresAfter72Hours() {
        assertFalse(LicenseCachePolicy.isInsideGrace(1_000L, 1_001L + EntitlementStore.OFFLINE_GRACE_MS))
    }

    @Test fun rejectsMissingOrFutureVerification() {
        assertFalse(LicenseCachePolicy.isInsideGrace(0L, 5_000L))
        assertFalse(LicenseCachePolicy.isInsideGrace(6_000L, 5_000L))
    }
}
