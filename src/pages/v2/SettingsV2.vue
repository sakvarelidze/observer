<template>
    <div class="v2-settings">
        <header class="topbar">
            <router-link to="/dashboard" class="back" title="Back to dashboard">
                <span class="back-arrow">←</span>
                <span class="back-label">dashboard</span>
            </router-link>

            <h1 class="topbar-title">settings</h1>

            <div class="topbar-right">
                <MenuTrigger />
            </div>
        </header>

        <main class="settings-shell">
            <nav class="settings-nav" aria-label="Settings sections">
                <template v-for="section in navSections" :key="section.label">
                    <span class="nav-group-label">{{ section.label }}</span>
                    <ul class="nav-group">
                        <li v-for="item in section.items" :key="item.id">
                            <router-link
                                v-if="item.to"
                                :to="item.to"
                                class="nav-item"
                                active-class="active"
                            >
                                <span class="nav-item-icon">
                                    <font-awesome-icon :icon="item.icon" />
                                </span>
                                <span class="nav-item-label">{{ item.label }}</span>
                            </router-link>
                            <span v-else class="nav-item disabled" :title="`${item.label} — coming soon`">
                                <span class="nav-item-icon">
                                    <font-awesome-icon :icon="item.icon" />
                                </span>
                                <span class="nav-item-label">{{ item.label }}</span>
                                <span class="nav-item-tag">soon</span>
                            </span>
                        </li>
                    </ul>
                </template>
            </nav>

            <section class="settings-content">
                <router-view v-slot="{ Component }">
                    <transition name="settings-page" mode="out-in">
                        <component :is="Component" />
                    </transition>
                </router-view>
            </section>
        </main>

        <CommandPalette />
    </div>
</template>

<script>
import CommandPalette from "./CommandPalette.vue";
import MenuTrigger from "./MenuTrigger.vue";

export default {
    name: "SettingsV2",
    components: { CommandPalette,
        MenuTrigger },
    computed: {
        navSections() {
            return [
                {
                    label: "Workspace",
                    items: [
                        { id: "general",
                            label: "General",
                            icon: "cog",
                            to: "/settings/general" },
                        { id: "notifications",
                            label: "Notifications",
                            icon: "bell",
                            to: "/settings/notifications" },
                        { id: "tags",
                            label: "Tags",
                            icon: "filter",
                            to: "/settings/tags" },
                        { id: "monitor-history",
                            label: "Monitor History",
                            icon: "stream",
                            to: "/settings/monitor-history" },
                    ],
                },
                {
                    label: "Personal",
                    items: [
                        { id: "appearance",
                            label: "Appearance",
                            icon: "sun",
                            to: "/settings/appearance" },
                        { id: "security",
                            label: "Security & 2FA",
                            icon: "award",
                            to: "/settings/security" },
                        { id: "api-keys",
                            label: "API Keys",
                            icon: "link",
                            to: "/settings/api-keys" },
                    ],
                },
                {
                    label: "Advanced",
                    items: [
                        { id: "users",
                            label: "Users",
                            icon: "list",
                            to: "/settings/users" },
                        { id: "reverse-proxy",
                            label: "Reverse Proxy",
                            icon: "external-link-square-alt",
                            to: "/settings/reverse-proxy" },
                        { id: "ldap",
                            label: "LDAP",
                            icon: "link",
                            to: "/settings/ldap" },
                        { id: "about",
                            label: "About",
                            icon: "info-circle",
                            to: "/settings/about" },
                    ],
                },
            ];
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.v2-settings {
    @include v2-surface-tokens;
    @include v2-shell-base;

    background:
        radial-gradient(circle at 12% -10%, hsl(217 91% 60% / 0.05), transparent 60%),
        var(--bg);
    padding: 0 32px 64px;
    animation: v2-fade-in 280ms var(--enter-ease) both;
}

.topbar {
    @include v2-sticky-topbar(16px);
}

.back {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: var(--text-muted);
    text-decoration: none;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 6px 10px;
    border-radius: 8px;
    border: 1px solid transparent;
    transition: color 140ms ease, background 140ms ease, border-color 140ms ease;

    &:hover {
        color: var(--text);
        background: var(--bg-soft);
        border-color: var(--border);
    }

    .back-arrow { transition: transform 200ms $v2-ease; }
    &:hover .back-arrow { transform: translateX(-3px); }
}

.topbar-title {
    justify-self: center;
    margin: 0;
    font-size: 14px;
    font-weight: 500;
    text-transform: lowercase;
    letter-spacing: 0.02em;
    color: var(--text);
}

.topbar-right {
    display: inline-flex;
    align-items: center;
    gap: 12px;
}

.settings-shell {
    display: grid;
    grid-template-columns: 240px 1fr;
    gap: 32px;
    margin: 24px auto 0;
    max-width: 1100px;
    animation: v2-up 320ms var(--enter-ease) both;
    animation-delay: 60ms;
}

.settings-nav {
    display: flex;
    flex-direction: column;
    gap: 18px;
    position: sticky;
    top: 80px;
    align-self: start;
}

.nav-group-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    color: var(--text-faint);
    padding: 0 12px;
    font-weight: 600;
}

.nav-group {
    list-style: none;
    margin: 4px 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
}

.nav-item {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    border-radius: 8px;
    color: var(--text-muted);
    text-decoration: none;
    font-size: 13px;
    cursor: pointer;
    transition: background 140ms ease, color 140ms ease;

    &:hover:not(.disabled) {
        background: var(--bg-soft);
        color: var(--text);
    }

    &.active {
        background: hsl(142 71% 45% / 0.10);
        color: hsl(142 71% 75%);
    }

    &.disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }

    .nav-item-icon {
        width: 18px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
        color: currentColor;
    }

    .nav-item-label {
        flex: 1;
    }

    .nav-item-tag {
        font-size: 9px;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        padding: 1px 5px;
        border-radius: 3px;
        background: var(--control);
        border: 1px solid var(--border);
    }
}

.settings-content {
    min-width: 0;
    padding-bottom: 40px;
}

.settings-page-enter-active,
.settings-page-leave-active {
    transition: opacity 180ms $v2-ease, transform 180ms $v2-ease;
}

.settings-page-enter-from {
    opacity: 0;
    transform: translateY(6px);
}

.settings-page-leave-to {
    opacity: 0;
    transform: translateY(-4px);
}

@media (prefers-reduced-motion: reduce) {
    .v2-settings,
    .settings-shell {
        animation: none;
    }

    .settings-page-enter-active,
    .settings-page-leave-active {
        transition: none;
    }
}

@media (max-width: 880px) {
    .v2-settings { padding: 0 16px 40px; }

    .settings-shell {
        grid-template-columns: 1fr;
        gap: 20px;
    }

    .settings-nav {
        position: static;
    }
}
</style>
