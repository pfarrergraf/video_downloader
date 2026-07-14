package de.classydl.app

import android.app.Activity

/** Distribution-specific purchase implementation supplied by each flavor. */
interface PurchaseController {
    fun start()
    fun close()
    fun purchase(activity: Activity)
    fun restore()
    fun statusJson(): String
}
