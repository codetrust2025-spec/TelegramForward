package com.teleautomation.android.ui.nav

import com.teleautomation.android.core.Module
import com.teleautomation.android.core.RoleModuleAccess
import com.teleautomation.android.data.api.Role
import io.kotest.core.spec.style.StringSpec
import io.kotest.matchers.collections.shouldContainExactly
import io.kotest.matchers.collections.shouldNotContain
import io.kotest.matchers.ints.shouldBeLessThanOrEqual
import io.kotest.matchers.shouldBe

/**
 * Example-based unit tests for the pure bottom-nav / drawer split that backs
 * [NavScaffold] (R5.1, R5.2, R24.2). These lock in the role-resolved layout the
 * navigation shell renders; Compose UI coverage is added separately (tasks plan 7.7).
 */
class NavLayoutTest : StringSpec({

    fun List<NavModule>.modules() = map { it.module }

    // ── Admin: 4 primary destinations + More → drawer (R5.1, R5.2) ──
    "admin bottom bar holds Dashboard, Inbox, Accounts, Candidates plus a More entry" {
        val layout = resolveNavLayout(Role.ADMIN)
        layout.bottom.modules() shouldContainExactly listOf(
            Module.Dashboard,
            Module.Inbox,
            Module.Accounts,
            Module.Candidates,
        )
        layout.showMore shouldBe true
    }

    "admin drawer holds Daily Ops, Data Room, Admin, Logs" {
        val layout = resolveNavLayout(Role.ADMIN)
        layout.drawer.modules() shouldContainExactly listOf(
            Module.DailyOps,
            Module.DataRoom,
            Module.Admin,
            Module.Logs,
        )
    }

    "admin navigation never surfaces the Handler Kit home module" {
        val layout = resolveNavLayout(Role.ADMIN)
        (layout.bottom + layout.drawer).modules() shouldNotContain Module.HandlerKit
    }

    // ── Handler: exactly three destinations, all in the bottom bar, no drawer ──
    "handler bottom bar holds exactly Handler Kit, Candidates, Data Room with no drawer" {
        val layout = resolveNavLayout(Role.HANDLER)
        layout.bottom.modules() shouldContainExactly listOf(
            Module.HandlerKit,
            Module.Candidates,
            Module.DataRoom,
        )
        layout.drawer shouldBe emptyList()
        layout.showMore shouldBe false
    }

    // ── Invariants across both roles ──
    "the bottom bar presents between 3 and 5 destinations for every role (R5.2)" {
        Role.entries.forEach { role ->
            val layout = resolveNavLayout(role)
            val itemCount = layout.bottom.size + if (layout.showMore) 1 else 0
            (itemCount in 3..MAX_BOTTOM_DESTINATIONS) shouldBe true
        }
    }

    "every navigable destination appears exactly once across bottom and drawer (R5.1)" {
        Role.entries.forEach { role ->
            val layout = resolveNavLayout(role)
            val presented = (layout.bottom + layout.drawer).map { it.module }
            presented shouldContainExactly orderedNavModules(role).map { it.module }
            presented.distinct().size shouldBe presented.size
        }
    }

    "a drawer is present iff there is overflow beyond the bottom bar" {
        Role.entries.forEach { role ->
            val layout = resolveNavLayout(role)
            layout.showMore shouldBe layout.drawer.isNotEmpty()
        }
    }

    "the role default landing leads the presented destinations" {
        Role.entries.forEach { role ->
            orderedNavModules(role).first().module shouldBe RoleModuleAccess.defaultLanding(role)
        }
    }

    "presented destinations are a subset of the role's navigable modules" {
        Role.entries.forEach { role ->
            val navigable = RoleModuleAccess.navigableModules(role)
            orderedNavModules(role).forEach { (it.module in navigable) shouldBe true }
            orderedNavModules(role).map { it.module }.toSet().size shouldBeLessThanOrEqual navigable.size
        }
    }
})
