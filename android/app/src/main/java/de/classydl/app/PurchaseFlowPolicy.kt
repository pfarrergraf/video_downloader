package de.classydl.app

/** Billing-library results translated into product-level purchase signals. */
enum class PurchaseFlowSignal {
    OK,
    USER_CANCELLED,
    ITEM_ALREADY_OWNED,
    RETRYABLE_ERROR,
    FATAL_ERROR,
}

enum class PurchaseFlowDecision {
    PROCESS_PURCHASES,
    RECONCILE_OWNED,
    REPORT_CANCELLED,
    REPORT_RETRYABLE_ERROR,
    REPORT_INCOMPLETE,
    REPORT_FATAL_ERROR,
}

/** Pure policy kept outside BillingClient so every transition is unit-testable. */
object PurchaseFlowPolicy {
    fun decide(signal: PurchaseFlowSignal, hasRelevantPurchase: Boolean): PurchaseFlowDecision =
        when (signal) {
            PurchaseFlowSignal.OK -> if (hasRelevantPurchase) {
                PurchaseFlowDecision.PROCESS_PURCHASES
            } else {
                PurchaseFlowDecision.REPORT_INCOMPLETE
            }
            PurchaseFlowSignal.ITEM_ALREADY_OWNED -> PurchaseFlowDecision.RECONCILE_OWNED
            PurchaseFlowSignal.USER_CANCELLED -> PurchaseFlowDecision.REPORT_CANCELLED
            PurchaseFlowSignal.RETRYABLE_ERROR -> PurchaseFlowDecision.REPORT_RETRYABLE_ERROR
            PurchaseFlowSignal.FATAL_ERROR -> PurchaseFlowDecision.REPORT_FATAL_ERROR
        }
}
