<template>
    <div class="v2-maintenance-edit">
        <header class="topbar">
            <router-link to="/maintenance" class="back" title="Back to maintenance">
                <span class="back-arrow">←</span>
                <span class="back-label">all windows</span>
            </router-link>
            <h1 class="topbar-title">{{ mode === "create" ? "new maintenance window" : "edit maintenance" }}</h1>
            <div class="topbar-right">
                <MenuTrigger />
            </div>
        </header>

        <main class="main">
            <div v-if="loading" class="page-loading">
                <LoaderBars size="md" />
            </div>

            <form v-else class="form" @submit.prevent="onSave">
                <!-- General -->
                <section class="block">
                    <h3 class="block-title">general</h3>
                    <div class="block-body">
                        <label class="field">
                            <span class="field-label">title <span class="req">*</span></span>
                            <input
                                v-model="form.title"
                                type="text"
                                class="input"
                                placeholder="Database migration"
                                required
                                autocomplete="off"
                            >
                        </label>
                        <label class="field">
                            <span class="field-label">description</span>
                            <textarea
                                v-model="form.description"
                                class="input textarea"
                                placeholder="What's happening, who's running it, how long it should take. Markdown supported."
                                rows="3"
                            ></textarea>
                            <span class="field-help">shown to visitors of attached status pages while the window is active.</span>
                        </label>
                        <div class="field">
                            <span class="field-label">enabled</span>
                            <div class="row-toggle">
                                <span class="toggle-label-text">{{ form.active ? "this window is active" : "paused (won't fire even if scheduled)" }}</span>
                                <button
                                    type="button"
                                    class="toggle"
                                    :class="{ on: form.active }"
                                    role="switch"
                                    :aria-checked="form.active ? 'true' : 'false'"
                                    @click="form.active = !form.active"
                                >
                                    <span class="toggle-track"><span class="toggle-thumb"></span></span>
                                </button>
                            </div>
                        </div>
                    </div>
                </section>

                <!-- Schedule -->
                <section class="block">
                    <h3 class="block-title">schedule</h3>
                    <div class="block-body">
                        <div class="field">
                            <span class="field-label">strategy</span>
                            <div class="strategy-grid">
                                <button
                                    v-for="opt in strategyOptions"
                                    :key="opt.value"
                                    type="button"
                                    class="strategy-card"
                                    :class="{ active: form.strategy === opt.value }"
                                    @click="form.strategy = opt.value"
                                >
                                    <span class="strategy-name">{{ opt.label }}</span>
                                    <span class="strategy-desc">{{ opt.desc }}</span>
                                </button>
                            </div>
                        </div>

                        <!-- Single window -->
                        <template v-if="form.strategy === 'single'">
                            <div class="field-row">
                                <label class="field">
                                    <span class="field-label">starts <span class="req">*</span></span>
                                    <input
                                        v-model="form.dateRange[0]"
                                        type="datetime-local"
                                        max="9999-12-31T23:59"
                                        class="input"
                                        required
                                    >
                                </label>
                                <label class="field">
                                    <span class="field-label">ends <span class="req">*</span></span>
                                    <input
                                        v-model="form.dateRange[1]"
                                        type="datetime-local"
                                        max="9999-12-31T23:59"
                                        class="input"
                                        required
                                    >
                                </label>
                            </div>
                        </template>

                        <!-- Cron -->
                        <template v-if="form.strategy === 'cron'">
                            <label class="field">
                                <span class="field-label">cron expression <span class="req">*</span></span>
                                <input
                                    v-model="form.cron"
                                    type="text"
                                    class="input mono"
                                    placeholder="30 3 * * *"
                                    required
                                >
                                <span class="field-help">{{ cronHelp }}</span>
                            </label>
                            <label class="field">
                                <span class="field-label">duration (minutes) <span class="req">*</span></span>
                                <input
                                    v-model.number="form.durationMinutes"
                                    type="number"
                                    min="1"
                                    step="1"
                                    class="input"
                                    required
                                >
                            </label>
                        </template>

                        <!-- Recurring - interval -->
                        <template v-if="form.strategy === 'recurring-interval'">
                            <div class="field-row">
                                <label class="field">
                                    <span class="field-label">every (days) <span class="req">*</span></span>
                                    <input
                                        v-model.number="form.intervalDay"
                                        type="number"
                                        min="1"
                                        max="3650"
                                        step="1"
                                        class="input"
                                        required
                                    >
                                </label>
                                <label class="field">
                                    <span class="field-label">duration (minutes) <span class="req">*</span></span>
                                    <input
                                        v-model.number="form.durationMinutes"
                                        type="number"
                                        min="1"
                                        step="1"
                                        class="input"
                                        required
                                    >
                                </label>
                            </div>
                        </template>

                        <!-- Recurring - weekday -->
                        <template v-if="form.strategy === 'recurring-weekday'">
                            <div class="field">
                                <span class="field-label">days of week</span>
                                <div class="weekday-grid">
                                    <button
                                        v-for="wd in weekdays"
                                        :key="wd.value"
                                        type="button"
                                        class="day-pill"
                                        :class="{ active: form.weekdays.includes(wd.value) }"
                                        @click="toggleWeekday(wd.value)"
                                    >
                                        {{ wd.label }}
                                    </button>
                                </div>
                            </div>
                        </template>

                        <!-- Recurring - day of month -->
                        <template v-if="form.strategy === 'recurring-day-of-month'">
                            <div class="field">
                                <span class="field-label">days of month</span>
                                <div class="dom-grid">
                                    <button
                                        v-for="d in 31"
                                        :key="d"
                                        type="button"
                                        class="day-pill compact"
                                        :class="{ active: form.daysOfMonth.includes(d) }"
                                        @click="toggleDay(d)"
                                    >
                                        {{ d }}
                                    </button>
                                </div>
                                <label class="day-extra">
                                    <input
                                        type="checkbox"
                                        :checked="form.daysOfMonth.includes('lastDay1')"
                                        @change="toggleDay('lastDay1')"
                                    >
                                    <span>also fire on the last day of the month</span>
                                </label>
                            </div>
                        </template>

                        <!-- Recurring schedules: time-of-day window -->
                        <template v-if="needsTimeWindow">
                            <div class="field-row">
                                <label class="field">
                                    <span class="field-label">starts at <span class="req">*</span></span>
                                    <input
                                        v-model="timeRangeStart"
                                        type="time"
                                        class="input"
                                        required
                                    >
                                </label>
                                <label class="field">
                                    <span class="field-label">ends at <span class="req">*</span></span>
                                    <input
                                        v-model="timeRangeEnd"
                                        type="time"
                                        class="input"
                                        required
                                    >
                                </label>
                            </div>
                        </template>

                        <!-- Effective range (cron + recurring) -->
                        <template v-if="needsEffectiveRange">
                            <div class="field-row">
                                <label class="field">
                                    <span class="field-label">effective from</span>
                                    <input
                                        v-model="form.dateRange[0]"
                                        type="datetime-local"
                                        max="9999-12-31T23:59"
                                        class="input"
                                    >
                                </label>
                                <label class="field">
                                    <span class="field-label">effective until</span>
                                    <input
                                        v-model="form.dateRange[1]"
                                        type="datetime-local"
                                        max="9999-12-31T23:59"
                                        class="input"
                                    >
                                </label>
                            </div>
                            <span class="field-help section-help">leave blank to run indefinitely.</span>
                        </template>

                        <!-- Timezone -->
                        <label v-if="form.strategy !== 'manual'" class="field">
                            <span class="field-label">timezone</span>
                            <select v-model="form.timezoneOption" class="input select">
                                <option :value="null">(use server timezone)</option>
                                <option value="UTC">UTC</option>
                                <option
                                    v-for="tz in timezones"
                                    :key="tz.value"
                                    :value="tz.value"
                                >{{ tz.name }}</option>
                            </select>
                        </label>

                        <p v-if="form.strategy === 'manual'" class="block-empty">
                            Manual windows have no schedule — toggle them on or off from the list whenever an ad-hoc maintenance starts.
                        </p>
                    </div>
                </section>

                <!-- Affected monitors -->
                <section class="block">
                    <h3 class="block-title-row">affected monitors</h3>
                    <div class="block-body">
                        <p v-if="availableMonitors.length === 0" class="block-empty">
                            No monitors available. Add one before scheduling maintenance.
                        </p>
                        <template v-else>
                            <div class="chip-row">
                                <span
                                    v-for="m in selectedMonitorObjs"
                                    :key="m.id"
                                    class="monitor-chip"
                                >
                                    <span class="monitor-chip-dot" :class="`tone-${chipStatus(m.id)}`"></span>
                                    <span class="monitor-chip-name">{{ m.name }}</span>
                                    <button
                                        type="button"
                                        class="monitor-chip-x"
                                        title="Remove"
                                        @click="removeMonitor(m.id)"
                                    >×</button>
                                </span>
                                <select
                                    class="input monitor-select"
                                    :value="''"
                                    @change="addMonitor($event)"
                                >
                                    <option value="">+ add monitor…</option>
                                    <option
                                        v-for="m in unselectedMonitors"
                                        :key="m.id"
                                        :value="m.id"
                                    >
                                        {{ m.name }}
                                    </option>
                                </select>
                            </div>
                            <span class="field-help">heartbeats from these monitors are tagged "under maintenance" while the window is active — alerts are suppressed.</span>
                        </template>
                    </div>
                </section>

                <!-- Status pages -->
                <section class="block">
                    <h3 class="block-title-row">status pages</h3>
                    <div class="block-body">
                        <label class="day-extra">
                            <input
                                type="checkbox"
                                :checked="form.showOnAllPages"
                                @change="toggleShowOnAll"
                            >
                            <span>show on all status pages</span>
                        </label>
                        <template v-if="!form.showOnAllPages">
                            <div v-if="availableStatusPages.length === 0" class="block-empty">
                                No status pages yet. <router-link class="inline-link" to="/status-pages/new">create one</router-link> if you want visitors to see the window.
                            </div>
                            <div v-else class="chip-row">
                                <span
                                    v-for="sp in selectedStatusPageObjs"
                                    :key="sp.slug"
                                    class="monitor-chip"
                                >
                                    <span class="monitor-chip-name">{{ sp.title }}</span>
                                    <button
                                        type="button"
                                        class="monitor-chip-x"
                                        title="Remove"
                                        @click="removeStatusPage(sp.slug)"
                                    >×</button>
                                </span>
                                <select
                                    class="input monitor-select"
                                    :value="''"
                                    @change="addStatusPage($event)"
                                >
                                    <option value="">+ add status page…</option>
                                    <option
                                        v-for="sp in unselectedStatusPages"
                                        :key="sp.slug"
                                        :value="sp.slug"
                                    >
                                        {{ sp.title }}
                                    </option>
                                </select>
                            </div>
                        </template>
                    </div>
                </section>

                <footer class="form-foot">
                    <span v-if="error" class="form-error">{{ error }}</span>
                    <span v-else-if="savedRecently" class="form-saved">saved</span>

                    <button
                        v-if="mode === 'edit'"
                        type="button"
                        class="action danger-outline"
                        :disabled="saving"
                        @click="askDelete"
                    >
                        delete window
                    </button>
                    <button type="button" class="action" :disabled="saving" @click="onCancel">cancel</button>
                    <button type="submit" class="action primary" :disabled="!canSave || saving">
                        <span v-if="!saving">{{ mode === "create" ? "schedule window" : "save changes" }}</span>
                        <span v-else>saving…</span>
                    </button>
                </footer>
            </form>
        </main>

        <CommandPalette />

        <ConfirmV2
            :open="pendingDelete"
            tone="danger"
            title="delete maintenance"
            confirm-label="delete window"
            busy-label="deleting…"
            :busy="deleteSaving"
            @cancel="cancelDelete"
            @confirm="confirmDelete"
        >
            Permanently delete <strong>{{ form.title || `maintenance #${form.id}` }}</strong>? Monitor associations are removed too.
        </ConfirmV2>
    </div>
</template>

<script>
import cronstrue from "cronstrue";
import CommandPalette from "./CommandPalette.vue";
import ConfirmV2 from "./ConfirmV2.vue";
import LoaderBars from "./LoaderBars.vue";
import MenuTrigger from "./MenuTrigger.vue";
import { timezoneList } from "../../util-frontend";

const STATUS_KEY_BY_NUM = {
    1: "up",
    0: "down",
    2: "pending",
    3: "maintenance",
};

const STRATEGY_OPTIONS = [
    { value: "manual",
        label: "manual",
        desc: "toggle on/off whenever needed" },
    { value: "single",
        label: "one-shot",
        desc: "single window with start & end" },
    { value: "cron",
        label: "cron",
        desc: "any cron expression + duration" },
    { value: "recurring-interval",
        label: "every N days",
        desc: "fixed interval, e.g. every 7 days" },
    { value: "recurring-weekday",
        label: "weekly",
        desc: "specific days of the week" },
    { value: "recurring-day-of-month",
        label: "monthly",
        desc: "specific dates of the month" },
];

const WEEKDAYS = [
    { value: 1,
        label: "Mon" },
    { value: 2,
        label: "Tue" },
    { value: 3,
        label: "Wed" },
    { value: 4,
        label: "Thu" },
    { value: 5,
        label: "Fri" },
    { value: 6,
        label: "Sat" },
    { value: 0,
        label: "Sun" },
];

/**
 * Pad a number with a leading zero if needed.
 * @param {number} n value to pad
 * @returns {string} padded string
 */
function pad(n) {
    return String(n).padStart(2, "0");
}

export default {
    name: "MaintenanceEditV2",
    components: { CommandPalette,
        ConfirmV2,
        LoaderBars,
        MenuTrigger },
    data() {
        return {
            form: this.emptyForm(),
            loading: true,
            saving: false,
            error: null,
            savedRecently: false,
            savedTimer: null,
            pendingDelete: false,
            deleteSaving: false,
            strategyOptions: STRATEGY_OPTIONS,
            weekdays: WEEKDAYS,
            timezones: timezoneList(),
        };
    },
    computed: {
        mode() {
            return this.routeId ? "edit" : "create";
        },
        routeId() {
            return this.$route.params.id || null;
        },
        availableMonitors() {
            const list = Object.values(this.$root.monitorList || {});
            return list
                .filter(m => m && m.type !== "group")
                .sort((a, b) => (a.name || "").localeCompare(b.name || ""));
        },
        selectedMonitorObjs() {
            const ids = new Set(this.form.affectedMonitors || []);
            return this.availableMonitors.filter(m => ids.has(m.id));
        },
        unselectedMonitors() {
            const ids = new Set(this.form.affectedMonitors || []);
            return this.availableMonitors.filter(m => !ids.has(m.id));
        },
        availableStatusPages() {
            return Object.values(this.$root.statusPageList || {})
                .map(sp => ({ slug: sp.slug,
                    title: sp.title || sp.slug,
                    id: sp.id }))
                .sort((a, b) => (a.title || "").localeCompare(b.title || ""));
        },
        selectedStatusPageObjs() {
            const slugs = new Set(this.form.selectedStatusPages || []);
            return this.availableStatusPages.filter(sp => slugs.has(sp.slug));
        },
        unselectedStatusPages() {
            const slugs = new Set(this.form.selectedStatusPages || []);
            return this.availableStatusPages.filter(sp => !slugs.has(sp.slug));
        },
        needsTimeWindow() {
            return [ "recurring-interval", "recurring-weekday", "recurring-day-of-month" ].includes(this.form.strategy);
        },
        needsEffectiveRange() {
            return [ "cron", "recurring-interval", "recurring-weekday", "recurring-day-of-month" ].includes(this.form.strategy);
        },
        timeRangeStart: {
            get() {
                const t = (this.form.timeRange || [])[0];
                if (!t) {
                    return "02:00";
                }
                return `${pad(t.hours ?? 2)}:${pad(t.minutes ?? 0)}`;
            },
            set(v) {
                const [ h, m ] = (v || "02:00").split(":").map(n => parseInt(n, 10) || 0);
                if (!Array.isArray(this.form.timeRange)) {
                    this.form.timeRange = [{}, {}];
                }
                this.form.timeRange[0] = { hours: h,
                    minutes: m };
            },
        },
        timeRangeEnd: {
            get() {
                const t = (this.form.timeRange || [])[1];
                if (!t) {
                    return "03:00";
                }
                return `${pad(t.hours ?? 3)}:${pad(t.minutes ?? 0)}`;
            },
            set(v) {
                const [ h, m ] = (v || "03:00").split(":").map(n => parseInt(n, 10) || 0);
                if (!Array.isArray(this.form.timeRange)) {
                    this.form.timeRange = [{}, {}];
                }
                this.form.timeRange[1] = { hours: h,
                    minutes: m };
            },
        },
        cronHelp() {
            if (!this.form.cron) {
                return "minute hour day month weekday — e.g. \"30 3 * * *\" runs at 03:30 every day.";
            }
            try {
                return cronstrue.toString(this.form.cron);
            } catch (e) {
                return `invalid cron: ${e?.message || "could not parse"}`;
            }
        },
        canSave() {
            if (!this.form.title?.trim()) {
                return false;
            }
            if ((this.form.affectedMonitors || []).length === 0) {
                return false;
            }
            if (this.form.strategy === "single") {
                if (!this.form.dateRange[0] || !this.form.dateRange[1]) {
                    return false;
                }
            }
            if (this.form.strategy === "cron") {
                if (!this.form.cron?.trim() || !this.form.durationMinutes) {
                    return false;
                }
            }
            if (this.form.strategy === "recurring-interval" && !this.form.intervalDay) {
                return false;
            }
            if (this.form.strategy === "recurring-weekday" && (this.form.weekdays || []).length === 0) {
                return false;
            }
            if (this.form.strategy === "recurring-day-of-month" && (this.form.daysOfMonth || []).length === 0) {
                return false;
            }
            return true;
        },
    },
    watch: {
        routeId: {
            immediate: true,
            handler() {
                this.hydrate();
            },
        },
    },
    beforeUnmount() {
        clearTimeout(this.savedTimer);
    },
    methods: {
        emptyForm() {
            return {
                id: null,
                title: "",
                description: "",
                strategy: "single",
                active: true,
                cron: "30 3 * * *",
                durationMinutes: 60,
                intervalDay: 1,
                dateRange: [ "", "" ],
                timeRange: [{ hours: 2,
                    minutes: 0 }, { hours: 3,
                    minutes: 0 }],
                weekdays: [],
                daysOfMonth: [],
                timezoneOption: null,
                affectedMonitors: [],
                showOnAllPages: false,
                selectedStatusPages: [],
            };
        },
        async hydrate() {
            this.loading = true;
            this.error = null;
            try {
                if (this.mode === "edit") {
                    const id = Number(this.routeId);
                    const { data } = await this.$root.api.get(`/maintenance/${id}`);
                    if (!data?.ok) {
                        this.error = "could not load maintenance";
                        return;
                    }
                    const m = this.$root.sanitizeMaintenance(data.maintenance || {});
                    const empty = this.emptyForm();
                    this.form = {
                        ...empty,
                        ...m,
                        id,
                        active: m.active !== false && m.active !== 0,
                        dateRange: Array.isArray(m.dateRange) && m.dateRange.length >= 2
                            ? [ m.dateRange[0] || "", m.dateRange[1] || "" ]
                            : [ "", "" ],
                        timeRange: Array.isArray(m.timeRange) && m.timeRange.length >= 2
                            ? m.timeRange
                            : empty.timeRange,
                        weekdays: Array.isArray(m.weekdays) ? m.weekdays : [],
                        daysOfMonth: Array.isArray(m.daysOfMonth) ? m.daysOfMonth : [],
                        timezoneOption: m.timezoneOption ?? null,
                        affectedMonitors: [],
                        showOnAllPages: false,
                        selectedStatusPages: [],
                    };

                    // Affected monitors.
                    try {
                        const { data: mr } = await this.$root.api.get(`/maintenance/${id}/monitors`);
                        if (mr?.ok) {
                            this.form.affectedMonitors = (mr.monitors || []).map(x => x.id);
                        }
                    } catch (e) {
                        console.warn("could not load maintenance monitors", e);
                    }

                    // Status pages.
                    try {
                        const { data: sr } = await this.$root.api.get(`/maintenance/${id}/status-pages`);
                        if (sr?.ok) {
                            const list = sr.statusPages || [];
                            const all = this.availableStatusPages;
                            const selected = list
                                .map(sp => {
                                    if (sp.slug) {
                                        return sp.slug;
                                    }
                                    const match = all.find(a => a.id === sp.id || a.title === sp.title);
                                    return match?.slug;
                                })
                                .filter(Boolean);
                            this.form.selectedStatusPages = selected;
                            this.form.showOnAllPages = all.length > 0 && selected.length === all.length;
                        }
                    } catch (e) {
                        console.warn("could not load maintenance status pages", e);
                    }
                } else {
                    this.form = this.emptyForm();
                }
            } catch (e) {
                console.warn("hydrate failed", e);
                this.error = e?.response?.data?.detail || "could not load maintenance";
            } finally {
                this.loading = false;
            }
        },
        toggleWeekday(value) {
            const set = new Set(this.form.weekdays || []);
            if (set.has(value)) {
                set.delete(value);
            } else {
                set.add(value);
            }
            this.form.weekdays = [ ...set ].sort((a, b) => a - b);
        },
        toggleDay(value) {
            const arr = this.form.daysOfMonth || [];
            const idx = arr.indexOf(value);
            if (idx >= 0) {
                arr.splice(idx, 1);
            } else {
                arr.push(value);
                arr.sort((a, b) => {
                    if (typeof a === "number" && typeof b === "number") {
                        return a - b;
                    }
                    return String(a).localeCompare(String(b));
                });
            }
            this.form.daysOfMonth = [ ...arr ];
        },
        addMonitor(e) {
            const id = Number(e.target?.value);
            if (!Number.isFinite(id)) {
                return;
            }
            if (!this.form.affectedMonitors.includes(id)) {
                this.form.affectedMonitors.push(id);
            }
            if (e.target) {
                e.target.value = "";
            }
        },
        removeMonitor(id) {
            this.form.affectedMonitors = this.form.affectedMonitors.filter(x => x !== id);
        },
        addStatusPage(e) {
            const slug = e.target?.value;
            if (!slug) {
                return;
            }
            if (!this.form.selectedStatusPages.includes(slug)) {
                this.form.selectedStatusPages.push(slug);
            }
            if (e.target) {
                e.target.value = "";
            }
        },
        removeStatusPage(slug) {
            this.form.selectedStatusPages = this.form.selectedStatusPages.filter(x => x !== slug);
        },
        toggleShowOnAll(e) {
            this.form.showOnAllPages = !!e.target.checked;
        },
        chipStatus(monitorId) {
            const last = this.$root.lastHeartbeatList?.[monitorId];
            if (!last) {
                return "unknown";
            }
            return STATUS_KEY_BY_NUM[last.status] || "unknown";
        },
        buildPayload() {
            const f = this.form;
            const payload = {
                title: (f.title || "").trim(),
                description: f.description || "",
                strategy: f.strategy,
                active: !!f.active,
                timezoneOption: f.timezoneOption || null,
            };
            if (f.strategy === "single") {
                payload.dateRange = [ f.dateRange[0] || "", f.dateRange[1] || "" ];
            }
            if (f.strategy === "cron") {
                payload.cron = (f.cron || "").trim();
                payload.durationMinutes = Number(f.durationMinutes) || 0;
                payload.dateRange = [ f.dateRange[0] || "", f.dateRange[1] || "" ];
            }
            if (f.strategy === "recurring-interval") {
                payload.intervalDay = Number(f.intervalDay) || 1;
                payload.timeRange = f.timeRange;
                payload.dateRange = [ f.dateRange[0] || "", f.dateRange[1] || "" ];
            }
            if (f.strategy === "recurring-weekday") {
                payload.weekdays = [ ...(f.weekdays || []) ];
                payload.timeRange = f.timeRange;
                payload.dateRange = [ f.dateRange[0] || "", f.dateRange[1] || "" ];
            }
            if (f.strategy === "recurring-day-of-month") {
                payload.daysOfMonth = [ ...(f.daysOfMonth || []) ];
                payload.timeRange = f.timeRange;
                payload.dateRange = [ f.dateRange[0] || "", f.dateRange[1] || "" ];
            }
            return payload;
        },
        async syncMonitors(id) {
            const monitors = this.form.affectedMonitors.map(mid => {
                const m = this.availableMonitors.find(x => x.id === mid);
                return { id: mid,
                    name: m?.name || `monitor #${mid}` };
            });
            await this.$root.api.post(`/maintenance/${id}/monitors`, { monitors });
        },
        async syncStatusPages(id) {
            let pages;
            if (this.form.showOnAllPages) {
                pages = this.availableStatusPages.map(sp => ({ id: sp.slug,
                    name: sp.title }));
            } else {
                pages = this.form.selectedStatusPages.map(slug => {
                    const sp = this.availableStatusPages.find(x => x.slug === slug);
                    return { id: slug,
                        name: sp?.title || slug };
                });
            }
            await this.$root.api.post(`/maintenance/${id}/status-pages`, { statusPages: pages });
        },
        async onSave() {
            if (!this.canSave || this.saving) {
                return;
            }
            this.saving = true;
            this.error = null;
            this.savedRecently = false;
            try {
                const payload = this.buildPayload();
                if (this.mode === "create") {
                    const { data } = await this.$root.api.post("/maintenance", payload);
                    if (data?.ok === false) {
                        this.error = data?.msg || "could not create maintenance";
                        return;
                    }
                    const newId = data?.maintenanceID || data?.maintenance_id;
                    if (newId) {
                        await this.syncMonitors(newId);
                        await this.syncStatusPages(newId);
                    }
                    if (typeof this.$root.loadMaintenances === "function") {
                        this.$root.loadMaintenances().catch(() => {});
                    }
                    this.$router.push("/maintenance");
                } else {
                    const id = Number(this.routeId);
                    const { data } = await this.$root.api.post(`/maintenance/${id}`, payload);
                    if (data?.ok === false) {
                        this.error = data?.msg || "could not save changes";
                        return;
                    }
                    await this.syncMonitors(id);
                    await this.syncStatusPages(id);
                    if (typeof this.$root.loadMaintenances === "function") {
                        this.$root.loadMaintenances().catch(() => {});
                    }
                    this.savedRecently = true;
                    clearTimeout(this.savedTimer);
                    this.savedTimer = setTimeout(() => {
                        this.savedRecently = false;
                    }, 2400);
                }
            } catch (e) {
                this.error = e?.response?.data?.detail || e?.message || "request failed";
            } finally {
                this.saving = false;
            }
        },
        onCancel() {
            this.$router.push("/maintenance");
        },
        askDelete() {
            this.pendingDelete = true;
        },
        cancelDelete() {
            if (this.deleteSaving) {
                return;
            }
            this.pendingDelete = false;
        },
        async confirmDelete() {
            const id = Number(this.routeId);
            if (!id) {
                return;
            }
            this.deleteSaving = true;
            try {
                await this.$root.api.delete(`/maintenance/${id}`);
                if (typeof this.$root.loadMaintenances === "function") {
                    this.$root.loadMaintenances().catch(() => {});
                }
                this.$router.push("/maintenance");
            } catch (e) {
                this.error = e?.response?.data?.detail || "could not delete";
            } finally {
                this.deleteSaving = false;
                this.pendingDelete = false;
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@import "./_base.scss";

.v2-maintenance-edit {
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
    gap: 8px;
}

.main {
    max-width: 920px;
    margin: 24px auto 0;
    animation: v2-up 320ms var(--enter-ease) both;
    animation-delay: 60ms;
}

.page-loading {
    display: flex;
    justify-content: center;
    padding: 80px 0;
}

.form {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.block {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
}

.block-title,
.block-title-row {
    margin: 0;
    padding: 14px 18px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-faint);
    font-weight: 600;
    border-bottom: 1px solid var(--border);
}

.block-body {
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.block-empty {
    margin: 0;
    color: var(--text-muted);
    font-size: 13px;
    line-height: 1.55;
}

.field {
    display: flex;
    flex-direction: column;
    gap: 6px;

    .req {
        color: hsl(0 84% 60%);
        margin-left: 2px;
    }
}

.field-row {
    display: flex;
    gap: 12px;
    align-items: stretch;

    .field { flex: 1; }
}

.field-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
}

.field-help {
    font-size: 11px;
    color: var(--text-faint);
    line-height: 1.5;

    &.section-help { margin-top: -6px; }
}

.input {
    appearance: none;
    background: hsl(0 0% 6%);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    font-size: 14px;
    font-family: inherit;
    padding: 10px 12px;
    transition: border-color 140ms ease, background 140ms ease, box-shadow 140ms ease;

    &::placeholder { color: var(--text-faint); }
    &:hover { border-color: var(--border-strong); }
    &:focus {
        outline: none;
        background: var(--bg-hover);
        border-color: hsl(38 92% 55%);
        box-shadow: 0 0 0 3px hsl(38 92% 55% / 0.2);
    }

    &.mono {
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 13px;
    }
}

.textarea {
    resize: vertical;
    min-height: 70px;
    line-height: 1.5;
}

.select {
    cursor: pointer;
}

.row-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    background: hsl(0 0% 6%);
    border: 1px solid var(--border);
    border-radius: 8px;

    .toggle-label-text {
        font-size: 12.5px;
        color: var(--text);
    }
}

.toggle {
    appearance: none;
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0;

    .toggle-track {
        position: relative;
        width: 38px;
        height: 22px;
        background: hsl(0 0% 14%);
        border: 1px solid var(--border);
        border-radius: 999px;
        transition: background 160ms ease, border-color 160ms ease;
        display: inline-block;
    }

    .toggle-thumb {
        position: absolute;
        top: 2px;
        left: 2px;
        width: 16px;
        height: 16px;
        background: var(--text-faint);
        border-radius: 50%;
        transition: transform 220ms $v2-ease, background 160ms ease;
    }

    &.on .toggle-track {
        background: hsl(38 92% 50% / 0.22);
        border-color: hsl(38 92% 50% / 0.5);
    }

    &.on .toggle-thumb {
        transform: translateX(16px);
        background: hsl(38 92% 60%);
    }
}

.strategy-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 8px;
}

.strategy-card {
    appearance: none;
    text-align: left;
    background: hsl(0 0% 6%);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 12px;
    color: var(--text);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 3px;
    transition: background 140ms ease, border-color 140ms ease, transform 140ms ease;

    &:hover {
        background: var(--bg-hover);
        border-color: var(--border-strong);
    }

    &.active {
        background: hsl(38 92% 50% / 0.12);
        border-color: hsl(38 92% 50% / 0.55);

        .strategy-name { color: hsl(38 92% 75%); }
    }

    .strategy-name {
        font-size: 13px;
        font-weight: 600;
    }

    .strategy-desc {
        font-size: 11px;
        color: var(--text-faint);
        line-height: 1.4;
    }
}

.weekday-grid,
.dom-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.day-pill {
    appearance: none;
    background: hsl(0 0% 6%);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text-muted);
    font-size: 12px;
    padding: 8px 12px;
    cursor: pointer;
    min-width: 48px;
    text-align: center;
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease;

    &:hover {
        background: var(--bg-hover);
        color: var(--text);
        border-color: var(--border-strong);
    }

    &.active {
        background: hsl(38 92% 50% / 0.18);
        border-color: hsl(38 92% 50% / 0.55);
        color: hsl(38 92% 75%);
    }

    &.compact {
        min-width: 36px;
        padding: 6px 0;
    }
}

.day-extra {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text);
    cursor: pointer;
    user-select: none;

    input[type="checkbox"] {
        appearance: none;
        width: 16px;
        height: 16px;
        background: hsl(0 0% 6%);
        border: 1px solid var(--border-strong);
        border-radius: 4px;
        cursor: pointer;
        position: relative;
        transition: background 140ms ease, border-color 140ms ease;

        &:checked {
            background: hsl(38 92% 50%);
            border-color: hsl(38 92% 50%);

            &::after {
                content: "";
                position: absolute;
                left: 4px;
                top: 1px;
                width: 5px;
                height: 9px;
                border: solid hsl(0 0% 6%);
                border-width: 0 2px 2px 0;
                transform: rotate(45deg);
            }
        }
    }
}

.chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.monitor-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 4px 4px 10px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 999px;
    font-size: 12px;
    color: var(--text);

    .monitor-chip-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: hsl(0 0% 38%);

        &.tone-up { background: hsl(142 71% 45%); }
        &.tone-down { background: hsl(0 84% 60%); }
        &.tone-pending { background: hsl(38 92% 55%); }
        &.tone-maintenance { background: hsl(217 91% 60%); }
    }

    .monitor-chip-x {
        appearance: none;
        background: transparent;
        border: none;
        color: var(--text-faint);
        font-size: 14px;
        line-height: 1;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        cursor: pointer;

        &:hover {
            background: var(--bg-hover);
            color: var(--text);
        }
    }
}

.monitor-select {
    background: var(--bg-soft);
    font-size: 12px;
    padding: 5px 10px;
    border-radius: 999px;
    color: var(--text-muted);
    border: 1px dashed var(--border-strong);
    cursor: pointer;
    min-width: 200px;

    &:hover {
        background: var(--bg-hover);
        color: var(--text);
        border-style: solid;
    }
}

.inline-link {
    color: hsl(38 92% 70%);
    text-decoration: underline;
    text-decoration-color: hsl(38 92% 50% / 0.4);
    text-underline-offset: 2px;

    &:hover { color: hsl(38 92% 80%); }
}

.form-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 4px;

    .form-error,
    .form-saved {
        flex: 1;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        text-align: left;
    }

    .form-error { color: hsl(0 84% 65%); }
    .form-saved { color: hsl(142 71% 65%); }
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

    &:disabled { opacity: 0.45; cursor: not-allowed; }

    &.primary {
        background: hsl(38 92% 50% / 0.18);
        border-color: hsl(38 92% 50% / 0.5);
        color: hsl(38 92% 70%);

        &:hover:not(:disabled) {
            background: hsl(38 92% 50% / 0.28);
            border-color: hsl(38 92% 50% / 0.75);
            color: hsl(38 92% 80%);
            transform: translateY(-1px);
        }
    }

    &.danger-outline {
        background: transparent;
        border-color: hsl(0 84% 60% / 0.4);
        color: hsl(0 84% 70%);

        &:hover:not(:disabled) {
            background: hsl(0 84% 60% / 0.12);
            border-color: hsl(0 84% 60% / 0.7);
            color: hsl(0 84% 80%);
        }
    }
}

@media (max-width: 760px) {
    .v2-maintenance-edit { padding: 0 16px 40px; }

    .field-row { flex-direction: column; }

    .form-foot {
        flex-wrap: wrap;
        justify-content: stretch;

        .form-error,
        .form-saved {
            flex-basis: 100%;
        }
    }
}
</style>
