package ai.pickup.app.data

import ai.pickup.app.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.serializer
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import java.util.concurrent.TimeUnit

class ApiException(val status: Int, message: String) : Exception(message)

val AppJson = Json {
    ignoreUnknownKeys = true
    explicitNulls = false
    encodeDefaults = true
    coerceInputValues = true
}

/** Small JSON-over-HTTPS client with automatic access-token refresh. */
class ApiClient(private val store: SessionStore) {
    val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS) // the assistant chat can take a while
        .writeTimeout(30, TimeUnit.SECONDS)
        .pingInterval(20, TimeUnit.SECONDS)
        .build()

    private val refreshLock = Mutex()
    private val jsonType = "application/json".toMediaType()

    var onSignedOut: (suspend () -> Unit)? = null

    suspend fun baseUrl(): String = (store.server() ?: BuildConfig.API_BASE_URL).trimEnd('/')

    suspend fun <T> call(method: String, path: String, body: String?, out: KSerializer<T>, auth: Boolean = true): T =
        withContext(Dispatchers.IO) {
            var response = execute(method, path, body, auth)
            if (response.code == 401 && auth) {
                response.close()
                if (refreshTokens()) {
                    response = execute(method, path, body, auth)
                } else {
                    onSignedOut?.invoke()
                    throw ApiException(401, "Your session expired. Sign in again.")
                }
            }
            response.use { resp ->
                val text = resp.body.string()
                if (!resp.isSuccessful) throw ApiException(resp.code, errorMessage(resp.code, text))
                if (text.isBlank() || out.descriptor.serialName == "kotlin.Unit") {
                    @Suppress("UNCHECKED_CAST")
                    return@withContext Unit as T
                }
                AppJson.decodeFromString(out, text)
            }
        }

    private suspend fun execute(method: String, path: String, body: String?, auth: Boolean): Response {
        val builder = Request.Builder().url(baseUrl() + path)
        if (auth) store.access()?.let { builder.header("Authorization", "Bearer $it") }
        val requestBody = body?.toRequestBody(jsonType) ?: if (method == "GET" || method == "DELETE") null else "".toRequestBody(jsonType)
        builder.method(method, requestBody)
        return try {
            http.newCall(builder.build()).execute()
        } catch (e: IOException) {
            throw ApiException(0, "Can't reach Pickup. Check your internet connection.")
        }
    }

    private suspend fun refreshTokens(): Boolean = refreshLock.withLock {
        val refresh = store.refresh() ?: return false
        val payload = AppJson.encodeToString(RefreshBody.serializer(), RefreshBody(refresh))
        val response = execute("POST", "/v1/auth/refresh", payload, auth = false)
        response.use { resp ->
            if (!resp.isSuccessful) return false
            val tokens = AppJson.decodeFromString(Tokens.serializer(), resp.body.string())
            store.saveTokens(tokens.accessToken, tokens.refreshToken, AppJson.encodeToString(UserDto.serializer(), tokens.user))
            return true
        }
    }

    private fun errorMessage(code: Int, text: String): String {
        val detail = runCatching { AppJson.parseToJsonElement(text).jsonObject["detail"] }.getOrNull()
        val message = when (detail) {
            is JsonPrimitive -> detail.contentOrNull
            is JsonArray -> detail.firstOrNull()?.let { runCatching { it.jsonObject["msg"]?.jsonPrimitive?.contentOrNull }.getOrNull() }
            else -> null
        }
        return message ?: when (code) {
            402 -> "This is part of Pickup Pro."
            404 -> "Not found."
            in 500..599 -> "Pickup is having trouble right now. Try again in a minute."
            else -> "Something went wrong ($code)."
        }
    }

    suspend inline fun <reified T> get(path: String): T = call("GET", path, null, serializer<T>())

    suspend inline fun <reified B, reified T> post(path: String, body: B, auth: Boolean = true): T =
        call("POST", path, AppJson.encodeToString(serializer<B>(), body), serializer<T>(), auth)

    suspend inline fun <reified T> postEmpty(path: String): T = call("POST", path, null, serializer<T>())

    suspend inline fun <reified B, reified T> patch(path: String, body: B): T =
        call("PATCH", path, AppJson.encodeToString(serializer<B>(), body), serializer<T>())

    suspend inline fun <reified B, reified T> put(path: String, body: B): T =
        call("PUT", path, AppJson.encodeToString(serializer<B>(), body), serializer<T>())

    suspend fun delete(path: String) {
        call("DELETE", path, null, serializer<Unit>())
    }
}
