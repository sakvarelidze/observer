<template>
    <section class="v2-chart-card">
        <header class="v2-chart-head">
            <div class="v2-chart-titles">
                <span class="v2-chart-title">daily uptime</span>
                <span v-if="!loading && summary && summary.probes" class="v2-chart-summary">
                    <strong>{{ summary.uptime }}%</strong>
                    over {{ summary.days }} day{{ summary.days === 1 ? "" : "s" }}
                    · {{ summary.down }} down probe{{ summary.down === 1 ? "" : "s" }}
                </span>
                <span v-else-if="!loading" class="v2-chart-summary muted">
                    no probe data yet
                </span>
            </div>
            <div class="v2-chart-periods" role="tablist">
                <button
                    v-for="p in periods"
                    :key="p.days"
                    type="button"
                    class="v2-chart-period"
                    :class="{ active: days === p.days }"
                    role="tab"
                    :aria-selected="days === p.days"
                    @click="setDays(p.days)"
                >{{ p.label }}</button>
            </div>
        </header>

        <div class="v2-chart-body">
            <div v-if="loading" class="v2-chart-loading">
                <LoaderBars size="sm" />
            </div>
            <Bar v-else-if="hasData" :data="chartData" :options="chartOptions" />
            <div v-else class="v2-chart-empty">no data yet</div>
        </div>
    </section>
</template>

<script>
import dayjs from "dayjs";
import { Bar } from "vue-chartjs";
import LoaderBars from "./LoaderBars.vue";
import { ensureChartsRegistered } from "./charts/_register.js";

ensureChartsRegistered();

const COLOR_OK = "hsl(142 71% 45%)";
const COLOR_DEGRADED = "hsl(38 92% 50%)";
const COLOR_DOWN = "hsl(0 84% 60%)";
const COLOR_UNKNOWN = "hsl(0 0% 26%)";

function colorFor(pct) {
    if (pct == null) {
        return COLOR_UNKNOWN;
    }
    if (pct >= 99) {
        return COLOR_OK;
    }
    if (pct >= 95) {
        return COLOR_DEGRADED;
    }
    return COLOR_DOWN;
}

export default {
    name: "UptimeChart",
    components: { Bar,
        LoaderBars },
    props: {
        monitorId: { type: Number,
            required: true },
    },
    data() {
        return {
            days: 30,
            periods: [
                { days: 7,
                    label: "7d" },
                { days: 30,
                    label: "30d" },
                { days: 90,
                    label: "90d" },
            ],
            loading: true,
            buckets: [],
            summary: { uptime: null,
                probes: 0,
                down: 0,
                days: 0 },
            inFlight: 0,
            // Daily uptime only shifts as the current day's percentage
            // shifts — gradual. 5 minutes is plenty.
            refreshHandle: null,
            refreshIntervalMs: 300000,
        };
    },
    computed: {
        hasData() {
            return this.buckets.some(b => b.uptime != null);
        },
        chartData() {
            return {
                labels: this.buckets.map(b => b.date),
                datasets: [{
                    label: "uptime",
                    data: this.buckets.map(b => (b.uptime == null ? 0 : b.uptime)),
                    backgroundColor: this.buckets.map(b => colorFor(b.uptime)),
                    borderRadius: 3,
                    barPercentage: 0.85,
                    categoryPercentage: 0.95,
                }],
            };
        },
        chartOptions() {
            return {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index",
                    intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => {
                                if (!items?.length) {
                                    return "";
                                }
                                return dayjs(items[0].label).format("D MMM YYYY");
                            },
                            label: (item) => {
                                const b = this.buckets[item.dataIndex];
                                if (!b || b.uptime == null) {
                                    return "no probes";
                                }
                                return [
                                    `uptime: ${b.uptime}%`,
                                    `${b.probes} probes · ${b.down} down`,
                                ];
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: {
                            maxRotation: 0,
                            autoSkipPadding: 12,
                            callback: (v, i) => {
                                const b = this.buckets[i];
                                if (!b) {
                                    return "";
                                }
                                return dayjs(b.date).format("D MMM");
                            },
                        },
                    },
                    y: {
                        min: 0,
                        max: 100,
                        grid: { color: "hsl(0 0% 16%)",
                            drawTicks: false },
                        border: { display: false },
                        ticks: {
                            padding: 8,
                            stepSize: 25,
                            callback: (v) => `${v}%`,
                        },
                    },
                },
                animation: false,
            };
        },
    },
    watch: {
        monitorId: {
            immediate: true,
            handler() { this.fetch(); },
        },
    },
    mounted() {
        this.refreshHandle = setInterval(() => this.tickRefresh(), this.refreshIntervalMs);
        document.addEventListener("visibilitychange", this.onVisibilityChange);
    },
    beforeUnmount() {
        clearInterval(this.refreshHandle);
        document.removeEventListener("visibilitychange", this.onVisibilityChange);
    },
    methods: {
        setDays(d) {
            if (d === this.days) {
                return;
            }
            this.days = d;
            this.fetch();
        },
        tickRefresh() {
            if (document.hidden) {
                return;
            }
            this.fetch({ silent: true });
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
                    `/monitors/${this.monitorId}/uptime-daily`,
                    { params: { days: this.days } },
                );
                if (id !== this.inFlight) {
                    return;
                }
                if (data?.ok) {
                    this.buckets = data.buckets || [];
                    this.summary = data.summary || { uptime: null,
                        probes: 0,
                        down: 0,
                        days: 0 };
                }
            } catch (e) {
                if (id !== this.inFlight) {
                    return;
                }
                if (!silent) {
                    console.warn("Failed to load uptime stats", e);
                    this.buckets = [];
                    this.summary = { uptime: null,
                        probes: 0,
                        down: 0,
                        days: 0 };
                }
                // Silent ticks keep the previous data on transient errors.
            } finally {
                if (id === this.inFlight && !silent) {
                    this.loading = false;
                }
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;
@use "./charts/_card" as *;
</style>
