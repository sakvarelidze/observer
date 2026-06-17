<template>
    <div class="settings-page">
        <header class="page-head">
            <div class="page-head-text">
                <h2 class="page-title">Notifications</h2>
                <p class="page-sub">channels we send alerts to. attach them to any monitor from its edit page.</p>
            </div>
            <button
                v-if="!loading && !creating"
                type="button"
                class="action primary"
                @click="startCreate"
            >
                <font-awesome-icon icon="plus" />
                <span>new channel</span>
            </button>
        </header>

        <div v-if="loading" class="page-loading">
            <LoaderBars size="md" />
        </div>

        <div v-else class="notifs-pane">
            <transition name="inline-form">
                <ChannelForm
                    v-if="creating"
                    key="create"
                    mode="create"
                    :saving="createSaving"
                    :testing="testingCreate"
                    :error="createError"
                    :provider-catalog="providers"
                    :draft="createDraft"
                    @cancel="cancelCreate"
                    @submit="submitCreate"
                    @test="testFromForm"
                />
            </transition>

            <ul v-if="channels.length > 0" class="notif-list">
                <li
                    v-for="channel in channels"
                    :key="channel.id"
                    class="notif-row"
                    :class="{
                        editing: editingId === channel.id,
                        inactive: !channel.active,
                    }"
                >
                    <template v-if="editingId !== channel.id">
                        <span class="notif-row-mark" :class="`tone-${toneFor(channel.type)}`">
                            <font-awesome-icon icon="bell" />
                        </span>

                        <div class="notif-row-body">
                            <div class="notif-row-head">
                                <span class="notif-row-name">{{ channel.name }}</span>
                                <span v-if="channel.is_default" class="notif-row-badge default">default</span>
                                <span v-if="!channel.active" class="notif-row-badge muted">disabled</span>
                            </div>
                            <span class="notif-row-type">{{ providerLabel(channel.type) }}</span>
                        </div>

                        <div class="notif-row-actions">
                            <button
                                type="button"
                                class="row-toggle-btn"
                                :class="{ on: channel.active }"
                                :title="channel.active ? 'Click to disable' : 'Click to enable'"
                                @click="toggleActive(channel)"
                            >
                                <span class="toggle-track"><span class="toggle-thumb"></span></span>
                                <span class="toggle-label">{{ channel.active ? "on" : "off" }}</span>
                            </button>
                            <button
                                type="button"
                                class="row-btn"
                                :disabled="testInFlight === channel.id"
                                title="Send a test alert"
                                @click="testExisting(channel)"
                            >
                                <font-awesome-icon
                                    :icon="testInFlight === channel.id ? 'spinner' : 'bullhorn'"
                                    :spin="testInFlight === channel.id"
                                />
                            </button>
                            <button
                                type="button"
                                class="row-btn"
                                title="Edit"
                                @click="startEdit(channel)"
                            >
                                <font-awesome-icon icon="pen" />
                            </button>
                            <button
                                type="button"
                                class="row-btn danger"
                                title="Delete"
                                @click="confirmDelete(channel)"
                            >
                                <font-awesome-icon icon="trash" />
                            </button>
                        </div>
                    </template>

                    <ChannelForm
                        v-else
                        :key="`edit-${channel.id}`"
                        mode="edit"
                        :saving="editSaving"
                        :testing="testingEdit"
                        :error="editError"
                        :provider-catalog="providers"
                        :draft="editDraft"
                        @cancel="cancelEdit"
                        @submit="submitEdit"
                        @test="testFromForm"
                    />
                </li>
            </ul>

            <div v-else-if="!creating" class="empty-state">
                <span class="empty-icon">
                    <font-awesome-icon icon="bell" />
                </span>
                <p class="empty-title">No channels yet</p>
                <p class="empty-sub">Set one up so monitors can shout when something goes wrong.</p>
                <button type="button" class="action primary" @click="startCreate">
                    <font-awesome-icon icon="plus" />
                    <span>add your first channel</span>
                </button>
            </div>

            <Teleport to="body">
                <div v-if="testToast" class="test-toast" :class="`tone-${testToast.tone}`">
                    <font-awesome-icon :icon="testToast.tone === 'down' ? 'times-circle' : 'check-circle'" />
                    <span>{{ testToast.message }}</span>
                </div>
            </Teleport>
        </div>

        <ConfirmV2
            :open="!!pendingDelete"
            tone="danger"
            title="delete channel"
            confirm-label="delete channel"
            busy-label="deleting…"
            :busy="deleteSaving"
            @cancel="cancelDelete"
            @confirm="confirmedDelete"
        >
            Remove <strong>{{ pendingDelete?.name }}</strong>? Monitors that use it will stop receiving alerts via this channel.
        </ConfirmV2>
    </div>
</template>

<script>
import LoaderBars from "../LoaderBars.vue";
import ConfirmV2 from "../ConfirmV2.vue";
import ChannelForm from "./ChannelForm.vue";
import { NOTIF_PROVIDERS } from "../MonitorFields.vue";

// Tone-per-provider so the row icon picks up a recognizable accent
// without needing per-provider FontAwesome icons.
const TONE_BY_TYPE = {
    discord: "purple",
    slack: "yellow",
    teams: "blue",
    telegram: "blue",
    ntfy: "green",
    pagerduty: "red",
    "grafana-oncall": "orange",
    twilio: "red",
};

export default {
    name: "SettingsNotifications",
    components: { LoaderBars,
        ChannelForm,
        ConfirmV2 },
    data() {
        return {
            channels: [],
            loading: true,
            error: null,

            creating: false,
            createDraft: this.emptyDraft(),
            createSaving: false,
            createError: null,
            testingCreate: false,

            editingId: null,
            editDraft: this.emptyDraft(),
            editSaving: false,
            editError: null,
            testingEdit: false,

            testInFlight: null,
            testToast: null,
            testToastTimer: null,

            pendingDelete: null,
            deleteSaving: false,
        };
    },
    computed: {
        providers() {
            return NOTIF_PROVIDERS;
        },
    },
    mounted() {
        this.fetchChannels();
    },
    beforeUnmount() {
        clearTimeout(this.testToastTimer);
    },
    methods: {
        emptyDraft() {
            return {
                type: NOTIF_PROVIDERS[0]?.type || "discord",
                name: "",
                fields: {},
                active: true,
                isDefault: false,
            };
        },
        toneFor(type) {
            return TONE_BY_TYPE[type] || "muted";
        },
        providerLabel(type) {
            const p = NOTIF_PROVIDERS.find(x => x.type === type);
            return p?.label || type;
        },
        async fetchChannels() {
            this.loading = true;
            this.error = null;
            try {
                const { data } = await this.$root.api.get("/notifications");
                const list = Array.isArray(data) ? data : (data?.notifications || []);
                this.channels = list
                    .map(c => this.normalizeChannel(c))
                    .sort((a, b) => (a.name || "").localeCompare(b.name || ""));
                // Push to root so MonitorFields sees the same list.
                if (typeof this.$root.loadNotifications === "function") {
                    await this.$root.loadNotifications();
                }
            } catch (e) {
                this.error = e?.response?.data?.detail || e?.message || "could not load channels";
            } finally {
                this.loading = false;
            }
        },
        normalizeChannel(raw) {
            if (!raw) {
                return raw;
            }
            return {
                id: raw.id,
                name: raw.name,
                type: raw.type,
                active: raw.active !== false,
                is_default: !!(raw.is_default ?? raw.isDefault),
                config: raw.config && typeof raw.config === "object" ? raw.config : {},
            };
        },
        startCreate() {
            this.creating = true;
            this.createDraft = this.emptyDraft();
            this.createError = null;
            this.editingId = null;
        },
        cancelCreate() {
            this.creating = false;
            this.createError = null;
        },
        async submitCreate() {
            this.createSaving = true;
            this.createError = null;
            try {
                const payload = this.draftToPayload(this.createDraft);
                const { data } = await this.$root.api.post("/notifications", payload);
                if (!data?.ok && data?.id == null) {
                    this.createError = data?.msg || "could not create channel";
                    return;
                }
                await this.fetchChannels();
                this.cancelCreate();
            } catch (e) {
                this.createError = e?.response?.data?.detail || e?.message || "request failed";
            } finally {
                this.createSaving = false;
            }
        },
        startEdit(channel) {
            this.editingId = channel.id;
            this.editDraft = {
                type: channel.type,
                name: channel.name,
                // Spread the existing config so users can edit just the
                // surfaced fields without losing advanced ones (icon
                // emoji, custom username, etc. that v1 sets but v2's
                // catalog doesn't surface yet).
                fields: { ...(channel.config || {}) },
                active: !!channel.active,
                isDefault: !!channel.is_default,
            };
            this.editError = null;
            this.creating = false;
        },
        cancelEdit() {
            this.editingId = null;
            this.editError = null;
        },
        async submitEdit() {
            if (this.editingId == null) {
                return;
            }
            this.editSaving = true;
            this.editError = null;
            try {
                const payload = this.draftToPayload(this.editDraft);
                const { data } = await this.$root.api.post(
                    `/notifications/${this.editingId}`,
                    payload,
                );
                if (!data?.ok) {
                    this.editError = data?.msg || "could not save channel";
                    return;
                }
                await this.fetchChannels();
                this.cancelEdit();
            } catch (e) {
                this.editError = e?.response?.data?.detail || e?.message || "request failed";
            } finally {
                this.editSaving = false;
            }
        },
        draftToPayload(draft) {
            return {
                name: draft.name.trim(),
                type: draft.type,
                active: !!draft.active,
                is_default: !!draft.isDefault,
                config: { ...(draft.fields || {}) },
            };
        },
        async toggleActive(channel) {
            const next = !channel.active;
            // Optimistic — flip the row immediately, roll back on error.
            const original = channel.active;
            channel.active = next;
            try {
                await this.$root.api.post(`/notifications/${channel.id}`, {
                    name: channel.name,
                    type: channel.type,
                    active: next,
                    is_default: channel.is_default,
                    config: channel.config || {},
                });
            } catch (e) {
                channel.active = original;
                this.flashTest("could not update channel", "down");
            }
        },
        async testExisting(channel) {
            this.testInFlight = channel.id;
            try {
                await this.$root.api.post("/notifications/test", {
                    name: channel.name,
                    type: channel.type,
                    config: channel.config || {},
                });
                this.flashTest(`test sent via ${channel.name}`, "up");
            } catch (e) {
                const detail = e?.response?.data?.detail
                    || e?.response?.data?.msg
                    || e?.message
                    || "test failed";
                this.flashTest(detail, "down");
            } finally {
                this.testInFlight = null;
            }
        },
        async testFromForm() {
            const draft = this.creating ? this.createDraft : this.editDraft;
            const flag = this.creating ? "testingCreate" : "testingEdit";
            this[flag] = true;
            try {
                await this.$root.api.post("/notifications/test", {
                    name: draft.name?.trim() || "preview",
                    type: draft.type,
                    config: { ...(draft.fields || {}) },
                });
                this.flashTest("test alert sent", "up");
            } catch (e) {
                const detail = e?.response?.data?.detail
                    || e?.response?.data?.msg
                    || e?.message
                    || "test failed";
                this.flashTest(detail, "down");
            } finally {
                this[flag] = false;
            }
        },
        flashTest(message, tone) {
            this.testToast = { message,
                tone };
            clearTimeout(this.testToastTimer);
            this.testToastTimer = setTimeout(() => {
                this.testToast = null;
            }, 3200);
        },
        confirmDelete(channel) {
            this.pendingDelete = { ...channel };
        },
        cancelDelete() {
            if (this.deleteSaving) {
                return;
            }
            this.pendingDelete = null;
        },
        async confirmedDelete() {
            const channel = this.pendingDelete;
            if (!channel) {
                return;
            }
            this.deleteSaving = true;
            try {
                await this.$root.api.delete(`/notifications/${channel.id}`);
                await this.fetchChannels();
                this.pendingDelete = null;
                if (this.editingId === channel.id) {
                    this.cancelEdit();
                }
            } catch (e) {
                this.flashTest("could not delete channel", "down");
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
        max-width: 56ch;
    }
}

.page-loading {
    display: flex;
    justify-content: center;
    padding: 40px 0;
}

.notifs-pane {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.notif-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.notif-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 14px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;
    transition: background 140ms ease, border-color 140ms ease;

    &:hover:not(.editing) {
        background: var(--bg-hover);
        border-color: var(--border-strong);
    }

    &.editing {
        flex-direction: column;
        align-items: stretch;
        gap: 0;
        padding: 0;
        border-color: hsl(217 91% 60% / 0.45);
    }

    &.inactive:not(.editing) {
        opacity: 0.6;
    }
}

.notif-row-mark {
    width: 36px;
    height: 36px;
    flex: none;
    border-radius: 10px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    background: var(--control);
    color: var(--text-muted);

    &.tone-purple { background: hsl(265 78% 60% / 0.16); color: hsl(265 78% 75%); }
    &.tone-yellow { background: hsl(48 92% 55% / 0.16); color: hsl(48 92% 70%); }
    &.tone-blue { background: hsl(217 91% 60% / 0.16); color: hsl(217 91% 75%); }
    &.tone-green { background: hsl(142 71% 45% / 0.16); color: hsl(142 71% 75%); }
    &.tone-red { background: hsl(0 84% 60% / 0.16); color: hsl(0 84% 75%); }
    &.tone-orange { background: hsl(28 92% 55% / 0.16); color: hsl(28 92% 70%); }
}

.notif-row-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 3px;
    min-width: 0;
}

.notif-row-head {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}

.notif-row-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
}

.notif-row-badge {
    font-size: 9.5px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 2px 6px;
    border-radius: 999px;
    border: 1px solid var(--border);

    &.default {
        background: hsl(142 71% 45% / 0.14);
        border-color: hsl(142 71% 45% / 0.4);
        color: hsl(142 71% 75%);
    }

    &.muted {
        background: var(--control);
        color: var(--text-faint);
    }
}

.notif-row-type {
    font-size: 11px;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

.notif-row-actions {
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

    &:hover:not(:disabled) {
        background: var(--bg-hover);
        color: var(--text);
        border-color: var(--border);
    }

    &:disabled { opacity: 0.5; cursor: not-allowed; }

    &.danger:hover {
        background: hsl(0 84% 60% / 0.12);
        color: hsl(0 84% 70%);
        border-color: hsl(0 84% 60% / 0.4);
    }
}

/* Channel form styles live in ChannelForm.vue itself. */

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
        background: hsl(217 91% 60% / 0.08);
        color: hsl(217 91% 70%);
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

.test-toast {
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: var(--bg-soft);
    border: 1px solid var(--border-strong);
    border-radius: 10px;
    padding: 12px 16px;
    color: var(--text);
    font-size: 13px;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    box-shadow: 0 12px 28px hsl(0 0% 0% / 0.45);
    animation: v2-up 220ms $v2-ease both;
    z-index: 50;

    &.tone-up {
        border-color: hsl(142 71% 45% / 0.55);
        color: hsl(142 71% 80%);
    }

    &.tone-down {
        border-color: hsl(0 84% 60% / 0.55);
        color: hsl(0 84% 80%);
    }
}

.inline-form-enter-active,
.inline-form-leave-active {
    transition: opacity 200ms $v2-ease, transform 200ms $v2-ease,
        max-height 220ms $v2-ease;
    max-height: 800px;
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

    .notif-row {
        flex-wrap: wrap;
    }

    .notif-row-actions {
        order: 3;
        width: 100%;
        justify-content: flex-end;
    }
}
</style>
