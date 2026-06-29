package com.teleautomation.android.core

import com.teleautomation.android.data.api.Role

/**
 * The set of top-level application modules an [Operator][Role] can navigate to.
 *
 * This mirrors the module list named in the navigation requirements (R5.1) plus
 * the Handler-only landing module, and matches the "Role-Based Navigation
 * Resolution" diagram in the design document:
 *  - **Admin** reaches every module.
 *  - **Handler** reaches exactly [HandlerKit], [Candidates], and [DataRoom]
 *    (the restricted *Opportunities* view of the Data Room).
 *
 * [DataRoom] is a single module for navigation/access purposes; the Handler's
 * restriction to the Opportunities tab is a within-screen concern handled by the
 * Data Room screen itself, not by module-level access resolution.
 */
enum class Module {
    Dashboard,
    Inbox,
    Accounts,
    Candidates,
    DailyOps,
    DataRoom,
    Admin,
    Logs,
    HandlerKit,
}

/**
 * The outcome of guarding a navigation [Module] target for a given [Role].
 *
 * Either the target is reachable for the role ([Allowed]) or the role is not
 * permitted and must be sent elsewhere with an authorization error
 * ([RedirectWithError]). For a Handler aiming at an Admin-only module this mirrors
 * the Backend's `_require_fleet_admin` rejection, surfaced client-side as a
 * redirect to the Handler Kit (R4.4).
 */
sealed interface AccessDecision {

    /** The role may navigate to the requested module. */
    data object Allowed : AccessDecision

    /**
     * The role may not navigate to the requested module; navigation is redirected
     * to [destination] and an [authorizationError] is surfaced (R4.4).
     *
     * @param destination the module the Operator is sent to instead (the role's
     *   default landing module).
     * @param authorizationError a human-readable message indicating the requested
     *   module is restricted.
     */
    data class RedirectWithError(
        val destination: Module,
        val authorizationError: String,
    ) : AccessDecision
}

/**
 * Pure, device-independent resolver for role-based module access and navigation
 * defaults (R4.1, R4.2, R4.4).
 *
 * This logic lives in `core` (no Android, Compose, Hilt, OkHttp, or Retrofit
 * dependencies — only the plain [Role] enum) so it is unit/property testable on the
 * plain JVM. The navigation shell (`NavScaffold`, tasks plan 7.5) and the navigation
 * guard (tasks plan 7.6) delegate here; see the "Role-Based Navigation Resolution"
 * flowchart in the design document.
 *
 * Backing property (Property 3): for any [Role] the resolved navigable set equals the
 * role's allowed set — Handler is exactly {Handler Kit, Candidates, Data Room} with no
 * Admin-only module, and Admin is a superset that includes every Handler module — and
 * for any Admin-only target while the role is Handler the guard yields a redirect to
 * the Handler Kit with an authorization error.
 */
object RoleModuleAccess {

    /**
     * The exact set of modules a [Role.HANDLER] may navigate to (R4.1):
     * the Handler Kit, the Candidates tracker, and the restricted Data Room
     * (Opportunities). Contains no Admin-only module.
     */
    val HANDLER_MODULES: Set<Module> = setOf(
        Module.HandlerKit,
        Module.Candidates,
        Module.DataRoom,
    )

    /**
     * The set of modules a [Role.ADMIN] may navigate to (R4.2): every module. This is
     * a superset of [HANDLER_MODULES], so every module reachable by a Handler is also
     * reachable by an Admin.
     */
    val ADMIN_MODULES: Set<Module> = Module.entries.toSet()

    /**
     * Modules reachable only by an Admin — the Admin set minus the Handler set. A
     * [Role.HANDLER] navigating to any of these is redirected with an authorization
     * error (R4.4). Computed from the two sets so it can never drift out of sync.
     */
    val ADMIN_ONLY_MODULES: Set<Module> = ADMIN_MODULES - HANDLER_MODULES

    /**
     * Returns the complete set of modules [role] may navigate to (R4.1, R4.2).
     *
     * Handler → [HANDLER_MODULES] (exactly three, no Admin-only module);
     * Admin → [ADMIN_MODULES] (all modules, a superset of the Handler set).
     */
    fun navigableModules(role: Role): Set<Module> =
        when (role) {
            Role.ADMIN -> ADMIN_MODULES
            Role.HANDLER -> HANDLER_MODULES
        }

    /**
     * The module [role] lands on after authentication and the target of an
     * authorization redirect: Handler → [Module.HandlerKit]; Admin →
     * [Module.Dashboard] (per the design's Role-Based Navigation Resolution).
     */
    fun defaultLanding(role: Role): Module =
        when (role) {
            Role.ADMIN -> Module.Dashboard
            Role.HANDLER -> Module.HandlerKit
        }

    /**
     * Whether [role] is permitted to navigate to [target] — true iff [target] is in
     * the role's [navigableModules] set (R4.1, R4.2).
     */
    fun isAccessAllowed(role: Role, target: Module): Boolean =
        target in navigableModules(role)

    /**
     * Guards a navigation [target] for [role] (R4.4).
     *
     * Returns [AccessDecision.Allowed] when the role may reach [target]; otherwise
     * returns [AccessDecision.RedirectWithError] pointing at the role's
     * [defaultLanding] (the Handler Kit for a Handler) with an authorization error
     * naming the restricted module — the client-side mirror of the Backend's
     * fleet-admin gating.
     */
    fun guard(role: Role, target: Module): AccessDecision =
        if (isAccessAllowed(role, target)) {
            AccessDecision.Allowed
        } else {
            AccessDecision.RedirectWithError(
                destination = defaultLanding(role),
                authorizationError = "The $target module is restricted and is not available for your role.",
            )
        }
}
