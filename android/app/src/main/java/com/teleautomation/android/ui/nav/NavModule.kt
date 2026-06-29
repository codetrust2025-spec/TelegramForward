package com.teleautomation.android.ui.nav

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ListAlt
import androidx.compose.material.icons.filled.AdminPanelSettings
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Handyman
import androidx.compose.material.icons.filled.Inbox
import androidx.compose.material.icons.filled.ManageAccounts
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Today
import androidx.compose.ui.graphics.vector.ImageVector
import com.teleautomation.android.core.Module
import com.teleautomation.android.core.RoleModuleAccess
import com.teleautomation.android.data.api.Role

/**
 * UI metadata (stable route, label, icon) for each navigable [Module].
 *
 * The pure access/role logic lives in [RoleModuleAccess] (in `core`, no UI deps);
 * this enum is the UI-layer presentation mapping consumed by [NavScaffold] to
 * build the `NavHost` routes, the bottom navigation bar, and the drawer.
 */
enum class NavModule(
    val module: Module,
    val route: String,
    val label: String,
    val icon: ImageVector,
) {
    DASHBOARD(Module.Dashboard, "dashboard", "Dashboard", Icons.Filled.Dashboard),
    INBOX(Module.Inbox, "inbox", "Inbox", Icons.Filled.Inbox),
    ACCOUNTS(Module.Accounts, "accounts", "Accounts", Icons.Filled.ManageAccounts),
    CANDIDATES(Module.Candidates, "candidates", "Candidates", Icons.Filled.People),
    DAILY_OPS(Module.DailyOps, "daily_ops", "Daily Ops", Icons.Filled.Today),
    DATA_ROOM(Module.DataRoom, "data_room", "Data Room", Icons.Filled.Folder),
    ADMIN(Module.Admin, "admin", "Admin", Icons.Filled.AdminPanelSettings),
    LOGS(Module.Logs, "logs", "Logs", Icons.AutoMirrored.Filled.ListAlt),
    HANDLER_KIT(Module.HandlerKit, "handler_kit", "Handler Kit", Icons.Filled.Handyman),
    ;

    companion object {
        /** The [NavModule] presenting [module]. */
        fun forModule(module: Module): NavModule = entries.first { it.module == module }

        /** The [NavModule] for a `NavHost` [route], or `null` for an unknown route. */
        fun forRoute(route: String?): NavModule? = entries.firstOrNull { it.route == route }
    }
}

/**
 * The bottom-nav / drawer split for a role's navigable modules (R5.2, R24.2).
 *
 * @param bottom the primary destinations shown in the bottom navigation bar
 *   (3–5 entries, including a "More" entry when [showMore] is true).
 * @param drawer the remaining authorized destinations shown in the navigation
 *   drawer; empty when everything fits in the bottom bar.
 * @param showMore whether the bottom bar carries a "More" entry that opens the
 *   drawer (true exactly when [drawer] is non-empty).
 */
data class NavLayout(
    val bottom: List<NavModule>,
    val drawer: List<NavModule>,
    val showMore: Boolean,
)

/**
 * Android-native bottom navigation bars present at most five destinations; the
 * shell reserves the fifth slot for the "More" drawer entry whenever overflow
 * exists, leaving four real primary destinations (R5.2).
 */
const val MAX_BOTTOM_DESTINATIONS: Int = 5

/**
 * Canonical display order for the navigation destinations (R5.1). The active
 * role's [RoleModuleAccess.defaultLanding] is always surfaced first so the home
 * destination leads the bottom bar.
 */
private val CANONICAL_ORDER: List<Module> = listOf(
    Module.Dashboard,
    Module.Inbox,
    Module.Accounts,
    Module.Candidates,
    Module.DailyOps,
    Module.DataRoom,
    Module.Admin,
    Module.Logs,
    Module.HandlerKit,
)

/**
 * The ordered list of [NavModule]s presented to [role], driven by
 * [RoleModuleAccess.navigableModules] (R4.1, R4.2).
 *
 * The role's default landing module leads the list; the remainder follow
 * [CANONICAL_ORDER]. Handler Kit is the Handler's home destination, so for an
 * Admin (whose home is the Dashboard) it is omitted from the presented set,
 * matching the eight Admin destinations enumerated in R5.1 and the design's
 * Role-Based Navigation Resolution.
 */
fun orderedNavModules(role: Role): List<NavModule> {
    val navigable = RoleModuleAccess.navigableModules(role)
    val landing = RoleModuleAccess.defaultLanding(role)
    val ordered = (listOf(landing) + CANONICAL_ORDER.filter { it != landing })
        .filter { it in navigable }
        .distinct()
    val presented = if (role == Role.ADMIN) ordered.filterNot { it == Module.HandlerKit } else ordered
    return presented.map { NavModule.forModule(it) }
}

/**
 * Resolves the bottom-nav / drawer split for [role] (R5.2, R24.2).
 *
 * When the presented destinations fit within [MAX_BOTTOM_DESTINATIONS] they all
 * live in the bottom bar with no drawer (Handler: Handler Kit, Candidates, Data
 * Room). Otherwise the first four lead the bottom bar, a "More" entry occupies
 * the fifth slot, and the remainder move to the drawer (Admin: Dashboard, Inbox,
 * Accounts, Candidates + More → Daily Ops, Data Room, Admin, Logs).
 */
fun resolveNavLayout(role: Role): NavLayout {
    val ordered = orderedNavModules(role)
    return if (ordered.size <= MAX_BOTTOM_DESTINATIONS) {
        NavLayout(bottom = ordered, drawer = emptyList(), showMore = false)
    } else {
        NavLayout(
            bottom = ordered.take(MAX_BOTTOM_DESTINATIONS - 1),
            drawer = ordered.drop(MAX_BOTTOM_DESTINATIONS - 1),
            showMore = true,
        )
    }
}
