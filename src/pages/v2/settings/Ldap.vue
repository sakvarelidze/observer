<template>
    <div class="settings-page">
        <header class="page-head">
            <h2 class="page-title">LDAP</h2>
            <p class="page-sub">optional fall-through directory auth. when configured, sign-ins that don't match a local user are tried against the directory.</p>
        </header>

        <div v-if="loading" class="page-loading">
            <LoaderBars size="md" />
        </div>

        <form v-else class="form" autocomplete="off" @submit.prevent="onSave">
            <div class="info-banner" :class="configured ? 'tone-on' : 'tone-off'">
                <span class="info-dot"></span>
                <span class="info-text">
                    <span class="info-status">{{ configured ? "configured" : "disabled" }}</span>
                    <span class="info-help">{{ configured
                        ? "sign-ins falling through local accounts will hit your directory."
                        : "leave both fields blank to keep LDAP off." }}</span>
                </span>
            </div>

            <label class="field">
                <span class="field-label">LDAP URL</span>
                <input
                    v-model="settings.ldapURL"
                    type="text"
                    class="input mono"
                    placeholder="ldap://example.com"
                    autocomplete="off"
                >
                <span class="field-help">connection URL to your directory server. supports <code>ldap://</code> or <code>ldaps://</code>.</span>
            </label>

            <label class="field">
                <span class="field-label">DN template</span>
                <input
                    v-model="settings.ldapDNTemplate"
                    type="text"
                    class="input mono"
                    placeholder="uid={username},ou=people,dc=example,dc=com"
                    autocomplete="off"
                >
                <span class="field-help">user binding template — <code>{username}</code> is replaced with whatever the user types into the login form.</span>
            </label>

            <footer class="form-foot">
                <span v-if="error" class="form-error">{{ error }}</span>
                <span v-else-if="savedRecently" class="form-saved">saved</span>
                <button
                    type="button"
                    class="action ghost"
                    :disabled="saving || !configured"
                    @click="clearLdap"
                >
                    clear &amp; disable
                </button>
                <button type="submit" class="action primary" :disabled="saving">
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
    name: "SettingsLdap",
    components: { LoaderBars },
    data() {
        return {
            settings: {
                ldapURL: "",
                ldapDNTemplate: "",
            },
            loading: true,
            saving: false,
            error: null,
            savedRecently: false,
            savedTimer: null,
        };
    },
    computed: {
        configured() {
            return !!this.settings.ldapURL?.trim() || !!this.settings.ldapDNTemplate?.trim();
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
                    ldapURL: incoming.ldapURL || "",
                    ldapDNTemplate: incoming.ldapDNTemplate || "",
                };
            } catch (e) {
                this.error = e?.response?.data?.detail || e?.message || "could not load settings";
            } finally {
                this.loading = false;
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
        async clearLdap() {
            this.settings.ldapURL = "";
            this.settings.ldapDNTemplate = "";
            await this.onSave();
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
        max-width: 60ch;
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

.info-banner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;

    .info-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: hsl(0 0% 38%);
        flex: none;
    }

    .info-text {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .info-status {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 600;
        color: var(--text);
    }

    .info-help {
        font-size: 12px;
        color: var(--text-muted);
    }

    &.tone-on {
        border-color: hsl(142 71% 45% / 0.4);
        background: hsl(142 71% 45% / 0.06);

        .info-dot {
            background: hsl(142 71% 45%);
            box-shadow: 0 0 0 4px hsl(142 71% 45% / 0.15);
        }

        .info-status { color: hsl(142 71% 75%); }
    }

    &.tone-off {
        .info-dot {
            background: hsl(0 0% 38%);
        }
    }
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

    code {
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 10.5px;
        padding: 1px 5px;
        background: var(--bg-soft);
        border: 1px solid var(--border);
        border-radius: 4px;
        color: var(--text-muted);
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

    &::placeholder { color: var(--text-faint); }
    &:hover { border-color: var(--border-strong); }
    &:focus {
        outline: none;
        background: var(--bg-hover);
        border-color: hsl(142 71% 45%);
        box-shadow: 0 0 0 3px hsl(142 71% 45% / 0.15);
    }

    &.mono {
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 13px;
    }
}

.form-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 8px;

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
