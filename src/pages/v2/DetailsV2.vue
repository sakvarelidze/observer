<template>
    <div v-if="monitor" class="v2-details" :class="`status-${statusKey}`">
        <header class="topbar">
            <router-link to="/dashboard" class="back" title="Back to dashboard">
                <span class="back-arrow">←</span>
                <span class="back-label">all monitors</span>
            </router-link>

            <div class="actions">
                <MenuTrigger />
                <button
                    type="button"
                    class="action"
                    title="Get an embeddable uptime badge"
                    @click="showBadge = true"
                >
                    share
                </button>
                <button
                    v-if="monitor.active"
                    type="button"
                    class="action"
                    @click="onPause"
                >
                    pause
                </button>
                <button
                    v-else
                    type="button"
                    class="action accent"
                    :disabled="monitor.forceInactive"
                    @click="onResume"
                >
                    resume
                </button>
                <router-link :to="editPath" class="action">
                    edit
                </router-link>
                <router-link
                    v-if="canClone"
                    :to="clonePath"
                    class="action"
                    title="Create a new monitor pre-filled from this one"
                >
                    clone
                </router-link>
                <button type="button" class="action danger" @click="onDelete">
                    delete
                </button>
            </div>
        </header>

        <section class="hero">
            <div class="hero-name-block">
                <h1 class="hero-name">{{ monitor.name }}</h1>
                <p v-if="monitor.description" class="hero-description">
                    {{ monitor.description }}
                </p>
                <p class="hero-address">
                    <span class="address-type">{{ monitor.type }}</span>
                    <span class="address-divider">·</span>
                    <a
                        v-if="addressIsLink"
                        :href="addressHref"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="address-link"
                    >{{ addressText }}</a>
                    <span v-else>{{ addressText }}</span>
                </p>
            </div>

            <div class="hero-status">
                <span class="hero-status-row">
                    <span class="status-dot" :class="{ pulsing }"></span>
                    <span class="status-word">{{ statusWord }}</span>
                </span>
                <span class="hero-status-meta">
                    {{ lastCheckedText }}
                </span>
                <span class="hero-status-countdown">
                    {{ countdownText }}
                </span>
            </div>
        </section>

        <section class="hero-bar">
            <HeartbeatBar :monitor-id="monitor.id" />
            <div class="hero-bar-foot">
                <span>checks every {{ monitor.interval }}s</span>
                <span>{{ beatCount }} beats loaded</span>
            </div>
        </section>

        <section class="stat-strip">
            <div
                v-for="s in statPills"
                :key="s.key"
                class="stat-pill"
                :class="[{ accent: s.accent }, s.tone ? `tone-${s.tone}` : '']"
                :title="s.tooltip || ''"
            >
                <span class="stat-value">{{ s.value }}</span>
                <span class="stat-label">{{ s.label }}</span>
            </div>
        </section>

        <section class="chart-strip">
            <PingChart :monitor-id="monitor.id" />
            <UptimeChart :monitor-id="monitor.id" />
        </section>

        <section class="events">
            <header class="events-header">
                <h2>recent events</h2>
                <span class="events-count">{{ recentEvents.length }} shown</span>
            </header>
            <div v-if="recentEvents.length > 0" class="events-strip">
                <div
                    v-for="e in recentEvents"
                    :key="e.time"
                    class="event-card"
                    :class="`event-${eventKey(e.status)}`"
                    :title="humanizeStatusMessage(e.msg)"
                >
                    <span class="event-dot"></span>
                    <span class="event-status">{{ eventKey(e.status) }}</span>
                    <span class="event-time">{{ relative(e.time) }}</span>
                    <span v-if="e.msg" class="event-msg">{{ humanizeStatusMessage(e.msg) }}</span>
                </div>
            </div>
            <div v-else class="events-empty">
                <span class="empty-line"></span>
                <span>No events yet</span>
                <span class="empty-line"></span>
            </div>
        </section>

        <IncidentTimeline :monitor-id="monitor.id" />
    </div>

    <div v-else class="loading-shell">
        <LoaderBars size="md" />
        <p>Loading monitor…</p>
    </div>

    <CommandPalette />

    <ConfirmV2
        :open="!!confirmAction"
        :tone="confirmAction?.tone || 'primary'"
        :title="confirmAction?.title || ''"
        :body="confirmAction?.body || ''"
        :confirm-label="confirmAction?.confirmLabel || 'confirm'"
        :busy="!!confirmAction?.busy"
        @cancel="cancelConfirm"
        @confirm="runConfirm"
    />

    <BadgeEmbed
        v-if="monitor"
        :open="showBadge"
        :monitor-id="monitor.id"
        @close="showBadge = false"
    />
</template>

<script>
import dayjs from "dayjs";
import { humanizeStatusMessage } from "../../util-frontend";
import HeartbeatBar from "../../components/HeartbeatBar.vue";
import CommandPalette from "./CommandPalette.vue";
import ConfirmV2 from "./ConfirmV2.vue";
import LoaderBars from "./LoaderBars.vue";
import MenuTrigger from "./MenuTrigger.vue";
import BadgeEmbed from "./BadgeEmbed.vue";
import IncidentTimeline from "./IncidentTimeline.vue";
import PingChart from "./PingChart.vue";
import UptimeChart from "./UptimeChart.vue";

const STATUS_WORD = {
    1: "up",
    0: "down",
    2: "pending",
    3: "maintenance",
};

const V2_EDITABLE_TYPES = new Set([ "http", "port", "ping", "push" ]);

export default {
    name: "DetailsV2",
    components: { BadgeEmbed,
        CommandPalette,
        ConfirmV2,
        HeartbeatBar,
        IncidentTimeline,
        LoaderBars,
        MenuTrigger,
        PingChart,
        UptimeChart },
    data() {
        return {
            now: Math.floor(Date.now() / 1000),
            tickHandle: null,
            recentEvents: [],
            pulsing: false,
            pulseTimer: null,
            tickRender: 0,
            confirmAction: null,
            showBadge: false,
        };
    },
    computed: {
        monitor() {
            const id = Number(this.$route.params.id);
            return this.$root.monitorList?.[id] || null;
        },
        lastBeat() {
            if (!this.monitor) {
                return null;
            }
            return this.$root.lastHeartbeatList?.[this.monitor.id] || null;
        },
        statusKey() {
            if (!this.monitor) {
                return "unknown";
            }
            if (!this.monitor.active) {
                return "paused";
            }
            if (!this.lastBeat) {
                return "unknown";
            }
            return STATUS_WORD[this.lastBeat.status] || "unknown";
        },
        statusWord() {
            return this.statusKey;
        },
        addressText() {
            const m = this.monitor;
            if (!m) {
                return "";
            }
            switch (m.type) {
                case "http":
                case "keyword":
                case "json-query":
                case "real-browser":
                    return this.censor(m.url);
                case "port":
                    return `${m.hostname}:${m.port}`;
                case "ping":
                case "dns":
                    return m.hostname;
                case "push":
                    return "(push)";
                case "grpc-keyword":
                    return this.censor(m.grpcUrl);
                case "mongodb":
                case "mysql":
                case "postgres":
                case "redis":
                case "sqlserver":
                    return this.censor(m.databaseConnectionString);
                case "steam":
                    return `${m.hostname}:${m.port}`;
                default:
                    return m.url || m.hostname || "";
            }
        },
        editPath() {
            if (!this.monitor) {
                return "/dashboard";
            }
            return `/dashboard/${this.monitor.id}/edit`;
        },
        canClone() {
            return !!(this.monitor && V2_EDITABLE_TYPES.has(this.monitor.type));
        },
        clonePath() {
            return this.monitor ? `/add?clone=${this.monitor.id}` : "/add";
        },
        addressIsLink() {
            const m = this.monitor;
            return m && (m.type === "http" || m.type === "keyword" || m.type === "json-query" || m.type === "real-browser");
        },
        addressHref() {
            return this.monitor?.url || "";
        },
        statPills() {
            const m = this.monitor;
            if (!m) {
                return [];
            }
            const pills = [];
            const last = this.lastBeat;

            if (last && last.ping != null) {
                pills.push({
                    key: "ping",
                    value: `${Math.round(last.ping)}ms`,
                    label: "current",
                });
            } else {
                pills.push({
                    key: "ping",
                    value: "—",
                    label: "current",
                });
            }

            const avg = this.$root.avgPingList?.[m.id];
            pills.push({
                key: "avgPing",
                value: avg != null ? `${Math.round(avg)}ms` : "—",
                label: "avg 24h",
            });

            const u = this.$root.uptimeList || {};
            pills.push({
                key: "u24",
                value: this.formatUptime(u[`${m.id}_24`]),
                label: "uptime 24h",
                accent: true,
            });
            pills.push({
                key: "u30",
                value: this.formatUptime(u[`${m.id}_720`]),
                label: "uptime 30d",
            });
            pills.push({
                key: "u1y",
                value: this.formatUptime(u[`${m.id}_1y`]),
                label: "uptime 1y",
            });

            const tls = this.$root.tlsInfoList?.[m.id]?.certInfo;
            if (tls && tls.daysRemaining != null) {
                const days = tls.daysRemaining;
                const threshold = m.cert_expiry_threshold_days ?? 14;
                let tone = "cert-ok";
                if (days < 0) {
                    tone = "cert-expired";
                } else if (days <= threshold) {
                    tone = "cert-warn";
                }
                const value = days < 0
                    ? "expired"
                    : `${days} ${days === 1 ? "day" : "days"}`;
                const tooltip = tls.validTo
                    ? `Valid until ${new Date(tls.validTo).toLocaleString()}`
                    : null;
                pills.push({
                    key: "cert",
                    value,
                    label: "cert exp.",
                    tone,
                    tooltip,
                });
            }

            return pills;
        },
        beatCount() {
            const m = this.monitor;
            if (!m) {
                return 0;
            }
            return (this.$root.heartbeatList?.[m.id] || []).length;
        },
        countdownText() {
            const m = this.monitor;
            // Touch tickRender so this recomputes on the 1s tick.
            void this.tickRender;
            if (!m) {
                return "";
            }
            if (!m.active) {
                return "monitor paused";
            }
            if (!this.lastBeat) {
                return "waiting for first beat…";
            }
            const lastUnix = dayjs.utc(this.lastBeat.time).valueOf() / 1000;
            const interval = Math.max(m.interval || 60, 1);
            const remain = Math.round((lastUnix + interval) - this.now);
            if (remain <= 0) {
                return "checking now…";
            }
            return `next check in ${this.formatRemain(remain)}`;
        },
        lastCheckedText() {
            void this.tickRender;
            if (!this.lastBeat) {
                return "no beats yet";
            }
            const sec = Math.max(0, this.now - dayjs.utc(this.lastBeat.time).valueOf() / 1000);
            return `last check ${this.formatRelative(Math.round(sec))} ago`;
        },
    },
    watch: {
        "lastBeat.time"(newVal, oldVal) {
            if (newVal && oldVal && newVal !== oldVal) {
                this.pulsing = true;
                clearTimeout(this.pulseTimer);
                this.pulseTimer = setTimeout(() => {
                    this.pulsing = false;
                }, 360);
            }
        },
        "monitor.id": {
            immediate: true,
            handler(newId) {
                if (newId != null) {
                    this.loadRecentEvents();
                    this.ensureCoverage();
                    this.fetchTLSSummary();
                    this.fetchUptime();
                }
            },
        },
    },
    mounted() {
        this.tickHandle = setInterval(() => {
            this.now = Math.floor(Date.now() / 1000);
            this.tickRender++;
        }, 1000);

        this.$root.emitter?.on?.("newImportantHeartbeat", this.onNewImportant);
    },
    beforeUnmount() {
        clearInterval(this.tickHandle);
        clearTimeout(this.pulseTimer);
        this.$root.emitter?.off?.("newImportantHeartbeat", this.onNewImportant);
    },
    methods: {
        humanizeStatusMessage,
        formatUptime(value) {
            if (value == null) {
                return "—";
            }
            return `${Number(value).toFixed(2)}%`;
        },
        formatRemain(sec) {
            if (sec >= 3600) {
                return `${Math.round(sec / 3600)}h`;
            }
            if (sec >= 120) {
                return `${Math.round(sec / 60)}m`;
            }
            return `${sec}s`;
        },
        formatRelative(sec) {
            if (sec < 60) {
                return `${sec}s`;
            }
            if (sec < 3600) {
                return `${Math.round(sec / 60)}m`;
            }
            if (sec < 86400) {
                return `${Math.round(sec / 3600)}h`;
            }
            return `${Math.round(sec / 86400)}d`;
        },
        relative(timeStr) {
            const sec = Math.max(0, this.now - dayjs.utc(timeStr).valueOf() / 1000);
            return `${this.formatRelative(Math.round(sec))} ago`;
        },
        eventKey(status) {
            return STATUS_WORD[status] || "unknown";
        },
        censor(s) {
            if (!s) {
                return "";
            }
            try {
                const u = new URL(s);
                if (u.password) {
                    u.password = "******";
                }
                return u.toString();
            } catch (e) {
                return s.replace(/Password=([^;]+);/ig, "Password=******;");
            }
        },
        async fetchUptime() {
            // The dashboard poll only carries the 24h window (computing
            // 30d/1y for every monitor on every poll was the source of the
            // slow loads). Fetch the longer windows for just this monitor
            // on demand and merge them into the shared uptimeList.
            const m = this.monitor;
            if (!m || !Number.isInteger(m.id)) {
                return;
            }
            try {
                const { data } = await this.$root.api.get(
                    `/monitors/${m.id}/uptime`,
                    { params: { windows: "24,720,1y" } },
                );
                if (data?.ok && data.uptimeList) {
                    this.$root.uptimeList = {
                        ...this.$root.uptimeList,
                        ...data.uptimeList,
                    };
                }
            } catch (e) {
                console.warn("Failed to load monitor uptime", e);
            }
        },
        async loadRecentEvents() {
            const m = this.monitor;
            if (!m || !Number.isInteger(m.id)) {
                return;
            }
            try {
                const { data } = await this.$root.api.get(
                    `/monitors/${m.id}/heartbeats`,
                    { params: { offset: 0,
                        limit: 20 } },
                );
                if (data?.ok && Array.isArray(data.data)) {
                    this.recentEvents = data.data;
                }
            } catch (e) {
                console.warn("Failed to load recent events", e);
            }
        },
        async ensureCoverage() {
            if (!this.monitor?.id) {
                return;
            }
            if (typeof this.$root.ensureHeartbeatCoverage !== "function") {
                return;
            }
            try {
                await this.$root.ensureHeartbeatCoverage(this.monitor.id, 24);
            } catch (e) {
                console.warn("Cannot ensure coverage for v2 details", e);
            }
        },
        fetchTLSSummary() {
            const m = this.monitor;
            if (!m?.id) {
                return;
            }
            this.$root.api
                .get(`/monitors/${m.id}/tls-summary`)
                .then(({ data }) => {
                    if (data?.ok) {
                        const days = data.certInfo?.daysRemaining ?? null;
                        this.$root.tlsInfoList[m.id] = {
                            valid: !!data.valid,
                            certInfo: {
                                daysRemaining: days,
                                validTo: data.certInfo?.validTo || null,
                            },
                        };
                    }
                })
                .catch(() => {});
        },
        onNewImportant(beat) {
            if (!this.monitor || beat?.monitorID !== this.monitor.id) {
                return;
            }
            this.recentEvents = [ beat, ...this.recentEvents ].slice(0, 20);
        },
        onPause() {
            this.confirmAction = {
                kind: "pause",
                title: "pause monitor",
                body: `Stop probing "${this.monitor.name}"? Heartbeats won't fire until you resume it.`,
                confirmLabel: "pause monitor",
                tone: "danger",
                busy: false,
            };
        },
        async onResume() {
            try {
                const { data } = await this.$root.api.post(`/monitors/${this.monitor.id}/resume`);
                if (data?.ok) {
                    this.$root.monitorList[this.monitor.id].active = true;
                }
            } catch (e) {
                console.error("resume failed", e);
            }
        },
        onDelete() {
            this.confirmAction = {
                kind: "delete",
                title: "delete monitor",
                body: `Permanently delete "${this.monitor.name}" and all its heartbeats? This can't be undone.`,
                confirmLabel: "delete monitor",
                tone: "danger",
                busy: false,
            };
        },
        cancelConfirm() {
            if (this.confirmAction?.busy) {
                return;
            }
            this.confirmAction = null;
        },
        async runConfirm() {
            if (!this.confirmAction || this.confirmAction.busy) {
                return;
            }
            this.confirmAction.busy = true;
            try {
                if (this.confirmAction.kind === "pause") {
                    const { data } = await this.$root.api.post(`/monitors/${this.monitor.id}/pause`);
                    if (data?.ok) {
                        this.$root.monitorList[this.monitor.id].active = false;
                    }
                    this.confirmAction = null;
                } else if (this.confirmAction.kind === "delete") {
                    const id = this.monitor.id;
                    const { data } = await this.$root.api.delete(`/monitors/${id}`);
                    if (data?.ok) {
                        delete this.$root.monitorList[id];
                        delete this.$root.lastHeartbeatList[id];
                        delete this.$root.heartbeatList[id];
                        delete this.$root.dashboardHeartbeatList[id];
                        this.confirmAction = null;
                        this.$router.push("/dashboard");
                        return;
                    }
                }
            } catch (e) {
                console.error("confirm action failed", e);
                if (this.confirmAction) {
                    this.confirmAction.busy = false;
                }
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.v2-details {
    @include v2-surface-tokens;
    @include v2-shell-base;
    // Soft background tint (0.18 alpha) — different role from the bold
    // glow used on dot pulses, so we override the mixin default.
    @include v2-status-tokens(0.18);

    background:
        radial-gradient(circle at 0% 0%, var(--status-glow), transparent 55%),
        radial-gradient(circle at 100% -10%, var(--shell-tint), transparent 65%),
        var(--bg);
    padding: 0 32px 48px;
    transition: background 240ms ease;
    animation: v2-fade-in 320ms var(--enter-ease) both;
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

    .back-arrow {
        font-size: 14px;
        line-height: 1;
        transform: translateX(0);
        transition: transform 200ms cubic-bezier(0.2, 0.8, 0.2, 1);
    }

    &:hover .back-arrow {
        transform: translateX(-3px);
    }
}

.actions {
    grid-column: 3;
    display: inline-flex;
    gap: 4px;

    .action {
        appearance: none;
        background: var(--bg-soft);
        border: 1px solid var(--border);
        color: var(--text-muted);
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 7px 12px;
        border-radius: 8px;
        cursor: pointer;
        text-decoration: none;
        transition: background 140ms ease, color 140ms ease, border-color 140ms ease;

        &:hover {
            background: var(--bg-hover);
            border-color: var(--border-strong);
            color: var(--text);
        }

        &.accent {
            background: hsl(142 71% 45% / 0.14);
            border-color: hsl(142 71% 45% / 0.45);
            color: hsl(142 71% 65%);

            &:hover {
                background: hsl(142 71% 45% / 0.22);
                border-color: hsl(142 71% 45% / 0.7);
                color: hsl(142 71% 75%);
            }
        }

        &.danger:hover {
            background: hsl(0 84% 60% / 0.12);
            border-color: hsl(0 84% 60% / 0.45);
            color: hsl(0 84% 70%);
        }

        &:disabled {
            opacity: 0.45;
            cursor: not-allowed;
        }
    }
}

.hero {
    display: grid;
    grid-template-columns: 1fr auto;
    align-items: end;
    gap: 32px;
    padding: 24px 0 16px;
}

.hero-name-block {
    min-width: 0;
}

.hero-name {
    font-size: clamp(28px, 4.5vw, 44px);
    font-weight: 600;
    letter-spacing: -0.02em;
    line-height: 1.05;
    margin: 0 0 6px;
    color: var(--text);
    overflow-wrap: anywhere;
}

.hero-description {
    margin: 4px 0 8px;
    color: var(--text-muted);
    font-size: 13px;
    max-width: 70ch;
}

.hero-address {
    margin: 0;
    font-size: 12px;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-variant-numeric: tabular-nums;

    .address-type {
        color: var(--text-muted);
        text-transform: uppercase;
    }

    .address-divider {
        margin: 0 8px;
        opacity: 0.5;
    }

    .address-link {
        color: var(--text-muted);
        text-decoration: none;
        text-transform: none;
        letter-spacing: 0;
        transition: color 140ms ease;

        &:hover {
            color: var(--text);
            text-decoration: underline;
            text-decoration-color: var(--status);
        }
    }
}

.hero-status {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
    text-align: right;
    font-variant-numeric: tabular-nums;
}

.hero-status-row {
    display: inline-flex;
    align-items: center;
    gap: 12px;
}

.status-dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--status);
    box-shadow: 0 0 0 0 var(--status-glow);
    transition: box-shadow 220ms ease;

    &.pulsing {
        animation: v2-status-pulse 360ms $v2-ease;
    }
}

.status-word {
    font-size: clamp(28px, 3.5vw, 40px);
    font-weight: 600;
    letter-spacing: -0.02em;
    text-transform: uppercase;
    color: var(--status);
    line-height: 1;
}

.hero-status-meta,
.hero-status-countdown {
    font-size: 11px;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

.hero-status-countdown {
    color: var(--text-muted);
}

.hero-bar {
    margin: 8px 0 24px;
    padding: 18px 20px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 14px;

    .hero-bar-foot {
        display: flex;
        justify-content: space-between;
        margin-top: 10px;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-faint);
        font-variant-numeric: tabular-nums;
    }
}

.stat-strip {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 8px;
    margin-bottom: 24px;
}

.chart-strip {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    gap: 12px;
    margin-bottom: 32px;
}

@media (max-width: 900px) {
    .chart-strip {
        grid-template-columns: 1fr;
    }
}

.stat-pill {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 14px 16px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 12px;
    transition: border-color 180ms ease, background 180ms ease;

    &:hover {
        border-color: var(--border-strong);
        background: var(--bg-hover);
    }

    &.accent {
        border-color: var(--border-strong);
    }

    .stat-value {
        font-size: 22px;
        font-weight: 600;
        letter-spacing: -0.02em;
        font-variant-numeric: tabular-nums;
        color: var(--text);
        line-height: 1;
    }

    &.accent .stat-value {
        color: var(--status);
    }

    // Cert-expiry pill colors. Border tint + value color move together so
    // an expiring cert reads at a glance from a screenful of stat boxes.
    &.tone-cert-ok {
        border-color: hsl(142 71% 30%);

        .stat-value {
            color: hsl(142 71% 55%);
        }
    }

    &.tone-cert-warn {
        border-color: hsl(38 92% 35%);

        .stat-value {
            color: hsl(38 92% 60%);
        }
    }

    &.tone-cert-expired {
        border-color: hsl(0 84% 40%);

        .stat-value {
            color: hsl(0 84% 65%);
        }
    }

    .stat-label {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-faint);
    }
}

.events {
    margin-top: 8px;
    margin-bottom: 32px;

    .events-header {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        margin-bottom: 12px;

        h2 {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            color: var(--text-faint);
            font-weight: 500;
            margin: 0;
        }

        .events-count {
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-faint);
            font-variant-numeric: tabular-nums;
        }
    }
}

.events-strip {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 6px;
    scrollbar-width: thin;
    scrollbar-color: var(--border-strong) transparent;

    &::-webkit-scrollbar {
        height: 6px;
    }
    &::-webkit-scrollbar-thumb {
        background: var(--border-strong);
        border-radius: 3px;
    }
}

.event-card {
    --event-color: var(--text-faint);

    flex: none;
    min-width: 140px;
    max-width: 240px;
    padding: 10px 12px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-left: 2px solid var(--event-color);
    border-radius: 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-variant-numeric: tabular-nums;
    transition: background 140ms ease, border-color 140ms ease;

    &:hover {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        border-left-color: var(--event-color);
    }

    &.event-up { --event-color: hsl(142 71% 45%); }
    &.event-down { --event-color: hsl(0 84% 60%); }
    &.event-pending { --event-color: hsl(38 92% 50%); }
    &.event-maintenance { --event-color: hsl(217 91% 60%); }

    .event-dot {
        width: 6px;
        height: 6px;
        border-radius: 50%;
        background: var(--event-color);
    }

    .event-status {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--event-color);
        font-weight: 600;
    }

    .event-time {
        font-size: 10px;
        color: var(--text-faint);
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .event-msg {
        font-size: 11px;
        color: var(--text-muted);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
}

.events-empty {
    display: flex;
    align-items: center;
    gap: 12px;
    color: var(--text-faint);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 14px 0;

    .empty-line {
        flex: 1;
        height: 1px;
        background: var(--border);
    }
}

.loading-shell {
    min-height: 60vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 20px;
    background: var(--bg);
    color: var(--text-muted);
}

/*
 * Staged entrance — the detail view blooms out of the dashboard tile click.
 * Total wall-clock under ~700ms; per-element animations stay short so the
 * page is interactive almost immediately while the cascade is still
 * finishing. Keyframes are imported from _base.scss.
 */

.topbar {
    animation: v2-down 260ms var(--enter-ease) both;
    animation-delay: 40ms;
}

.hero-name-block {
    animation: v2-up 360ms var(--enter-ease) both;
    animation-delay: 90ms;
}

.hero-status {
    animation: v2-up 360ms var(--enter-ease) both;
    animation-delay: 130ms;
}

.hero-bar {
    animation: v2-rise 380ms var(--enter-ease) both;
    animation-delay: 160ms;
    transform-origin: top center;
}

.stat-pill {
    animation: v2-rise 320ms var(--enter-ease) both;
    animation-delay: 220ms;

    &:nth-child(2) { animation-delay: 250ms; }
    &:nth-child(3) { animation-delay: 280ms; }
    &:nth-child(4) { animation-delay: 310ms; }
    &:nth-child(5) { animation-delay: 340ms; }
    &:nth-child(6) { animation-delay: 370ms; }
}

.chart-strip {
    animation: v2-rise 380ms var(--enter-ease) both;
    animation-delay: 360ms;
}

.events {
    animation: v2-up 360ms var(--enter-ease) both;
    animation-delay: 420ms;
}

@media (prefers-reduced-motion: reduce) {
    .v2-details,
    .topbar,
    .hero-name-block,
    .hero-status,
    .hero-bar,
    .stat-pill,
    .events {
        animation: none;
    }
}

@media (max-width: 760px) {
    .v2-details {
        padding: 0 16px 32px;
    }

    .topbar {
        grid-template-columns: auto 1fr;
        gap: 8px;
    }

    .actions {
        grid-column: 1 / -1;
        order: 2;
        flex-wrap: wrap;
    }

    .hero {
        grid-template-columns: 1fr;
        gap: 12px;
        align-items: start;
    }

    .hero-status {
        align-items: flex-start;
        text-align: left;
    }
}
</style>
