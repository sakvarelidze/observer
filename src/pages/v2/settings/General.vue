<template>
    <div class="settings-page">
        <header class="page-head">
            <h2 class="page-title">General</h2>
            <p class="page-sub">core workspace settings — timezone, entry page, base URL.</p>
        </header>

        <div v-if="loading" class="page-loading">
            <LoaderBars size="md" />
        </div>

        <form v-else class="form" @submit.prevent="onSave">
            <label class="field">
                <span class="field-label">display timezone</span>
                <select v-model="userTimezone" class="input">
                    <option value="auto">auto · {{ guessTimezone }}</option>
                    <option v-for="tz in timezoneList" :key="tz.value" :value="tz.value">
                        {{ tz.name }}
                    </option>
                </select>
                <span class="field-help">how dates and times render in your dashboard.</span>
            </label>

            <label class="field">
                <span class="field-label">server timezone</span>
                <select v-model="settings.serverTimezone" class="input">
                    <option value="UTC">UTC</option>
                    <option v-for="tz in timezoneList" :key="tz.value" :value="tz.value">
                        {{ tz.name }}
                    </option>
                </select>
                <span class="field-help">used internally by the probe scheduler. utc is a safe default.</span>
            </label>

            <div class="field row-toggle">
                <div class="toggle-text">
                    <span class="field-label">search engine indexing</span>
                    <span class="field-help">when off, status pages and the dashboard add a noindex meta tag.</span>
                </div>
                <button
                    type="button"
                    class="toggle"
                    :class="{ on: !!settings.searchEngineIndex }"
                    role="switch"
                    :aria-checked="settings.searchEngineIndex ? 'true' : 'false'"
                    @click="settings.searchEngineIndex = !settings.searchEngineIndex"
                >
                    <span class="toggle-track"><span class="toggle-thumb"></span></span>
                    <span class="toggle-label">{{ settings.searchEngineIndex ? "allowed" : "discouraged" }}</span>
                </button>
            </div>

            <div class="field">
                <span class="field-label">entry page</span>
                <span class="field-help">where logged-out visitors land when they hit the root URL.</span>
                <div class="radio-group">
                    <label class="radio-row">
                        <input
                            v-model="settings.entryPage"
                            type="radio"
                            name="entryPage"
                            value="dashboard"
                        >
                        <span class="radio-label">
                            <span class="radio-title">dashboard</span>
                            <span class="radio-help">redirect to the dashboard (login required).</span>
                        </span>
                    </label>
                    <label
                        v-for="page in statusPages"
                        :key="page.slug"
                        class="radio-row"
                    >
                        <input
                            v-model="settings.entryPage"
                            type="radio"
                            name="entryPage"
                            :value="`statusPage-${page.slug}`"
                        >
                        <span class="radio-label">
                            <span class="radio-title">status page · {{ page.title }}</span>
                            <span class="radio-help">/status/{{ page.slug }}</span>
                        </span>
                    </label>
                </div>
            </div>

            <label class="field">
                <span class="field-label">primary base URL</span>
                <div class="input-action-row">
                    <input
                        v-model="settings.primaryBaseURL"
                        type="text"
                        class="input"
                        placeholder="https://"
                        pattern="https?://.+"
                        autocomplete="off"
                    >
                    <button type="button" class="action ghost" @click="autoBaseUrl">
                        auto-detect
                    </button>
                </div>
                <span class="field-help">used in notification messages and external links.</span>
            </label>

            <div v-if="$root.info?.isContainer" class="field row-toggle">
                <div class="toggle-text">
                    <span class="field-label">DNS cache (nscd)</span>
                    <span class="field-help">recommended on docker — caches DNS lookups so transient resolver hiccups don't trigger false alarms.</span>
                </div>
                <button
                    type="button"
                    class="toggle"
                    :class="{ on: !!settings.nscd }"
                    role="switch"
                    :aria-checked="settings.nscd ? 'true' : 'false'"
                    @click="settings.nscd = !settings.nscd"
                >
                    <span class="toggle-track"><span class="toggle-thumb"></span></span>
                    <span class="toggle-label">{{ settings.nscd ? "enabled" : "disabled" }}</span>
                </button>
            </div>

            <footer class="form-foot">
                <span v-if="error" class="form-error">{{ error }}</span>
                <span v-else-if="savedRecently" class="form-saved">saved</span>
                <button
                    type="submit"
                    class="action primary"
                    :disabled="saving"
                >
                    <span v-if="!saving">save changes</span>
                    <span v-else>saving…</span>
                </button>
            </footer>
        </form>
    </div>
</template>

<script>
import dayjs from "dayjs";
import { timezoneList } from "../../../util-frontend";
import LoaderBars from "../LoaderBars.vue";

export default {
    name: "SettingsGeneral",
    components: { LoaderBars },
    data() {
        return {
            settings: {
                serverTimezone: "UTC",
                searchEngineIndex: false,
                entryPage: "dashboard",
                primaryBaseURL: "",
                nscd: false,
            },
            loading: true,
            saving: false,
            error: null,
            savedRecently: false,
            savedTimer: null,
            timezoneList: timezoneList(),
        };
    },
    computed: {
        userTimezone: {
            get() {
                return this.$root.userTimezone || "auto";
            },
            set(v) {
                this.$root.userTimezone = v;
                localStorage.timezone = v;
            },
        },
        guessTimezone() {
            return dayjs.tz.guess();
        },
        statusPages() {
            const list = this.$root.statusPageList || {};
            return Object.values(list);
        },
    },
    mounted() {
        this.fetchSettings();
    },
    beforeUnmount() {
        clearTimeout(this.savedTimer);
    },
    methods: {
        async fetchSettings() {
            this.loading = true;
            this.error = null;
            try {
                const { data } = await this.$root.api.get("/settings");
                const incoming = data?.data || {};
                this.settings = {
                    serverTimezone: incoming.serverTimezone || "UTC",
                    searchEngineIndex: !!incoming.searchEngineIndex,
                    entryPage: incoming.entryPage || "dashboard",
                    primaryBaseURL: incoming.primaryBaseURL || "",
                    nscd: !!incoming.nscd,
                };
            } catch (e) {
                this.error = e?.response?.data?.detail || e?.message || "could not load settings";
            } finally {
                this.loading = false;
            }
        },
        autoBaseUrl() {
            if (typeof window !== "undefined") {
                this.settings.primaryBaseURL = window.location.protocol + "//" + window.location.host;
            }
        },
        async onSave() {
            this.saving = true;
            this.error = null;
            this.savedRecently = false;
            try {
                await this.$root.api.post("/settings", { settings: { ...this.settings } });
                this.savedRecently = true;
                clearTimeout(this.savedTimer);
                this.savedTimer = setTimeout(() => {
                    this.savedRecently = false;
                }, 2400);
            } catch (e) {
                this.error = e?.response?.data?.detail || e?.message || "could not save settings";
            } finally {
                this.saving = false;
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@use "../_base" as *;

.settings-page {
    @include v2-surface-tokens;

    color: var(--text);
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.page-head {
    display: flex;
    flex-direction: column;
    gap: 4px;

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
    }
}

.page-loading {
    display: flex;
    justify-content: center;
    padding: 40px 0;
}

.form {
    display: flex;
    flex-direction: column;
    gap: 18px;
}

.field {
    display: flex;
    flex-direction: column;
    gap: 6px;
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
}

.input {
    appearance: none;
    background: var(--bg-soft);
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
        border-color: hsl(142 71% 45%);
        box-shadow: 0 0 0 3px hsl(142 71% 45% / 0.15);
    }
}

.input-action-row {
    display: flex;
    gap: 6px;

    .input { flex: 1; }
}

.row-toggle {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;
    gap: 16px;

    .toggle-text {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
}

.toggle {
    appearance: none;
    background: transparent;
    border: none;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: var(--text-muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 0;

    .toggle-track {
        position: relative;
        width: 38px;
        height: 22px;
        background: hsl(0 0% 14%);
        border: 1px solid var(--border);
        border-radius: 999px;
        transition: background 160ms ease, border-color 160ms ease;
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

    &.on {
        color: hsl(142 71% 70%);
        .toggle-track {
            background: hsl(142 71% 45% / 0.22);
            border-color: hsl(142 71% 45% / 0.5);
        }
        .toggle-thumb {
            transform: translateX(16px);
            background: hsl(142 71% 60%);
        }
    }
}

.radio-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.radio-row {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 14px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;
    cursor: pointer;
    transition: background 140ms ease, border-color 140ms ease;

    &:hover {
        background: var(--bg-hover);
        border-color: var(--border-strong);
    }

    input[type="radio"] {
        accent-color: hsl(142 71% 45%);
        margin-top: 4px;
    }

    .radio-label {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .radio-title {
        font-size: 13px;
        color: var(--text);
        font-weight: 500;
    }

    .radio-help {
        font-size: 11px;
        color: var(--text-faint);
    }
}

.form-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 8px;

    .form-error,
    .form-saved {
        flex: 1;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-variant-numeric: tabular-nums;
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
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease,
        transform 140ms ease;

    &:hover:not(:disabled) {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        color: var(--text);
    }

    &:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }

    &.ghost { background: transparent; }

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
</style>
