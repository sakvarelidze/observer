<template>
    <div class="v2-setup" data-cy="setup-form">
        <div class="v2-auth-card">
            <header class="v2-auth-brand">
                <object class="v2-auth-mark" data="/icon.svg" />
                <span class="v2-auth-name">Observer</span>
                <span class="v2-auth-tag">{{ $t("Create your admin account") }}</span>
            </header>

            <form class="form" @submit.prevent="submit">
                <label class="field">
                    <span class="field-label">{{ $t("Language") }}</span>
                    <select v-model="$root.language" class="input">
                        <option v-for="(lang, i) in $i18n.availableLocales" :key="`Lang${i}`" :value="lang">
                            {{ $i18n.messages[lang].languageName }}
                        </option>
                    </select>
                </label>

                <label class="field">
                    <span class="field-label">{{ $t("Username") }}</span>
                    <input
                        v-model="username"
                        type="text"
                        class="input"
                        autocomplete="username"
                        required
                        data-cy="username-input"
                        :disabled="processing"
                    >
                </label>

                <label class="field">
                    <span class="field-label">{{ $t("Password") }}</span>
                    <input
                        v-model="password"
                        type="password"
                        class="input"
                        autocomplete="new-password"
                        required
                        data-cy="password-input"
                        :disabled="processing"
                    >
                </label>

                <label class="field">
                    <span class="field-label">{{ $t("Repeat Password") }}</span>
                    <input
                        v-model="repeatPassword"
                        type="password"
                        class="input"
                        autocomplete="new-password"
                        required
                        data-cy="password-repeat-input"
                        :disabled="processing"
                    >
                    <span v-if="passwordMismatch" class="field-help mismatch">
                        passwords don't match
                    </span>
                </label>

                <button
                    class="btn-primary"
                    type="submit"
                    :disabled="processing || passwordMismatch"
                    data-cy="submit-setup-form"
                >
                    {{ processing ? $t("Loading...") : $t("Create") }}
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
            repeatPassword: "",
        };
    },
    computed: {
        passwordMismatch() {
            return !!(this.password && this.repeatPassword && this.password !== this.repeatPassword);
        },
    },
    mounted() {
        this.$root.api.get("/setup-needed").then(({ data }) => {
            if (!data.needSetup) {
                this.$router.push("/");
            }
        });
    },
    methods: {
        async submit() {
            this.processing = true;

            if (this.password !== this.repeatPassword) {
                this.$root.toastError("PasswordsDoNotMatch");
                this.processing = false;
                return;
            }

            try {
                const { data } = await this.$root.api.post("/setup", {
                    username: this.username,
                    password: this.password,
                });
                this.$root.toastRes(data);

                if (data.ok) {
                    this.$root.token = data.token;
                    this.$root.username = this.username;
                    this.$router.push("/dashboard");
                }
            } catch (e) {
                this.$root.toastError(e.response?.data?.detail || e.message);
            } finally {
                this.processing = false;
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@import "./v2/_auth.scss";

.v2-setup { @include v2-auth-shell; }
.v2-auth-card { @include v2-auth-card; }
.v2-auth-brand { @include v2-auth-brand; }

.form {
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.field { @include v2-auth-field; }

.input {
    @include v2-auth-input;
}

select.input {
    cursor: pointer;
}

.field-help {
    font-size: 11px;
    line-height: 1.5;
    color: var(--text-faint);

    &.mismatch { color: hsl(0 84% 70%); }
}

.btn-primary { @include v2-auth-button; }
</style>
