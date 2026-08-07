package de.classydl.app

import org.junit.Assert.assertEquals
import org.junit.Test

class PurchaseFlowPolicyTest {
    @Test fun alreadyOwnedAlwaysReconcilesInsteadOfLaunchingAgain() {
        assertEquals(
            PurchaseFlowDecision.RECONCILE_OWNED,
            PurchaseFlowPolicy.decide(PurchaseFlowSignal.ITEM_ALREADY_OWNED, false),
        )
    }

    @Test fun userCancellationIsNotReportedAsPurchaseFailureOrSuccess() {
        assertEquals(
            PurchaseFlowDecision.REPORT_CANCELLED,
            PurchaseFlowPolicy.decide(PurchaseFlowSignal.USER_CANCELLED, false),
        )
    }

    @Test fun okProcessesOnlyWhenPlayActuallyReturnsTheProduct() {
        assertEquals(
            PurchaseFlowDecision.PROCESS_PURCHASES,
            PurchaseFlowPolicy.decide(PurchaseFlowSignal.OK, true),
        )
        assertEquals(
            PurchaseFlowDecision.REPORT_INCOMPLETE,
            PurchaseFlowPolicy.decide(PurchaseFlowSignal.OK, false),
        )
    }

    @Test fun retryableAndFatalErrorsStayDistinct() {
        assertEquals(
            PurchaseFlowDecision.REPORT_RETRYABLE_ERROR,
            PurchaseFlowPolicy.decide(PurchaseFlowSignal.RETRYABLE_ERROR, false),
        )
        assertEquals(
            PurchaseFlowDecision.REPORT_FATAL_ERROR,
            PurchaseFlowPolicy.decide(PurchaseFlowSignal.FATAL_ERROR, false),
        )
    }
}
