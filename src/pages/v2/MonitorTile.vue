<template>
    <router-link
        :to="`/dashboard/${monitor.id}`"
        class="tile"
        :class="[
            `status-${statusKey}`,
            `density-${density}`,
            { paused: !monitor.active, pulsing },
        ]"
    >
        <div class="tile-row top">
            <span class="status-dot"></span>
            <span class="tile-name" :title="monitor.name">{{ monitor.name }}</span>
            <span class="tile-ping">{{ pingText }}</span>
        </div>
        <div class="tile-bar">
            <HeartbeatBar :monitor-id="monitor.id" size="small" />
        </div>
        <div class="tile-row bottom">
            <span class="meta-uptime">{{ uptime24 }}</span>
            <span
                v-if="certWarning"
                class="meta-cert"
                :class="{ expired: certWarning.expired }"
                :title="certWarning.tooltip"
            >
                <font-awesome-icon icon="certificate" />
                {{ certWarning.label }}
            </span>
            <span class="meta-countdown">{{ countdownText }}</span>
        </div>
        <div class="tile-glow" aria-hidden="true"></div>
    </router-link>
</template>

<script>
import dayjs from "dayjs";
import HeartbeatBar from "../../components/HeartbeatBar.vue";

export default {
    name: "MonitorTile",
    components: { HeartbeatBar },
    props: {
        monitor: {
            type: Object,
            required: true,
        },
        now: {
            type: Number,
            required: true,
        },
        density: {
            type: String,
            default: "comfortable",
        },
    },
    data() {
        return {
            pulsing: false,
            pulseTimer: null,
        };
    },
    computed: {
        lastBeat() {
            return this.$root.lastHeartbeatList?.[this.monitor.id] || null;
        },
        statusKey() {
            if (!this.monitor.active) {
                return "paused";
            }
            if (!this.lastBeat) {
                return "unknown";
            }
            switch (this.lastBeat.status) {
                case 1: return "up";
                case 0: return "down";
                case 2: return "pending";
                case 3: return "maintenance";
                default: return "unknown";
            }
        },
        pingText() {
            if (!this.lastBeat || this.lastBeat.ping == null) {
                return "—";
            }
            return `${Math.round(this.lastBeat.ping)} ms`;
        },
        uptime24() {
            const u = this.$root.uptimeList?.[`${this.monitor.id}_24`];
            if (u == null) {
                return "—";
            }
            return `${u.toFixed(2)}%`;
        },
        certWarning() {
            // Only surface the cert chip when the most recent probe reported
            // a TLS cert age AND the monitor is within (or past) its own
            // per-monitor expiry threshold. Quiet otherwise — the dashboard
            // is for alerts, not background telemetry.
            const days = this.lastBeat?.cert_expire;
            if (days == null) {
                return null;
            }
            const threshold = this.monitor.cert_expiry_threshold_days ?? 14;
            if (days > threshold) {
                return null;
            }
            const expired = days < 0;
            const label = expired
                ? "expired"
                : days === 0
                    ? "<1d"
                    : `${days}d`;
            const tooltip = expired
                ? `TLS certificate expired ${-days} day${-days === 1 ? "" : "s"} ago`
                : `TLS certificate expires in ${days} day${days === 1 ? "" : "s"} (alert threshold ${threshold}d)`;
            return {
                label,
                tooltip,
                expired,
            };
        },
        countdownText() {
            if (!this.monitor.active) {
                return "paused";
            }
            if (!this.lastBeat) {
                return "—";
            }
            const lastUnix = dayjs.utc(this.lastBeat.time).valueOf() / 1000;
            const interval = Math.max(this.monitor.interval || 60, 1);
            const remain = Math.round((lastUnix + interval) - this.now);
            if (remain <= 0) {
                return "checking…";
            }
            if (remain >= 3600) {
                return `${Math.round(remain / 3600)}h`;
            }
            if (remain >= 120) {
                return `${Math.round(remain / 60)}m`;
            }
            return `${remain}s`;
        },
    },
    watch: {
        "lastBeat.time"(newTime, oldTime) {
            if (newTime && oldTime && newTime !== oldTime) {
                this.pulsing = true;
                clearTimeout(this.pulseTimer);
                this.pulseTimer = setTimeout(() => {
                    this.pulsing = false;
                }, 360);
            }
        },
    },
    beforeUnmount() {
        clearTimeout(this.pulseTimer);
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.tile {
    @include v2-status-tokens;

    position: relative;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px 12px 8px;
    background: hsl(0 0% 9%);
    border: 1px solid hsl(0 0% 16%);
    border-radius: 10px;
    text-decoration: none;
    color: hsl(0 0% 92%);
    overflow: hidden;
    transition: transform 180ms $v2-ease,
        border-color 180ms ease, background 180ms ease, box-shadow 220ms ease;
    will-change: transform;

    &:hover {
        transform: translateY(-2px);
        border-color: hsl(0 0% 24%);
        background: hsl(0 0% 11%);
        box-shadow: 0 8px 24px hsl(0 0% 0% / 0.4);
    }

    // Tile-specific tweaks layered on top of the shared status tokens.
    &.status-down {
        border-color: hsl(0 60% 30%);
    }

    &.paused,
    &.status-paused {
        opacity: 0.62;
    }
}

.tile-row {
    display: flex;
    align-items: center;
    gap: 8px;
    line-height: 1;
    font-size: 12px;
}

.tile-row.top {
    .tile-name {
        flex: 1;
        font-size: 13px;
        font-weight: 500;
        letter-spacing: -0.01em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        color: hsl(0 0% 96%);
    }

    .tile-ping {
        font-variant-numeric: tabular-nums;
        font-size: 11px;
        color: hsl(0 0% 62%);
        font-feature-settings: "tnum";
    }
}

.tile-row.bottom {
    justify-content: space-between;
    font-size: 10.5px;
    font-variant-numeric: tabular-nums;
    color: hsl(0 0% 50%);
    text-transform: uppercase;
    letter-spacing: 0.04em;

    .meta-uptime {
        color: var(--status);
        font-weight: 600;
    }

    .meta-cert {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        color: hsl(38 92% 60%);
        font-weight: 600;
        // The bottom row uses justify-content: space-between, so dropping a
        // middle child redistributes everything to three points; that's the
        // intended layout when the chip is present.

        svg {
            font-size: 9px;
        }

        &.expired {
            color: hsl(0 84% 65%);
        }
    }
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--status);
    box-shadow: 0 0 0 0 var(--status-glow);
    flex: none;
    transition: box-shadow 220ms ease;
}

.tile-bar {
    flex: none;
    /* Sized to host HeartbeatBar size="small" comfortably */
    min-height: 18px;
    display: flex;
    align-items: center;
    opacity: 0.95;
}

.tile-glow {
    position: absolute;
    inset: 0;
    pointer-events: none;
    border-radius: inherit;
    background: radial-gradient(
        circle at 0% 0%,
        var(--status-glow),
        transparent 60%
    );
    opacity: 0;
    transition: opacity 200ms ease;
}

.tile.pulsing {
    animation: tile-pulse 360ms $v2-ease;

    .status-dot {
        box-shadow: 0 0 0 6px var(--status-glow);
    }

    .tile-glow {
        opacity: 1;
    }
}

@keyframes tile-pulse {
    0% {
        transform: translateY(0);
        border-color: var(--status);
    }
    35% {
        transform: translateY(-2px);
        border-color: var(--status);
    }
    100% {
        transform: translateY(0);
        border-color: hsl(0 0% 16%);
    }
}

.tile.density-compact {
    padding: 8px 10px 6px;
    gap: 4px;
    border-radius: 8px;

    .tile-row.top .tile-name {
        font-size: 12px;
    }

    .tile-row.top .tile-ping {
        font-size: 10.5px;
    }

    .tile-row.bottom {
        font-size: 9.5px;
    }
}
</style>
