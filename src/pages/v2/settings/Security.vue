<template>
    <div class="settings-page">
        <header class="page-head">
            <h2 class="page-title">Security &amp; 2FA</h2>
            <p class="page-sub">change your password, manage two-factor authentication.</p>
        </header>

        <!-- Account -->
        <section class="block">
            <h3 class="block-title">account</h3>
            <div class="block-body block-row">
                <div class="row-text">
                    <span class="row-label">signed in as</span>
                    <span class="row-value mono">{{ $root.username || "—" }}</span>
                </div>
                <button type="button" class="action danger-outline" @click="onLogout">
                    <font-awesome-icon icon="sign-out-alt" />
                    <span>log out</span>
                </button>
            </div>
        </section>

        <!-- Change password -->
        <section class="block">
            <h3 class="block-title">password</h3>
            <form class="block-body form" autocomplete="off" @submit.prevent="onChangePassword">
                <label class="field">
                    <span class="field-label">current password <span class="req">*</span></span>
                    <input
                        v-model="pw.current"
                        type="password"
                        class="input"
                        autocomplete="current-password"
                        required
                    >
                </label>
                <div class="field-row">
                    <label class="field flex-1">
                        <span class="field-label">new password <span class="req">*</span></span>
                        <input
                            v-model="pw.next"
                            type="password"
                            class="input"
                            autocomplete="new-password"
                            required
                            minlength="8"
                        >
                    </label>
                    <label class="field flex-1">
                        <span class="field-label">repeat <span class="req">*</span></span>
                        <input
                            v-model="pw.repeat"
                            type="password"
                            class="input"
                            autocomplete="new-password"
                            required
                            minlength="8"
                        >
                    </label>
                </div>
                <div class="form-foot">
                    <span v-if="pwError" class="form-error">{{ pwError }}</span>
                    <span v-else-if="pwSavedRecently" class="form-saved">password updated</span>
                    <button
                        type="submit"
                        class="action primary"
                        :disabled="!canChangePassword"
                    >
                        <span v-if="!pwSaving">change password</span>
                        <span v-else>saving…</span>
                    </button>
                </div>
            </form>
        </section>

        <!-- Two-factor -->
        <section class="block">
            <h3 class="block-title">two-factor authentication</h3>
            <div v-if="twofaLoading" class="block-body block-row centered">
                <LoaderBars size="sm" />
            </div>
            <div v-else class="block-body twofa-body">
                <div class="block-row">
                    <div class="row-text">
                        <span class="row-label">status</span>
                        <span class="row-value">
                            <span class="status-dot" :class="twofaEnabled ? 'on' : 'off'"></span>
                            <span>{{ twofaEnabled ? "enabled" : "disabled" }}</span>
                        </span>
                    </div>
                    <button
                        v-if="!twofaEnabled && !enableFlow.open"
                        type="button"
                        class="action primary"
                        @click="startEnable"
                    >
                        <font-awesome-icon icon="award" />
                        <span>enable 2FA</span>
                    </button>
                    <button
                        v-else-if="twofaEnabled"
                        type="button"
                        class="action danger-outline"
                        @click="openDisable"
                    >
                        <font-awesome-icon icon="times-circle" />
                        <span>disable 2FA</span>
                    </button>
                </div>

                <transition name="inline-form">
                    <div v-if="enableFlow.open" class="enable-flow">
                        <header class="flow-head">
                            <span class="flow-step">step {{ enableFlow.stage === "password" ? "1" : "2" }} of 2</span>
                            <span class="flow-title">{{ enableFlow.stage === "password" ? "confirm your password" : "scan with your authenticator app" }}</span>
                        </header>

                        <template v-if="enableFlow.stage === 'password'">
                            <label class="field">
                                <span class="field-label">current password <span class="req">*</span></span>
                                <input
                                    ref="enablePasswordInput"
                                    v-model="enableFlow.password"
                                    type="password"
                                    class="input"
                                    autocomplete="current-password"
                                    required
                                    @keydown.enter.prevent="prepareEnable"
                                >
                            </label>
                        </template>

                        <template v-else>
                            <div class="qr-wrap">
                                <div class="qr-canvas">
                                    <vue-qrcode
                                        :value="enableFlow.uri"
                                        :options="{ width: 192,
                                                    margin: 1,
                                                    color: { light: '#ffffff', dark: '#000000' } }"
                                    />
                                </div>
                                <div class="qr-help">
                                    <p>scan this with Authy, Google Authenticator, 1Password, Bitwarden, or any TOTP app.</p>
                                    <details class="qr-fallback">
                                        <summary>can't scan? show secret</summary>
                                        <code>{{ enableFlow.uri }}</code>
                                    </details>
                                </div>
                            </div>
                            <label class="field">
                                <span class="field-label">verification code <span class="req">*</span></span>
                                <input
                                    ref="enableCodeInput"
                                    v-model="enableFlow.code"
                                    type="text"
                                    class="input mono code-input"
                                    inputmode="numeric"
                                    autocomplete="one-time-code"
                                    placeholder="123456"
                                    pattern="\d{6}"
                                    maxlength="6"
                                    required
                                    @keydown.enter.prevent="confirmEnable"
                                >
                            </label>
                        </template>

                        <div class="flow-foot">
                            <span v-if="enableFlow.error" class="form-error">{{ enableFlow.error }}</span>
                            <button
                                type="button"
                                class="action ghost"
                                :disabled="enableFlow.saving"
                                @click="cancelEnable"
                            >
                                cancel
                            </button>
                            <button
                                v-if="enableFlow.stage === 'password'"
                                type="button"
                                class="action primary"
                                :disabled="!enableFlow.password || enableFlow.saving"
                                @click="prepareEnable"
                            >
                                <span v-if="!enableFlow.saving">continue</span>
                                <span v-else>preparing…</span>
                            </button>
                            <button
                                v-else
                                type="button"
                                class="action primary"
                                :disabled="!/^\d{6}$/.test(enableFlow.code) || enableFlow.saving"
                                @click="confirmEnable"
                            >
                                <span v-if="!enableFlow.saving">enable 2FA</span>
                                <span v-else>verifying…</span>
                            </button>
                        </div>
                    </div>
                </transition>
            </div>
        </section>

        <ConfirmV2
            :open="!!disableConfirm"
            tone="danger"
            title="disable two-factor authentication"
            confirm-label="disable 2FA"
            busy-label="disabling…"
            :busy="disableConfirm?.busy"
            @cancel="cancelDisable"
            @confirm="confirmDisable"
        >
            <span>Confirm with your current password to turn off two-factor login.</span>
            <input
                v-if="disableConfirm"
                ref="disablePasswordInput"
                v-model="disableConfirm.password"
                type="password"
                class="input confirm-input"
                autocomplete="current-password"
                placeholder="current password"
                required
                @keydown.enter="confirmDisable"
            >
            <span v-if="disableConfirm?.error" class="confirm-error">{{ disableConfirm.error }}</span>
        </ConfirmV2>
    </div>
</template>

<script>
import VueQrcode from "vue-qrcode";
import LoaderBars from "../LoaderBars.vue";
import ConfirmV2 from "../ConfirmV2.vue";

export default {
    name: "SettingsSecurity",
    components: { LoaderBars,
        ConfirmV2,
        VueQrcode },
    data() {
        return {
            // Change password
            pw: { current: "",
                next: "",
                repeat: "" },
            pwSaving: false,
            pwError: null,
            pwSavedRecently: false,
            pwSavedTimer: null,

            // 2FA status
            twofaLoading: true,
            twofaEnabled: false,

            // Enable 2FA flow
            enableFlow: this.emptyEnableFlow(),

            // Disable 2FA confirmation
            disableConfirm: null,
        };
    },
    computed: {
        canChangePassword() {
            if (this.pwSaving) {
                return false;
            }
            const { current, next, repeat } = this.pw;
            if (!current || !next || !repeat) {
                return false;
            }
            if (next !== repeat) {
                return false;
            }
            if (next.length < 8) {
                return false;
            }
            return true;
        },
    },
    mounted() {
        this.fetchTwofaStatus();
    },
    beforeUnmount() {
        clearTimeout(this.pwSavedTimer);
    },
    methods: {
        emptyEnableFlow() {
            return {
                open: false,
                stage: "password",
                password: "",
                uri: "",
                code: "",
                saving: false,
                error: null,
            };
        },
        async onLogout() {
            if (typeof this.$root.logout === "function") {
                await this.$root.logout();
            }
        },
        async onChangePassword() {
            if (!this.canChangePassword) {
                return;
            }
            this.pwSaving = true;
            this.pwError = null;
            this.pwSavedRecently = false;
            try {
                const { data } = await this.$root.api.post("/change-password", {
                    currentPassword: this.pw.current,
                    newPassword: this.pw.next,
                });
                if (data?.token) {
                    // Backend rotates the token on password change.
                    localStorage.token = data.token;
                    if (this.$root.api?.defaults?.headers) {
                        this.$root.api.defaults.headers.Authorization = `Bearer ${data.token}`;
                    }
                }
                this.pw = { current: "",
                    next: "",
                    repeat: "" };
                this.pwSavedRecently = true;
                clearTimeout(this.pwSavedTimer);
                this.pwSavedTimer = setTimeout(() => {
                    this.pwSavedRecently = false;
                }, 2400);
            } catch (e) {
                const detail = e?.response?.data?.detail || e?.message || "could not change password";
                if (detail === "invalidCurrentPassword") {
                    this.pwError = "current password is incorrect";
                } else {
                    this.pwError = detail;
                }
            } finally {
                this.pwSaving = false;
            }
        },
        async fetchTwofaStatus() {
            this.twofaLoading = true;
            try {
                const { data } = await this.$root.api.get("/twofa/status");
                this.twofaEnabled = !!data?.status;
            } catch (e) {
                console.warn("could not fetch 2FA status", e);
            } finally {
                this.twofaLoading = false;
            }
        },
        startEnable() {
            this.enableFlow = this.emptyEnableFlow();
            this.enableFlow.open = true;
            this.$nextTick(() => {
                this.$refs.enablePasswordInput?.focus();
            });
        },
        cancelEnable() {
            this.enableFlow = this.emptyEnableFlow();
        },
        async prepareEnable() {
            if (!this.enableFlow.password) {
                return;
            }
            this.enableFlow.saving = true;
            this.enableFlow.error = null;
            try {
                const { data } = await this.$root.api.post("/twofa/prepare", {
                    currentPassword: this.enableFlow.password,
                });
                if (!data?.uri) {
                    this.enableFlow.error = data?.msg || "could not start 2FA setup";
                    return;
                }
                this.enableFlow.uri = data.uri;
                this.enableFlow.stage = "code";
                this.$nextTick(() => {
                    this.$refs.enableCodeInput?.focus();
                });
            } catch (e) {
                const detail = e?.response?.data?.detail || e?.message;
                this.enableFlow.error = detail === "invalidCurrentPassword"
                    ? "current password is incorrect"
                    : (detail || "could not start 2FA setup");
            } finally {
                this.enableFlow.saving = false;
            }
        },
        async confirmEnable() {
            if (!/^\d{6}$/.test(this.enableFlow.code)) {
                return;
            }
            this.enableFlow.saving = true;
            this.enableFlow.error = null;
            try {
                await this.$root.api.post("/twofa/enable", {
                    currentPassword: this.enableFlow.password,
                    token: this.enableFlow.code,
                });
                this.twofaEnabled = true;
                this.cancelEnable();
            } catch (e) {
                const detail = e?.response?.data?.detail || e?.message;
                if (detail === "invalidTwoFAToken") {
                    this.enableFlow.error = "code didn't match — try again with a fresh one";
                } else {
                    this.enableFlow.error = detail || "could not enable 2FA";
                }
            } finally {
                this.enableFlow.saving = false;
            }
        },
        openDisable() {
            this.disableConfirm = { password: "",
                error: null,
                busy: false };
            this.$nextTick(() => {
                this.$refs.disablePasswordInput?.focus();
            });
        },
        cancelDisable() {
            if (this.disableConfirm?.busy) {
                return;
            }
            this.disableConfirm = null;
        },
        async confirmDisable() {
            if (!this.disableConfirm || this.disableConfirm.busy) {
                return;
            }
            if (!this.disableConfirm.password) {
                this.disableConfirm.error = "enter your current password";
                return;
            }
            this.disableConfirm.busy = true;
            this.disableConfirm.error = null;
            try {
                await this.$root.api.post("/twofa/disable", {
                    currentPassword: this.disableConfirm.password,
                });
                this.twofaEnabled = false;
                this.disableConfirm = null;
            } catch (e) {
                const detail = e?.response?.data?.detail || e?.message;
                this.disableConfirm.error = detail === "invalidCurrentPassword"
                    ? "current password is incorrect"
                    : (detail || "could not disable 2FA");
                this.disableConfirm.busy = false;
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
}

.block-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;

    &.centered {
        justify-content: center;
    }
}

.row-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.row-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-faint);
}

.row-value {
    font-size: 14px;
    color: var(--text);
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 8px;

    &.mono {
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
    }
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: hsl(0 0% 38%);

    &.on {
        background: hsl(142 71% 45%);
        box-shadow: 0 0 0 4px hsl(142 71% 45% / 0.15);
    }

    &.off {
        background: hsl(0 0% 38%);
    }
}

.form {
    display: flex;
    flex-direction: column;
    gap: 16px;
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

.field-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
}

.field-row {
    display: flex;
    gap: 12px;

    .field { flex: 1; }
    .flex-1 { flex: 1; }
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

    &.mono {
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
    }

    &.code-input {
        font-size: 18px;
        letter-spacing: 0.3em;
        text-align: center;
    }
}

.confirm-input {
    margin-top: 8px;
}

.confirm-error {
    margin-top: 8px;
    font-size: 12px;
    color: hsl(0 84% 65%);
    display: block;
}

.form-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;

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

.twofa-body {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.enable-flow {
    background: hsl(0 0% 6%);
    border: 1px solid hsl(217 91% 60% / 0.35);
    border-radius: 12px;
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.flow-head {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border);

    .flow-step {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: var(--text-faint);
        font-variant-numeric: tabular-nums;
    }

    .flow-title {
        font-size: 14px;
        font-weight: 600;
        color: var(--text);
    }
}

.qr-wrap {
    display: flex;
    align-items: center;
    gap: 18px;
    flex-wrap: wrap;
}

.qr-canvas {
    background: #ffffff;
    border-radius: 10px;
    padding: 10px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 0 1px var(--border) inset;
    flex: none;

    :deep(img),
    :deep(canvas) {
        display: block;
        max-width: 192px;
        height: auto;
    }
}

.qr-help {
    flex: 1;
    min-width: 220px;
    color: var(--text-muted);
    font-size: 13px;
    line-height: 1.55;

    p { margin: 0 0 8px; }

    .qr-fallback {
        font-size: 12px;
        color: var(--text-faint);

        summary {
            cursor: pointer;
            user-select: none;
        }

        code {
            display: block;
            margin-top: 8px;
            padding: 8px 10px;
            background: var(--bg-soft);
            border: 1px solid var(--border);
            border-radius: 6px;
            font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
                Monaco, Consolas, monospace;
            font-size: 11px;
            word-break: break-all;
            color: var(--text-muted);
        }
    }
}

.flow-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;

    .form-error {
        flex: 1;
        font-size: 12px;
        color: hsl(0 84% 65%);
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

.inline-form-enter-active,
.inline-form-leave-active {
    transition: opacity 200ms $v2-ease, transform 200ms $v2-ease,
        max-height 240ms $v2-ease;
    max-height: 800px;
    overflow: hidden;
}

.inline-form-enter-from,
.inline-form-leave-to {
    opacity: 0;
    transform: translateY(-6px);
    max-height: 0;
}

@media (max-width: 540px) {
    .block-row {
        flex-direction: column;
        align-items: stretch;
        gap: 12px;
    }

    .field-row { flex-direction: column; }
}
</style>
