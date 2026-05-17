import { createApp, h } from "vue";
import Toast, { useToast } from "vue-toastification";
import "vue-toastification/dist/index.css";
import App from "./App.vue";
import "./assets/app.scss";
import { i18n } from "./i18n";
import { FontAwesomeIcon } from "./icon.js";
import datetime from "./mixins/datetime";
import mobile from "./mixins/mobile";
import publicMixin from "./mixins/public";
import api from "./mixins/api";
import socketStub from "./mixins/socket-stub";
import theme from "./mixins/theme";
import lang from "./mixins/lang";
import { router } from "./router";
import { appName, UP, DOWN, PENDING, MAINTENANCE } from "./util.ts";
import dayjs from "dayjs";
import timezone from "./modules/dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";
import relativeTime from "dayjs/plugin/relativeTime";
import { loadToastSettings } from "./util-frontend";
dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(relativeTime);

// Number of heartbeats to fetch for each monitor on the dashboard.
// This should match the number of history slots shown in the UI so
// that historical status squares are filled with real data instead of
// gray placeholders.
const DASHBOARD_HEARTBEAT_LIMIT = 50;

// Upper bound for heartbeat history requests. This mirrors the
// longest range offered in the response time chart (1 week for monitors
// with a one-minute interval ≈ 10080 points) while preventing
// unbounded requests against the API.
const MAX_HEARTBEAT_FETCH_LIMIT = 10080;

// List of known boolean fields so numeric values can be coerced correctly
const BOOLEAN_KEYS = new Set([
    "active",
    "expiryNotification",
    "cacheBust",
    "upsideDown",
    "important",
    "isDefault",
    "invertKeyword",
    "pingNumeric",
    "ping_numeric",
    "grpcEnableTls",
    "grpc_enable_tls",
    "public",
]);

export function normalizeDeepBooleans(obj) {
    if (Array.isArray(obj)) {
        for (let i = 0; i < obj.length; i++) {
            obj[i] = normalizeDeepBooleans(obj[i]);
        }
        return obj;
    }
    if (obj && typeof obj === "object") {
        for (const key of Object.keys(obj)) {
            obj[key] = normalizeDeepBooleans(obj[key]);
            if (BOOLEAN_KEYS.has(key)) {
                if (obj[key] === "1" || obj[key] === 1) {
                    obj[key] = true;
                } else if (obj[key] === "0" || obj[key] === 0) {
                    obj[key] = false;
                } else if (obj[key] === null || obj[key] === undefined) {
                    obj[key] = false;
                }
            }
        }
        return obj;
    }
    if (typeof obj === "string") {
        const lower = obj.toLowerCase();
        if (lower === "true") {
            return true;
        }
        if (lower === "false") {
            return false;
        }
    }
    return obj;
}

export function normalizeDeepBooleansForBackend(obj) {
    if (Array.isArray(obj)) {
        for (let i = 0; i < obj.length; i++) {
            obj[i] = normalizeDeepBooleansForBackend(obj[i]);
        }
        return obj;
    }
    if (obj && typeof obj === "object") {
        for (const key of Object.keys(obj)) {
            obj[key] = normalizeDeepBooleansForBackend(obj[key]);
        }
        return obj;
    }
    if (obj === true) {
        return 1;
    }
    if (obj === false) {
        return 0;
    }
    return obj;
}

const app = createApp({
    mixins: [
        socketStub,
        api,
        theme,
        mobile,
        datetime,
        publicMixin,
        lang,
    ],
    data() {
        return {
            appName: appName,
            info: {},
            monitorList: {},
            lastHeartbeatList: {},
            heartbeatList: {},
            dashboardHeartbeatList: {},
            // Unix timestamp (seconds) of the newest heartbeat we've
            // ingested. Passed as `since=` on subsequent polls so the
            // server only returns deltas instead of the full window.
            _hbSince: null,
            monitorTypeList: {},
            notificationList: [],
            notifications: JSON.parse(localStorage.getItem("notifications") || "[]"),
            proxyList: [],
            remoteBrowserList: [],
            apiKeyList: {},
            statusPageList: {},
            statusPageListLoaded: false,
            maintenanceList: {},
            uptimeList: {},
            avgPingList: {},
            statusList: {},
            tlsInfoList: {},
            frontendVersion: typeof FRONTEND_VERSION !== "undefined" ? FRONTEND_VERSION : "",
            isFrontendBackendVersionMatched: true,
            remember: localStorage.remember !== "0",
            heartbeatRefreshTimer: null,
            // 10s instead of the historical 30s — typical monitor probe
            // intervals are ≤30s, so a 30s poll could miss the freshly
            // completed probe by half a cycle. 10s tightens "probe ran"
            // → "dashboard reflects it" to under 10s without hammering
            // the API. Each poll uses ?since= so it only fetches deltas.
            autoRefreshInterval: 10000,
            monitorListRefreshTimer: null,
            monitorListRefreshInterval: 15000,
            _hbInFlight: false,
            _mlInFlight: false,
            cloudflared: {
                installed: null,
                running: false,
                errorMessage: "",
                message: "",
                cloudflareTunnelToken: "",
                currentPassword: "",
            },
        };
    },
    computed: {
        /**
         * Calculate quick statistics for the dashboard.
         * Generates counters for various monitor states so UI can
         * render safely even when monitor data has not yet loaded.
         *
         * @returns {object} Stats object with up/down/etc counters
         */
        stats() {
            const result = {
                up: 0,
                down: 0,
                pending: 0,
                maintenance: 0,
                unknown: 0,
                pause: 0,
                active: 0,
            };

            const monitors = this.monitorList || {};
            const heartbeats = this.lastHeartbeatList || {};

            for (const id in monitors) {
                const monitor = monitors[id];
                if (monitor.type === "group") {
                    continue;
                }
                const hb = heartbeats[id];

                if (monitor.active) {
                    result.active += 1;
                } else {
                    result.pause += 1;
                }

                const status = hb?.status;

                if (status === 1) {
                    result.up += 1;
                } else if (status === 0) {
                    result.down += 1;
                } else if (status === 2) {
                    result.pending += 1;
                } else if (status === 3) {
                    result.maintenance += 1;
                } else {
                    result.unknown += 1;
                }
            }

            return result;
        },

        usernameFirstChar() {
            return this.username ? this.username.charAt(0).toUpperCase() : "?";
        },
    },
    watch: {
        remember(newVal) {
            localStorage.remember = newVal ? "1" : "0";
        },
        loggedIn(logged) {
            if (logged) {
                this.loadInitialData().then(() => {
                    this.startMonitorListAutoRefresh();
                });
                this.startHeartbeatAutoRefresh();
            }
        },
    },
    methods: {
        addNotificationEvent(message) {
            this.notifications.unshift({
                message,
                time: Date.now(),
            });
            if (this.notifications.length > 100) {
                this.notifications = this.notifications.slice(0, 100);
            }
            localStorage.setItem("notifications", JSON.stringify(this.notifications));
        },

        removeNotification(index) {
            this.notifications.splice(index, 1);
            localStorage.setItem("notifications", JSON.stringify(this.notifications));
        },

        clearNotifications() {
            this.notifications = [];
            localStorage.removeItem("notifications");
        },

        /**
         * Load monitor list and heartbeat data from the backend
         * and store them in the root state.
         * @returns {Promise<void>}
         */
        async loadInitialData() {
            try {
                const monitorRes = await this.getMonitors();
                const monitors = monitorRes.monitors || monitorRes;
                if (Array.isArray(monitors)) {
                    this.monitorList = {};
                    for (const m of monitors) {
                        this.monitorList[m.id] = m;
                    }
                }

                try {
                    this.notificationList = await this.getNotifications();
                } catch (e) {
                    console.warn("Cannot load notifications", e);
                }

                await this.loadStatusPages();
                await this.loadMaintenances();
                await this.loadAPIKeys();

                // Try to fetch heartbeat data using the default status page.
                // Cold start: no `since` so we get the full window per
                // monitor; subsequent refreshes will use delta polling.
                try {
                    this._hbSince = null;
                    await this.loadHeartbeatData();
                } catch (e) {
                    console.warn("Cannot load heartbeat data", e);
                }
            } catch (e) {
                console.error("Failed to load monitors", e);
            }
        },

        /**
         * Refresh heartbeat data periodically.
         * @returns {Promise<void>}
         */
        async refreshHeartbeatData() {
            if (this._hbInFlight) {
                return;
            }
            this._hbInFlight = true;
            try {
                await this.loadHeartbeatData({
                    notify: true,
                    since: this._hbSince,
                });
            } catch (e) {
                console.warn("Cannot refresh heartbeat data", e);
            } finally {
                this._hbInFlight = false;
            }
        },

        sanitizeHeartbeatData(rawHeartbeatList) {
            const sanitized = {};
            if (!rawHeartbeatList) {
                return sanitized;
            }

            for (const id in rawHeartbeatList) {
                const beats = Array.isArray(rawHeartbeatList[id]) ? rawHeartbeatList[id] : [];
                if (beats.length > 0) {
                    sanitized[id] = beats;
                }
            }

            return sanitized;
        },

        trimHeartbeatsForDashboard(beats) {
            if (!Array.isArray(beats) || beats.length === 0) {
                return [];
            }

            const start = Math.max(beats.length - DASHBOARD_HEARTBEAT_LIMIT, 0);
            return beats.slice(start);
        },

        processHeartbeatPayload(data, { notify = false } = {}) {
            if (!data?.heartbeatList) {
                return;
            }

            const sanitized = this.sanitizeHeartbeatData(data.heartbeatList);
            const oldLast = notify ? { ...this.lastHeartbeatList } : null;
            const toast = notify ? useToast() : null;

            // Merge incoming beats with what is already stored. Both arrays
            // are chronological; append only beats strictly newer than the
            // latest beat in memory so delta polls (since=) and full polls
            // both produce a correct timeline.
            const mergedHeartbeatList = { ...this.heartbeatList };
            for (const id in sanitized) {
                const existing = Array.isArray(mergedHeartbeatList[id]) ? mergedHeartbeatList[id] : [];
                const incoming = sanitized[id];

                if (existing.length === 0) {
                    mergedHeartbeatList[id] = incoming;
                    continue;
                }

                const latestTime = existing[existing.length - 1].time;
                const newBeats = incoming.filter(b => b.time > latestTime);
                mergedHeartbeatList[id] = newBeats.length > 0
                    ? [...existing, ...newBeats]
                    : existing;
            }

            // Build last/dashboard from the merged list and only touch the
            // monitors whose payload included beats. Monitors with no delta
            // this poll keep their previous values (critical when since=
            // returns an empty list for quiet monitors).
            const newLast = { ...this.lastHeartbeatList };
            const newDashboard = { ...this.dashboardHeartbeatList };
            let maxTimeIso = null;

            for (const id in sanitized) {
                const beats = mergedHeartbeatList[id];
                const latest = beats[beats.length - 1];
                const previous = notify ? oldLast?.[id] : null;
                newLast[id] = latest;
                newDashboard[id] = this.trimHeartbeatsForDashboard(beats);

                if (!maxTimeIso || latest.time > maxTimeIso) {
                    maxTimeIso = latest.time;
                }

                if (notify) {
                    const name = this.monitorList[id]?.name || this.$t("Monitor");
                    if ((!previous && latest.status === DOWN) || (previous && previous.status !== latest.status)) {
                        if (latest.status === DOWN) {
                            const message = this.$t("monitorWentDown", [ name ]);
                            toast?.error(message);
                            this.addNotificationEvent(message);
                        } else if (latest.status === UP) {
                            const message = this.$t("monitorBackUp", [ name ]);
                            toast?.success(message);
                            this.addNotificationEvent(message);
                        }
                    }

                    if (!previous || previous.time !== latest.time) {
                        this.emitter.emit("newImportantHeartbeat", latest);
                    }
                }
            }

            this.heartbeatList = mergedHeartbeatList;
            this.lastHeartbeatList = newLast;
            this.dashboardHeartbeatList = newDashboard;
            this.uptimeList = data.uptimeList || {};

            if (maxTimeIso) {
                const ts = dayjs.utc(maxTimeIso).valueOf() / 1000;
                if (Number.isFinite(ts) && (this._hbSince == null || ts > this._hbSince)) {
                    this._hbSince = ts;
                }
            }

            this.computeStats();
        },

        async loadHeartbeatData({ notify = false, since = null } = {}) {
            const params = { limit: DASHBOARD_HEARTBEAT_LIMIT };
            if (since != null) {
                // Re-include the boundary beat; processHeartbeatPayload
                // dedupes via the `time > latestTime` filter.
                params.since = since;
            }

            const { data } = await this.api.get(
                "/status-page/heartbeat/default",
                { params }
            );

            this.processHeartbeatPayload(data, { notify });
        },

        async ensureHeartbeatCoverage(monitorId, periodHours) {
            if (!periodHours || periodHours <= 0) {
                return;
            }

            const beats = Array.isArray(this.heartbeatList[monitorId]) ? this.heartbeatList[monitorId] : [];
            const coverageStart = dayjs().subtract(periodHours, "hour");

            let earliest = null;
            for (const beat of beats) {
                const beatTime = this.toDayjs(beat.time);
                if (!earliest || beatTime.isBefore(earliest)) {
                    earliest = beatTime;
                }
            }

            if (earliest && (earliest.isBefore(coverageStart) || earliest.isSame(coverageStart))) {
                return;
            }

            const interval = this.monitorList[monitorId]?.interval || 60;
            const safeInterval = Math.max(interval, 1);
            const requiredPoints = Math.ceil((periodHours * 3600) / safeInterval);
            const desiredLimit = Math.min(
                MAX_HEARTBEAT_FETCH_LIMIT,
                Math.max(requiredPoints + 20, DASHBOARD_HEARTBEAT_LIMIT)
            );

            if (earliest && (earliest.isBefore(coverageStart) || earliest.isSame(coverageStart))) {
                return;
            }

            if (beats.length >= desiredLimit) {
                return;
            }

            await this.loadMonitorHeartbeats(monitorId, desiredLimit);
        },

        async loadMonitorHeartbeats(monitorId, limit) {
            const safeLimit = Math.min(
                MAX_HEARTBEAT_FETCH_LIMIT,
                Math.max(limit || DASHBOARD_HEARTBEAT_LIMIT, DASHBOARD_HEARTBEAT_LIMIT)
            );

            const { data } = await this.api.get(`/monitors/${monitorId}/heartbeats`, {
                params: {
                    limit: safeLimit,
                },
            });

            if (!data?.ok) {
                return;
            }

            const beatsDesc = Array.isArray(data.data) ? data.data : [];
            const beats = beatsDesc.slice().reverse();
            const nextHeartbeats = { ...this.heartbeatList };
            nextHeartbeats[monitorId] = beats;
            this.heartbeatList = nextHeartbeats;

            const nextLast = { ...this.lastHeartbeatList };
            if (beats.length > 0) {
                nextLast[monitorId] = beats[beats.length - 1];
            } else {
                delete nextLast[monitorId];
            }
            this.lastHeartbeatList = nextLast;

            const nextDashboard = { ...this.dashboardHeartbeatList };
            nextDashboard[monitorId] = this.trimHeartbeatsForDashboard(beats);
            this.dashboardHeartbeatList = nextDashboard;

            this.computeStats();
        },

        async loadNotifications() {
            try {
                this.notificationList = await this.getNotifications();
            } catch (e) {
                console.warn("Cannot load notifications", e);
            }
        },

        async loadAPIKeys() {
            try {
                const list = await this.getAPIKeys();
                this.apiKeyList = {};
                for (const key of list) {
                    this.apiKeyList[key.id] = key;
                }
            } catch (e) {
                console.warn("Cannot load API keys", e);
            }
        },

        async loadStatusPages() {
            try {
                const { data } = await this.api.get("/status-page");
                this.statusPageList = {};
                for (const page of data) {
                    const normalized = this.camelCaseKeys(page);
                    this.statusPageList[normalized.slug] = normalized;
                }
                this.statusPageListLoaded = true;
            } catch (e) {
                console.warn("Cannot load status pages", e);
                this.statusPageListLoaded = true;
            }
        },

        async loadMaintenances() {
            try {
                const { data } = await this.api.get("/maintenance");
                this.maintenanceList = {};
                for (const m of data) {
                    const normalized = this.sanitizeMaintenance(m);
                    this.maintenanceList[normalized.id] = normalized;
                }
            } catch (e) {
                console.warn("Cannot load maintenances", e);
            }
        },

        /**
         * Start periodic heartbeat refresh using REST.
         * @returns {void}
         */
        startHeartbeatAutoRefresh() {
            if (this.heartbeatRefreshTimer) {
                clearInterval(this.heartbeatRefreshTimer);
            }
            this.heartbeatRefreshTimer = setInterval(() => {
                if (!this._hbInFlight) {
                    this.refreshHeartbeatData();
                }
            }, this.autoRefreshInterval);
        },

        async refreshMonitorListOnce() {
            if (this._mlInFlight) {
                return;
            }
            this._mlInFlight = true;
            try {
                const res = await this.getMonitors();
                const list = res.monitors || res;
                if (Array.isArray(list)) {
                    const next = {};
                    for (const m of list) {
                        next[m.id] = m;
                    }
                    const prevIDs = new Set(Object.keys(this.monitorList || {}));
                    const nextIDs = new Set(Object.keys(next));
                    const hasNew = [...nextIDs].some(id => !prevIDs.has(id));
                    this.monitorList = next;
                    if (hasNew) {
                        this.refreshHeartbeatData().catch(() => {});
                    }
                }
            } finally {
                this._mlInFlight = false;
            }
        },

        startMonitorListAutoRefresh() {
            if (this.monitorListRefreshTimer) {
                clearInterval(this.monitorListRefreshTimer);
            }
            this.monitorListRefreshTimer = setInterval(() => {
                this.refreshMonitorListOnce().catch(() => {});
            }, this.monitorListRefreshInterval);
        },

        /**
         * Generate chart data for a monitor from stored heartbeats.
         * The real backend endpoint is missing in this demo, so
         * this function emulates it on the client.
         * @param {number} monitorId Monitor ID
         * @param {number} period Number of hours
         * @param {Function} cb Callback function
         * @returns {void}
         */
        async getMonitorChartData(monitorId, period, cb) {
            try {
                await this.ensureHeartbeatCoverage(monitorId, period);
            } catch (e) {
                console.warn("Cannot ensure heartbeat coverage", e);
            }

            const beats = this.heartbeatList[monitorId] || [];
            const end = dayjs();
            const start = end.subtract(period, "hour");
            const data = [];

            for (const beat of beats) {
                const t = this.toDayjs(beat.time);
                if (t.isBefore(start)) {
                    continue;
                }

                data.push({
                    timestamp: t.unix(),
                    up: beat.status === UP ? 1 : 0,
                    down: beat.status === DOWN || beat.status === PENDING ? 1 : 0,
                    maintenance: beat.status === MAINTENANCE ? 1 : 0,
                    avgPing: beat.ping ?? null,
                    minPing: beat.ping ?? null,
                    maxPing: beat.ping ?? null,
                });
            }

            // Ensure the dataset spans the requested period by
            // adding placeholder points at the start and end.
            data.push({
                timestamp: start.unix(),
                up: 0,
                down: 0,
                maintenance: 0,
                avgPing: null,
                minPing: null,
                maxPing: null,
            });

            data.push({
                timestamp: end.unix(),
                up: 0,
                down: 0,
                maintenance: 0,
                avgPing: null,
                minPing: null,
                maxPing: null,
            });

            // Sort by timestamp so start/end placeholders are at the
            // boundaries of the dataset.
            data.sort((a, b) => a.timestamp - b.timestamp);

            cb({ ok: true, data, start: start.unix(), end: end.unix() });
        },

        /**
         * Calculate uptime percentages and average ping for loaded heartbeats
         * and store them in the root state.
         * @returns {void}
         */
        computeStats() {
            this.avgPingList = {};
            const now = dayjs();
            const start = now.subtract(24, "hour");

            for (const id in this.heartbeatList) {
                if (this.monitorList[id]?.type === "group") {
                    continue;
                }
                const beats = Array.isArray(this.heartbeatList[id])
                    ? this.heartbeatList[id]
                    : [];
                const pingFiltered = beats.filter(
                    b => b.ping !== undefined && b.ping !== null && dayjs(b.time).isAfter(start)
                );
                if (pingFiltered.length > 0) {
                    const sum = pingFiltered.reduce((t, h) => t + h.ping, 0);
                    this.avgPingList[id] = Math.round(sum / pingFiltered.length);
                }
            }
        },

        /**
         * Clear heartbeat and event data for all monitors.
         * @param {Function} cb Optional callback
         * @returns {Promise<void>}
         */
        async clearStatistics(cb) {
            try {
                for (const id in this.monitorList) {
                    await this.api.post(`/monitors/${id}/clear-heartbeats`);
                    await this.api.post(`/monitors/${id}/clear-events`);
                    delete this.lastHeartbeatList[id];
                    delete this.heartbeatList[id];
                    delete this.dashboardHeartbeatList[id];
                }
                this.computeStats();
                cb && cb({ ok: true });
            } catch (e) {
                const msg =
                    e.response?.data?.detail || e.message || "Failed";
                cb && cb({ ok: false, msg });
            }
        },

        async updateMonitor(id, payload) {
            // backend expects singular /monitor path
            payload = this.toAPIPayload(payload);
            const { data } = await this.api.post(`/monitor/${id}`, payload);
            return data;
        },

        async addMonitor(payload) {
            payload = this.toAPIPayload(payload);
            const { data } = await this.api.post(`/monitors`, payload);
            // Backend now returns the full monitor record on create.
            // Merge it into the store so the dashboard reflects the new
            // monitor immediately instead of waiting up to 15s for the
            // next monitor-list poll (or for loadInitialData to refetch
            // everything in the UI flow).
            if (data?.ok && data.monitor) {
                const normalized = this.normalizeDeepBooleans(this.camelCaseKeysDeep(data.monitor));
                if (!Array.isArray(normalized.notificationIDList)) {
                    normalized.notificationIDList = Object.keys(normalized.notificationIDList || {})
                        .filter(id => normalized.notificationIDList[id])
                        .map(id => Number(id));
                }
                this.monitorList = {
                    ...this.monitorList,
                    [normalized.id]: normalized,
                };
            }
            return data;
        },

        async addNotification(payload) {
            payload = this.toAPIPayload(payload);
            const { data } = await this.api.post(`/notifications`, payload);
            return data;
        },

        async updateNotification(id, payload) {
            payload = this.toAPIPayload(payload);
            const { data } = await this.api.post(`/notifications/${id}`, payload);
            return data;
        },

        async deleteNotification(id) {
            const { data } = await this.api.delete(`/notifications/${id}`);
            return data;
        },

        async testNotification(payload) {
            payload = this.toAPIPayload(payload);
            try {
                const { data } = await this.api.post(`/notifications/test`, payload);
                return data;
            } catch (e) {
                const msg = e.response?.data?.detail || e.message || "Failed";
                return { ok: false, msg };
            }
        },

        async addAPIKey(payload, cb) {
            try {
                const data = await this.apiAddAPIKey(payload);
                await this.loadAPIKeys();
                cb && cb(data);
            } catch (e) {
                const msg = e.response?.data?.detail || e.message || "Failed";
                cb && cb({ ok: false, msg });
            }
        },

        async deleteAPIKey(id, cb) {
            try {
                const data = await this.apiDeleteAPIKey(id);
                await this.loadAPIKeys();
                cb && cb(data);
            } catch (e) {
                const msg = e.response?.data?.detail || e.message || "Failed";
                cb && cb({ ok: false, msg });
            }
        },

        normalizeDeepBooleans,

        normalizeDeepBooleansForBackend,

        normalizeBooleans(obj) {
            for (const key in obj) {
                if (obj[key] === true) obj[key] = 1;
                if (obj[key] === false) obj[key] = 0;
            }
            return obj;
        },
    },
    async mounted() {
        if (this.loggedIn) {
            await this.loadInitialData();
            this.startHeartbeatAutoRefresh();
            this.startMonitorListAutoRefresh();
        }
    },
    unmounted() {
        if (this.heartbeatRefreshTimer) {
            clearInterval(this.heartbeatRefreshTimer);
            this.heartbeatRefreshTimer = null;
        }
    },
    render: () => h(App),
});

app.use(router);
app.use(i18n);

app.use(Toast, loadToastSettings());
app.component("FontAwesomeIcon", FontAwesomeIcon);

app.mount("#app");

// Register the service worker only in production builds. Vite's dev
// server already does aggressive HMR, and a SW intercepting requests
// during dev would fight it. Failure to register is non-fatal — the
// app is fully usable without the SW; users just don't get the
// install / offline-fallback / fast-second-open benefits.
if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").catch((err) => {
            console.warn("Service worker registration failed", err);
        });
    });
}

// Expose the vue instance for development
if (process.env.NODE_ENV === "development") {
    console.log("Dev Only: window.app is the vue instance");
    window.app = app._instance;
    window.normalizeDeepBooleans = normalizeDeepBooleans;
    window.normalizeDeepBooleansForBackend = normalizeDeepBooleansForBackend;
}
