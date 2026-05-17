<template>
    <div class="settings-page">
        <header class="page-head">
            <h2 class="page-title">Monitor History</h2>
            <p class="page-sub">how long to keep heartbeats. older data is dropped to keep the database fast and small.</p>
        </header>

        <div v-if="loading" class="page-loading">
            <LoaderBars size="md" />
        </div>

        <form v-else class="form" @submit.prevent="onSave">
            <label class="field">
                <span class="field-label">keep heartbeats for</span>
                <span class="input-wrap">
                    <input
                        v-model.number="settings.keepDataPeriodDays"
                        type="number"
                        class="input"
                        min="1"
                        max="3650"
                        required
                    >
                    <span class="input-suffix">days</span>
                </span>
                <span class="field-help">heartbeats older than this are pruned in the background. setting it lower frees disk space; setting it higher means longer-range charts have data to render.</span>
            </label>

            <div class="estimate">
                <span class="estimate-label">retention preview</span>
                <span class="estimate-value">
                    {{ retentionPreview }}
                </span>
            </div>

            <footer class="form-foot">
                <span v-if="error" class="form-error">{{ error }}</span>
                <span v-else-if="savedRecently" class="form-saved">saved</span>
                <button
                    type="submit"
                    class="action primary"
                    :disabled="saving || !canSave"
                >
                    <span v-if="!saving">save</span>
                    <span v-else>saving…</span>
                </button>
            </footer>
        </form>
    </div>
</template>

<script>
import LoaderBars from "../LoaderBars.vue";

export default {
    name: "SettingsMonitorHistory",
    components: { LoaderBars },
    data() {
        return {
            settings: { keepDataPeriodDays: 180 },
            loading: true,
            saving: false,
            error: null,
            savedRecently: false,
            savedTimer: null,
        };
    },
    computed: {
        canSave() {
            const v = this.settings.keepDataPeriodDays;
            return Number.isFinite(v) && v >= 1 && v <= 3650;
        },
        retentionPreview() {
            const days = Number(this.settings.keepDataPeriodDays) || 0;
            if (days < 1) {
                return "—";
            }
            if (days < 30) {
                return `roughly ${days} day${days === 1 ? "" : "s"} of recent activity`;
            }
            if (days < 365) {
                const months = Math.round(days / 30);
                return `roughly ${months} month${months === 1 ? "" : "s"} of activity`;
            }
            const years = (days / 365).toFixed(days < 730 ? 1 : 0);
            return `roughly ${years} year${parseFloat(years) === 1 ? "" : "s"} of activity`;
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
                    keepDataPeriodDays: Number.isFinite(Number(incoming.keepDataPeriodDays))
                        ? Number(incoming.keepDataPeriodDays)
                        : 180,
                };
            } catch (e) {
                this.error = e?.response?.data?.detail || e?.message || "could not load settings";
            } finally {
                this.loading = false;
            }
        },
        async onSave() {
            if (!this.canSave) {
                return;
            }
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
                this.error = e?.response?.data?.detail || e?.message || "could not save";
            } finally {
                this.saving = false;
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@import "../_base.scss";

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
    max-width: 60ch;
}

.input-wrap {
    position: relative;
    display: flex;
    align-items: center;

    .input {
        flex: 1;
        padding-right: 56px;
    }

    .input-suffix {
        position: absolute;
        right: 12px;
        font-size: 12px;
        color: var(--text-faint);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        pointer-events: none;
    }
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

    &:hover { border-color: var(--border-strong); }
    &:focus {
        outline: none;
        background: var(--bg-hover);
        border-color: hsl(142 71% 45%);
        box-shadow: 0 0 0 3px hsl(142 71% 45% / 0.15);
    }
}

.estimate {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 16px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;

    .estimate-label {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--text-faint);
    }

    .estimate-value {
        font-size: 14px;
        color: var(--text);
        font-variant-numeric: tabular-nums;
    }
}

.form-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 4px;

    .form-error,
    .form-saved {
        flex: 1;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
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
