<template>
    <div class="settings-page">
        <header class="page-head">
            <div class="page-head-text">
                <h2 class="page-title">API Keys</h2>
                <p class="page-sub">programmatic access to your Observer instance. each key is shown once at creation — store it in a password manager.</p>
            </div>
            <button
                v-if="!loading && !creating && !justCreated"
                type="button"
                class="action primary"
                @click="startCreate"
            >
                <font-awesome-icon icon="plus" />
                <span>new key</span>
            </button>
        </header>

        <div v-if="loading" class="page-loading">
            <LoaderBars size="md" />
        </div>

        <div v-else class="keys-pane">
            <!-- One-time clear-key reveal after successful create -->
            <transition name="inline-form">
                <div v-if="justCreated" class="reveal-panel">
                    <div class="reveal-head">
                        <span class="reveal-title">copy this — it won't be shown again</span>
                        <button type="button" class="reveal-dismiss" @click="dismissReveal">
                            <font-awesome-icon icon="times" />
                        </button>
                    </div>
                    <div class="reveal-body">
                        <code class="reveal-key">{{ justCreated.key }}</code>
                        <button
                            type="button"
                            class="action"
                            :class="copied ? 'copy-success' : 'ghost'"
                            @click="copyKey"
                        >
                            <font-awesome-icon :icon="copied ? 'check' : 'copy'" />
                            <span>{{ copied ? "copied" : "copy" }}</span>
                        </button>
                    </div>
                    <p class="reveal-help">
                        Use this in API requests as <code>Authorization: Bearer &lt;key&gt;</code> or via the <code>X-API-Key</code> header. Treat it like a password.
                    </p>
                </div>
            </transition>

            <transition name="inline-form">
                <form
                    v-if="creating"
                    class="key-form"
                    @submit.prevent="submitCreate"
                    @keydown.esc.prevent.stop="cancelCreate"
                >
                    <div class="key-form-body">
                        <label class="field">
                            <span class="field-label">name <span class="req">*</span></span>
                            <input
                                ref="createNameInput"
                                v-model="createDraft.name"
                                type="text"
                                class="input"
                                placeholder="e.g. terraform deploys"
                                autocomplete="off"
                                required
                            >
                        </label>
                        <div class="field-row">
                            <label class="field flex-1">
                                <span class="field-label">role</span>
                                <select v-model="createDraft.role" class="input">
                                    <option value="read">read — list monitors &amp; status</option>
                                    <option value="write">write — mutate (no read)</option>
                                    <option value="readwrite">read + write — full access</option>
                                </select>
                            </label>
                            <label class="field flex-1">
                                <span class="field-label">expires</span>
                                <select v-model="createDraft.expiresIn" class="input">
                                    <option value="never">never</option>
                                    <option value="7d">in 7 days</option>
                                    <option value="30d">in 30 days</option>
                                    <option value="90d">in 90 days</option>
                                    <option value="365d">in 1 year</option>
                                </select>
                            </label>
                        </div>
                    </div>
                    <div class="key-form-foot">
                        <span v-if="createError" class="form-error">{{ createError }}</span>
                        <button type="button" class="action ghost" :disabled="createSaving" @click="cancelCreate">cancel</button>
                        <button type="submit" class="action primary" :disabled="createSaving || !createDraft.name.trim()">
                            <span v-if="!createSaving">create key</span>
                            <span v-else>creating…</span>
                        </button>
                    </div>
                </form>
            </transition>

            <ul v-if="keys.length > 0" class="key-list">
                <li
                    v-for="key in keys"
                    :key="key.id"
                    class="key-row"
                    :class="{ inactive: !key.active, expired: keyExpired(key) }"
                >
                    <span class="key-row-mark">
                        <font-awesome-icon icon="link" />
                    </span>
                    <div class="key-row-body">
                        <div class="key-row-head">
                            <span class="key-row-name">{{ key.name }}</span>
                            <span class="key-row-badge" :class="`role-${key.role}`">{{ roleLabel(key.role) }}</span>
                            <span v-if="!key.active" class="key-row-badge muted">disabled</span>
                            <span v-if="keyExpired(key)" class="key-row-badge danger">expired</span>
                        </div>
                        <div class="key-row-meta">
                            <span v-if="key.created_at || key.createdDate">
                                created {{ relativeTime(key.created_at || key.createdDate) }}
                            </span>
                            <span v-if="key.expires" class="key-meta-sep">·</span>
                            <span v-if="key.expires">
                                {{ keyExpired(key) ? "expired" : "expires" }} {{ relativeTime(key.expires) }}
                            </span>
                            <span v-if="!key.expires" class="key-meta-sep">·</span>
                            <span v-if="!key.expires" class="key-meta-faint">never expires</span>
                        </div>
                    </div>
                    <div class="key-row-actions">
                        <button
                            type="button"
                            class="row-toggle-btn"
                            :class="{ on: key.active }"
                            :title="key.active ? 'disable' : 'enable'"
                            @click="toggleActive(key)"
                        >
                            <span class="toggle-track"><span class="toggle-thumb"></span></span>
                            <span class="toggle-label">{{ key.active ? "on" : "off" }}</span>
                        </button>
                        <button type="button" class="row-btn danger" title="Revoke" @click="confirmDelete(key)">
                            <font-awesome-icon icon="trash" />
                        </button>
                    </div>
                </li>
            </ul>

            <div v-else-if="!creating && !justCreated" class="empty-state">
                <span class="empty-icon">
                    <font-awesome-icon icon="link" />
                </span>
                <p class="empty-title">No API keys yet</p>
                <p class="empty-sub">Generate a key to call the Observer API from scripts, CI, or other tools.</p>
                <button type="button" class="action primary" @click="startCreate">
                    <font-awesome-icon icon="plus" />
                    <span>create your first key</span>
                </button>
            </div>
        </div>

        <ConfirmV2
            :open="!!pendingDelete"
            tone="danger"
            title="revoke API key"
            confirm-label="revoke key"
            busy-label="revoking…"
            :busy="deleteSaving"
            @cancel="cancelDelete"
            @confirm="confirmedDelete"
        >
            Revoke <strong>{{ pendingDelete?.name }}</strong>? Any service or script using this key will start getting 401s immediately.
        </ConfirmV2>
    </div>
</template>

<script>
import dayjs from "dayjs";
import LoaderBars from "../LoaderBars.vue";
import ConfirmV2 from "../ConfirmV2.vue";

export default {
    name: "SettingsApiKeys",
    components: { LoaderBars,
        ConfirmV2 },
    data() {
        return {
            keys: [],
            loading: true,

            creating: false,
            createDraft: this.emptyDraft(),
            createSaving: false,
            createError: null,

            justCreated: null,
            copied: false,
            copiedTimer: null,

            pendingDelete: null,
            deleteSaving: false,
        };
    },
    mounted() {
        this.fetchKeys();
    },
    beforeUnmount() {
        clearTimeout(this.copiedTimer);
    },
    methods: {
        emptyDraft() {
            return {
                name: "",
                role: "read",
                expiresIn: "never",
            };
        },
        async fetchKeys() {
            this.loading = true;
            try {
                const { data } = await this.$root.api.get("/api-keys");
                const list = Array.isArray(data) ? data : (data?.keys || data?.api_keys || []);
                this.keys = list.sort((a, b) => {
                    // Active first, then by name
                    if (a.active !== b.active) {
                        return a.active ? -1 : 1;
                    }
                    return (a.name || "").localeCompare(b.name || "");
                });
            } catch (e) {
                console.warn("could not load api keys", e);
                this.keys = [];
            } finally {
                this.loading = false;
            }
        },
        relativeTime(value) {
            if (!value) {
                return "—";
            }
            try {
                return dayjs(value).fromNow();
            } catch (e) {
                return value;
            }
        },
        roleLabel(role) {
            switch (role) {
                case "read": return "read";
                case "write": return "write";
                case "readwrite": return "read + write";
                default: return role || "—";
            }
        },
        keyExpired(key) {
            if (!key.expires) {
                return false;
            }
            try {
                return dayjs(key.expires).isBefore(dayjs());
            } catch (e) {
                return false;
            }
        },
        startCreate() {
            this.creating = true;
            this.createDraft = this.emptyDraft();
            this.createError = null;
            this.justCreated = null;
            this.$nextTick(() => {
                this.$refs.createNameInput?.focus();
            });
        },
        cancelCreate() {
            this.creating = false;
            this.createError = null;
        },
        expiresAtFromDraft() {
            const v = this.createDraft.expiresIn;
            if (v === "never") {
                return null;
            }
            const days = parseInt(v, 10);
            if (!Number.isFinite(days)) {
                return null;
            }
            return dayjs().add(days, "day").toISOString();
        },
        async submitCreate() {
            const name = this.createDraft.name?.trim();
            if (!name) {
                return;
            }
            this.createSaving = true;
            this.createError = null;
            try {
                const payload = {
                    name,
                    role: this.createDraft.role,
                    expires: this.expiresAtFromDraft(),
                    active: true,
                };
                const { data } = await this.$root.api.post("/api-keys", payload);
                if (!data?.ok || !data?.key) {
                    this.createError = data?.msg || "could not create key";
                    return;
                }
                // Reveal the clear key once. Server only returns it on
                // create, never again — store it before the user navigates.
                this.justCreated = { key: data.key,
                    id: data.id,
                    name };
                this.creating = false;
                this.createDraft = this.emptyDraft();
                await this.fetchKeys();
            } catch (e) {
                this.createError = e?.response?.data?.detail || e?.message || "request failed";
            } finally {
                this.createSaving = false;
            }
        },
        async copyKey() {
            if (!this.justCreated?.key) {
                return;
            }
            try {
                await navigator.clipboard?.writeText?.(this.justCreated.key);
                this.copied = true;
                clearTimeout(this.copiedTimer);
                this.copiedTimer = setTimeout(() => {
                    this.copied = false;
                }, 1500);
            } catch (e) {
                console.warn("clipboard write failed", e);
            }
        },
        dismissReveal() {
            this.justCreated = null;
            this.copied = false;
        },
        async toggleActive(key) {
            const original = key.active;
            key.active = !original;
            const path = key.active
                ? `/api-keys/${key.id}/enable`
                : `/api-keys/${key.id}/disable`;
            try {
                await this.$root.api.post(path);
            } catch (e) {
                key.active = original;
                console.warn("could not toggle key", e);
            }
        },
        confirmDelete(key) {
            this.pendingDelete = { ...key };
        },
        cancelDelete() {
            if (this.deleteSaving) {
                return;
            }
            this.pendingDelete = null;
        },
        async confirmedDelete() {
            const key = this.pendingDelete;
            if (!key) {
                return;
            }
            this.deleteSaving = true;
            try {
                await this.$root.api.delete(`/api-keys/${key.id}`);
                await this.fetchKeys();
                this.pendingDelete = null;
            } catch (e) {
                console.warn("could not revoke key", e);
            } finally {
                this.deleteSaving = false;
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
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;

    .page-head-text {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

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

.keys-pane {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.reveal-panel {
    background: hsl(142 71% 45% / 0.06);
    border: 1px solid hsl(142 71% 45% / 0.5);
    border-radius: 12px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.reveal-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;

    .reveal-title {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: hsl(142 71% 75%);
        font-weight: 600;
    }

    .reveal-dismiss {
        appearance: none;
        background: transparent;
        border: none;
        color: var(--text-muted);
        cursor: pointer;
        font-size: 14px;
        width: 24px;
        height: 24px;
        border-radius: 6px;
        display: inline-flex;
        align-items: center;
        justify-content: center;

        &:hover {
            background: var(--bg-soft);
            color: var(--text);
        }
    }
}

.reveal-body {
    display: flex;
    align-items: stretch;
    gap: 8px;

    .reveal-key {
        flex: 1;
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 13px;
        background: var(--bg);
        border: 1px solid var(--border-strong);
        border-radius: 8px;
        padding: 10px 12px;
        color: hsl(142 71% 75%);
        overflow-x: auto;
        white-space: nowrap;
        display: flex;
        align-items: center;
    }
}

.reveal-help {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.5;

    code {
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 11px;
        padding: 1px 5px;
        background: var(--bg-soft);
        border: 1px solid var(--border);
        border-radius: 4px;
        color: var(--text);
    }
}

.key-form {
    display: flex;
    flex-direction: column;
    background: var(--bg-soft);
    border: 1px solid hsl(217 91% 60% / 0.35);
    border-radius: 10px;
}

.key-form-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
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

.key-form-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    padding: 10px 14px;
    border-top: 1px solid var(--border);
    background: var(--bg);
    border-radius: 0 0 10px 10px;

    .form-error {
        flex: 1;
        text-align: left;
        font-size: 12px;
        color: hsl(0 84% 65%);
    }
}

.key-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.key-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 14px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;
    transition: background 140ms ease, border-color 140ms ease;

    &:hover {
        background: var(--bg-hover);
        border-color: var(--border-strong);
    }

    &.inactive { opacity: 0.6; }

    &.expired {
        border-color: hsl(0 84% 60% / 0.4);
        background: hsl(0 84% 60% / 0.04);
    }
}

.key-row-mark {
    width: 36px;
    height: 36px;
    flex: none;
    border-radius: 10px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    background: hsl(48 92% 55% / 0.14);
    color: hsl(48 92% 70%);
}

.key-row-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
}

.key-row-head {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.key-row-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
}

.key-row-badge {
    font-size: 9.5px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 2px 7px;
    border-radius: 999px;
    border: 1px solid var(--border);

    &.role-read {
        background: hsl(217 91% 60% / 0.14);
        border-color: hsl(217 91% 60% / 0.4);
        color: hsl(217 91% 75%);
    }

    &.role-write {
        background: hsl(28 92% 55% / 0.14);
        border-color: hsl(28 92% 55% / 0.4);
        color: hsl(28 92% 70%);
    }

    &.role-readwrite {
        background: hsl(265 78% 60% / 0.14);
        border-color: hsl(265 78% 60% / 0.4);
        color: hsl(265 78% 75%);
    }

    &.muted {
        background: var(--control);
        color: var(--text-faint);
    }

    &.danger {
        background: hsl(0 84% 60% / 0.14);
        border-color: hsl(0 84% 60% / 0.4);
        color: hsl(0 84% 75%);
    }
}

.key-row-meta {
    font-size: 11px;
    color: var(--text-faint);
    text-transform: lowercase;
    letter-spacing: 0.02em;

    .key-meta-sep {
        margin: 0 6px;
        opacity: 0.6;
    }

    .key-meta-faint {
        color: var(--text-faint);
    }
}

.key-row-actions {
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.row-toggle-btn {
    appearance: none;
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;

    .toggle-track {
        position: relative;
        width: 28px;
        height: 16px;
        background: var(--control);
        border: 1px solid var(--border);
        border-radius: 999px;
        transition: background 160ms ease, border-color 160ms ease;
    }

    .toggle-thumb {
        position: absolute;
        top: 1px;
        left: 1px;
        width: 12px;
        height: 12px;
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
            transform: translateX(12px);
            background: hsl(142 71% 60%);
        }
    }
}

.row-btn {
    appearance: none;
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    width: 30px;
    height: 30px;
    border-radius: 7px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease;

    &:hover {
        background: var(--bg-hover);
        color: var(--text);
        border-color: var(--border);
    }

    &.danger:hover {
        background: hsl(0 84% 60% / 0.12);
        color: hsl(0 84% 70%);
        border-color: hsl(0 84% 60% / 0.4);
    }
}

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    padding: 40px 20px;
    background: var(--bg-soft);
    border: 1px dashed var(--border-strong);
    border-radius: 14px;
    text-align: center;

    .empty-icon {
        width: 48px;
        height: 48px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
        background: hsl(48 92% 55% / 0.12);
        color: hsl(48 92% 70%);
        font-size: 18px;
    }

    .empty-title {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: var(--text);
    }

    .empty-sub {
        margin: 0;
        max-width: 40ch;
        color: var(--text-muted);
        font-size: 13px;
        line-height: 1.5;
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

    &.copy-success {
        background: hsl(142 71% 45% / 0.22);
        border-color: hsl(142 71% 45% / 0.6);
        color: hsl(142 71% 80%);
    }
}

.inline-form-enter-active,
.inline-form-leave-active {
    transition: opacity 200ms $v2-ease, transform 200ms $v2-ease, max-height 220ms $v2-ease;
    max-height: 600px;
    overflow: hidden;
}

.inline-form-enter-from,
.inline-form-leave-to {
    opacity: 0;
    transform: translateY(-6px);
    max-height: 0;
}

@media (max-width: 640px) {
    .page-head {
        flex-direction: column;
        align-items: stretch;
    }

    .key-row {
        flex-wrap: wrap;
    }

    .key-row-actions {
        width: 100%;
        justify-content: flex-end;
    }
}
</style>
