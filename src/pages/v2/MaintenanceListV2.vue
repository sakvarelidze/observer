<template>
    <div class="v2-maintenance-list">
        <header class="topbar">
            <router-link to="/dashboard" class="back" title="Back to dashboard">
                <span class="back-arrow">←</span>
                <span class="back-label">dashboard</span>
            </router-link>
            <h1 class="topbar-title">maintenance</h1>
            <div class="topbar-right">
                <MenuTrigger />
            </div>
        </header>

        <main class="main">
            <header class="page-head">
                <div class="page-head-text">
                    <h2 class="page-title">maintenance windows</h2>
                    <p class="page-sub">scheduled or ad-hoc maintenance suppresses alerts and tells visitors a downtime is expected. attach monitors so heartbeats are tagged as "under maintenance" while a window is active.</p>
                </div>
                <router-link to="/maintenance/new" class="action primary">
                    <font-awesome-icon icon="plus" />
                    <span>new window</span>
                </router-link>
            </header>

            <div v-if="loading" class="page-loading">
                <LoaderBars size="md" />
            </div>

            <ul v-else-if="maintenances.length > 0" class="maint-list">
                <li
                    v-for="m in maintenances"
                    :key="m.id"
                    class="maint-row"
                    :class="`tone-${stateOf(m)}`"
                    @click="$router.push(`/maintenance/${m.id}/edit`)"
                >
                    <span class="maint-mark">
                        <font-awesome-icon icon="wrench" />
                    </span>
                    <div class="maint-body">
                        <div class="maint-row-head">
                            <span class="maint-title">{{ m.title || `maintenance #${m.id}` }}</span>
                            <span class="maint-state-pill" :class="`tone-${stateOf(m)}`">
                                <span class="state-dot"></span>
                                <span>{{ stateLabel(m) }}</span>
                            </span>
                            <span class="maint-strategy-pill">{{ strategyLabel(m.strategy) }}</span>
                        </div>
                        <div class="maint-meta">
                            <span v-if="scheduleSummary(m)">{{ scheduleSummary(m) }}</span>
                        </div>
                    </div>
                    <div class="maint-actions" @click.stop>
                        <router-link
                            :to="`/maintenance/${m.id}/edit`"
                            class="row-btn"
                            title="Edit"
                        >
                            <font-awesome-icon icon="pen" />
                        </router-link>
                        <button
                            type="button"
                            class="row-btn danger"
                            title="Delete"
                            @click="askDelete(m)"
                        >
                            <font-awesome-icon icon="trash" />
                        </button>
                    </div>
                </li>
            </ul>

            <div v-else class="empty-state">
                <span class="empty-icon">
                    <font-awesome-icon icon="wrench" />
                </span>
                <p class="empty-title">No maintenance windows yet</p>
                <p class="empty-sub">Schedule one when you're about to deploy, restart, or migrate something — Observer will mute alerts during the window.</p>
                <router-link to="/maintenance/new" class="action primary">
                    <font-awesome-icon icon="plus" />
                    <span>schedule first window</span>
                </router-link>
            </div>
        </main>

        <CommandPalette />

        <ConfirmV2
            :open="!!pendingDelete"
            tone="danger"
            title="delete maintenance"
            confirm-label="delete window"
            busy-label="deleting…"
            :busy="deleteSaving"
            @cancel="cancelDelete"
            @confirm="confirmedDelete"
        >
            Permanently delete <strong>{{ pendingDelete?.title || `maintenance #${pendingDelete?.id}` }}</strong>? Monitor associations are removed too. Already-fired alerts during this window stay where they are.
        </ConfirmV2>
    </div>
</template>

<script>
import dayjs from "dayjs";
import CommandPalette from "./CommandPalette.vue";
import ConfirmV2 from "./ConfirmV2.vue";
import LoaderBars from "./LoaderBars.vue";
import MenuTrigger from "./MenuTrigger.vue";

const STRATEGY_LABEL = {
    manual: "manual",
    single: "one-shot",
    cron: "cron",
    "recurring-interval": "every N days",
    "recurring-weekday": "weekly",
    "recurring-day-of-month": "monthly",
};

export default {
    name: "MaintenanceListV2",
    components: { CommandPalette,
        ConfirmV2,
        LoaderBars,
        MenuTrigger },
    data() {
        return {
            maintenances: [],
            loading: true,
            pendingDelete: null,
            deleteSaving: false,
        };
    },
    mounted() {
        this.fetch();
    },
    methods: {
        async fetch() {
            this.loading = true;
            try {
                const { data } = await this.$root.api.get("/maintenance");
                const list = Array.isArray(data) ? data : (data?.maintenances || []);
                this.maintenances = list.sort((a, b) => {
                    // Active first, then upcoming, then idle, then inactive.
                    const order = { active: 0,
                        upcoming: 1,
                        scheduled: 2,
                        idle: 3,
                        inactive: 4 };
                    const sa = order[this.stateOf(a)] ?? 5;
                    const sb = order[this.stateOf(b)] ?? 5;
                    if (sa !== sb) {
                        return sa - sb;
                    }
                    return (a.title || "").localeCompare(b.title || "");
                });
            } catch (e) {
                console.warn("could not load maintenances", e);
                this.maintenances = [];
            } finally {
                this.loading = false;
            }
        },
        strategyLabel(strategy) {
            return STRATEGY_LABEL[strategy] || strategy || "—";
        },
        stateOf(m) {
            if (m.active === false) {
                return "inactive";
            }
            if (m.strategy === "manual") {
                return "active";
            }
            const range = Array.isArray(m.dateRange) ? m.dateRange : [];
            const now = dayjs();
            if (m.strategy === "single") {
                const start = range[0] ? dayjs(range[0]) : null;
                const end = range[1] ? dayjs(range[1]) : null;
                if (!start || !end) {
                    return "idle";
                }
                if (now.isBefore(start)) {
                    return "upcoming";
                }
                if (now.isAfter(end)) {
                    return "idle";
                }
                return "active";
            }
            // For recurring strategies, just say "scheduled" — full
            // calculation of next-fire would re-implement v1's scheduler.
            if (range.length >= 2) {
                const start = range[0] ? dayjs(range[0]) : null;
                const end = range[1] ? dayjs(range[1]) : null;
                if (start && now.isBefore(start)) {
                    return "upcoming";
                }
                if (end && now.isAfter(end)) {
                    return "idle";
                }
            }
            return "scheduled";
        },
        stateLabel(m) {
            switch (this.stateOf(m)) {
                case "active": return "active now";
                case "upcoming": return "upcoming";
                case "scheduled": return "scheduled";
                case "idle": return "idle";
                case "inactive": return "paused";
                default: return "—";
            }
        },
        scheduleSummary(m) {
            if (m.strategy === "manual") {
                return "manual — toggle on/off whenever needed";
            }
            const range = Array.isArray(m.dateRange) ? m.dateRange : [];
            if (m.strategy === "single") {
                if (range[0] && range[1]) {
                    return `${dayjs(range[0]).format("MMM D, HH:mm")} → ${dayjs(range[1]).format("MMM D, HH:mm")}`;
                }
                return "one-shot (no time set)";
            }
            if (m.strategy === "cron") {
                const dur = m.durationMinutes ? `${m.durationMinutes}m` : "";
                return `cron · ${m.cron || "?"}${dur ? ` · ${dur}` : ""}`;
            }
            if (m.strategy === "recurring-interval") {
                return `every ${m.intervalDay || "?"} day${m.intervalDay === 1 ? "" : "s"} · ${m.durationMinutes || "?"}m`;
            }
            if (m.strategy === "recurring-weekday") {
                const days = (m.weekdays || []).map(d => [ "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat" ][d]).join(", ");
                return `weekly · ${days || "—"} · ${m.startTime || "?"} for ${m.duration || "?"}m`;
            }
            if (m.strategy === "recurring-day-of-month") {
                const days = (m.daysOfMonth || []).join(", ");
                return `monthly · day ${days || "—"} · ${m.startTime || "?"} for ${m.duration || "?"}m`;
            }
            return "";
        },
        askDelete(m) {
            this.pendingDelete = { ...m };
        },
        cancelDelete() {
            if (this.deleteSaving) {
                return;
            }
            this.pendingDelete = null;
        },
        async confirmedDelete() {
            const m = this.pendingDelete;
            if (!m) {
                return;
            }
            this.deleteSaving = true;
            try {
                await this.$root.api.delete(`/maintenance/${m.id}`);
                await this.fetch();
                this.pendingDelete = null;
            } catch (e) {
                console.warn("could not delete maintenance", e);
            } finally {
                this.deleteSaving = false;
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@import "./_base.scss";

.v2-maintenance-list {
    @include v2-surface-tokens;
    @include v2-shell-base;

    background:
        radial-gradient(circle at 12% -10%, hsl(38 92% 50% / 0.05), transparent 60%),
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
    gap: 24px;
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
}

.page-loading {
    display: flex;
    justify-content: center;
    padding: 40px 0;
}

.maint-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.maint-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 12px;
    cursor: pointer;
    transition: background 140ms ease, border-color 140ms ease, transform 140ms ease;

    &:hover {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        transform: translateY(-1px);
    }

    &.tone-active {
        border-color: hsl(38 92% 50% / 0.45);
        background: hsl(38 92% 50% / 0.05);
    }

    &.tone-inactive {
        opacity: 0.65;
    }
}

.maint-mark {
    width: 38px;
    height: 38px;
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 10px;
    background: hsl(38 92% 50% / 0.16);
    color: hsl(38 92% 70%);
    font-size: 14px;
}

.maint-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
}

.maint-row-head {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.maint-title {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--text);
}

.maint-state-pill {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border: 1px solid var(--border);
    background: hsl(0 0% 14%);
    color: var(--text-faint);

    .state-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: hsl(0 0% 38%);
    }

    &.tone-active {
        background: hsl(38 92% 50% / 0.16);
        border-color: hsl(38 92% 50% / 0.45);
        color: hsl(38 92% 70%);

        .state-dot { background: hsl(38 92% 55%); animation: pulse-active 1.6s ease-in-out infinite; }
    }

    &.tone-upcoming {
        background: hsl(217 91% 60% / 0.14);
        border-color: hsl(217 91% 60% / 0.4);
        color: hsl(217 91% 75%);

        .state-dot { background: hsl(217 91% 60%); }
    }

    &.tone-scheduled {
        background: hsl(265 78% 60% / 0.12);
        border-color: hsl(265 78% 60% / 0.4);
        color: hsl(265 78% 75%);

        .state-dot { background: hsl(265 78% 60%); }
    }

    &.tone-idle {
        color: var(--text-faint);
    }
}

@keyframes pulse-active {
    0%, 100% { box-shadow: 0 0 0 0 hsl(38 92% 50% / 0.6); }
    50% { box-shadow: 0 0 0 4px hsl(38 92% 50% / 0); }
}

.maint-strategy-pill {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-faint);
    padding: 2px 7px;
    border-radius: 4px;
    background: hsl(0 0% 6%);
    border: 1px solid var(--border);
}

.maint-meta {
    font-size: 11.5px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;
}

.maint-actions {
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.row-btn {
    appearance: none;
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    width: 32px;
    height: 32px;
    border-radius: 7px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    text-decoration: none;
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease;

    &:hover {
        background: var(--bg-hover);
        color: var(--text);
        border-color: var(--border);
    }

    &.danger:hover {
        background: hsl(0 84% 60% / 0.12);
        color: hsl(0 84% 70%);
        border-color: hsl(0 84% 60% / 0.4);
    }
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
        background: hsl(38 92% 50% / 0.12);
        color: hsl(38 92% 70%);
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
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease, transform 140ms ease;

    &:hover:not(:disabled) {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        color: var(--text);
    }

    &.primary {
        background: hsl(142 71% 45% / 0.18);
        border-color: hsl(142 71% 45% / 0.5);
        color: hsl(142 71% 70%);

        &:hover:not(:disabled) {
            background: hsl(142 71% 45% / 0.28);
            border-color: hsl(142 71% 45% / 0.75);
            color: hsl(142 71% 80%);
            transform: translateY(-1px);
        }
    }
}

@media (max-width: 640px) {
    .v2-maintenance-list { padding: 0 16px 40px; }

    .page-head {
        flex-direction: column;
        align-items: stretch;
    }

    .maint-row { flex-wrap: wrap; }
    .maint-actions { width: 100%; justify-content: flex-end; }
}
</style>
