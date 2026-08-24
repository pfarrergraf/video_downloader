package de.classydl.app

import android.app.Activity
import android.content.Context
import android.os.Handler
import android.os.Looper
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.ConsumeParams
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import org.json.JSONObject
import java.security.MessageDigest

object PurchaseControllerFactory {
    fun create(context: Context, deliver: (String) -> Unit): PurchaseController =
        PlayPurchaseController(context.applicationContext, deliver)
}

private class PlayPurchaseController(
    context: Context,
    private val deliver: (String) -> Unit,
) : PurchaseController {
    private val appContext = context.applicationContext
    private val entitlement = EntitlementStore(context)
    private val purchaseAccountId = MessageDigest.getInstance("SHA-256")
        .digest(InstallIdentity.getOrCreate(context).toByteArray(Charsets.UTF_8))
        .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
    private val api = EntitlementApi(context, ::onServerResult)
    private val mainHandler = Handler(Looper.getMainLooper())
    private var reconnecting = false
    @Volatile private var purchaseFlowInProgress = false
    private val pendingReadyActions = mutableListOf<Pair<Boolean, () -> Unit>>()

    private val billingClient = BillingClient.newBuilder(context)
        .setListener { result, purchases -> handleBillingUpdate(result, purchases) }
        .enablePendingPurchases(
            PendingPurchasesParams.newBuilder().enableOneTimeProducts().build(),
        )
        .enableAutoServiceReconnection()
        .build()

    override fun start() = connect { /* onResume performs the owned-purchase sync */ }

    override fun close() {
        api.close()
        billingClient.endConnection()
    }

    override fun purchase(activity: Activity) {
        if (purchaseFlowInProgress) {
            deliver(errorJson("purchase_in_progress", ""))
            return
        }
        if (entitlement.isPro()) {
            deliver(entitlement.statusJson(billingAvailable = true).let(::successJson))
            return
        }
        purchaseFlowInProgress = true
        connect {
            loadProduct { details, offerToken ->
                launchPurchase(activity, details, offerToken)
            }
        }
    }

    override fun restore() {
        if (purchaseFlowInProgress) {
            deliver(errorJson("purchase_in_progress", ""))
            return
        }
        purchaseFlowInProgress = true
        syncPurchases(reportMissingPurchase = true, remainingEmptyRetries = 2, event = "restore")
    }

    override fun refreshPurchases() {
        // Returning from Play is also the recovery path for a callback which
        // was lost because the process or Billing connection was interrupted.
        purchaseFlowInProgress = false
        syncPurchases(reportMissingPurchase = false, event = "sync")
    }

    override fun statusJson(): String = entitlement.statusJson(billingAvailable = true)

    private fun launchPurchase(activity: Activity, details: ProductDetails, offerToken: String) {
        val productParams = BillingFlowParams.ProductDetailsParams.newBuilder()
            .setProductDetails(details)
            .setOfferToken(offerToken)
            .build()
        val result = billingClient.launchBillingFlow(
            activity,
            BillingFlowParams.newBuilder()
                .setProductDetailsParamsList(listOf(productParams))
                .setObfuscatedAccountId(purchaseAccountId)
                .build(),
        )
        // OK only means that Play displayed its purchase sheet. The actual
        // purchase result arrives later through handleBillingUpdate().
        if (result.responseCode != BillingClient.BillingResponseCode.OK) {
            handleBillingUpdate(result, null)
        }
    }

    private fun handleBillingUpdate(result: BillingResult, purchases: List<Purchase>?) {
        val relevant = relevantPurchases(purchases.orEmpty())
        when (PurchaseFlowPolicy.decide(signalFor(result.responseCode), relevant.isNotEmpty())) {
            PurchaseFlowDecision.PROCESS_PURCHASES -> {
                relevant.forEach { handlePurchase(it, "purchase") }
            }
            PurchaseFlowDecision.RECONCILE_OWNED -> {
                deliver(errorJson("restoring_purchase", result.debugMessage))
                // Play can report ITEM_ALREADY_OWNED just before its local
                // purchase cache becomes visible. Retry only the query; never
                // open another checkout for this state.
                syncPurchases(reportMissingPurchase = true, remainingEmptyRetries = 2, event = "purchase")
            }
            PurchaseFlowDecision.REPORT_CANCELLED -> {
                purchaseFlowInProgress = false
                deliver(errorJson("purchase_cancelled", result.debugMessage))
            }
            PurchaseFlowDecision.REPORT_RETRYABLE_ERROR -> {
                purchaseFlowInProgress = false
                deliver(errorJson("billing_temporary_error", result.debugMessage))
            }
            PurchaseFlowDecision.REPORT_INCOMPLETE -> {
                purchaseFlowInProgress = false
                deliver(errorJson("purchase_not_completed", result.debugMessage))
            }
            PurchaseFlowDecision.REPORT_FATAL_ERROR -> {
                purchaseFlowInProgress = false
                deliver(errorJson("billing_update_failed", result.debugMessage))
            }
        }
    }

    private fun signalFor(responseCode: Int): PurchaseFlowSignal = when (responseCode) {
        BillingClient.BillingResponseCode.OK -> PurchaseFlowSignal.OK
        BillingClient.BillingResponseCode.USER_CANCELED -> PurchaseFlowSignal.USER_CANCELLED
        BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED -> PurchaseFlowSignal.ITEM_ALREADY_OWNED
        BillingClient.BillingResponseCode.NETWORK_ERROR,
        BillingClient.BillingResponseCode.SERVICE_DISCONNECTED,
        BillingClient.BillingResponseCode.SERVICE_UNAVAILABLE,
        BillingClient.BillingResponseCode.BILLING_UNAVAILABLE -> PurchaseFlowSignal.RETRYABLE_ERROR
        else -> PurchaseFlowSignal.FATAL_ERROR
    }

    private fun syncPurchases(
        reportMissingPurchase: Boolean,
        remainingEmptyRetries: Int = 0,
        event: String,
    ) {
        connect(reportErrors = reportMissingPurchase) {
            queryOwnedPurchases(
                onResult = { purchases ->
                    if (purchases.isEmpty() && remainingEmptyRetries > 0) {
                        mainHandler.postDelayed(
                            {
                                syncPurchases(
                                    reportMissingPurchase,
                                    remainingEmptyRetries - 1,
                                    event,
                                )
                            },
                            500L,
                        )
                    } else if (purchases.isEmpty() && reportMissingPurchase) {
                        purchaseFlowInProgress = false
                        deliver(errorJson("no_purchase_found", ""))
                    } else {
                        purchases.forEach { handlePurchase(it, event) }
                    }
                },
                onError = { result ->
                    // A foreground resume can occur while Play reconnects. Do
                    // not turn a silent reconciliation into a false error.
                    purchaseFlowInProgress = false
                    if (reportMissingPurchase) {
                        deliver(errorJson("restore_failed", result.debugMessage))
                    }
                },
            )
        }
    }

    private fun queryOwnedPurchases(
        onResult: (List<Purchase>) -> Unit,
        onError: (BillingResult) -> Unit,
    ) {
        billingClient.queryPurchasesAsync(
            QueryPurchasesParams.newBuilder()
                .setProductType(BillingClient.ProductType.INAPP)
                .build(),
        ) { result, purchases ->
            if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                onResult(relevantPurchases(purchases))
            } else {
                onError(result)
            }
        }
    }

    private fun relevantPurchases(purchases: List<Purchase>): List<Purchase> = purchases
        .filter { BuildConfig.PLAY_PRODUCT_ID in it.products }
        .distinctBy { it.purchaseToken }

    private fun handlePurchase(purchase: Purchase, event: String) {
        when (purchase.purchaseState) {
            Purchase.PurchaseState.PURCHASED -> {
                api.verifyPurchase(purchase.purchaseToken, BuildConfig.PLAY_PRODUCT_ID, event)
            }
            Purchase.PurchaseState.PENDING -> {
                purchaseFlowInProgress = false
                deliver(errorJson("purchase_pending", ""))
            }
            else -> {
                purchaseFlowInProgress = false
                deliver(errorJson("purchase_not_completed", ""))
            }
        }
    }

    private fun onServerResult(result: JSONObject) {
        purchaseFlowInProgress = false
        val verifiedToken = result.optString("_purchase_token").takeIf { it.isNotBlank() }
        // Purchase tokens are backend credentials. They are attached only
        // inside the native callback so parallel verification stays bound to
        // the correct token, and removed before anything reaches WebView JS.
        result.remove("_purchase_token")
        val licenseKey = result.optString("license_key", result.optString("licenseKey"))
        val active = result.optBoolean(
            "entitled",
            result.optBoolean("pro", result.optBoolean("active", false)),
        )
        if (result.optBoolean("ok") && active && licenseKey.isNotBlank()) {
            entitlement.recordVerified(licenseKey)
            EntitlementCoordinator.recordVerified(appContext, licenseKey)
            EntitlementCoordinator.applyDesiredAsync(appContext)
            verifiedToken?.let(api::confirmPurchaseDelivered)
        }
        // Failed or unknown server results never destroy an existing paid
        // entitlement. Only an explicit, authenticated revocation does.
        if (result.optBoolean("revoked")) {
            entitlement.clear()
            EntitlementCoordinator.recordRevoked(appContext)
            EntitlementCoordinator.applyDesiredAsync(appContext)
            verifiedToken?.let(::consumeRevokedPurchase)
        }
        result.put("pro", entitlement.isPro())
        result.put("licenseKey", entitlement.licenseKey() ?: JSONObject.NULL)
        result.put("billingAvailable", true)
        deliver(result.toString())
    }

    private fun consumeRevokedPurchase(token: String) {
        billingClient.consumeAsync(
            ConsumeParams.newBuilder().setPurchaseToken(token).build(),
        ) { result, _ ->
            if (
                result.responseCode != BillingClient.BillingResponseCode.OK &&
                result.responseCode != BillingClient.BillingResponseCode.ITEM_NOT_OWNED
            ) {
                android.util.Log.w(
                    "ClassyDL",
                    "Could not clear a server-revoked Play purchase: ${result.responseCode}",
                )
            }
        }
    }

    private fun loadProduct(after: (ProductDetails, String) -> Unit) {
        val product = QueryProductDetailsParams.Product.newBuilder()
            .setProductId(BuildConfig.PLAY_PRODUCT_ID)
            .setProductType(BillingClient.ProductType.INAPP)
            .build()
        billingClient.queryProductDetailsAsync(
            QueryProductDetailsParams.newBuilder().setProductList(listOf(product)).build(),
        ) { result, detailsResult ->
            val details = detailsResult.productDetailsList
                .firstOrNull { it.productId == BuildConfig.PLAY_PRODUCT_ID }
            val offerToken = details
                ?.oneTimePurchaseOfferDetailsList
                ?.firstOrNull()
                ?.offerToken
            if (
                result.responseCode != BillingClient.BillingResponseCode.OK ||
                details == null ||
                offerToken == null
            ) {
                purchaseFlowInProgress = false
                deliver(errorJson("product_unavailable", result.debugMessage))
            } else {
                after(details, offerToken)
            }
        }
    }

    private fun connect(reportErrors: Boolean = true, ready: () -> Unit) {
        if (billingClient.isReady) {
            ready()
            return
        }
        pendingReadyActions += reportErrors to ready
        if (reconnecting) return
        reconnecting = true
        billingClient.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(result: BillingResult) {
                reconnecting = false
                if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                    val actions = pendingReadyActions.toList()
                    pendingReadyActions.clear()
                    actions.forEach { (_, action) -> action() }
                } else {
                    val shouldReport = pendingReadyActions.any { (report, _) -> report }
                    pendingReadyActions.clear()
                    purchaseFlowInProgress = false
                    if (shouldReport) deliver(errorJson("billing_unavailable", result.debugMessage))
                }
            }

            override fun onBillingServiceDisconnected() {
                reconnecting = false
                if (pendingReadyActions.isNotEmpty()) {
                    val shouldReport = pendingReadyActions.any { (report, _) -> report }
                    pendingReadyActions.clear()
                    purchaseFlowInProgress = false
                    if (shouldReport) deliver(errorJson("billing_temporary_error", "service disconnected"))
                }
            }
        })
    }

    private fun successJson(statusJson: String): String = JSONObject(statusJson)
        .put("ok", true)
        .toString()

    private fun errorJson(code: String, detail: String): String = JSONObject()
        .put("ok", false)
        .put("error", code)
        .put("detail", detail)
        .put("billingAvailable", true)
        .put("pro", entitlement.isPro())
        .toString()
}
