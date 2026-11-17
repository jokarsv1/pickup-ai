package ai.pickup.app

import ai.pickup.app.notify.CallNotifications
import ai.pickup.app.ui.call.CallDetailScreen
import ai.pickup.app.ui.call.CallViewModel
import ai.pickup.app.ui.call.LiveCallScreen
import ai.pickup.app.ui.chat.ChatScreen
import ai.pickup.app.ui.chat.ChatViewModel
import ai.pickup.app.ui.home.HomeScreen
import ai.pickup.app.ui.home.HomeViewModel
import ai.pickup.app.ui.onboarding.OnboardingRoute
import ai.pickup.app.ui.onboarding.OnboardingViewModel
import ai.pickup.app.ui.onboarding.Step
import ai.pickup.app.ui.settings.InstructionsScreen
import ai.pickup.app.ui.settings.PlanScreen
import ai.pickup.app.ui.settings.SettingsScreen
import ai.pickup.app.ui.settings.SettingsViewModel
import ai.pickup.app.ui.theme.PickupTheme
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import kotlinx.coroutines.flow.combine

class MainActivity : ComponentActivity() {
    /** "live:<callId>", "call:<callId>" or "home", from a tapped notification. */
    private val deepLink = mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)
        deepLink.value = parse(intent)
        val graph = (application as PickupApp).graph
        setContent {
            PickupTheme {
                AppRoot(graph, deepLink.value) { deepLink.value = null }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        deepLink.value = parse(intent)
    }

    private fun parse(intent: Intent?): String? {
        val screen = intent?.getStringExtra(CallNotifications.EXTRA_OPEN) ?: return null
        val callId = intent.getStringExtra(CallNotifications.EXTRA_CALL_ID)
        return if (callId != null) "$screen:$callId" else screen
    }
}

private object Routes {
    const val ONBOARDING = "onboarding"
    const val SETUP = "setup"
    const val HOME = "home"
    const val CHAT = "chat"
    const val SETTINGS = "settings"
    const val INSTRUCTIONS = "instructions"
    const val PLAN = "plan"
    const val CALL = "call/{id}"
    const val LIVE = "live/{id}"
    fun call(id: String) = "call/$id"
    fun live(id: String) = "live/$id"
}

private enum class Gate { Loading, Onboarding, Main }

@Composable
private fun AppRoot(graph: AppGraph, deepLink: String?, onDeepLinkHandled: () -> Unit) {
    val gateFlow = androidx.compose.runtime.remember {
        combine(graph.repository.signedIn, graph.repository.user) { signedIn, user ->
            if (signedIn && user?.onboardingCompleted == true) Gate.Main else Gate.Onboarding
        }
    }
    val gate by gateFlow.collectAsStateWithLifecycle(initialValue = Gate.Loading)
    when (gate) {
        Gate.Loading -> Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background), contentAlignment = Alignment.Center) {
            CircularProgressIndicator()
        }
        // A fresh navigation stack whenever the user signs in, finishes setup or signs out.
        else -> androidx.compose.runtime.key(gate) {
            AppNav(graph, startAtMain = gate == Gate.Main, deepLink = deepLink, onDeepLinkHandled = onDeepLinkHandled)
        }
    }
}

@Composable
private fun AppNav(graph: AppGraph, startAtMain: Boolean, deepLink: String?, onDeepLinkHandled: () -> Unit) {
    val nav = rememberNavController()
    val backStack by nav.currentBackStackEntryAsState()
    val route = backStack?.destination?.route
    val showBar = route in setOf(Routes.HOME, Routes.CHAT, Routes.SETTINGS)

    LaunchedEffect(deepLink, startAtMain) {
        if (deepLink == null || !startAtMain) return@LaunchedEffect
        val parts = deepLink.split(":", limit = 2)
        when (parts[0]) {
            "live" -> parts.getOrNull(1)?.let { nav.navigate(Routes.live(it)) }
            "call" -> parts.getOrNull(1)?.let { nav.navigate(Routes.call(it)) }
        }
        onDeepLinkHandled()
    }

    Scaffold(
        bottomBar = {
            if (showBar) {
                NavigationBar {
                    NavItem(nav, route, Routes.HOME, "Calls") { Icon(Icons.Filled.Home, null) }
                    NavItem(nav, route, Routes.CHAT, "Ask Pickup") { Icon(Icons.Filled.AutoAwesome, null) }
                    NavItem(nav, route, Routes.SETTINGS, "Settings") { Icon(Icons.Filled.Settings, null) }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = nav,
            startDestination = if (startAtMain) Routes.HOME else Routes.ONBOARDING,
            modifier = Modifier.padding(bottom = if (showBar) padding.calculateBottomPadding() else androidx.compose.ui.unit.Dp(0f)).background(MaterialTheme.colorScheme.background),
        ) {
            composable(Routes.ONBOARDING) {
                val vm = viewModel { OnboardingViewModel(graph) }
                // Finishing flips the sign-in gate, which rebuilds navigation at Home.
                OnboardingRoute(vm) {}
            }
            composable(Routes.SETUP) {
                val vm = viewModel(key = "setup") { OnboardingViewModel(graph, forcedStep = Step.Permissions) }
                OnboardingRoute(vm) { nav.popBackStack() }
            }
            composable(Routes.HOME) {
                val vm = viewModel { HomeViewModel(graph) }
                HomeScreen(
                    vm,
                    onOpenCall = { nav.navigate(Routes.call(it)) },
                    onOpenLive = { nav.navigate(Routes.live(it)) },
                    onFixSetup = { nav.navigate(Routes.SETUP) },
                )
            }
            composable(Routes.CHAT) {
                val vm = viewModel { ChatViewModel(graph) }
                ChatScreen(vm)
            }
            composable(Routes.SETTINGS) {
                val vm = viewModel { SettingsViewModel(graph) }
                SettingsScreen(
                    vm,
                    onOpenInstructions = { nav.navigate(Routes.INSTRUCTIONS) },
                    onOpenPlan = { nav.navigate(Routes.PLAN) },
                    onRerunSetup = { nav.navigate(Routes.SETUP) },
                    onSignedOut = { /* the gate switches back to onboarding */ },
                )
            }
            composable(Routes.INSTRUCTIONS) {
                val vm = viewModel { SettingsViewModel(graph) }
                InstructionsScreen(vm, onBack = { nav.popBackStack() })
            }
            composable(Routes.PLAN) {
                val vm = viewModel { SettingsViewModel(graph) }
                val products by androidx.compose.runtime.produceState(initialValue = emptyList<String>()) {
                    value = runCatching { graph.repository.config().playProducts }.getOrDefault(emptyList())
                }
                PlanScreen(vm, products, onBack = { nav.popBackStack() })
            }
            composable(Routes.CALL) { entry ->
                val id = entry.arguments?.getString("id") ?: return@composable
                val vm = viewModel(key = "call-$id") { CallViewModel(graph, id) }
                CallDetailScreen(vm, onBack = { nav.popBackStack() }, onOpenLive = { nav.navigate(Routes.live(it)) { popUpTo(Routes.CALL) { inclusive = true } } })
            }
            composable(Routes.LIVE) { entry ->
                val id = entry.arguments?.getString("id") ?: return@composable
                val vm = viewModel(key = "live-$id") { CallViewModel(graph, id) }
                LiveCallScreen(vm, onBack = { nav.popBackStack() }, onOpenDetail = { nav.navigate(Routes.call(it)) { popUpTo(Routes.LIVE) { inclusive = true } } })
            }
        }
    }
}

@Composable
private fun androidx.compose.foundation.layout.RowScope.NavItem(
    nav: NavHostController,
    current: String?,
    target: String,
    label: String,
    icon: @Composable () -> Unit,
) {
    NavigationBarItem(
        selected = current == target,
        onClick = {
            if (current != target) {
                nav.navigate(target) {
                    popUpTo(Routes.HOME) { saveState = true }
                    launchSingleTop = true
                    restoreState = true
                }
            }
        },
        icon = icon,
        label = { Text(label) },
    )
}
