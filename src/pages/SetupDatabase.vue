<template>
    <div class="v2-setup-db">
        <div class="v2-auth-card wide">
            <header class="v2-auth-brand">
                <object class="v2-auth-mark" data="/icon.svg" />
                <span class="v2-auth-name">Observer</span>
                <span class="v2-auth-tag">Choose a database</span>
            </header>

            <div v-if="loading" class="loading-state">
                <span>checking…</span>
            </div>

            <div v-else-if="applying" class="loading-state">
                <span>connecting and persisting your choice…</span>
            </div>

            <form v-else class="form" @submit.prevent="onSubmit">
                <fieldset class="field">
                    <legend class="field-label">database engine</legend>
                    <div class="engine-grid">
                        <label
                            v-for="opt in engines"
                            :key="opt.type"
                            class="engine-card"
                            :class="{ active: form.type === opt.type }"
                        >
                            <input
                                v-model="form.type"
                                type="radio"
                                :value="opt.type"
                                class="visually-hidden"
                            >
                            <span class="engine-name">{{ opt.label }}</span>
                            <span class="engine-desc">{{ opt.desc }}</span>
                        </label>
                    </div>
                </fieldset>

                <template v-if="form.type === 'sqlite'">
                    <label class="field">
                        <span class="field-label">file path</span>
                        <input
                            v-model="form.path"
                            type="text"
                            class="input"
                            :placeholder="'./data/observer.db'"
                        >
                        <span class="field-help">
                            relative to the working directory; defaults to <code>./data/observer.db</code>.
                        </span>
                    </label>
                </template>

                <template v-else-if="form.type === 'postgres' || form.type === 'mysql'">
                    <div class="field-row">
                        <label class="field flex-2">
                            <span class="field-label">host</span>
                            <input
                                v-model="form.hostname"
                                type="text"
                                class="input"
                                placeholder="db.example.com"
                                required
                            >
                        </label>
                        <label class="field flex-1">
                            <span class="field-label">port</span>
                            <input
                                v-model.number="form.port"
                                type="number"
                                class="input"
                                :placeholder="form.type === 'postgres' ? '5432' : '3306'"
                            >
                        </label>
                    </div>
                    <label class="field">
                        <span class="field-label">database name</span>
                        <input
                            v-model="form.database"
                            type="text"
                            class="input"
                            placeholder="observer"
                            required
                        >
                    </label>
                    <div class="field-row">
                        <label class="field">
                            <span class="field-label">username</span>
                            <input
                                v-model="form.username"
                                type="text"
                                class="input"
                                autocomplete="username"
                                required
                            >
                        </label>
                        <label class="field">
                            <span class="field-label">password</span>
                            <input
                                v-model="form.password"
                                type="password"
                                class="input"
                                autocomplete="new-password"
                            >
                        </label>
                    </div>
                </template>

                <p v-if="testResult" class="test-result" :class="testResult.tone">
                    {{ testResult.text }}
                </p>
                <p v-if="error" class="form-error">{{ error }}</p>

                <div class="form-foot">
                    <button
                        type="button"
                        class="btn-secondary"
                        :disabled="!canTest || testing"
                        @click="onTest"
                    >
                        {{ testing ? "testing…" : "test connection" }}
                    </button>
                    <button class="btn-primary" type="submit" :disabled="!canSubmit">
                        save and continue
                    </button>
                </div>
            </form>
        </div>
    </div>
</template>

<script>
const ENGINES = [
    {
        type: "sqlite",
        label: "SQLite",
        desc: "single file on disk — easiest to back up.",
    },
    {
        type: "postgres",
        label: "PostgreSQL",
        desc: "connect to an existing Postgres server.",
    },
    {
        type: "mysql",
        label: "MySQL / MariaDB",
        desc: "connect to an existing MySQL or MariaDB server.",
    },
];

export default {
    data() {
        return {
            engines: ENGINES,
            loading: true,
            applying: false,
            testing: false,
            error: null,
            testResult: null,
            form: {
                type: "sqlite",
                path: "",
                hostname: "",
                port: null,
                database: "observer",
                username: "",
                password: "",
            },
        };
    },
    computed: {
        canTest() {
            if (this.form.type === "sqlite") {
                return true;
            }
            return !!(this.form.hostname && this.form.username && this.form.database);
        },
        canSubmit() {
            return this.canTest && !this.applying;
        },
    },
    async mounted() {
        try {
            const { data } = await this.$root.api.get("/setup-database-info");
            if (!data.needsDbSetup) {
                // Already configured — bounce to admin setup or app.
                this.$router.replace("/setup");
                return;
            }
        } catch (e) {
            // Backend reachable but errored; let the user proceed
            // anyway. The submit will surface a clearer error.
        }
        this.loading = false;
    },
    methods: {
        async onTest() {
            this.testing = true;
            this.error = null;
            this.testResult = null;
            try {
                await this.$root.api.post(
                    "/setup-database/test",
                    this.payload(),
                );
                this.testResult = {
                    tone: "ok",
                    text: "connection looks good",
                };
            } catch (e) {
                this.testResult = {
                    tone: "bad",
                    text: e?.response?.data?.detail || "could not connect",
                };
            } finally {
                this.testing = false;
            }
        },
        async onSubmit() {
            this.applying = true;
            this.error = null;
            try {
                await this.$root.api.post("/setup-database", this.payload());
                // Brief pause so the user sees the "applying" state, then
                // hop into account setup against the fresh database.
                this.$router.replace("/setup");
            } catch (e) {
                this.error = e?.response?.data?.detail || "could not save database settings";
                this.applying = false;
            }
        },
        payload() {
            const p = { type: this.form.type };
            if (this.form.type === "sqlite") {
                if (this.form.path) {
                    p.path = this.form.path;
                }
            } else {
                p.hostname = this.form.hostname;
                p.port = this.form.port || undefined;
                p.database = this.form.database;
                p.username = this.form.username;
                p.password = this.form.password;
            }
            return p;
        },
    },
};
</script>

<style lang="scss" scoped>
@import "./v2/_auth.scss";

.v2-setup-db { @include v2-auth-shell; }
.v2-auth-card {
    @include v2-auth-card;

    &.wide { max-width: 560px; }
}
.v2-auth-brand { @include v2-auth-brand; }

.form {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.field {
    @include v2-auth-field;

    &.flex-1 { flex: 1; }
    &.flex-2 { flex: 2; }
}

.field-row {
    display: flex;
    gap: 12px;

    .field { flex: 1; }
}

.input { @include v2-auth-input; }

.field-help {
    font-size: 11px;
    color: var(--text-faint);
    line-height: 1.5;

    code {
        background: hsl(0 0% 6%);
        padding: 1px 5px;
        border-radius: 4px;
        font-size: 11px;
    }
}

fieldset.field {
    border: none;
    padding: 0;
    margin: 0;
}

.engine-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 8px;
}

.engine-card {
    background: hsl(0 0% 6%);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 4px;
    transition: background 140ms ease, border-color 140ms ease;

    &:hover {
        background: var(--bg-hover);
        border-color: var(--border-strong);
    }

    &.active {
        background: hsl(142 71% 45% / 0.12);
        border-color: hsl(142 71% 45% / 0.55);

        .engine-name { color: hsl(142 71% 75%); }
    }

    .engine-name {
        font-size: 13px;
        font-weight: 600;
        color: var(--text);
    }

    .engine-desc {
        font-size: 11px;
        color: var(--text-faint);
        line-height: 1.4;
    }
}

.test-result {
    margin: 0;
    font-size: 12px;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid;

    &.ok {
        background: hsl(142 71% 45% / 0.1);
        border-color: hsl(142 71% 45% / 0.45);
        color: hsl(142 71% 75%);
    }
    &.bad {
        background: hsl(0 84% 60% / 0.1);
        border-color: hsl(0 84% 60% / 0.45);
        color: hsl(0 84% 78%);
    }
}

.form-error {
    margin: 0;
    font-size: 12px;
    color: hsl(0 84% 75%);
}

.form-foot {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-top: 4px;
}

.btn-primary { @include v2-auth-button; flex: 1; }
.btn-secondary {
    appearance: none;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-muted);
    font-family: inherit;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 11px 14px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease;

    &:hover:not(:disabled) {
        color: var(--text);
        border-color: var(--border-strong);
        background: var(--bg-soft);
    }
    &:disabled { opacity: 0.45; cursor: not-allowed; }
}

.loading-state {
    color: var(--text-muted);
    font-size: 13px;
    text-align: center;
    padding: 24px 0;
}

.visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
}
</style>
