<template>
    <div class="v2-shell" :class="`density-${density}`">
        <header class="v2-topbar">
            <div class="brand">
                <span class="brand-mark" :class="{ live: globalPulse }">
                    <span class="brand-mark-core"></span>
                </span>
                <span class="brand-name">Observer</span>
            </div>

            <div class="counters">
                <button
                    v-for="c in counters"
                    :key="c.key"
                    type="button"
                    class="counter"
                    :class="[
                        `tone-${c.tone}`,
                        { active: activeFilter === c.key, pulsing: counterFlash[c.key] },
                    ]"
                    @click="toggleFilter(c.key)"
                >
                    <span class="counter-dot"></span>
                    <span class="counter-label">{{ c.label }}</span>
                    <span class="counter-value">{{ c.value }}</span>
                </button>
            </div>

            <div class="controls">
                <MenuTrigger />
                <router-link to="/events" class="events-btn" title="Recent events">
                    <font-awesome-icon icon="bell" />
                </router-link>
                <router-link to="/add" class="add-btn" title="Add monitor">
                    <span class="add-plus">+</span>
                    <span class="add-label">add</span>
                </router-link>
                <input
                    v-model="filter"
                    type="text"
                    class="search"
                    :placeholder="`Filter ${monitorCount} monitors…`"
                    @keydown.esc="onFilterEsc"
                />
                <button
                    type="button"
                    class="density-btn"
                    :title="`Density: ${density}`"
                    @click="toggleDensity"
                >
                    <span class="density-icon" :class="density">
                        <span></span>
                        <span></span>
                        <span></span>
                    </span>
                </button>
            </div>
        </header>

        <main v-if="visibleMonitors.length > 0" class="v2-grid">
            <MonitorTile
                v-for="m in visibleMonitors"
                :key="m.id"
                :monitor="m"
                :now="now"
                :density="density"
            />
        </main>

        <main v-else class="v2-empty">
            <LoaderBars size="md" />
            <p v-if="filter || activeFilter">
                No monitors match the current filter.
            </p>
            <p v-else>
                No monitors yet.
                <router-link to="/add">Add your first one →</router-link>
            </p>
        </main>

        <CommandPalette />
    </div>
</template>

<script>
import CommandPalette from "./CommandPalette.vue";
import LoaderBars from "./LoaderBars.vue";
import MenuTrigger from "./MenuTrigger.vue";
import MonitorTile from "./MonitorTile.vue";

const STATUS_BY_KEY = {
    up: 1,
    down: 0,
    pending: 2,
    maintenance: 3,
};

export default {
    name: "DashboardV2",
    components: { CommandPalette,
        LoaderBars,
        MenuTrigger,
        MonitorTile },
    data() {
        return {
            filter: "",
            density: "comfortable",
            activeFilter: null,
            now: Math.floor(Date.now() / 1000),
            tickHandle: null,

            globalPulse: false,
            globalPulseTimer: null,

            counterFlash: {
                up: false,
                down: false,
                pending: false,
                maintenance: false,
                paused: false,
            },
            counterFlashTimers: {},
        };
    },
    computed: {
        monitors() {
            const list = Object.values(this.$root.monitorList || {});
            return list.filter(m => m && m.type !== "group");
        },
        monitorCount() {
            return this.monitors.length;
        },
        counters() {
            const stats = this.$root.stats || {};
            return [
                { key: "up",
                    tone: "up",
                    label: "Up",
                    value: stats.up ?? 0 },
                { key: "down",
                    tone: "down",
                    label: "Down",
                    value: stats.down ?? 0 },
                { key: "pending",
                    tone: "pending",
                    label: "Pending",
                    value: stats.pending ?? 0 },
                { key: "maintenance",
                    tone: "maintenance",
                    label: "Maint.",
                    value: stats.maintenance ?? 0 },
                { key: "paused",
                    tone: "paused",
                    label: "Paused",
                    value: stats.pause ?? 0 },
            ];
        },
        visibleMonitors() {
            const filterText = this.filter.trim().toLowerCase();
            const status = this.activeFilter;
            return this.monitors
                .filter(m => {
                    if (filterText) {
                        const name = (m.name || "").toLowerCase();
                        if (!name.includes(filterText)) {
                            return false;
                        }
                    }
                    if (status === "paused") {
                        return !m.active;
                    }
                    if (status != null) {
                        if (!m.active) {
                            return false;
                        }
                        const last = this.$root.lastHeartbeatList?.[m.id];
                        return last && last.status === STATUS_BY_KEY[status];
                    }
                    return true;
                })
                .sort((a, b) => {
                    // Down/pending bubble to the top so problems are obvious
                    const wa = this.weight(a);
                    const wb = this.weight(b);
                    if (wa !== wb) {
                        return wa - wb;
                    }
                    return (a.name || "").localeCompare(b.name || "");
                });
        },
    },
    watch: {
        "$root.lastHeartbeatList": {
            handler() {
                this.flashGlobal();
            },
            deep: true,
        },
        "$root.stats.up"() {
            this.flashCounter("up");
        },
        "$root.stats.down"() {
            this.flashCounter("down");
        },
        "$root.stats.pending"() {
            this.flashCounter("pending");
        },
        "$root.stats.maintenance"() {
            this.flashCounter("maintenance");
        },
    },
    mounted() {
        // Single shared 1s tick drives every tile's countdown.
        this.tickHandle = setInterval(() => {
            this.now = Math.floor(Date.now() / 1000);
        }, 1000);

        const stored = localStorage.getItem("v2-density");
        if (stored === "compact" || stored === "comfortable") {
            this.density = stored;
        }

        this.$root.emitter?.on?.("v2-density-changed", this.onExternalDensityChange);
    },
    beforeUnmount() {
        clearInterval(this.tickHandle);
        clearTimeout(this.globalPulseTimer);
        for (const t of Object.values(this.counterFlashTimers)) {
            clearTimeout(t);
        }
        this.$root.emitter?.off?.("v2-density-changed", this.onExternalDensityChange);
    },
    methods: {
        weight(m) {
            if (!m.active) {
                return 5;
            }
            const last = this.$root.lastHeartbeatList?.[m.id];
            if (!last) {
                return 4;
            }
            switch (last.status) {
                case 0: return 0; // down
                case 2: return 1; // pending
                case 3: return 2; // maintenance
                case 1: return 3; // up
                default: return 4;
            }
        },
        toggleFilter(key) {
            this.activeFilter = this.activeFilter === key ? null : key;
        },
        onFilterEsc(e) {
            // First press clears the input. If it's already empty, drop
            // focus so a follow-up Esc lands on the document and the
            // CommandPalette ⌘K listener can pick it up later.
            if (this.filter) {
                this.filter = "";
                e.preventDefault();
            } else if (e.target && typeof e.target.blur === "function") {
                e.target.blur();
            }
        },
        toggleDensity() {
            this.density = this.density === "comfortable" ? "compact" : "comfortable";
            localStorage.setItem("v2-density", this.density);
        },
        flashGlobal() {
            this.globalPulse = true;
            clearTimeout(this.globalPulseTimer);
            this.globalPulseTimer = setTimeout(() => {
                this.globalPulse = false;
            }, 220);
        },
        flashCounter(key) {
            this.counterFlash[key] = true;
            clearTimeout(this.counterFlashTimers[key]);
            this.counterFlashTimers[key] = setTimeout(() => {
                this.counterFlash[key] = false;
            }, 360);
        },
        onExternalDensityChange(next) {
            if (next === "compact" || next === "comfortable") {
                this.density = next;
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.v2-shell {
    @include v2-surface-tokens;
    @include v2-shell-base;

    background:
        radial-gradient(circle at 12% -20%, hsl(142 71% 45% / 0.06), transparent 60%),
        radial-gradient(circle at 90% 0%, hsl(217 91% 60% / 0.04), transparent 55%),
        var(--bg);
    font-feature-settings: "ss01", "cv11";
    padding: 0 24px 40px;
}

.v2-topbar {
    @include v2-sticky-topbar(24px);
    // Override the mixin's `auto 1fr auto` so the middle column sits at
    // viewport center instead of drifting toward the (narrower) brand
    // side. Counters now align to the geometric center of the page.
    grid-template-columns: 1fr auto 1fr;
    margin-bottom: 18px;
}

.brand {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
    letter-spacing: -0.01em;

    .brand-name {
        font-weight: 600;
        color: var(--text);
    }
}

.brand-mark {
    position: relative;
    width: 14px;
    height: 14px;
    display: inline-flex;
    align-items: center;
    justify-content: center;

    .brand-mark-core {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--accent);
        box-shadow: 0 0 0 0 hsl(142 71% 45% / 0.55);
        transition: box-shadow 220ms ease;
    }

    &.live .brand-mark-core {
        box-shadow: 0 0 0 6px hsl(142 71% 45% / 0);
        animation: brand-ping 220ms cubic-bezier(0.2, 0.8, 0.2, 1);
    }
}

@keyframes brand-ping {
    0% { box-shadow: 0 0 0 0 hsl(142 71% 45% / 0.6); }
    100% { box-shadow: 0 0 0 8px hsl(142 71% 45% / 0); }
}

.counters {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: center;
}

.counter {
    --tone: var(--text-muted);
    --tone-glow: hsl(0 0% 60% / 0);

    appearance: none;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    color: var(--text-muted);
    border-radius: 999px;
    padding: 5px 12px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    cursor: pointer;
    transition: background 140ms ease, border-color 140ms ease, color 140ms ease;

    &:hover {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        color: var(--text);
    }

    &.active {
        background: var(--control);
        border-color: var(--tone);
        color: var(--text);
    }

    &.tone-up { --tone: hsl(142 71% 45%); --tone-glow: hsl(142 71% 45% / 0.55); }
    &.tone-down { --tone: hsl(0 84% 60%); --tone-glow: hsl(0 84% 60% / 0.55); }
    &.tone-pending { --tone: hsl(38 92% 50%); --tone-glow: hsl(38 92% 50% / 0.55); }
    &.tone-maintenance { --tone: hsl(217 91% 60%); --tone-glow: hsl(217 91% 60% / 0.55); }
    &.tone-paused { --tone: var(--text-faint); --tone-glow: hsl(0 0% 50% / 0); }

    .counter-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--tone);
        box-shadow: 0 0 0 0 var(--tone-glow);
        transition: box-shadow 220ms ease;
    }

    .counter-value {
        // Tint the count in its status color (up=green, down=red, …) so the
        // legend carries color at a glance instead of reading as plain text.
        color: var(--tone);
        font-variant-numeric: tabular-nums;
        font-weight: 700;
        letter-spacing: 0;
    }

    &.pulsing {
        animation: counter-pop 360ms cubic-bezier(0.2, 0.8, 0.2, 1);

        .counter-dot {
            box-shadow: 0 0 0 6px var(--tone-glow);
        }
    }
}

@keyframes counter-pop {
    0%, 100% { transform: translateY(0); }
    40% { transform: translateY(-1px); }
}

.controls {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;

    .search {
        appearance: none;
        background: var(--bg-soft);
        border: 1px solid var(--border);
        border-radius: 8px;
        color: var(--text);
        font-size: 12px;
        padding: 7px 12px;
        width: 220px;
        transition: border-color 140ms ease, background 140ms ease;

        &::placeholder {
            color: var(--text-faint);
        }

        &:focus {
            outline: none;
            background: var(--bg-hover);
            border-color: var(--border-strong);
        }
    }

    .density-btn,
    .events-btn {
        appearance: none;
        background: var(--bg-soft);
        border: 1px solid var(--border);
        color: var(--text-muted);
        border-radius: 8px;
        width: 32px;
        height: 32px;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        text-decoration: none;
        font-size: 13px;

        &:hover {
            background: var(--bg-hover);
            border-color: var(--border-strong);
            color: var(--text);
        }
    }

    .density-icon {
        display: flex;
        flex-direction: column;
        gap: 2px;
        width: 12px;

        span {
            display: block;
            height: 2px;
            background: currentColor;
            border-radius: 1px;
        }

        &.compact span {
            opacity: 0.95;
        }

        &.comfortable {
            gap: 3px;
            span {
                height: 3px;
                opacity: 0.7;
            }
        }
    }

    .add-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 12px 6px 10px;
        background: hsl(142 71% 45% / 0.12);
        border: 1px solid hsl(142 71% 45% / 0.4);
        color: var(--accent);
        border-radius: 8px;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        text-decoration: none;
        font-weight: 600;
        transition: background 140ms ease, border-color 140ms ease,
            color 140ms ease, transform 140ms ease;

        &:hover {
            background: hsl(142 71% 45% / 0.22);
            border-color: hsl(142 71% 45% / 0.7);
            color: var(--accent);
            transform: translateY(-1px);
        }

        .add-plus {
            font-size: 14px;
            line-height: 1;
            font-weight: 400;
        }
    }

}

.v2-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 10px;
}

.density-compact .v2-grid {
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 6px;
}

.v2-empty {
    min-height: 240px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 18px;
    color: var(--text-muted);
    font-size: 13px;

    a {
        color: var(--accent);
        text-decoration: none;

        &:hover {
            text-decoration: underline;
        }
    }
}

@media (max-width: 760px) {
    .v2-shell {
        padding: 0 12px 24px;
    }

    .v2-topbar {
        grid-template-columns: 1fr;
        gap: 12px;
        padding: 12px 0;
    }

    .controls .search {
        flex: 1;
        width: auto;
    }
}
</style>
