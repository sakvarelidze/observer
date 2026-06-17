<template>
    <Teleport to="body">
        <transition name="palette">
            <div v-if="open" class="palette-root" @click.self="close">
                <div class="palette-backdrop" aria-hidden="true" @click="close"></div>
                <div
                    ref="dialog"
                    class="palette"
                    role="dialog"
                    aria-modal="true"
                    aria-label="command menu"
                >
                    <header class="palette-head">
                        <span class="palette-prompt" aria-hidden="true">⌘</span>
                        <input
                            ref="search"
                            v-model="query"
                            type="text"
                            class="palette-input"
                            :placeholder="searchPlaceholder"
                            @keydown.down.prevent="moveSelection(1)"
                            @keydown.up.prevent="moveSelection(-1)"
                            @keydown.enter.prevent="runSelected"
                            @keydown.escape.prevent="close"
                        >
                        <span class="palette-kbd" aria-hidden="true">esc</span>
                    </header>

                    <div ref="resultsEl" class="palette-results">
                        <template v-for="(group, gi) in groupedResults" :key="group.label">
                            <div class="palette-group-label">
                                {{ group.label }}
                                <span class="palette-group-count">{{ group.items.length }}</span>
                            </div>
                            <button
                                v-for="item in group.items"
                                :key="item.id"
                                ref="itemEls"
                                type="button"
                                class="palette-item"
                                :class="[
                                    `cat-${item.category}`,
                                    { active: flatIndex(gi, item) === selectedIndex },
                                ]"
                                @mouseenter="selectedIndex = flatIndex(gi, item)"
                                @click="runItem(item)"
                            >
                                <span class="palette-item-icon">
                                    <span v-if="item.statusKey" class="status-pip" :class="`pip-${item.statusKey}`"></span>
                                    <font-awesome-icon v-else :icon="item.icon || 'circle'" />
                                </span>
                                <span class="palette-item-body">
                                    <span class="palette-item-label">{{ item.label }}</span>
                                    <span v-if="item.secondary" class="palette-item-secondary">{{ item.secondary }}</span>
                                </span>
                                <span v-if="item.shortcut" class="palette-kbd palette-item-kbd">{{ item.shortcut }}</span>
                            </button>
                        </template>

                        <div v-if="filteredItems.length === 0" class="palette-empty">
                            no results for <strong>"{{ query }}"</strong>
                        </div>
                    </div>

                    <footer class="palette-foot">
                        <span class="foot-hint"><span class="palette-kbd">↑↓</span> navigate</span>
                        <span class="foot-hint"><span class="palette-kbd">↵</span> open</span>
                        <span class="foot-hint"><span class="palette-kbd">esc</span> close</span>
                        <span class="foot-spacer"></span>
                        <span class="foot-brand">observer · v2</span>
                    </footer>
                </div>
            </div>
        </transition>
    </Teleport>
</template>

<script>
const STATUS_KEY_BY_NUM = {
    1: "up",
    0: "down",
    2: "pending",
    3: "maintenance",
};

export default {
    name: "CommandPalette",
    data() {
        return {
            open: false,
            query: "",
            selectedIndex: 0,
        };
    },
    computed: {
        isMac() {
            return typeof navigator !== "undefined"
                && /mac|iphone|ipad/i.test(navigator.platform || navigator.userAgent || "");
        },
        searchPlaceholder() {
            return "search monitors, jump to a page…";
        },
        navigationItems() {
            return [
                {
                    id: "nav.v2-dashboard",
                    category: "navigation",
                    icon: "home",
                    label: "Dashboard",
                    secondary: "/dashboard",
                    keywords: [ "home", "monitors", "wall" ],
                    to: "/dashboard",
                },
                {
                    id: "nav.v2-add",
                    category: "navigation",
                    icon: "plus",
                    label: "Add Monitor",
                    secondary: "/add",
                    keywords: [ "new", "create" ],
                    to: "/add",
                },
                {
                    id: "nav.events",
                    category: "navigation",
                    icon: "bell",
                    label: "Events",
                    secondary: "/events",
                    keywords: [ "activity", "feed", "alerts", "history", "incidents", "down", "recovered" ],
                    to: "/events",
                },
                {
                    id: "nav.maintenance",
                    category: "navigation",
                    icon: "wrench",
                    label: "Maintenance",
                    secondary: "/maintenance",
                    keywords: [ "schedule", "downtime", "window" ],
                    to: "/maintenance",
                },
                {
                    id: "nav.notifications",
                    category: "navigation",
                    icon: "bell",
                    label: "Notifications",
                    secondary: "/settings/notifications",
                    keywords: [ "alerts", "channels", "discord", "slack" ],
                    to: "/settings/notifications",
                },
                {
                    id: "nav.status-pages",
                    category: "navigation",
                    icon: "list",
                    label: "Status Pages",
                    secondary: "/status-pages",
                    keywords: [ "public", "incident", "uptime" ],
                    to: "/status-pages",
                },
                {
                    id: "nav.settings",
                    category: "navigation",
                    icon: "cog",
                    label: "Settings",
                    secondary: "/settings/general",
                    keywords: [ "preferences", "config" ],
                    to: "/settings/general",
                },
                {
                    id: "nav.appearance",
                    category: "navigation",
                    icon: "sun",
                    label: "Appearance",
                    secondary: "/settings/appearance",
                    keywords: [ "theme", "language", "dark", "light", "color" ],
                    to: "/settings/appearance",
                },
                {
                    id: "nav.tags",
                    category: "navigation",
                    icon: "filter",
                    label: "Tags",
                    secondary: "/settings/tags",
                    keywords: [ "label", "category", "color" ],
                    to: "/settings/tags",
                },
                {
                    id: "nav.security",
                    category: "navigation",
                    icon: "award",
                    label: "Security & 2FA",
                    secondary: "/settings/security",
                    keywords: [ "password", "two factor", "totp", "auth", "logout" ],
                    to: "/settings/security",
                },
                {
                    id: "nav.api-keys",
                    category: "navigation",
                    icon: "link",
                    label: "API Keys",
                    secondary: "/settings/api-keys",
                    keywords: [ "token", "programmatic", "automation", "ci" ],
                    to: "/settings/api-keys",
                },
                {
                    id: "nav.users",
                    category: "navigation",
                    icon: "list",
                    label: "Users",
                    secondary: "/settings/users",
                    keywords: [ "accounts", "members", "admin", "team" ],
                    to: "/settings/users",
                },
                {
                    id: "nav.ldap",
                    category: "navigation",
                    icon: "link",
                    label: "LDAP",
                    secondary: "/settings/ldap",
                    keywords: [ "directory", "auth", "active directory", "ad" ],
                    to: "/settings/ldap",
                },
                {
                    id: "nav.monitor-history",
                    category: "navigation",
                    icon: "stream",
                    label: "Monitor History",
                    secondary: "/settings/monitor-history",
                    keywords: [ "retention", "purge", "data", "heartbeats" ],
                    to: "/settings/monitor-history",
                },
                {
                    id: "nav.reverse-proxy",
                    category: "navigation",
                    icon: "external-link-square-alt",
                    label: "Reverse Proxy",
                    secondary: "/settings/reverse-proxy",
                    keywords: [ "cloudflared", "cloudflare", "tunnel", "trust", "x-forwarded" ],
                    to: "/settings/reverse-proxy",
                },
                {
                    id: "nav.about",
                    category: "navigation",
                    icon: "info-circle",
                    label: "About",
                    secondary: "/settings/about",
                    keywords: [ "version", "info", "update" ],
                    to: "/settings/about",
                },
            ];
        },
        monitorItems() {
            const list = Object.values(this.$root.monitorList || {});
            return list
                .filter(m => m && m.type !== "group")
                .map(m => {
                    const last = this.$root.lastHeartbeatList?.[m.id];
                    let statusKey = "unknown";
                    if (!m.active) {
                        statusKey = "paused";
                    } else if (last) {
                        statusKey = STATUS_KEY_BY_NUM[last.status] || "unknown";
                    }
                    return {
                        id: `monitor.${m.id}`,
                        category: "monitor",
                        statusKey,
                        label: m.name,
                        secondary: this.monitorSecondary(m),
                        keywords: [ m.type, m.url, m.hostname ].filter(Boolean),
                        to: `/dashboard/${m.id}`,
                    };
                });
        },
        actionItems() {
            return [
                {
                    id: "action.toggle-density",
                    category: "action",
                    icon: "sliders-h",
                    label: "Toggle Density",
                    secondary: "compact ↔ comfortable on the dashboard",
                    keywords: [ "tile size", "spacing" ],
                    handler: () => {
                        const cur = localStorage.getItem("v2-density") || "comfortable";
                        const next = cur === "compact" ? "comfortable" : "compact";
                        localStorage.setItem("v2-density", next);
                        // Lightweight signal so the dashboard can react if mounted
                        this.$root.emitter?.emit?.("v2-density-changed", next);
                    },
                },
            ];
        },
        allItems() {
            return [
                ...this.navigationItems,
                ...this.monitorItems,
                ...this.actionItems,
            ];
        },
        filteredItems() {
            const q = this.query.trim().toLowerCase();
            if (!q) {
                return this.allItems;
            }
            const matches = [];
            for (const item of this.allItems) {
                const label = (item.label || "").toLowerCase();
                const sec = (item.secondary || "").toLowerCase();
                const kw = (item.keywords || []).join(" ").toLowerCase();
                let score = 0;
                if (label.startsWith(q)) {
                    score = 3;
                } else if (label.includes(q)) {
                    score = 2;
                } else if (sec.includes(q) || kw.includes(q)) {
                    score = 1;
                }
                if (score > 0) {
                    matches.push({ item,
                        score });
                }
            }
            return matches
                .sort((a, b) => b.score - a.score)
                .map(({ item }) => item);
        },
        groupedResults() {
            const order = [ "navigation", "monitor", "action" ];
            const labels = {
                navigation: "navigate",
                monitor: "jump to monitor",
                action: "actions",
            };
            const groups = {};
            for (const item of this.filteredItems) {
                if (!groups[item.category]) {
                    groups[item.category] = [];
                }
                groups[item.category].push(item);
            }
            return order
                .filter(cat => groups[cat]?.length)
                .map(cat => ({
                    label: labels[cat],
                    category: cat,
                    items: groups[cat],
                }));
        },
    },
    watch: {
        query() {
            this.selectedIndex = 0;
            this.$nextTick(() => this.scrollSelectedIntoView());
        },
        selectedIndex() {
            this.$nextTick(() => this.scrollSelectedIntoView());
        },
        open(isOpen) {
            if (isOpen) {
                this.$nextTick(() => {
                    this.$refs.search?.focus();
                });
            }
        },
    },
    mounted() {
        window.addEventListener("keydown", this.onGlobalKey);
        this.$root.emitter?.on?.("open-command-palette", this.openPalette);
    },
    beforeUnmount() {
        window.removeEventListener("keydown", this.onGlobalKey);
        this.$root.emitter?.off?.("open-command-palette", this.openPalette);
    },
    methods: {
        monitorSecondary(m) {
            if (m.url) {
                return m.url;
            }
            if (m.hostname && m.port) {
                return `${m.hostname}:${m.port}`;
            }
            if (m.hostname) {
                return m.hostname;
            }
            return m.type;
        },
        openPalette() {
            this.open = true;
            this.query = "";
            this.selectedIndex = 0;
        },
        close() {
            this.open = false;
        },
        flatIndex(groupIndex, item) {
            // Build the flat selection index by counting items in earlier groups
            // plus the position within this group.
            let idx = 0;
            for (let g = 0; g < this.groupedResults.length; g++) {
                const group = this.groupedResults[g];
                if (g < groupIndex) {
                    idx += group.items.length;
                } else if (g === groupIndex) {
                    return idx + group.items.indexOf(item);
                }
            }
            return idx;
        },
        moveSelection(delta) {
            const total = this.filteredItems.length;
            if (total === 0) {
                return;
            }
            this.selectedIndex = (this.selectedIndex + delta + total) % total;
        },
        runSelected() {
            const item = this.filteredItems[this.selectedIndex];
            if (item) {
                this.runItem(item);
            }
        },
        runItem(item) {
            this.close();
            if (item.handler) {
                item.handler();
                return;
            }
            if (item.to) {
                this.$router.push(item.to);
            }
        },
        scrollSelectedIntoView() {
            const items = Array.isArray(this.$refs.itemEls)
                ? this.$refs.itemEls
                : [];
            const target = items[this.selectedIndex];
            if (target?.scrollIntoView) {
                target.scrollIntoView({ block: "nearest" });
            }
        },
        onGlobalKey(e) {
            const isToggle = (e.metaKey || e.ctrlKey)
                && (e.key === "k" || e.key === "K");
            if (isToggle) {
                e.preventDefault();
                if (this.open) {
                    this.close();
                } else {
                    this.openPalette();
                }
                return;
            }
            if (this.open && e.key === "Escape") {
                e.preventDefault();
                this.close();
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.palette-root {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 12vh 24px 24px;
    @include v2-surface-tokens;
}

.palette-backdrop {
    position: absolute;
    inset: 0;
    background: hsl(0 0% 0% / 0.55);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
}

.palette {
    position: relative;
    width: 100%;
    max-width: 640px;
    background: var(--bg-soft);
    border: 1px solid var(--border-strong);
    border-radius: 14px;
    box-shadow:
        0 1px 0 hsl(0 0% 100% / 0.04) inset,
        0 24px 60px hsl(0 0% 0% / 0.5);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen,
        Ubuntu, Cantarell, "Helvetica Neue", sans-serif;
    letter-spacing: -0.005em;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    max-height: 70vh;
}

.palette-head {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 14px 14px 12px;
    border-bottom: 1px solid var(--border);
}

.palette-prompt {
    width: 22px;
    height: 22px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    background: var(--bg-soft);
    color: var(--text-muted);
    font-size: 11px;
    font-weight: 600;
}

.palette-input {
    flex: 1;
    appearance: none;
    background: transparent;
    border: none;
    color: var(--text);
    font-size: 16px;
    line-height: 1.2;
    padding: 4px 0;
    font-family: inherit;
    letter-spacing: -0.005em;

    &:focus {
        outline: none;
    }

    &::placeholder {
        color: var(--text-faint);
    }
}

.palette-results {
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 6px 6px 6px;
    scrollbar-width: thin;
    scrollbar-color: var(--border-strong) transparent;

    &::-webkit-scrollbar {
        width: 6px;
    }
    &::-webkit-scrollbar-thumb {
        background: var(--border-strong);
        border-radius: 3px;
    }
}

.palette-group-label {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 10px 6px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-faint);

    .palette-group-count {
        font-variant-numeric: tabular-nums;
        color: var(--text-faint);
        opacity: 0.6;
    }
}

.palette-item {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 9px 10px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    color: var(--text);
    font-size: 13px;
    text-align: left;
    cursor: pointer;
    transition: background 80ms ease, border-color 80ms ease, color 80ms ease;
    font-family: inherit;

    &.active {
        background: hsl(142 71% 45% / 0.12);
        border-color: hsl(142 71% 45% / 0.45);
        color: var(--text);
    }

    &:focus-visible {
        outline: none;
        border-color: hsl(142 71% 45% / 0.6);
    }
}

.palette-item-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 26px;
    border-radius: 7px;
    background: var(--bg-soft);
    color: var(--text-muted);
    font-size: 12px;
    flex: none;

    .palette-item.active & {
        background: hsl(142 71% 45% / 0.2);
        color: hsl(142 71% 70%);
    }
}

.status-pip {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-faint);

    &.pip-up { background: hsl(142 71% 45%); }
    &.pip-down { background: hsl(0 84% 60%); }
    &.pip-pending { background: hsl(38 92% 50%); }
    &.pip-maintenance { background: hsl(217 91% 60%); }
    &.pip-paused { background: var(--text-faint); }
    &.pip-unknown { background: var(--text-faint); }
}

.palette-item-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.palette-item-label {
    font-weight: 500;
    color: var(--text);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.palette-item-secondary {
    font-size: 11px;
    color: var(--text-faint);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-variant-numeric: tabular-nums;
}

.palette-item.cat-monitor .palette-item-secondary {
    text-transform: lowercase;
    letter-spacing: 0.01em;
}

.palette-item-kbd {
    flex: none;
}

.palette-empty {
    padding: 24px 14px 28px;
    text-align: center;
    color: var(--text-faint);
    font-size: 13px;

    strong {
        color: var(--text-muted);
        font-weight: 600;
    }
}

.palette-foot {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 10px 14px;
    border-top: 1px solid var(--border);
    background: var(--bg-soft);
    color: var(--text-faint);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;

    .foot-hint {
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }

    .foot-spacer {
        flex: 1;
    }

    .foot-brand {
        font-size: 10px;
        opacity: 0.6;
    }
}

.palette-kbd {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 22px;
    height: 18px;
    padding: 0 5px;
    border-radius: 4px;
    border: 1px solid var(--border);
    background: var(--bg-soft);
    color: var(--text-muted);
    font-size: 10px;
    font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
        Monaco, Consolas, monospace;
    text-transform: none;
    letter-spacing: 0;
    line-height: 1;
}

/* Open / close motion */

.palette-enter-active,
.palette-leave-active {
    transition: opacity 160ms $v2-ease;

    .palette {
        transition: opacity 200ms $v2-ease, transform 200ms $v2-ease;
    }
}

.palette-enter-from,
.palette-leave-to {
    opacity: 0;

    .palette {
        opacity: 0;
        transform: translateY(-8px) scale(0.97);
    }
}

@media (prefers-reduced-motion: reduce) {
    .palette-enter-active,
    .palette-leave-active {
        transition: none;

        .palette {
            transition: none;
        }
    }

    .palette-enter-from,
    .palette-leave-to .palette {
        transform: none;
    }
}

@media (max-width: 640px) {
    .palette-root {
        padding: 6vh 12px 12px;
    }

    .palette {
        max-height: 80vh;
    }

    .palette-foot {
        flex-wrap: wrap;
        gap: 8px;

        .foot-spacer { display: none; }
    }
}
</style>
