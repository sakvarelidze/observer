<template>
    <section class="incident-timeline">
        <header class="incident-head">
            <div class="incident-titles">
                <h3 class="incident-title">past incidents</h3>
                <span class="incident-summary" :class="{ muted: !incidents.length }">
                    {{ summaryText }}
                </span>
            </div>
            <div class="incident-periods" role="tablist">
                <button
                    v-for="p in periods"
                    :key="p"
                    type="button"
                    class="incident-period"
                    :class="{ active: period === p }"
                    role="tab"
                    :aria-selected="period === p"
                    @click="setPeriod(p)"
                >{{ p }}</button>
            </div>
        </header>

        <div v-if="loading" class="incident-loading">
            <LoaderBars size="sm" />
        </div>

        <ul v-else-if="incidents.length > 0" class="incident-list">
            <li
                v-for="inc in incidents"
                :key="inc.startedAt"
                class="incident"
                :class="{ ongoing: inc.ongoing }"
            >
                <span class="incident-dot"></span>
                <div class="incident-body">
                    <div class="incident-row">
                        <span class="incident-pill" :class="{ ongoing: inc.ongoing }">
                            {{ inc.ongoing ? "ONGOING" : "DOWN" }}
                        </span>
                        <span class="incident-duration">
                            {{ formatDuration(inc.ongoing ? liveDuration(inc) : inc.durationSeconds) }}
                        </span>
                        <span class="incident-meta">
                            <span :title="absoluteTime(inc.startedAt)">{{ relativeTime(inc.startedAt) }}</span>
                            <template v-if="inc.probeCount > 1">
                                <span class="incident-sep">·</span>
                                <span>{{ inc.probeCount }} probes</span>
                            </template>
                        </span>
                    </div>
                    <p v-if="inc.msg" class="incident-msg">{{ humanizeStatusMessage(inc.msg) }}</p>
                </div>
            </li>
        </ul>

        <div v-else class="incident-empty">
            <span class="empty-line"></span>
            <span>no incidents in this window</span>
            <span class="empty-line"></span>
        </div>
    </section>
</template>

<script>
import dayjs from "dayjs";
import { humanizeStatusMessage } from "../../util-frontend";
import LoaderBars from "./LoaderBars.vue";

export default {
    name: "IncidentTimeline",
    components: { LoaderBars },
    props: {
        monitorId: { type: Number,
            required: true },
    },
    data() {
        return {
            period: "30d",
            periods: [ "7d", "30d", "90d" ],
            loading: true,
            incidents: [],
            summary: { count: 0,
                ongoing: false,
                totalDowntimeSeconds: 0 },
            inFlight: 0,
            tickRender: 0,
            tickHandle: null,
            refreshHandle: null,
            refreshIntervalMs: 60000,
        };
    },
    computed: {
        summaryText() {
            void this.tickRender; // recompute every second so live durations stay fresh
            if (!this.incidents.length) {
                return "no incidents in this window";
            }
            const total = this.summary.totalDowntimeSeconds || 0;
            const n = this.incidents.length;
            const noun = n === 1 ? "incident" : "incidents";
            const totalLabel = total > 0 ? ` · ${this.formatDuration(total)} total` : "";
            const ongoing = this.summary.ongoing ? " · 1 ongoing" : "";
            return `${n} ${noun}${totalLabel}${ongoing}`;
        },
    },
    watch: {
        monitorId: {
            immediate: true,
            handler() { this.fetch(); },
        },
    },
    mounted() {
        // 1s tick keeps "ongoing" durations updating in real time.
        this.tickHandle = setInterval(() => {
            this.tickRender++;
        }, 1000);
        // Periodic re-fetch picks up new incidents and closes ongoing ones.
        this.refreshHandle = setInterval(() => {
            if (!document.hidden) {
                this.fetch({ silent: true });
            }
        }, this.refreshIntervalMs);
        document.addEventListener("visibilitychange", this.onVisibilityChange);
    },
    beforeUnmount() {
        clearInterval(this.tickHandle);
        clearInterval(this.refreshHandle);
        document.removeEventListener("visibilitychange", this.onVisibilityChange);
    },
    methods: {
        setPeriod(p) {
            if (p === this.period) {
                return;
            }
            this.period = p;
            this.fetch();
        },
        onVisibilityChange() {
            if (!document.hidden) {
                this.fetch({ silent: true });
            }
        },
        async fetch({ silent = false } = {}) {
            const id = ++this.inFlight;
            if (!silent) {
                this.loading = true;
            }
            try {
                const { data } = await this.$root.api.get(
                    `/monitors/${this.monitorId}/incidents`,
                    { params: { period: this.period } },
                );
                if (id !== this.inFlight) {
                    return;
                }
                if (data?.ok) {
                    this.incidents = data.incidents || [];
                    this.summary = data.summary || { count: 0,
                        ongoing: false,
                        totalDowntimeSeconds: 0 };
                }
            } catch (e) {
                if (id !== this.inFlight) {
                    return;
                }
                if (!silent) {
                    console.warn("Failed to load incidents", e);
                    this.incidents = [];
                }
            } finally {
                if (id === this.inFlight && !silent) {
                    this.loading = false;
                }
            }
        },
        liveDuration(inc) {
            // For ongoing incidents, recompute now-vs-start every second
            // (the tickRender getter dependency in summaryText keeps this
            // reactive on the parent template).
            void this.tickRender;
            const startMs = dayjs.utc(inc.startedAt).valueOf();
            return Math.max(0, Math.round((Date.now() - startMs) / 1000));
        },
        formatDuration(seconds) {
            const s = Math.max(0, Math.round(seconds));
            if (s < 60) {
                return `${s}s`;
            }
            const m = Math.floor(s / 60);
            const remS = s % 60;
            if (m < 60) {
                return remS ? `${m}m ${remS}s` : `${m}m`;
            }
            const h = Math.floor(m / 60);
            const remM = m % 60;
            if (h < 24) {
                return remM ? `${h}h ${remM}m` : `${h}h`;
            }
            const d = Math.floor(h / 24);
            const remH = h % 24;
            return remH ? `${d}d ${remH}h` : `${d}d`;
        },
        relativeTime(iso) {
            void this.tickRender;
            const t = dayjs.utc(iso);
            const diffSec = Math.max(0, Math.round((Date.now() - t.valueOf()) / 1000));
            if (diffSec < 60) {
                return `${diffSec}s ago`;
            }
            const diffMin = Math.round(diffSec / 60);
            if (diffMin < 60) {
                return `${diffMin}m ago`;
            }
            const diffHr = Math.round(diffMin / 60);
            if (diffHr < 24) {
                return `${diffHr}h ago`;
            }
            const diffDay = Math.round(diffHr / 24);
            return `${diffDay}d ago`;
        },
        absoluteTime(iso) {
            return dayjs.utc(iso).local().format("D MMM YYYY HH:mm:ss");
        },
        humanizeStatusMessage,
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.incident-timeline {
    @include v2-surface-tokens;
    margin-bottom: 32px;
    color: var(--text);
    animation: v2-up 360ms var(--enter-ease) both;
    animation-delay: 460ms;
}

.incident-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 12px;
}

.incident-titles {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
}

.incident-title {
    margin: 0;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-faint);
    font-weight: 500;
}

.incident-summary {
    font-size: 12px;
    color: var(--text-muted);
    font-variant-numeric: tabular-nums;

    &.muted { color: var(--text-faint); }
}

.incident-periods {
    display: inline-flex;
    gap: 2px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 2px;
    flex: none;
}

.incident-period {
    appearance: none;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-family: inherit;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 4px 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 120ms ease, color 120ms ease;

    &:hover { color: var(--text); }
    &.active {
        background: hsl(0 84% 60% / 0.15);
        color: hsl(0 84% 78%);
    }
}

.incident-loading,
.incident-empty {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    color: var(--text-faint);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;

    .empty-line {
        flex: 1;
        height: 1px;
        background: var(--border);
    }
}

.incident-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.incident {
    position: relative;
    display: flex;
    gap: 14px;
    align-items: flex-start;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-left: 3px solid hsl(0 84% 60%);
    border-radius: 10px;
    padding: 12px 14px;
    transition: background 140ms ease, border-color 140ms ease;

    &:hover {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        border-left-color: hsl(0 84% 60%);
    }

    &.ongoing {
        border-left-color: hsl(38 92% 50%);

        &:hover {
            border-left-color: hsl(38 92% 50%);
        }
    }
}

.incident-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: hsl(0 84% 60%);
    margin-top: 7px;
    flex: none;

    .incident.ongoing & {
        background: hsl(38 92% 50%);
        box-shadow: 0 0 0 0 hsl(38 92% 50% / 0.6);
        animation: incident-pulse 1600ms ease-in-out infinite;
    }
}

@keyframes incident-pulse {
    0%, 100% { box-shadow: 0 0 0 0 hsl(38 92% 50% / 0.5); }
    50% { box-shadow: 0 0 0 6px hsl(38 92% 50% / 0); }
}

.incident-body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.incident-row {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
    font-variant-numeric: tabular-nums;
}

.incident-pill {
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    background: hsl(0 84% 60% / 0.15);
    border: 1px solid hsl(0 84% 60% / 0.45);
    color: hsl(0 84% 78%);
    padding: 2px 8px;
    border-radius: 4px;
    flex: none;

    &.ongoing {
        background: hsl(38 92% 50% / 0.15);
        border-color: hsl(38 92% 50% / 0.55);
        color: hsl(38 92% 75%);
    }
}

.incident-duration {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
}

.incident-meta {
    font-size: 11px;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

.incident-sep {
    margin: 0 4px;
    opacity: 0.5;
}

.incident-msg {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.45;
    white-space: pre-wrap;
    word-break: break-word;
}
</style>
