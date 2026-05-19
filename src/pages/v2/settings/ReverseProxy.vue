<template>
    <div class="settings-page">
        <header class="page-head">
            <h2 class="page-title">Reverse Proxy</h2>
            <p class="page-sub">trust upstream proxy headers and run a Cloudflare tunnel directly from this instance.</p>
        </header>

        <!-- Trust proxy headers -->
        <section class="block">
            <h3 class="block-title">trust proxy headers</h3>
            <div v-if="settingsLoading" class="block-body centered">
                <LoaderBars size="sm" />
            </div>
            <div v-else class="block-body">
                <div class="row-toggle">
                    <div class="toggle-text">
                        <span class="field-label">trust X-Forwarded-* headers</span>
                        <span class="field-help">turn on when Observer sits behind nginx, Caddy, Cloudflare, or any other reverse proxy that rewrites client IPs in headers. when off, Observer treats the connecting peer as the source of every request.</span>
                    </div>
                    <button
                        type="button"
                        class="toggle"
                        :class="{ on: !!settings.trustProxy }"
                        role="switch"
                        :aria-checked="settings.trustProxy ? 'true' : 'false'"
                        @click="toggleTrustProxy"
                    >
                        <span class="toggle-track"><span class="toggle-thumb"></span></span>
                        <span class="toggle-label">{{ settings.trustProxy ? "trusted" : "ignored" }}</span>
                    </button>
                </div>
                <span v-if="settingsError" class="form-error">{{ settingsError }}</span>
                <span v-else-if="settingsSaved" class="form-saved">saved</span>
            </div>
        </section>

        <!-- Cloudflare tunnel -->
        <section class="block">
            <h3 class="block-title">cloudflare tunnel (cloudflared)</h3>
            <div v-if="cfLoading" class="block-body centered">
                <LoaderBars size="sm" />
            </div>
            <div v-else class="block-body cf-body">
                <div v-if="!cfInstalled" class="info-banner tone-warn">
                    <span class="info-dot"></span>
                    <span class="info-text">
                        <span class="info-status">not installed</span>
                        <span class="info-help">the <code>cloudflared</code> binary isn't available on this server. install it via your package manager, then refresh this page.</span>
                    </span>
                </div>

                <div v-else class="cf-status-row">
                    <span class="status-pill" :class="cfRunning ? 'tone-on' : 'tone-off'">
                        <span class="status-pill-dot"></span>
                        <span class="status-pill-label">{{ cfRunning ? "running" : "stopped" }}</span>
                    </span>
                    <span v-if="cfStatusMessage" class="cf-message">{{ cfStatusMessage }}</span>
                </div>

                <div v-if="cfErrorMessage" class="info-banner tone-error">
                    <span class="info-dot"></span>
                    <span class="info-text">
                        <span class="info-status">last error</span>
                        <pre class="info-error-pre">{{ cfErrorMessage }}</pre>
                    </span>
                </div>

                <label v-if="cfInstalled" class="field">
                    <span class="field-label">tunnel token</span>
                    <input
                        v-model="cfTokenDraft"
                        type="password"
                        class="input mono"
                        placeholder="eyJh…"
                        autocomplete="off"
                        :disabled="cfRunning"
                    >
                    <span class="field-help">paste the token from your Cloudflare Zero Trust dashboard. stored encrypted in this server's settings table.</span>
                </label>

                <div v-if="cfInstalled" class="cf-actions">
                    <span v-if="cfActionError" class="form-error">{{ cfActionError }}</span>
                    <span v-else-if="cfActionMessage" class="form-saved">{{ cfActionMessage }}</span>

                    <button
                        v-if="cfHasStoredToken && !cfRunning"
                        type="button"
                        class="action danger-outline"
                        :disabled="cfBusy"
                        @click="askRemoveToken"
                    >
                        clear token
                    </button>

                    <button
                        v-if="!cfRunning"
                        type="button"
                        class="action primary"
                        :disabled="cfBusy || !cfTokenDraft.trim()"
                        @click="startCloudflared"
                    >
                        <font-awesome-icon :icon="cfBusy ? 'spinner' : 'play'" :spin="cfBusy" />
                        <span v-if="!cfBusy">start tunnel</span>
                        <span v-else>starting…</span>
                    </button>

                    <button
                        v-if="cfRunning"
                        type="button"
                        class="action danger-outline"
                        :disabled="cfBusy"
                        @click="askStopCloudflared"
                    >
                        <font-awesome-icon :icon="cfBusy ? 'spinner' : 'pause'" :spin="cfBusy" />
                        <span v-if="!cfBusy">stop tunnel</span>
                        <span v-else>stopping…</span>
                    </button>
                </div>
            </div>
        </section>

        <ConfirmV2
            :open="confirmKind === 'stop'"
            tone="danger"
            title="stop cloudflare tunnel"
            confirm-label="stop tunnel"
            busy-label="stopping…"
            :busy="cfBusy"
            @cancel="cancelConfirm"
            @confirm="confirmStop"
        >
            Stop the tunnel? Inbound traffic via Cloudflare will fail until you start it again.
        </ConfirmV2>

        <ConfirmV2
            :open="confirmKind === 'clear-token'"
            tone="danger"
            title="clear tunnel token"
            confirm-label="clear token"
            busy-label="clearing…"
            :busy="cfBusy"
            @cancel="cancelConfirm"
            @confirm="confirmClearToken"
        >
            Forget the saved tunnel token? You'll need to paste it again to start the tunnel next time.
        </ConfirmV2>
    </div>
</template>

<script>
import LoaderBars from "../LoaderBars.vue";
import ConfirmV2 from "../ConfirmV2.vue";

export default {
    name: "SettingsReverseProxy",
    components: { LoaderBars,
        ConfirmV2 },
    data() {
        return {
            // trustProxy setting
            settings: { trustProxy: false },
            settingsLoading: true,
            settingsError: null,
            settingsSaved: false,
            settingsSavedTimer: null,

            // Cloudflared
            cfLoading: true,
            cfStatus: {},
            cfTokenDraft: "",
            cfBusy: false,
            cfActionError: null,
            cfActionMessage: null,
            cfActionTimer: null,

            confirmKind: null,
        };
    },
    computed: {
        cfInstalled() {
            return this.cfStatus?.installed !== false;
        },
        cfRunning() {
            return !!this.cfStatus?.running;
        },
        cfStatusMessage() {
            return this.cfStatus?.message || "";
        },
        cfErrorMessage() {
            return this.cfStatus?.errorMessage || "";
        },
        cfHasStoredToken() {
            return !!this.cfStatus?.token || !!this.cfStatus?.hasToken;
        },
    },
    mounted() {
        this.fetchSettings();
        this.fetchCloudflared();
    },
    beforeUnmount() {
        clearTimeout(this.settingsSavedTimer);
        clearTimeout(this.cfActionTimer);
    },
    methods: {
        async fetchSettings() {
            this.settingsLoading = true;
            try {
                const { data } = await this.$root.api.get("/settings");
                const incoming = data?.data || {};
                this.settings = { trustProxy: !!incoming.trustProxy };
            } catch (e) {
                this.settingsError = e?.response?.data?.detail || e?.message || "could not load";
            } finally {
                this.settingsLoading = false;
            }
        },
        async toggleTrustProxy() {
            const original = this.settings.trustProxy;
            this.settings.trustProxy = !original;
            this.settingsError = null;
            this.settingsSaved = false;
            try {
                await this.$root.api.post("/settings", {
                    settings: { trustProxy: this.settings.trustProxy },
                });
                this.settingsSaved = true;
                clearTimeout(this.settingsSavedTimer);
                this.settingsSavedTimer = setTimeout(() => {
                    this.settingsSaved = false;
                }, 2000);
            } catch (e) {
                this.settings.trustProxy = original;
                this.settingsError = e?.response?.data?.detail || e?.message || "could not save";
            }
        },
        async fetchCloudflared() {
            this.cfLoading = true;
            try {
                const { data } = await this.$root.api.get("/reverse-proxy/cloudflared");
                this.cfStatus = data?.data || {};
                if (!this.cfTokenDraft && this.cfStatus.token) {
                    this.cfTokenDraft = this.cfStatus.token;
                }
            } catch (e) {
                console.warn("could not fetch cloudflared status", e);
                this.cfStatus = { installed: false };
            } finally {
                this.cfLoading = false;
            }
        },
        flashAction(msg, tone) {
            if (tone === "error") {
                this.cfActionError = msg;
                this.cfActionMessage = null;
            } else {
                this.cfActionMessage = msg;
                this.cfActionError = null;
            }
            clearTimeout(this.cfActionTimer);
            this.cfActionTimer = setTimeout(() => {
                this.cfActionError = null;
                this.cfActionMessage = null;
            }, 2800);
        },
        async startCloudflared() {
            const token = this.cfTokenDraft.trim();
            if (!token) {
                return;
            }
            this.cfBusy = true;
            this.cfActionError = null;
            try {
                const { data } = await this.$root.api.post(
                    "/reverse-proxy/cloudflared/start",
                    { token },
                );
                if (data?.data) {
                    this.cfStatus = data.data;
                }
                if (data?.ok) {
                    this.flashAction("tunnel started", "ok");
                } else {
                    this.flashAction(data?.msg || "could not start tunnel", "error");
                }
            } catch (e) {
                this.flashAction(e?.response?.data?.detail || e?.message || "could not start tunnel", "error");
            } finally {
                this.cfBusy = false;
            }
        },
        askStopCloudflared() {
            this.confirmKind = "stop";
        },
        async confirmStop() {
            this.cfBusy = true;
            try {
                const { data } = await this.$root.api.post("/reverse-proxy/cloudflared/stop", {});
                if (data?.data) {
                    this.cfStatus = data.data;
                }
                this.flashAction("tunnel stopped", "ok");
                this.confirmKind = null;
            } catch (e) {
                this.flashAction(e?.response?.data?.detail || e?.message || "could not stop tunnel", "error");
            } finally {
                this.cfBusy = false;
            }
        },
        askRemoveToken() {
            this.confirmKind = "clear-token";
        },
        async confirmClearToken() {
            this.cfBusy = true;
            try {
                const { data } = await this.$root.api.delete("/reverse-proxy/cloudflared/token");
                if (data?.data) {
                    this.cfStatus = data.data;
                }
                this.cfTokenDraft = "";
                this.flashAction("token cleared", "ok");
                this.confirmKind = null;
            } catch (e) {
                this.flashAction(e?.response?.data?.detail || e?.message || "could not clear token", "error");
            } finally {
                this.cfBusy = false;
            }
        },
        cancelConfirm() {
            if (this.cfBusy) {
                return;
            }
            this.confirmKind = null;
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

.block {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
}

.block-title {
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

    &.centered {
        align-items: center;
    }
}

.cf-body {
    gap: 14px;
}

.row-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;

    .toggle-text {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
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

    code {
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 10.5px;
        padding: 1px 5px;
        background: hsl(0 0% 6%);
        border: 1px solid var(--border);
        border-radius: 4px;
        color: var(--text-muted);
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

.field {
    display: flex;
    flex-direction: column;
    gap: 6px;
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
        border-color: hsl(142 71% 45%);
        box-shadow: 0 0 0 3px hsl(142 71% 45% / 0.15);
    }

    &:disabled {
        opacity: 0.55;
        cursor: not-allowed;
    }

    &.mono {
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 12.5px;
    }
}

.cf-status-row {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 5px 12px 5px 10px;
    border-radius: 999px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 600;
    border: 1px solid var(--border);
    background: hsl(0 0% 6%);

    .status-pill-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: hsl(0 0% 38%);
    }

    &.tone-on {
        background: hsl(142 71% 45% / 0.14);
        border-color: hsl(142 71% 45% / 0.45);
        color: hsl(142 71% 75%);

        .status-pill-dot {
            background: hsl(142 71% 45%);
            box-shadow: 0 0 0 4px hsl(142 71% 45% / 0.18);
        }
    }

    &.tone-off {
        color: var(--text-muted);
    }
}

.cf-message {
    font-size: 12px;
    color: var(--text-muted);
}

.cf-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    flex-wrap: wrap;

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

.info-banner {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 14px;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--bg-soft);

    .info-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: hsl(0 0% 38%);
        margin-top: 6px;
        flex: none;
    }

    .info-text {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;
        min-width: 0;
    }

    .info-status {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 600;
    }

    .info-help {
        font-size: 12.5px;
        color: var(--text-muted);
        line-height: 1.5;

        code {
            font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
                Monaco, Consolas, monospace;
            font-size: 11px;
            padding: 1px 5px;
            background: hsl(0 0% 6%);
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text);
        }
    }

    .info-error-pre {
        margin: 0;
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 11.5px;
        color: var(--text);
        background: hsl(0 0% 4%);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 8px 10px;
        white-space: pre-wrap;
        overflow-x: auto;
        max-height: 160px;
    }

    &.tone-warn {
        border-color: hsl(38 92% 50% / 0.4);
        background: hsl(38 92% 50% / 0.06);
        color: hsl(38 92% 70%);

        .info-dot {
            background: hsl(38 92% 50%);
            box-shadow: 0 0 0 4px hsl(38 92% 50% / 0.14);
        }
    }

    &.tone-error {
        border-color: hsl(0 84% 60% / 0.4);
        background: hsl(0 84% 60% / 0.06);
        color: hsl(0 84% 75%);

        .info-dot {
            background: hsl(0 84% 60%);
            box-shadow: 0 0 0 4px hsl(0 84% 60% / 0.14);
        }
    }
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

.form-error,
.form-saved {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

.form-error { color: hsl(0 84% 65%); }
.form-saved { color: hsl(142 71% 65%); }
</style>
