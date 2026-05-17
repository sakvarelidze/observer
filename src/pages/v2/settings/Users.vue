<template>
    <div class="settings-page">
        <header class="page-head">
            <div class="page-head-text">
                <h2 class="page-title">Users</h2>
                <p class="page-sub">people who can sign in. admins can toggle others on/off and delete accounts; doing so requires re-entering an admin password.</p>
            </div>
            <button
                v-if="!loading && !creating"
                type="button"
                class="action primary"
                @click="startCreate"
            >
                <font-awesome-icon icon="plus" />
                <span>new user</span>
            </button>
        </header>

        <div v-if="loading" class="page-loading">
            <LoaderBars size="md" />
        </div>

        <div v-else class="users-pane">
            <transition name="inline-form">
                <form
                    v-if="creating"
                    class="user-form"
                    @submit.prevent="submitCreate"
                    @keydown.esc.prevent.stop="cancelCreate"
                >
                    <div class="user-form-body">
                        <label class="field">
                            <span class="field-label">username <span class="req">*</span></span>
                            <input
                                ref="createUsernameInput"
                                v-model="createDraft.username"
                                type="text"
                                class="input"
                                placeholder="alice"
                                autocomplete="off"
                                required
                            >
                        </label>
                        <label class="field">
                            <span class="field-label">temporary password <span class="req">*</span></span>
                            <input
                                v-model="createDraft.password"
                                type="password"
                                class="input"
                                autocomplete="new-password"
                                minlength="8"
                                required
                            >
                            <span class="field-help">share this securely. the user can change it after first sign-in.</span>
                        </label>
                        <label class="field-toggle">
                            <input
                                v-model="createDraft.is_admin"
                                type="checkbox"
                            >
                            <span class="field-label-inline">make this user an admin</span>
                        </label>
                    </div>
                    <div class="user-form-foot">
                        <span v-if="createError" class="form-error">{{ createError }}</span>
                        <button type="button" class="action ghost" :disabled="createSaving" @click="cancelCreate">cancel</button>
                        <button
                            type="submit"
                            class="action primary"
                            :disabled="createSaving || !canCreate"
                        >
                            <span v-if="!createSaving">create user</span>
                            <span v-else>creating…</span>
                        </button>
                    </div>
                </form>
            </transition>

            <ul v-if="users.length > 0" class="user-list">
                <li
                    v-for="user in users"
                    :key="user.id"
                    class="user-row"
                    :class="{ inactive: !user.active }"
                >
                    <span class="user-row-avatar">
                        {{ avatarLetter(user.username) }}
                    </span>
                    <div class="user-row-body">
                        <div class="user-row-head">
                            <span class="user-row-name">{{ user.username }}</span>
                            <span v-if="user.is_admin" class="user-row-badge admin">admin</span>
                            <span v-if="!user.active" class="user-row-badge muted">disabled</span>
                            <span v-if="isCurrentUser(user)" class="user-row-badge self">you</span>
                        </div>
                        <span class="user-row-meta">
                            <span v-if="user.is_admin">manages other users + system settings</span>
                            <span v-else>can view and edit monitors</span>
                        </span>
                    </div>
                    <div class="user-row-actions">
                        <button
                            type="button"
                            class="row-toggle-btn"
                            :class="{ on: user.active }"
                            :disabled="isCurrentUser(user)"
                            :title="toggleTitle(user)"
                            @click="askToggle(user)"
                        >
                            <span class="toggle-track"><span class="toggle-thumb"></span></span>
                            <span class="toggle-label">{{ user.active ? "on" : "off" }}</span>
                        </button>
                        <button
                            type="button"
                            class="row-btn danger"
                            :disabled="isCurrentUser(user)"
                            :title="deleteTitle(user)"
                            @click="askDelete(user)"
                        >
                            <font-awesome-icon icon="trash" />
                        </button>
                    </div>
                </li>
            </ul>

            <div v-else-if="!creating" class="empty-state">
                <span class="empty-icon">
                    <font-awesome-icon icon="list" />
                </span>
                <p class="empty-title">No users yet</p>
                <p class="empty-sub">Add another account so you're not the only one who can manage this instance.</p>
            </div>
        </div>

        <ConfirmV2
            :open="!!confirmAction"
            :tone="confirmAction?.tone || 'primary'"
            :title="confirmAction?.title || ''"
            :confirm-label="confirmAction?.confirmLabel || 'confirm'"
            busy-label="working…"
            :busy="confirmSaving"
            @cancel="cancelConfirm"
            @confirm="runConfirm"
        >
            <span v-if="confirmAction?.body">{{ confirmAction.body }}</span>
            <input
                v-if="confirmAction"
                ref="confirmPasswordInput"
                v-model="confirmAction.adminPassword"
                type="password"
                class="input confirm-input"
                autocomplete="current-password"
                placeholder="your admin password"
                required
                @keydown.enter.prevent="runConfirm"
            >
            <span v-if="confirmAction?.error" class="confirm-error">{{ confirmAction.error }}</span>
        </ConfirmV2>
    </div>
</template>

<script>
import LoaderBars from "../LoaderBars.vue";
import ConfirmV2 from "../ConfirmV2.vue";

export default {
    name: "SettingsUsers",
    components: { LoaderBars,
        ConfirmV2 },
    data() {
        return {
            users: [],
            loading: true,

            creating: false,
            createDraft: this.emptyDraft(),
            createSaving: false,
            createError: null,

            // Single confirm slot used for activate / deactivate / delete
            // since they all need an admin-password challenge.
            confirmAction: null,
            confirmSaving: false,
        };
    },
    computed: {
        canCreate() {
            const d = this.createDraft;
            return !!d.username?.trim() && !!d.password && d.password.length >= 8;
        },
    },
    mounted() {
        this.fetchUsers();
    },
    methods: {
        emptyDraft() {
            return { username: "",
                password: "",
                is_admin: false };
        },
        avatarLetter(username) {
            return (username || "?").trim().charAt(0).toUpperCase();
        },
        isCurrentUser(user) {
            return user?.username === this.$root.username;
        },
        toggleTitle(user) {
            if (this.isCurrentUser(user)) {
                return "Cannot toggle your own account";
            }
            return user.active ? "Disable" : "Enable";
        },
        deleteTitle(user) {
            if (this.isCurrentUser(user)) {
                return "Cannot delete your own account";
            }
            return "Delete user";
        },
        async fetchUsers() {
            this.loading = true;
            try {
                const list = await this.$root.getUsers();
                this.users = (Array.isArray(list) ? list : [])
                    .sort((a, b) => {
                        // Admins first, then alphabetically by username.
                        if (!!a.is_admin !== !!b.is_admin) {
                            return a.is_admin ? -1 : 1;
                        }
                        return (a.username || "").localeCompare(b.username || "");
                    });
            } catch (e) {
                console.warn("could not load users", e);
                this.users = [];
            } finally {
                this.loading = false;
            }
        },
        startCreate() {
            this.creating = true;
            this.createDraft = this.emptyDraft();
            this.createError = null;
            this.$nextTick(() => {
                this.$refs.createUsernameInput?.focus();
            });
        },
        cancelCreate() {
            this.creating = false;
            this.createError = null;
        },
        async submitCreate() {
            if (!this.canCreate) {
                return;
            }
            this.createSaving = true;
            this.createError = null;
            try {
                const payload = {
                    username: this.createDraft.username.trim(),
                    password: this.createDraft.password,
                    is_admin: !!this.createDraft.is_admin,
                    active: true,
                };
                const res = await this.$root.addUser(payload);
                if (!res?.id && !res?.ok) {
                    this.createError = res?.msg || res?.detail || "could not create user";
                    return;
                }
                await this.fetchUsers();
                this.cancelCreate();
            } catch (e) {
                const detail = e?.response?.data?.detail;
                if (detail === "usernameTaken") {
                    this.createError = "that username is already taken";
                } else {
                    this.createError = detail || e?.message || "request failed";
                }
            } finally {
                this.createSaving = false;
            }
        },
        askToggle(user) {
            if (this.isCurrentUser(user)) {
                return;
            }
            const next = !user.active;
            this.confirmAction = {
                kind: next ? "activate" : "deactivate",
                user,
                title: next ? `enable ${user.username}` : `disable ${user.username}`,
                body: next
                    ? `Re-enable ${user.username}'s account so they can sign in again? Confirm with your admin password.`
                    : `Disable ${user.username}'s account? They won't be able to sign in until you re-enable them. Confirm with your admin password.`,
                confirmLabel: next ? "enable user" : "disable user",
                tone: next ? "primary" : "danger",
                adminPassword: "",
                error: null,
            };
            this.$nextTick(() => {
                this.$refs.confirmPasswordInput?.focus();
            });
        },
        askDelete(user) {
            if (this.isCurrentUser(user)) {
                return;
            }
            this.confirmAction = {
                kind: "delete",
                user,
                title: `delete ${user.username}`,
                body: `Permanently delete ${user.username}? This can't be undone. Confirm with your admin password.`,
                confirmLabel: "delete user",
                tone: "danger",
                adminPassword: "",
                error: null,
            };
            this.$nextTick(() => {
                this.$refs.confirmPasswordInput?.focus();
            });
        },
        cancelConfirm() {
            if (this.confirmSaving) {
                return;
            }
            this.confirmAction = null;
        },
        async runConfirm() {
            if (!this.confirmAction || this.confirmSaving) {
                return;
            }
            const action = this.confirmAction;
            if (!action.adminPassword) {
                action.error = "enter your admin password";
                return;
            }
            this.confirmSaving = true;
            action.error = null;
            try {
                if (action.kind === "delete") {
                    await this.$root.deleteUser(action.user.id, action.adminPassword);
                } else if (action.kind === "deactivate") {
                    await this.$root.deactivateUser(action.user.id, action.adminPassword);
                } else if (action.kind === "activate") {
                    await this.$root.activateUser(action.user.id, action.adminPassword);
                }
                await this.fetchUsers();
                this.confirmAction = null;
            } catch (e) {
                const detail = e?.response?.data?.detail;
                if (detail === "invalidAdminPassword") {
                    action.error = "admin password is incorrect";
                } else {
                    action.error = detail || e?.message || "request failed";
                }
            } finally {
                this.confirmSaving = false;
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

.users-pane {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.user-form {
    display: flex;
    flex-direction: column;
    background: var(--bg-soft);
    border: 1px solid hsl(217 91% 60% / 0.35);
    border-radius: 10px;
}

.user-form-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
}

.user-form-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    padding: 10px 14px;
    border-top: 1px solid var(--border);
    background: hsl(0 0% 5%);
    border-radius: 0 0 10px 10px;

    .form-error {
        flex: 1;
        text-align: left;
        font-size: 12px;
        color: hsl(0 84% 65%);
    }
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

.field-help {
    font-size: 11px;
    color: var(--text-faint);
    line-height: 1.5;
}

.field-toggle {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    user-select: none;

    input[type="checkbox"] {
        accent-color: hsl(142 71% 45%);
        width: 16px;
        height: 16px;
    }

    .field-label-inline {
        font-size: 12px;
        color: var(--text);
        text-transform: none;
        letter-spacing: 0;
    }
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

.user-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.user-row {
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
}

.user-row-avatar {
    width: 36px;
    height: 36px;
    flex: none;
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 600;
    background: hsl(0 0% 14%);
    color: var(--text);
    text-transform: uppercase;
}

.user-row-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
}

.user-row-head {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.user-row-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
}

.user-row-badge {
    font-size: 9.5px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 2px 7px;
    border-radius: 999px;
    border: 1px solid var(--border);

    &.admin {
        background: hsl(265 78% 60% / 0.14);
        border-color: hsl(265 78% 60% / 0.4);
        color: hsl(265 78% 75%);
    }

    &.muted {
        background: hsl(0 0% 14%);
        color: var(--text-faint);
    }

    &.self {
        background: hsl(142 71% 45% / 0.14);
        border-color: hsl(142 71% 45% / 0.4);
        color: hsl(142 71% 75%);
    }
}

.user-row-meta {
    font-size: 11px;
    color: var(--text-faint);
}

.user-row-actions {
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
        background: hsl(0 0% 14%);
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

    &:disabled {
        opacity: 0.4;
        cursor: not-allowed;
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

    &:hover:not(:disabled) {
        background: var(--bg-hover);
        color: var(--text);
        border-color: var(--border);
    }

    &:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }

    &.danger:hover:not(:disabled) {
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
        background: hsl(265 78% 60% / 0.12);
        color: hsl(265 78% 75%);
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

    .user-row {
        flex-wrap: wrap;
    }

    .user-row-actions {
        width: 100%;
        justify-content: flex-end;
    }
}
</style>
