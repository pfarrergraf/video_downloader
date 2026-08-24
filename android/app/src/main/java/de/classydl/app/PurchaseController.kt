package de.classydl.app

import android.app.Activity

/** Distribution-specific purchase implementation supplied by each flavor. */
interface PurchaseController {
    fun start()
    fun close()
    fun purchase(activity: Activity)
    fun restore()
    /**
     * Reconcile purchases already owned by the Play account without showing a
     * misleading "no purchase" message when none exists. This covers a
     * purchase that Play finishes after its purchase sheet has been dismissed.
     */
    fun refreshPurchases()
    fun statusJson(): String
}
