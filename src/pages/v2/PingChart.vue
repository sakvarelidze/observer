<template>
    <section class="v2-chart-card">
        <header class="v2-chart-head">
            <div class="v2-chart-titles">
                <span class="v2-chart-title">response time</span>
                <span v-if="!loading && summary && summary.count" class="v2-chart-summary">
                    avg <strong>{{ summary.avg }}ms</strong>
                    · max <strong>{{ summary.max }}ms</strong>
                    · {{ summary.count }} probe{{ summary.count === 1 ? "" : "s" }}
                </span>
                <span v-else-if="!loading" class="v2-chart-summary muted">
                    no probe data in this window
                </span>
            </div>
            <div class="v2-chart-periods" role="tablist">
                <button
                    v-for="p in periods"
                    :key="p"
                    type="button"
                    class="v2-chart-period"
                    :class="{ active: period === p }"
                    role="tab"
                    :aria-selected="period === p"
                    @click="setPeriod(p)"
                >{{ p }}</button>
            </div>
        </header>

        <div class="v2-chart-body">
            <div v-if="loading" class="v2-chart-loading">
                <LoaderBars size="sm" />
            </div>
            <Line v-else-if="hasData" :data="chartData" :options="chartOptions" />
            <div v-else class="v2-chart-empty">no data yet</div>
        </div>
    </section>
</template>

<script>
import dayjs from "dayjs";
import { Line } from "vue-chartjs";
import LoaderBars from "./LoaderBars.vue";
import { ensureChartsRegistered } from "./charts/_register.js";

ensureChartsRegistered();

const ACCENT = "hsl(142 71% 55%)";
const ACCENT_FILL = "hsl(142 71% 55% / 0.08)";
const MAX_LINE = "hsl(0 0% 70%)";

export default {
    name: "PingChart",
    components: { Line,
        LoaderBars },
    props: {
        monitorId: { type: Number,
            required: true },
    },
    data() {
        return {
            period: "24h",
            periods: [ "24h", "7d", "30d" ],
            loading: true,
            buckets: [],
            summary: { avg: null,
                max: null,
                count: 0 },
            inFlight: 0,
            // Auto-refresh: response time changes minute-to-minute, so a
            // 60s cadence keeps the rightmost bucket fresh without
            // hammering the backend.
            refreshHandle: null,
            refreshIntervalMs: 60000,
        };
    },
    computed: {
        hasData() {
            return this.buckets.some(b => b.avg != null);
        },
        chartData() {
            // Explicit {x, y} pairs are more reliable than a parallel
            // labels array for time-scaled axes — Chart.js places each
            // point at its own date, no positional ambiguity.
            const maxData = this.buckets
                .filter(b => b.max != null)
                .map(b => ({ x: new Date(b.t), y: b.max }));
            const avgData = this.buckets
                .filter(b => b.avg != null)
                .map(b => ({ x: new Date(b.t), y: b.avg }));
            return {
                datasets: [
                    {
                        label: "max",
                        data: maxData,
                        borderColor: MAX_LINE,
                        borderWidth: 1,
                        borderDash: [ 4, 3 ],
                        // Small visible point so an isolated bucket of
                        // data renders as a dot rather than disappearing
                        // when surrounding buckets are empty.
                        pointRadius: 1.5,
                        pointHoverRadius: 4,
                        pointBackgroundColor: MAX_LINE,
                        pointBorderColor: MAX_LINE,
                        spanGaps: true,
                        tension: 0.25,
                    },
                    {
                        label: "avg",
                        data: avgData,
                        borderColor: ACCENT,
                        backgroundColor: ACCENT_FILL,
                        borderWidth: 2,
                        pointRadius: 2,
                        pointHoverRadius: 5,
                        pointBackgroundColor: ACCENT,
                        pointBorderColor: "hsl(0 0% 5%)",
                        pointBorderWidth: 1,
                        pointHoverBackgroundColor: ACCENT,
                        pointHoverBorderColor: "hsl(0 0% 5%)",
                        pointHoverBorderWidth: 2,
                        fill: "origin",
                        spanGaps: true,
                        tension: 0.25,
                    },
                ],
            };
        },
        chartOptions() {
            const period = this.period;
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
                                const t = dayjs(items[0].parsed.x);
                                if (period === "24h") {
                                    return t.format("HH:mm — ddd");
                                }
                                if (period === "7d") {
                                    return t.format("ddd HH:mm");
                                }
                                return t.format("D MMM YYYY");
                            },
                            label: (item) => {
                                const v = item.parsed.y;
                                if (v == null) {
                                    return null;
                                }
                                return `${item.dataset.label}: ${Math.round(v)}ms`;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        type: "time",
                        time: {
                            unit: period === "24h" ? "hour" : period === "7d" ? "day" : "day",
                            tooltipFormat: "PPpp",
                            displayFormats: {
                                hour: "HH:mm",
                                day: "d MMM",
                            },
                        },
                        grid: { display: false },
                        ticks: {
                            maxRotation: 0,
                            autoSkipPadding: 12,
                        },
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: "hsl(0 0% 16%)",
                            drawTicks: false },
                        border: { display: false },
                        ticks: {
                            padding: 8,
                            callback: (v) => `${v}ms`,
                        },
                    },
                },
                animation: false,  // snappy on period switch
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
        setPeriod(p) {
            if (p === this.period) {
                return;
            }
            this.period = p;
            this.fetch();
        },
        tickRefresh() {
            if (document.hidden) {
                return;
            }
            this.fetch({ silent: true });
        },
        onVisibilityChange() {
            // When the tab comes back into focus, refresh immediately so
            // the user isn't looking at potentially-minutes-stale data
            // while waiting for the next interval tick.
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
                    `/monitors/${this.monitorId}/ping-stats`,
                    { params: { period: this.period } },
                );
                if (id !== this.inFlight) {
                    return;
                }
                if (data?.ok) {
                    this.buckets = data.buckets || [];
                    this.summary = data.summary || { avg: null,
                        max: null,
                        count: 0 };
                }
            } catch (e) {
                if (id !== this.inFlight) {
                    return;
                }
                if (!silent) {
                    console.warn("Failed to load ping stats", e);
                    this.buckets = [];
                    this.summary = { avg: null,
                        max: null,
                        count: 0 };
                }
                // Silent ticks keep showing the previous data on transient
                // network failures rather than blanking the chart.
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
@import "./_base.scss";
@import "./charts/_card.scss";
</style>
