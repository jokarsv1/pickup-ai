package ai.pickup.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// Brand: deep "ink blue" for trust, saffron for the live state (India-first product).
private val Ink = Color(0xFF2747C9)
private val InkLight = Color(0xFFB8C6FF)
private val Saffron = Color(0xFFF08C00)
private val Paper = Color(0xFFF8F6F1)
private val Night = Color(0xFF111318)

private val LightColors = lightColorScheme(
    primary = Ink,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDDE3FF),
    onPrimaryContainer = Color(0xFF0B1C66),
    secondary = Color(0xFF4A5A7A),
    secondaryContainer = Color(0xFFE2E7F3),
    onSecondaryContainer = Color(0xFF1B2638),
    tertiary = Saffron,
    tertiaryContainer = Color(0xFFFFE3C2),
    onTertiaryContainer = Color(0xFF4A2800),
    background = Paper,
    onBackground = Color(0xFF1A1C22),
    surface = Paper,
    onSurface = Color(0xFF1A1C22),
    surfaceVariant = Color(0xFFE9E6DE),
    onSurfaceVariant = Color(0xFF4A4C55),
    surfaceContainerLowest = Color.White,
    surfaceContainerLow = Color(0xFFF3F1EB),
    surfaceContainer = Color(0xFFEFECE5),
    surfaceContainerHigh = Color(0xFFE9E6DF),
    outline = Color(0xFF7A7C86),
    outlineVariant = Color(0xFFD3D0C8),
    error = Color(0xFFBA1A1A),
)

private val DarkColors = darkColorScheme(
    primary = InkLight,
    onPrimary = Color(0xFF0B1C66),
    primaryContainer = Color(0xFF233A9E),
    onPrimaryContainer = Color(0xFFDDE3FF),
    secondary = Color(0xFFB9C6E2),
    secondaryContainer = Color(0xFF34425C),
    onSecondaryContainer = Color(0xFFDCE4F7),
    tertiary = Color(0xFFFFB866),
    tertiaryContainer = Color(0xFF5E3700),
    onTertiaryContainer = Color(0xFFFFDDB8),
    background = Night,
    onBackground = Color(0xFFE3E2E8),
    surface = Night,
    onSurface = Color(0xFFE3E2E8),
    surfaceVariant = Color(0xFF2B2E36),
    onSurfaceVariant = Color(0xFFC4C6D0),
    surfaceContainerLowest = Color(0xFF0C0E12),
    surfaceContainerLow = Color(0xFF191B21),
    surfaceContainer = Color(0xFF1D2026),
    surfaceContainerHigh = Color(0xFF272A31),
    outline = Color(0xFF8E909A),
    outlineVariant = Color(0xFF3F424B),
)

/** Colors that carry meaning beyond the Material roles. */
@Immutable
data class PickupColors(val live: Color, val success: Color, val warning: Color, val spam: Color)

val LocalPickupColors = staticCompositionLocalOf { PickupColors(Saffron, Color(0xFF2F9E44), Color(0xFFE67700), Color(0xFFC92A2A)) }

private val PickupTypography = Typography(
    displaySmall = TextStyle(fontWeight = FontWeight.Bold, fontSize = 34.sp, lineHeight = 40.sp, letterSpacing = (-0.5).sp),
    headlineMedium = TextStyle(fontWeight = FontWeight.Bold, fontSize = 28.sp, lineHeight = 34.sp, letterSpacing = (-0.3).sp),
    headlineSmall = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 22.sp, lineHeight = 28.sp),
    titleLarge = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 20.sp, lineHeight = 26.sp),
    titleMedium = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 16.sp, lineHeight = 22.sp),
    titleSmall = TextStyle(fontWeight = FontWeight.Medium, fontSize = 14.sp, lineHeight = 20.sp),
    bodyLarge = TextStyle(fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 20.sp),
    bodySmall = TextStyle(fontSize = 12.sp, lineHeight = 16.sp),
    labelLarge = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 14.sp, lineHeight = 20.sp),
    labelMedium = TextStyle(fontWeight = FontWeight.Medium, fontSize = 12.sp, lineHeight = 16.sp, letterSpacing = 0.3.sp),
)

private val PickupShapes = Shapes(
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(24.dp),
)

@Composable
fun PickupTheme(darkTheme: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = PickupTypography,
        shapes = PickupShapes,
        content = content,
    )
}
