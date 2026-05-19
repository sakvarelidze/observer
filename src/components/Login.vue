<template>
    <div class="v2-login">
        <div class="v2-auth-card">
            <header class="v2-auth-brand">
                <object class="v2-auth-mark" data="/icon.svg" />
                <span class="v2-auth-name">Observer</span>
                <span class="v2-auth-tag">{{ tokenRequired ? "two-factor required" : "sign in to continue" }}</span>
            </header>

            <form class="form" @submit.prevent="submit">
                <template v-if="!tokenRequired">
                    <label class="field">
                        <span class="field-label">{{ $t("Username") }}</span>
                        <input
                            v-model="username"
                            type="text"
                            class="input"
                            autocomplete="username"
                            required
                            :disabled="processing"
                            @input="clearError"
                        >
                    </label>
                    <label class="field">
                        <span class="field-label">{{ $t("Password") }}</span>
                        <input
                            v-model="password"
                            type="password"
                            class="input"
                            autocomplete="current-password"
                            required
                            :disabled="processing"
                            @input="clearError"
                        >
                    </label>
                </template>

                <label v-else class="field">
                    <span class="field-label">{{ $t("Token") }}</span>
                    <input
                        v-model="token"
                        type="text"
                        inputmode="numeric"
                        maxlength="6"
                        class="input mono center"
                        placeholder="123456"
                        autocomplete="one-time-code"
                        required
                        :disabled="processing"
                        @input="clearError"
                    >
                    <span class="field-help">enter the 6-digit code from your authenticator app.</span>
                </label>

                <div v-if="!tokenRequired" class="row-remember">
                    <label class="checkbox-row">
                        <input
                            id="remember"
                            v-model="$root.remember"
                            type="checkbox"
                            class="checkbox"
                            :disabled="processing"
                        >
                        <span>{{ $t("Remember me") }}</span>
                    </label>
                </div>

                <p v-if="res && !res.ok" class="form-error" role="alert">{{ res.msg }}</p>

                <button class="btn-primary" type="submit" :disabled="processing">
                    {{ processing ? $t("Loading...") : (tokenRequired ? $t("Verify") : $t("Login")) }}
                </button>

                <button
                    v-if="tokenRequired"
                    type="button"
                    class="btn-ghost"
                    :disabled="processing"
                    @click="resetTokenChallenge"
                >
                    use a different account
                </button>
            </form>
        </div>
    </div>
</template>

<script>
export default {
    data() {
        return {
            processing: false,
            username: "",
            password: "",
            token: "",
            res: null,
            tokenRequired: false,
        };
    },

    mounted() {
        document.title += " - Login";

        this.$root.api.get("/setup-needed").then(({ data }) => {
            if (data.needSetup) {
                this.$router.push("/setup");
            }
        });
    },

    unmounted() {
        document.title = document.title.replace(" - Login", "");
    },

    methods: {
        clearError() {
            if (this.res && !this.res.ok) {
                this.res = null;
            }
        },
        resetTokenChallenge() {
            this.tokenRequired = false;
            this.token = "";
            this.password = "";
            this.res = null;
        },
        async submit() {
            this.processing = true;

            try {
                const token = this.tokenRequired ? this.token : undefined;
                await this.$root.login(this.username, this.password, token);
                this.res = null;
                const next = this.$route.query?.next;
                this.$router.push(typeof next === "string" && next.startsWith("/") ? next : "/dashboard");
            } catch (e) {
                const detail = e?.response?.data?.detail;

                if (detail === "tokenRequired") {
                    this.tokenRequired = true;
                    this.token = "";
                    this.res = {
                        ok: false,
                        msg: this.$t("tokenRequired"),
                    };
                } else {
                    if (detail === "invalidTwoFAToken") {
                        this.tokenRequired = true;
                        this.token = "";
                    } else if (!detail || detail === "Invalid credentials") {
                        this.tokenRequired = false;
                        this.token = "";
                    }

                    const key = detail || "Invalid credentials";
                    const message = this.$t(key);
                    this.res = {
                        ok: false,
                        msg: message,
                    };
                }
            } finally {
                this.processing = false;
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@use "../pages/v2/_auth" as *;

.v2-login { @include v2-auth-shell; }
.v2-auth-card { @include v2-auth-card; }
.v2-auth-brand { @include v2-auth-brand; }

.form {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.field { @include v2-auth-field; }
.field-help {
    font-size: 11px;
    color: var(--text-faint);
    line-height: 1.5;
    text-align: center;
}

.input {
    @include v2-auth-input;

    &.mono {
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 18px;
        letter-spacing: 0.4em;
    }
    &.center { text-align: center; }
}

.row-remember {
    display: flex;
    justify-content: flex-start;
    margin-top: -2px;
}

.checkbox-row {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 12.5px;
    color: var(--text-muted);
    cursor: pointer;
    user-select: none;
}

.checkbox { @include v2-auth-checkbox; }

.form-error { @include v2-auth-error; margin: 0; }

.btn-primary { @include v2-auth-button; }

.btn-ghost {
    appearance: none;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 4px 8px;
    border-radius: 6px;
    cursor: pointer;
    align-self: center;

    &:hover:not(:disabled) {
        color: var(--text);
        background: var(--bg-hover);
    }

    &:disabled { opacity: 0.45; cursor: not-allowed; }
}
</style>
