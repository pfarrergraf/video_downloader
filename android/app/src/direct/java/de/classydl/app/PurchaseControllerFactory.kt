package de.classydl.app

import android.app.Activity
import android.content.Context

object PurchaseControllerFactory {
    fun create(context: Context, deliver: (String) -> Unit): PurchaseController =
        DirectPurchaseController(EntitlementStore(context), deliver)
}

private class DirectPurchaseController(
    private val entitlement: EntitlementStore,
    private val deliver: (String) -> Unit,
) : PurchaseController {
    override fun start() = Unit
    override fun close() = Unit
    override fun purchase(activity: Activity) {
        deliver("""{"ok":false,"error":"billing_unavailable","billingAvailable":false}""")
    }
    override fun restore() {
        deliver("""{"ok":false,"error":"billing_unavailable","billingAvailable":false}""")
    }
    override fun statusJson(): String = entitlement.statusJson(billingAvailable = false)
}
