package de.classydl.app

import android.app.Activity
import android.content.Context
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import org.json.JSONObject

object PurchaseControllerFactory {
    fun create(context: Context, deliver: (String) -> Unit): PurchaseController =
        PlayPurchaseController(context.applicationContext, deliver)
}

private class PlayPurchaseController(
    context: Context,
    private val deliver: (String) -> Unit,
) : PurchaseController {
    private val entitlement = EntitlementStore(context)
    private val api = EntitlementApi(context, ::onServerResult)
    private var productDetails: ProductDetails? = null
    private var reconnecting = false
    private val pendingReadyActions = mutableListOf<() -> Unit>()

    private val billingClient = BillingClient.newBuilder(context)
        .setListener { result, purchases ->
            if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                purchases.orEmpty().forEach(::handlePurchase)
            } else {
                deliver(errorJson("billing_update_failed", result.debugMessage))
            }
        }
        .enablePendingPurchases(
            PendingPurchasesParams.newBuilder().enableOneTimeProducts().build(),
        )
        .enableAutoServiceReconnection()
        .build()

    override fun start() = connect { loadProduct() }

    override fun close() {
        api.close()
        billingClient.endConnection()
    }

    override fun purchase(activity: Activity) {
        val details = productDetails
        if (details == null) {
            connect {
                loadProduct { purchase(activity) }
            }
            return
        }
        val params = BillingFlowParams.ProductDetailsParams.newBuilder()
            .setProductDetails(details)
            .build()
        val result = billingClient.launchBillingFlow(
            activity,
            BillingFlowParams.newBuilder().setProductDetailsParamsList(listOf(params)).build(),
        )
        if (result.responseCode != BillingClient.BillingResponseCode.OK) {
            deliver(errorJson("billing_launch_failed", result.debugMessage))
        }
    }

    override fun restore() {
        connect {
            billingClient.queryPurchasesAsync(
                QueryPurchasesParams.newBuilder()
                    .setProductType(BillingClient.ProductType.INAPP)
                    .build(),
            ) { result, purchases ->
                if (result.responseCode != BillingClient.BillingResponseCode.OK) {
                    deliver(errorJson("restore_failed", result.debugMessage))
                } else if (purchases.isEmpty()) {
                    deliver(errorJson("no_purchase_found", ""))
                } else {
                    purchases.forEach(::handlePurchase)
                }
            }
        }
    }

    override fun statusJson(): String = entitlement.statusJson(billingAvailable = true)

    private fun handlePurchase(purchase: com.android.billingclient.api.Purchase) {
        if (BuildConfig.PLAY_PRODUCT_ID !in purchase.products) {
            deliver(errorJson("wrong_product", ""))
            return
        }
        when (purchase.purchaseState) {
            com.android.billingclient.api.Purchase.PurchaseState.PURCHASED ->
                api.verifyPurchase(purchase.purchaseToken, BuildConfig.PLAY_PRODUCT_ID)
            com.android.billingclient.api.Purchase.PurchaseState.PENDING ->
                deliver(errorJson("purchase_pending", ""))
            else -> deliver(errorJson("purchase_not_completed", ""))
        }
    }

    private fun onServerResult(result: JSONObject) {
        val licenseKey = result.optString("license_key", result.optString("licenseKey"))
        val active = result.optBoolean(
            "entitled",
            result.optBoolean("pro", result.optBoolean("active", false)),
        )
        if (result.optBoolean("ok") && active && licenseKey.isNotBlank()) {
            entitlement.recordVerified(licenseKey)
        }
        // A failed/revoked server result never extends the cached timestamp.
        // Explicit revocation clears even a still-valid offline cache.
        if (
            result.optBoolean("revoked") ||
            (result.optBoolean("ok") && !active && licenseKey == entitlement.licenseKey())
        ) entitlement.clear()
        result.put("pro", entitlement.isPro())
        result.put("licenseKey", entitlement.licenseKey() ?: JSONObject.NULL)
        result.put("billingAvailable", true)
        deliver(result.toString())
    }

    private fun loadProduct(after: (() -> Unit)? = null) {
        val product = QueryProductDetailsParams.Product.newBuilder()
            .setProductId(BuildConfig.PLAY_PRODUCT_ID)
            .setProductType(BillingClient.ProductType.INAPP)
            .build()
        billingClient.queryProductDetailsAsync(
            QueryProductDetailsParams.newBuilder().setProductList(listOf(product)).build(),
        ) { result, detailsResult ->
            productDetails = detailsResult.productDetailsList.firstOrNull()
            if (result.responseCode != BillingClient.BillingResponseCode.OK || productDetails == null) {
                deliver(errorJson("product_unavailable", result.debugMessage))
            } else {
                after?.invoke()
            }
        }
    }

    private fun connect(ready: () -> Unit) {
        if (billingClient.isReady) {
            ready()
            return
        }
        pendingReadyActions += ready
        if (reconnecting) return
        reconnecting = true
        billingClient.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(result: BillingResult) {
                reconnecting = false
                if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                    val actions = pendingReadyActions.toList()
                    pendingReadyActions.clear()
                    actions.forEach { it() }
                } else {
                    pendingReadyActions.clear()
                    deliver(errorJson("billing_unavailable", result.debugMessage))
                }
            }

            override fun onBillingServiceDisconnected() {
                reconnecting = false
            }
        })
    }

    private fun errorJson(code: String, detail: String): String = JSONObject()
        .put("ok", false)
        .put("error", code)
        .put("detail", detail)
        .put("billingAvailable", true)
        .put("pro", entitlement.isPro())
        .toString()
}
