<template>
    <div v-if="loading" class="public-shell">
        <div class="public-loading">
            <LoaderBars size="md" />
            <p>Loading…</p>
        </div>
    </div>

    <div v-else-if="notFound" class="public-shell">
        <div class="public-empty">
            <h1>Not found</h1>
            <p>No status page lives at <code>/{{ slug }}</code> on this instance.</p>
        </div>
    </div>

    <div v-else class="public-shell" :class="`status-${overallKey}`">
        <header class="public-hero">
            <div class="hero-brand">
                <img v-if="config.icon" :src="config.icon" alt="" class="hero-icon">
                <h1 class="hero-title">{{ config.title || slug }}</h1>
            </div>

            <div class="hero-status">
                <span class="hero-status-pulse" :class="overallKey"></span>
                <span class="hero-status-headline">{{ overallHeadline }}</span>
                <span class="hero-status-meta">
                    <span>{{ monitorCount }} monitor{{ monitorCount === 1 ? "" : "s" }}</span>
                    <span class="dot-sep">·</span>
                    <span>updated {{ relativeTime(lastUpdated) }}</span>
                </span>
            </div>
        </header>

        <transition name="banner">
            <section v-if="activeIncident" class="banner banner-incident" :class="`tone-${incidentTone}`">
                <span class="banner-mark">
                    <font-awesome-icon icon="exclamation-circle" />
                </span>
                <div class="banner-body">
                    <span class="banner-eyebrow">Incident · {{ relativeTime(activeIncident.lastUpdatedDate || activeIncident.createdDate) }}</span>
                    <h2 class="banner-title">{{ activeIncident.title }}</h2>
                    <p class="banner-text">{{ activeIncident.content }}</p>
                </div>
            </section>
        </transition>

        <transition name="banner">
            <section v-if="activeMaintenances.length > 0" class="banner banner-maint">
                <span class="banner-mark">
                    <font-awesome-icon icon="wrench" />
                </span>
                <div class="banner-body">
                    <span class="banner-eyebrow">Scheduled maintenance</span>
                    <ul class="maint-list">
                        <li v-for="m in activeMaintenances" :key="m.id">
                            <strong>{{ m.title }}</strong>
                            <span v-if="m.description" class="maint-desc"> · {{ m.description }}</span>
                        </li>
                    </ul>
                </div>
            </section>
        </transition>

        <main class="public-main">
            <section v-for="group in displayGroups" :key="group.name || group.id" class="group">
                <header class="group-head">
                    <h2 class="group-title">{{ group.name || "Monitors" }}</h2>
                    <span class="group-meta">
                        <span class="group-status-pill" :class="groupStatusKey(group)">
                            <span class="group-status-dot"></span>
                            <span>{{ groupHeadline(group) }}</span>
                        </span>
                    </span>
                </header>

                <ul class="monitor-list">
                    <li
                        v-for="monitor in group.monitors"
                        :key="monitor.id"
                        class="monitor-row"
                        :class="`status-${monitorStatusKey(monitor)}`"
                    >
                        <div class="monitor-row-head">
                            <span class="monitor-row-status">
                                <span class="monitor-row-dot"></span>
                                <span class="monitor-row-name">{{ monitor.name }}</span>
                            </span>
                            <span class="monitor-row-pct">
                                <span v-if="uptimeOf(monitor.id, '24')" class="pct-pill">{{ uptimeOf(monitor.id, "24") }}<span class="pct-suffix">24h</span></span>
                                <span v-if="uptimeOf(monitor.id, '720')" class="pct-pill">{{ uptimeOf(monitor.id, "720") }}<span class="pct-suffix">30d</span></span>
                                <span v-if="uptimeOf(monitor.id, '1y')" class="pct-pill">{{ uptimeOf(monitor.id, "1y") }}<span class="pct-suffix">1y</span></span>
                            </span>
                        </div>
                        <div class="monitor-row-bar">
                            <div class="phb">
                                <span
                                    v-for="(b, i) in slotsFor(monitor.id)"
                                    :key="i"
                                    class="phb-cell"
                                    :class="beatClass(b)"
                                    :title="beatTitle(b)"
                                ></span>
                            </div>
                        </div>
                    </li>
                </ul>
            </section>

            <section v-if="displayGroups.length === 0" class="empty-monitors">
                <p>No monitors are configured on this status page yet.</p>
            </section>
        </main>

        <footer class="public-foot">
            <span class="foot-text">{{ config.footerText || "Powered by Observer." }}</span>
        </footer>
    </div>
</template>

<script>
import dayjs from "dayjs";
import { humanizeStatusMessage } from "../../util-frontend";
import LoaderBars from "./LoaderBars.vue";

const HEARTBEAT_BAR_SLOTS = 90;

const STATUS_KEY_BY_NUM = {
    1: "up",
    0: "down",
    2: "pending",
    3: "maintenance",
};

export default {
    name: "PublicStatusPageV2",
    components: { LoaderBars },
    props: {
        // Optional override for the matched-domain entrypoint where the
        // slug comes from a domain match, not a route param.
        overrideSlug: {
            type: String,
            default: null,
        },
    },
    data() {
        return {
            loading: true,
            notFound: false,
            config: {},
            incident: null,
            publicGroupList: [],
            maintenanceList: [],
            heartbeatList: {},
            uptimeList: {},
            lastUpdated: null,
            refreshHandle: null,
        };
    },
    computed: {
        slug() {
            return this.overrideSlug || this.$route.params.slug || "default";
        },
        monitors() {
            const out = [];
            for (const group of this.publicGroupList || []) {
                for (const m of (group.monitorList || [])) {
                    if (m && (m.id != null || m.name)) {
                        out.push(m);
                    }
                }
            }
            return out;
        },
        monitorCount() {
            return this.monitors.length;
        },
        displayGroups() {
            return (this.publicGroupList || []).map(g => ({
                name: g.name,
                monitors: (g.monitorList || []).map(m => ({
                    id: m.id,
                    name: m.name,
                    type: m.type,
                })),
            }));
        },
        overallKey() {
            // operational / degraded / outage / maintenance / unknown
            const monitors = this.monitors;
            if (monitors.length === 0) {
                return "operational";
            }
            let down = 0;
            let pending = 0;
            let maintenance = 0;
            let known = 0;
            for (const m of monitors) {
                const last = this.lastBeatOf(m.id);
                if (!last) {
                    continue;
                }
                known += 1;
                if (last.status === 0) {
                    down += 1;
                } else if (last.status === 2) {
                    pending += 1;
                } else if (last.status === 3) {
                    maintenance += 1;
                }
            }
            if (this.activeMaintenances.length > 0 && down === 0) {
                return "maintenance";
            }
            if (down === 0 && pending === 0 && known > 0) {
                return "operational";
            }
            if (down >= Math.ceil(monitors.length * 0.5)) {
                return "outage";
            }
            if (down > 0 || pending > 0) {
                return "degraded";
            }
            return known > 0 ? "operational" : "unknown";
        },
        overallHeadline() {
            switch (this.overallKey) {
                case "operational": return "All Systems Operational";
                case "degraded": return "Partially Degraded";
                case "outage": return "Major Outage";
                case "maintenance": return "Under Maintenance";
                default: return "Status Unknown";
            }
        },
        activeIncident() {
            return this.incident || null;
        },
        incidentTone() {
            const style = this.activeIncident?.style || "primary";
            // Map v1 "primary/info/warning/danger/dark/light" → tones.
            switch (style) {
                case "danger": return "danger";
                case "warning": return "warn";
                case "info":
                case "primary": return "info";
                default: return "info";
            }
        },
        activeMaintenances() {
            return Array.isArray(this.maintenanceList) ? this.maintenanceList : [];
        },
    },
    watch: {
        "$route.params.slug"() {
            this.fetchPage();
        },
    },
    mounted() {
        this.fetchPage();
        // Light auto-refresh — every 30s the page polls for new heartbeats
        // so visitors don't have to manually reload.
        this.refreshHandle = setInterval(() => this.fetchHeartbeats(), 30000);
    },
    beforeUnmount() {
        clearInterval(this.refreshHandle);
    },
    methods: {
        async fetchPage() {
            this.loading = true;
            this.notFound = false;
            try {
                const { data } = await this.$root.api.get(`/status-page/${this.slug}`);
                if (!data?.ok) {
                    this.notFound = true;
                    return;
                }
                this.config = data.config || {};
                this.incident = data.incident || null;
                this.publicGroupList = data.publicGroupList || [];
                this.maintenanceList = data.maintenanceList || [];
                document.title = `${this.config.title || this.slug} · status`;
            } catch (e) {
                if (e?.response?.status === 404) {
                    this.notFound = true;
                } else {
                    console.warn("could not load status page", e);
                    this.notFound = true;
                }
            } finally {
                this.loading = false;
            }
            await this.fetchHeartbeats();
        },
        async fetchHeartbeats() {
            try {
                const { data } = await this.$root.api.get(`/status-page/heartbeat/${this.slug}`, {
                    params: { limit: 90 },
                });
                this.heartbeatList = data?.heartbeatList || {};
                this.uptimeList = data?.uptimeList || {};
                this.lastUpdated = new Date();
            } catch (e) {
                console.warn("could not load heartbeats", e);
            }
        },
        beatsOf(monitorId) {
            return this.heartbeatList?.[monitorId] || [];
        },
        lastBeatOf(monitorId) {
            const beats = this.beatsOf(monitorId);
            return beats.length > 0 ? beats[beats.length - 1] : null;
        },
        slotsFor(monitorId) {
            // Tail of `HEARTBEAT_BAR_SLOTS` beats, left-padded with nulls so
            // newer monitors that haven't accumulated 90 beats yet still
            // render a fixed-width bar instead of a stub on the right.
            const beats = this.beatsOf(monitorId);
            const tail = beats.slice(Math.max(beats.length - HEARTBEAT_BAR_SLOTS, 0));
            const padCount = HEARTBEAT_BAR_SLOTS - tail.length;
            const out = new Array(padCount).fill(null);
            return out.concat(tail);
        },
        beatClass(beat) {
            if (!beat) {
                return "empty";
            }
            switch (beat.status) {
                case 1: return "up";
                case 0: return "down";
                case 2: return "pending";
                case 3: return "maintenance";
                default: return "empty";
            }
        },
        beatTitle(beat) {
            if (!beat) {
                return "";
            }
            const raw = beat.time || "";
            // The backend serialises naive UTC timestamps without a Z; appending
            // it forces JS to parse as UTC instead of local time.
            const t = raw ? new Date(raw + (raw.endsWith("Z") ? "" : "Z")).toLocaleString() : "";
            const msg = humanizeStatusMessage(beat.msg);
            return `${t}${msg ? " · " + msg : ""}`;
        },
        monitorStatusKey(monitor) {
            const last = this.lastBeatOf(monitor.id);
            if (!last) {
                return "unknown";
            }
            return STATUS_KEY_BY_NUM[last.status] || "unknown";
        },
        groupStatusKey(group) {
            const monitors = group.monitors || [];
            if (monitors.length === 0) {
                return "operational";
            }
            let down = 0;
            for (const m of monitors) {
                const last = this.lastBeatOf(m.id);
                if (last && last.status === 0) {
                    down += 1;
                }
            }
            if (down >= Math.ceil(monitors.length * 0.5)) {
                return "outage";
            }
            if (down > 0) {
                return "degraded";
            }
            return "operational";
        },
        groupHeadline(group) {
            switch (this.groupStatusKey(group)) {
                case "outage": return "Major Outage";
                case "degraded": return "Partially Degraded";
                default: return "Operational";
            }
        },
        uptimeOf(monitorId, period) {
            const v = this.uptimeList?.[`${monitorId}_${period}`];
            if (v == null) {
                return null;
            }
            return `${Number(v).toFixed(2)}%`;
        },
        relativeTime(value) {
            if (!value) {
                return "—";
            }
            try {
                return dayjs(value).fromNow();
            } catch (e) {
                return "";
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.public-shell {
    @include v2-surface-tokens;
    @include v2-shell-base;

    background:
        radial-gradient(circle at 0% -20%, var(--status-glow), transparent 60%),
        radial-gradient(circle at 100% -10%, hsl(0 0% 12% / 0.5), transparent 60%),
        var(--bg);
    padding: 0 24px 64px;
    min-height: 100vh;

    --status-glow: hsl(142 71% 45% / 0.16);

    &.status-degraded { --status-glow: hsl(38 92% 50% / 0.16); }
    &.status-outage { --status-glow: hsl(0 84% 60% / 0.18); }
    &.status-maintenance { --status-glow: hsl(217 91% 60% / 0.16); }
    &.status-unknown { --status-glow: hsl(0 0% 30% / 0.12); }
}

.public-loading,
.public-empty {
    min-height: 80vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 14px;
    color: var(--text-muted);

    h1 {
        margin: 0;
        font-size: 28px;
        font-weight: 600;
        color: var(--text);
        letter-spacing: -0.02em;
    }

    p { margin: 0; font-size: 14px; }

    code {
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        background: var(--bg-soft);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 2px 8px;
    }
}

.public-hero {
    max-width: 960px;
    margin: 0 auto;
    padding: 56px 8px 36px;
    display: flex;
    flex-direction: column;
    gap: 24px;
    animation: v2-fade-in 320ms var(--enter-ease) both;
}

.hero-brand {
    display: flex;
    align-items: center;
    gap: 14px;

    .hero-icon {
        width: 36px;
        height: 36px;
        border-radius: 9px;
        object-fit: contain;
    }

    .hero-title {
        margin: 0;
        font-size: clamp(24px, 3vw, 32px);
        font-weight: 600;
        letter-spacing: -0.02em;
    }
}

.hero-status {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 24px 28px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 16px;
    position: relative;
    overflow: hidden;

    .public-shell.status-operational & {
        border-color: hsl(142 71% 45% / 0.4);
        background: hsl(142 71% 45% / 0.05);
    }
    .public-shell.status-degraded & {
        border-color: hsl(38 92% 50% / 0.4);
        background: hsl(38 92% 50% / 0.05);
    }
    .public-shell.status-outage & {
        border-color: hsl(0 84% 60% / 0.45);
        background: hsl(0 84% 60% / 0.06);
    }
    .public-shell.status-maintenance & {
        border-color: hsl(217 91% 60% / 0.45);
        background: hsl(217 91% 60% / 0.06);
    }
}

.hero-status-pulse {
    position: absolute;
    top: 50%;
    left: 28px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: hsl(0 0% 38%);
    transform: translateY(-50%);

    &.operational { background: hsl(142 71% 45%); box-shadow: 0 0 0 8px hsl(142 71% 45% / 0.18); }
    &.degraded { background: hsl(38 92% 55%); box-shadow: 0 0 0 8px hsl(38 92% 50% / 0.18); }
    &.outage { background: hsl(0 84% 60%); box-shadow: 0 0 0 8px hsl(0 84% 60% / 0.2); animation: pulse-outage 1.6s ease-in-out infinite; }
    &.maintenance { background: hsl(217 91% 60%); box-shadow: 0 0 0 8px hsl(217 91% 60% / 0.18); }
    &.unknown { background: hsl(0 0% 38%); }
}

@keyframes pulse-outage {
    0%, 100% { box-shadow: 0 0 0 8px hsl(0 84% 60% / 0.2); }
    50% { box-shadow: 0 0 0 14px hsl(0 84% 60% / 0.05); }
}

.hero-status-headline {
    margin: 0 0 0 38px;
    font-size: clamp(24px, 3.5vw, 36px);
    font-weight: 700;
    letter-spacing: -0.02em;
    line-height: 1.1;
    color: var(--text);
}

.hero-status-meta {
    margin: 0 0 0 38px;
    color: var(--text-muted);
    font-size: 13px;
    text-transform: lowercase;

    .dot-sep {
        margin: 0 8px;
        opacity: 0.5;
    }
}

.banner {
    max-width: 960px;
    margin: 0 auto 16px;
    padding: 18px 22px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-left-width: 4px;
    border-radius: 12px;
    display: flex;
    gap: 16px;
    align-items: flex-start;

    &.banner-incident {
        &.tone-info { border-left-color: hsl(217 91% 60%); background: hsl(217 91% 60% / 0.05); }
        &.tone-warn { border-left-color: hsl(38 92% 55%); background: hsl(38 92% 50% / 0.05); }
        &.tone-danger { border-left-color: hsl(0 84% 60%); background: hsl(0 84% 60% / 0.06); }
    }

    &.banner-maint {
        border-left-color: hsl(217 91% 60%);
        background: hsl(217 91% 60% / 0.04);
    }

    .banner-mark {
        width: 36px;
        height: 36px;
        flex: none;
        border-radius: 10px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: hsl(0 0% 0% / 0.25);
        color: var(--text);
    }

    .banner-body {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 6px;
    }

    .banner-eyebrow {
        font-size: 10.5px;
        text-transform: uppercase;
        letter-spacing: 0.14em;
        color: var(--text-faint);
        font-weight: 600;
    }

    .banner-title {
        margin: 0;
        font-size: 18px;
        font-weight: 600;
    }

    .banner-text {
        margin: 0;
        color: var(--text-muted);
        font-size: 13.5px;
        line-height: 1.55;
        white-space: pre-wrap;
    }

    .maint-list {
        list-style: none;
        margin: 0;
        padding: 0;
        font-size: 13.5px;
        color: var(--text-muted);
        line-height: 1.55;

        li + li { margin-top: 4px; }
        strong { color: var(--text); }
        .maint-desc { color: var(--text-faint); }
    }
}

.banner-enter-active,
.banner-leave-active {
    transition: opacity 220ms ease, transform 220ms ease;
}

.banner-enter-from,
.banner-leave-to {
    opacity: 0;
    transform: translateY(-6px);
}

.public-main {
    max-width: 960px;
    margin: 28px auto 0;
    display: flex;
    flex-direction: column;
    gap: 24px;
    animation: v2-up 360ms var(--enter-ease) both;
    animation-delay: 100ms;
}

.group {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
}

.group-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);

    .group-title {
        margin: 0;
        font-size: 15px;
        font-weight: 600;
        letter-spacing: -0.01em;
    }
}

.group-status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
    border: 1px solid var(--border);

    .group-status-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: hsl(0 0% 38%);
    }

    &.operational {
        background: hsl(142 71% 45% / 0.12);
        border-color: hsl(142 71% 45% / 0.4);
        color: hsl(142 71% 75%);

        .group-status-dot { background: hsl(142 71% 45%); }
    }

    &.degraded {
        background: hsl(38 92% 50% / 0.12);
        border-color: hsl(38 92% 50% / 0.4);
        color: hsl(38 92% 70%);

        .group-status-dot { background: hsl(38 92% 55%); }
    }

    &.outage {
        background: hsl(0 84% 60% / 0.12);
        border-color: hsl(0 84% 60% / 0.4);
        color: hsl(0 84% 75%);

        .group-status-dot { background: hsl(0 84% 60%); }
    }
}

.monitor-list {
    list-style: none;
    margin: 0;
    padding: 0;
}

.monitor-row {
    --row-color: hsl(0 0% 38%);
    padding: 14px 20px;
    display: flex;
    flex-direction: column;
    gap: 10px;

    & + & {
        border-top: 1px solid var(--border);
    }

    &.status-up { --row-color: hsl(142 71% 45%); }
    &.status-down { --row-color: hsl(0 84% 60%); }
    &.status-pending { --row-color: hsl(38 92% 55%); }
    &.status-maintenance { --row-color: hsl(217 91% 60%); }
}

.monitor-row-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
    flex-wrap: wrap;
}

.monitor-row-status {
    display: inline-flex;
    align-items: center;
    gap: 10px;
}

.monitor-row-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--row-color);
    box-shadow: 0 0 0 4px color-mix(in oklab, var(--row-color) 18%, transparent);
}

.monitor-row-name {
    font-size: 14px;
    font-weight: 500;
    color: var(--text);
}

.monitor-row-pct {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-variant-numeric: tabular-nums;
}

.pct-pill {
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
    padding: 3px 8px;
    background: hsl(0 0% 6%);
    border: 1px solid var(--border);
    border-radius: 999px;
    font-size: 11.5px;
    color: var(--text);
    line-height: 1;

    .pct-suffix {
        font-size: 9.5px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-faint);
    }
}

.monitor-row-bar {
    width: 100%;
}

.phb {
    display: flex;
    gap: 2px;
    width: 100%;
}

.phb-cell {
    flex: 1;
    height: 22px;
    border-radius: 2px;
    background: hsl(142 71% 45%);
    transition: opacity 140ms ease;

    &.empty { background: hsl(0 0% 14%); }
    &.down { background: hsl(0 84% 60%); }
    &.pending { background: hsl(38 92% 55%); }
    &.maintenance { background: hsl(217 91% 60%); }
    &:hover { opacity: 0.75; }
}

.empty-monitors {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
    font-size: 14px;
    border: 1px dashed var(--border-strong);
    background: var(--bg-soft);
    border-radius: 14px;
}

.public-foot {
    max-width: 960px;
    margin: 36px auto 0;
    padding: 16px 8px;
    text-align: center;
    color: var(--text-faint);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;

    .foot-text {
        opacity: 0.7;
    }
}

@media (max-width: 720px) {
    .public-shell { padding: 0 16px 40px; }
    .public-hero { padding: 32px 4px 24px; }

    .group-head { flex-wrap: wrap; }

    .monitor-row-head {
        flex-direction: column;
        align-items: stretch;
        gap: 6px;
    }

    .monitor-row-pct {
        flex-wrap: wrap;
    }

    .phb-cell {
        height: 16px;
    }
}
</style>
