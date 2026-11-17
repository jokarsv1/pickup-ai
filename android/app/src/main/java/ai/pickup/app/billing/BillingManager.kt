package ai.pickup.app.billing

import android.app.Activity
import android.content.Context
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.QueryProductDetailsParams
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

/** Google Play subscriptions (Play Billing Library 9). The backend verifies every purchase. */
class BillingManager(
    context: Context,
    private val scope: CoroutineScope,
    private val onPurchase: suspend (productId: String, token: String) -> Unit,
) {

    data class Product(val id: String, val title: String, val price: String, val details: ProductDetails, val offerToken: String)

    private val _products = MutableStateFlow<List<Product>>(emptyList())
    val products: StateFlow<List<Product>> = _products

    private val _status = MutableStateFlow<String?>(null)
    val status: StateFlow<String?> = _status

    private val listener = PurchasesUpdatedListener { result, purchases ->
        if (result.responseCode == BillingClient.BillingResponseCode.OK && purchases != null) {
            pendingPurchases = purchases
            scope.launch { processPending() }
        } else if (result.responseCode == BillingClient.BillingResponseCode.USER_CANCELED) {
            _status.value = null
        } else {
            _status.value = "Purchase didn't go through (${result.debugMessage})"
        }
    }

    @Volatile
    var pendingPurchases: List<Purchase> = emptyList()
        private set

    private val client: BillingClient = BillingClient.newBuilder(context)
        .setListener(listener)
        .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
        .enableAutoServiceReconnection()
        .build()

    suspend fun connect(): Boolean {
        if (client.isReady) return true
        return suspendCancellableCoroutine { cont ->
            client.startConnection(object : BillingClientStateListener {
                override fun onBillingSetupFinished(billingResult: BillingResult) {
                    if (cont.isActive) cont.resume(billingResult.responseCode == BillingClient.BillingResponseCode.OK)
                }

                override fun onBillingServiceDisconnected() {
                    if (cont.isActive) cont.resume(false)
                }
            })
        }
    }

    suspend fun loadProducts(productIds: List<String>) {
        if (productIds.isEmpty() || !connect()) {
            _status.value = "Google Play isn't available on this device"
            return
        }
        val params = QueryProductDetailsParams.newBuilder()
            .setProductList(
                productIds.map {
                    QueryProductDetailsParams.Product.newBuilder().setProductId(it).setProductType(BillingClient.ProductType.SUBS).build()
                }
            )
            .build()
        val details: List<ProductDetails> = suspendCancellableCoroutine { cont ->
            client.queryProductDetailsAsync(params) { result, queryResult ->
                val list = if (result.responseCode == BillingClient.BillingResponseCode.OK) queryResult.productDetailsList else emptyList()
                if (cont.isActive) cont.resume(list)
            }
        }
        _products.value = details.mapNotNull { pd ->
            val offer = pd.subscriptionOfferDetails?.firstOrNull() ?: return@mapNotNull null
            val price = offer.pricingPhases.pricingPhaseList.lastOrNull()?.formattedPrice ?: return@mapNotNull null
            Product(pd.productId, pd.name, price, pd, offer.offerToken)
        }
        if (_products.value.isEmpty()) _status.value = "Plans aren't available yet"
    }

    fun buy(activity: Activity, product: Product) {
        val params = BillingFlowParams.newBuilder()
            .setProductDetailsParamsList(
                listOf(BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(product.details).setOfferToken(product.offerToken).build())
            )
            .build()
        client.launchBillingFlow(activity, params)
    }

    /** Send new purchases to the backend, then acknowledge them (Play refunds unacknowledged ones). */
    suspend fun processPending() {
        val purchases = pendingPurchases
        pendingPurchases = emptyList()
        for (purchase in purchases) {
            if (purchase.purchaseState != Purchase.PurchaseState.PURCHASED) continue
            val productId = purchase.products.firstOrNull() ?: continue
            runCatching { onPurchase(productId, purchase.purchaseToken) }.onFailure { _status.value = it.message; return }
            if (!purchase.isAcknowledged) {
                val ack = AcknowledgePurchaseParams.newBuilder().setPurchaseToken(purchase.purchaseToken).build()
                suspendCancellableCoroutine { cont -> client.acknowledgePurchase(ack) { if (cont.isActive) cont.resume(Unit) } }
            }
            _status.value = "Welcome to Pickup Pro"
        }
    }

    fun close() = client.endConnection()
}
