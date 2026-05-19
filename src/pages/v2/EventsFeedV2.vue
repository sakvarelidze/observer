<template>
    <div class="v2-events">
        <header class="topbar">
            <router-link to="/dashboard" class="back" title="Back to dashboard">
                <span class="back-arrow">←</span>
                <span class="back-label">dashboard</span>
            </router-link>
            <h1 class="topbar-title">events</h1>
            <div class="topbar-right">
                <MenuTrigger />
            </div>
        </header>

        <main class="main">
            <header class="page-head">
                <div class="page-head-text">
                    <h2 class="page-title">recent activity</h2>
                    <p class="page-sub">status changes across all your monitors. ordered newest first; auto-refreshes every 30s.</p>
                </div>
                <span class="updated-meta">updated {{ relativeTime(lastUpdated) }}</span>
            </header>

            <nav class="filters" role="tablist" aria-label="Event status filter">
                <button
                    v-for="opt in filterOptions"
                    :key="opt.value"
                    type="button"
                    role="tab"
                    :aria-selected="filter === opt.value ? 'true' : 'false'"
                    class="filter-pill"
                    :class="[`tone-${opt.tone}`, { active: filter === opt.value }]"
                    @click="setFilter(opt.value)"
                >
                    <span v-if="opt.dot" class="filter-dot" :class="`tone-${opt.tone}`"></span>
                    <span class="filter-label">{{ opt.label }}</span>
                    <span v-if="filter === opt.value && totalForFilter != null" class="filter-count">{{ totalForFilter }}</span>
                </button>
            </nav>

            <div v-if="loading && events.length === 0" class="page-loading">
                <LoaderBars size="md" />
            </div>

            <ul v-else-if="grouped.length > 0" class="day-list">
                <li v-for="group in grouped" :key="group.key" class="day-group">
                    <h3 class="day-label">{{ group.label }}</h3>
                    <ul class="event-list">
                        <li
                            v-for="ev in group.events"
                            :key="ev.id"
                            class="event-row"
                            :class="`status-${statusKey(ev.status)}`"
                        >
                            <span class="event-time" :title="absoluteTime(ev.time)">{{ formatClock(ev.time) }}</span>
                            <span class="event-dot" :class="`tone-${statusKey(ev.status)}`"></span>
                            <span class="event-body">
                                <router-link :to="`/dashboard/${ev.monitorID}`" class="event-monitor">{{ ev.monitorName }}</router-link>
                                <span class="event-status-pill" :class="`tone-${statusKey(ev.status)}`">
                                    {{ statusLabel(ev.status) }}
                                </span>
                                <span v-if="ev.msg" class="event-msg">{{ humanizeStatusMessage(ev.msg) }}</span>
                            </span>
                        </li>
                    </ul>
                </li>
            </ul>

            <div v-else class="empty-state">
                <span class="empty-icon">
                    <font-awesome-icon icon="bell" />
                </span>
                <p class="empty-title">{{ filter === 'all' ? "Everything's quiet" : 'No matching events' }}</p>
                <p class="empty-sub">
                    <template v-if="filter === 'all'">
                        Status changes (up ↔ down, maintenance starts, etc.) will appear here as they happen.
                    </template>
                    <template v-else-if="filter === 'down'">
                        No outages recorded in the visible history. That's a good sign.
                    </template>
                    <template v-else-if="filter === 'up'">
                        No recovery events yet — drop the filter to see all activity.
                    </template>
                    <template v-else>
                        Nothing matches this filter in the visible history.
                    </template>
                </p>
            </div>

            <div v-if="hasMore && events.length > 0" class="load-more-wrap">
                <button
                    type="button"
                    class="action ghost"
                    :disabled="loadingMore"
                    @click="loadMore"
                >
                    <span v-if="!loadingMore">load older events</span>
                    <span v-else>loading…</span>
                </button>
            </div>
        </main>

        <CommandPalette />
    </div>
</template>

<script>
import dayjs from "dayjs";
import { humanizeStatusMessage } from "../../util-frontend";
import CommandPalette from "./CommandPalette.vue";
import LoaderBars from "./LoaderBars.vue";
import MenuTrigger from "./MenuTrigger.vue";

const PAGE_SIZE = 50;
const REFRESH_INTERVAL_MS = 30000;

const STATUS_LABEL = {
    1: "up",
    0: "down",
    2: "pending",
    3: "maintenance",
};
const STATUS_KEY = {
    1: "up",
    0: "down",
    2: "pending",
    3: "maintenance",
};

const FILTER_OPTIONS = [
    { value: "all",
        label: "all",
        tone: "muted",
        dot: false },
    { value: "down",
        label: "down",
        tone: "down",
        dot: true },
    { value: "up",
        label: "recovered",
        tone: "up",
        dot: true },
    { value: "pending",
        label: "pending",
        tone: "pending",
        dot: true },
];

export default {
    name: "EventsFeedV2",
    components: { CommandPalette,
        LoaderBars,
        MenuTrigger },
    data() {
        return {
            filterOptions: FILTER_OPTIONS,
            events: [],
            total: 0,
            offset: 0,
            loading: true,
            loadingMore: false,
            lastUpdated: null,
            refreshHandle: null,
            tickHandle: null,
            now: Date.now(),
        };
    },
    computed: {
        filter() {
            const q = this.$route.query?.status;
            if (typeof q === "string" && [ "down", "up", "pending", "maintenance" ].includes(q)) {
                return q;
            }
            return "all";
        },
        hasMore() {
            return this.events.length < this.total;
        },
        totalForFilter() {
            return this.total;
        },
        grouped() {
            // Bucket events by local-day so the feed reads as a journal.
            // Each group label is "today" / "yesterday" / "Mon Mar 9"
            // depending on how recent the day is.
            const bucketsByKey = new Map();
            const bucketsOrder = [];
            const today = dayjs().startOf("day");
            const yesterday = today.subtract(1, "day");

            for (const ev of this.events) {
                if (!ev.time) {
                    continue;
                }
                const day = dayjs(this.normaliseTime(ev.time)).startOf("day");
                const key = day.format("YYYY-MM-DD");
                if (!bucketsByKey.has(key)) {
                    let label;
                    if (day.isSame(today)) {
                        label = "today";
                    } else if (day.isSame(yesterday)) {
                        label = "yesterday";
                    } else {
                        label = day.format("ddd MMM D");
                    }
                    bucketsByKey.set(key, { key,
                        label,
                        events: [] });
                    bucketsOrder.push(key);
                }
                bucketsByKey.get(key).events.push(ev);
            }
            return bucketsOrder.map(k => bucketsByKey.get(k));
        },
    },
    watch: {
        filter() {
            this.reload();
        },
    },
    mounted() {
        document.title = "Events · Observer";
        this.reload();
        this.refreshHandle = setInterval(() => this.refresh(), REFRESH_INTERVAL_MS);
        // Re-tick the relative-time label every 20s without re-fetching.
        this.tickHandle = setInterval(() => {
            this.now = Date.now();
        }, 20000);
    },
    beforeUnmount() {
        document.title = "Observer";
        clearInterval(this.refreshHandle);
        clearInterval(this.tickHandle);
    },
    methods: {
        humanizeStatusMessage,
        async reload() {
            this.loading = true;
            this.events = [];
            this.offset = 0;
            await this.fetchPage(0, true);
            this.loading = false;
        },
        async refresh() {
            // Light refresh: only pull the most-recent page so we pick up
            // new events without scrolling past the user's "load older"
            // expansions.
            await this.fetchPage(0, false);
        },
        async loadMore() {
            if (this.loadingMore || !this.hasMore) {
                return;
            }
            this.loadingMore = true;
            try {
                await this.fetchPage(this.events.length, false, { append: true });
            } finally {
                this.loadingMore = false;
            }
        },
        async fetchPage(offset, replace, { append = false } = {}) {
            const params = { limit: PAGE_SIZE,
                offset };
            if (this.filter !== "all") {
                params.status = this.filter;
            }
            try {
                const { data } = await this.$root.api.get("/events", { params });
                if (!data?.ok) {
                    return;
                }
                if (append) {
                    // Defensive: dedupe in case the same event reaches both
                    // pages (shouldn't, but a poll could overlap).
                    const seen = new Set(this.events.map(e => e.id));
                    for (const ev of data.events || []) {
                        if (!seen.has(ev.id)) {
                            this.events.push(ev);
                        }
                    }
                } else if (replace) {
                    this.events = data.events || [];
                } else {
                    // Refresh: merge the newest page in over the head of the
                    // current list. New events go on top; existing rows stay
                    // (load-more state preserved).
                    const seen = new Set((data.events || []).map(e => e.id));
                    const tail = this.events.filter(e => !seen.has(e.id));
                    this.events = [ ...(data.events || []), ...tail ];
                }
                this.total = data.total || 0;
                this.offset = offset;
                this.lastUpdated = new Date();
            } catch (e) {
                console.warn("could not load events", e);
            }
        },
        setFilter(value) {
            const next = { ...this.$route.query };
            if (value === "all") {
                delete next.status;
            } else {
                next.status = value;
            }
            this.$router.replace({ query: next });
        },
        statusKey(s) {
            return STATUS_KEY[s] || "unknown";
        },
        statusLabel(s) {
            return STATUS_LABEL[s] || "unknown";
        },
        normaliseTime(raw) {
            // Backend serialises naive UTC timestamps without a Z; appending
            // it forces JS to parse as UTC instead of local time.
            if (!raw) {
                return raw;
            }
            return raw.endsWith("Z") || raw.includes("+") ? raw : raw + "Z";
        },
        formatClock(raw) {
            if (!raw) {
                return "";
            }
            return dayjs(this.normaliseTime(raw)).format("HH:mm");
        },
        absoluteTime(raw) {
            if (!raw) {
                return "";
            }
            return dayjs(this.normaliseTime(raw)).format("ddd MMM D · HH:mm:ss");
        },
        relativeTime(date) {
            if (!date) {
                return "—";
            }
            const ms = this.now - new Date(date).getTime();
            if (ms < 5000) {
                return "just now";
            }
            if (ms < 60000) {
                return `${Math.round(ms / 1000)}s ago`;
            }
            if (ms < 3600000) {
                return `${Math.round(ms / 60000)}m ago`;
            }
            return `${Math.round(ms / 3600000)}h ago`;
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.v2-events {
    @include v2-surface-tokens;
    @include v2-shell-base;

    background:
        radial-gradient(circle at 12% -10%, hsl(0 84% 60% / 0.04), transparent 60%),
        radial-gradient(circle at 90% 0%, hsl(217 91% 60% / 0.04), transparent 55%),
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

.main {
    max-width: 920px;
    margin: 24px auto 0;
    display: flex;
    flex-direction: column;
    gap: 22px;
    animation: v2-up 320ms var(--enter-ease) both;
    animation-delay: 60ms;
}

.page-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;

    .page-head-text {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .page-title {
        margin: 0;
        font-size: 22px;
        font-weight: 600;
        letter-spacing: -0.015em;
    }

    .page-sub {
        margin: 0;
        color: var(--text-muted);
        font-size: 13px;
        max-width: 60ch;
        line-height: 1.55;
    }

    .updated-meta {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-faint);
        white-space: nowrap;
    }
}

.filters {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 6px;
}

.filter-pill {
    appearance: none;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-muted);
    border-radius: 999px;
    padding: 6px 12px;
    font-size: 12px;
    text-transform: lowercase;
    letter-spacing: 0.02em;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease;

    &:hover {
        background: var(--bg-soft);
        color: var(--text);
        border-color: var(--border-strong);
    }

    &.active {
        background: var(--bg-soft);
        color: var(--text);
        border-color: var(--border-strong);
    }

    .filter-count {
        font-size: 10px;
        padding: 1px 5px;
        border-radius: 999px;
        background: hsl(0 0% 4%);
        color: var(--text-faint);
    }
}

.filter-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: hsl(0 0% 38%);

    &.tone-up { background: hsl(142 71% 45%); }
    &.tone-down { background: hsl(0 84% 60%); }
    &.tone-pending { background: hsl(38 92% 55%); }
    &.tone-maintenance { background: hsl(217 91% 60%); }
}

.page-loading {
    display: flex;
    justify-content: center;
    padding: 60px 0;
}

.day-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 18px;
}

.day-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.day-label {
    margin: 0;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-faint);
    font-weight: 600;
}

.event-list {
    list-style: none;
    margin: 0;
    padding: 0;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
}

.event-row {
    display: grid;
    grid-template-columns: auto auto 1fr;
    align-items: center;
    gap: 14px;
    padding: 11px 16px;
    transition: background 140ms ease;

    & + & {
        border-top: 1px solid var(--border);
    }

    &:hover {
        background: var(--bg-hover);
    }

    &.status-down {
        background: hsl(0 84% 60% / 0.04);

        &:hover { background: hsl(0 84% 60% / 0.08); }
    }
}

.event-time {
    font-variant-numeric: tabular-nums;
    font-size: 12px;
    color: var(--text-faint);
    font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
        Monaco, Consolas, monospace;
}

.event-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: hsl(0 0% 38%);
    box-shadow: 0 0 0 4px hsl(0 0% 0% / 0);
    flex: none;

    &.tone-up { background: hsl(142 71% 45%); box-shadow: 0 0 0 4px hsl(142 71% 45% / 0.18); }
    &.tone-down { background: hsl(0 84% 60%); box-shadow: 0 0 0 4px hsl(0 84% 60% / 0.18); }
    &.tone-pending { background: hsl(38 92% 55%); box-shadow: 0 0 0 4px hsl(38 92% 50% / 0.18); }
    &.tone-maintenance { background: hsl(217 91% 60%); box-shadow: 0 0 0 4px hsl(217 91% 60% / 0.18); }
}

.event-body {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 8px;
    min-width: 0;
}

.event-monitor {
    color: var(--text);
    font-size: 14px;
    font-weight: 500;
    text-decoration: none;

    &:hover { color: hsl(142 71% 70%); }
}

.event-status-pill {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border-radius: 999px;
    background: hsl(0 0% 6%);
    border: 1px solid var(--border);
    color: var(--text-faint);

    &.tone-up { background: hsl(142 71% 45% / 0.16); border-color: hsl(142 71% 45% / 0.4); color: hsl(142 71% 75%); }
    &.tone-down { background: hsl(0 84% 60% / 0.16); border-color: hsl(0 84% 60% / 0.45); color: hsl(0 84% 75%); }
    &.tone-pending { background: hsl(38 92% 50% / 0.16); border-color: hsl(38 92% 50% / 0.4); color: hsl(38 92% 70%); }
    &.tone-maintenance { background: hsl(217 91% 60% / 0.16); border-color: hsl(217 91% 60% / 0.4); color: hsl(217 91% 75%); }
}

.event-msg {
    color: var(--text-muted);
    font-size: 13px;
    line-height: 1.4;

    // Wrap long messages without forcing overflow on narrow screens.
    overflow-wrap: anywhere;
}

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 60px 20px;
    background: var(--bg-soft);
    border: 1px dashed var(--border-strong);
    border-radius: 14px;
    text-align: center;

    .empty-icon {
        width: 48px;
        height: 48px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
        background: hsl(142 71% 45% / 0.12);
        color: hsl(142 71% 70%);
        font-size: 18px;
    }

    .empty-title {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: var(--text);
    }

    .empty-sub {
        margin: 0;
        max-width: 50ch;
        color: var(--text-muted);
        font-size: 13px;
        line-height: 1.5;
    }
}

.load-more-wrap {
    display: flex;
    justify-content: center;
    padding: 8px 0 0;
}

.action {
    appearance: none;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 9px 16px;
    border-radius: 8px;
    cursor: pointer;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease;

    &.ghost { background: transparent; }

    &:hover:not(:disabled) {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        color: var(--text);
    }

    &:disabled { opacity: 0.45; cursor: not-allowed; }
}

@media (max-width: 720px) {
    .v2-events { padding: 0 16px 40px; }

    .page-head { flex-direction: column; align-items: stretch; }

    .event-row {
        grid-template-columns: auto 1fr;
        row-gap: 4px;
    }

    .event-dot {
        order: -1;
    }

    .event-time {
        grid-column: 1 / -1;
        order: 2;
        font-size: 11px;
    }

    .event-body {
        grid-column: 1 / -1;
        order: 1;
    }
}
</style>
