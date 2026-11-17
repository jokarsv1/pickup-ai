package ai.pickup.app.data

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "pickup")

/** Everything the app keeps on the device: session tokens and a cached copy of the screening policy. */
class SessionStore(private val context: Context) {
    private object Keys {
        val access = stringPreferencesKey("access_token")
        val refresh = stringPreferencesKey("refresh_token")
        val user = stringPreferencesKey("user_json")
        val serverUrl = stringPreferencesKey("server_url")
        val policy = stringPreferencesKey("policy_json")
        val line = stringPreferencesKey("line_json")
        val configuredSims = intPreferencesKey("configured_sims")
        val verifyUntil = longPreferencesKey("verify_until")
        val fcmToken = stringPreferencesKey("fcm_token")
        val onboardingStep = stringPreferencesKey("onboarding_step")
    }

    val accessToken: Flow<String?> = context.dataStore.data.map { it[Keys.access] }
    val userJson: Flow<String?> = context.dataStore.data.map { it[Keys.user] }
    val serverUrl: Flow<String?> = context.dataStore.data.map { it[Keys.serverUrl] }
    val policyJson: Flow<String?> = context.dataStore.data.map { it[Keys.policy] }
    val lineJson: Flow<String?> = context.dataStore.data.map { it[Keys.line] }
    val configuredSims: Flow<Int> = context.dataStore.data.map { it[Keys.configuredSims] ?: 0 }
    val onboardingStep: Flow<String?> = context.dataStore.data.map { it[Keys.onboardingStep] }

    suspend fun snapshot(): Preferences = context.dataStore.data.first()

    suspend fun access(): String? = snapshot()[Keys.access]
    suspend fun refresh(): String? = snapshot()[Keys.refresh]
    suspend fun server(): String? = snapshot()[Keys.serverUrl]
    suspend fun fcmToken(): String? = snapshot()[Keys.fcmToken]
    suspend fun verifyUntil(): Long = snapshot()[Keys.verifyUntil] ?: 0L
    suspend fun sims(): Int = snapshot()[Keys.configuredSims] ?: 0

    suspend fun saveTokens(access: String, refresh: String, userJson: String) {
        context.dataStore.edit {
            it[Keys.access] = access
            it[Keys.refresh] = refresh
            it[Keys.user] = userJson
        }
    }

    suspend fun saveUser(userJson: String) = context.dataStore.edit { it[Keys.user] = userJson }
    suspend fun saveServer(url: String?) = context.dataStore.edit { if (url.isNullOrBlank()) it.remove(Keys.serverUrl) else it[Keys.serverUrl] = url }
    suspend fun savePolicy(json: String) = context.dataStore.edit { it[Keys.policy] = json }
    suspend fun saveLine(json: String?) = context.dataStore.edit { if (json == null) it.remove(Keys.line) else it[Keys.line] = json }
    suspend fun saveConfiguredSims(count: Int) = context.dataStore.edit { it[Keys.configuredSims] = count }
    suspend fun saveVerifyUntil(epochMillis: Long) = context.dataStore.edit { it[Keys.verifyUntil] = epochMillis }
    suspend fun saveFcmToken(token: String) = context.dataStore.edit { it[Keys.fcmToken] = token }
    suspend fun saveOnboardingStep(step: String?) = context.dataStore.edit { if (step == null) it.remove(Keys.onboardingStep) else it[Keys.onboardingStep] = step }

    suspend fun clearSession() {
        context.dataStore.edit {
            val server = it[Keys.serverUrl]
            it.clear()
            if (server != null) it[Keys.serverUrl] = server
        }
    }
}
