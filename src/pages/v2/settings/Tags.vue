<template>
    <div class="settings-page">
        <header class="page-head">
            <div class="page-head-text">
                <h2 class="page-title">Tags</h2>
                <p class="page-sub">label monitors so you can group, filter, and theme them at a glance.</p>
            </div>
            <button
                v-if="!loading && !creating"
                type="button"
                class="action primary"
                @click="startCreate"
            >
                <font-awesome-icon icon="plus" />
                <span>new tag</span>
            </button>
        </header>

        <div v-if="loading" class="page-loading">
            <LoaderBars size="md" />
        </div>

        <div v-else class="tags-pane">
            <transition name="inline-form">
                <form
                    v-if="creating"
                    class="tag-form create-form"
                    @submit.prevent="submitCreate"
                    @keydown.esc.prevent.stop="cancelCreate"
                >
                    <div class="tag-form-body">
                        <input
                            ref="createNameInput"
                            v-model="createDraft.name"
                            type="text"
                            class="input"
                            placeholder="tag name"
                            autocomplete="off"
                            required
                        >
                        <ColorSwatches v-model="createDraft.color" />
                    </div>
                    <div class="tag-form-foot">
                        <span v-if="createError" class="form-error">{{ createError }}</span>
                        <button type="button" class="action ghost" :disabled="createSaving" @click="cancelCreate">cancel</button>
                        <button type="submit" class="action primary" :disabled="createSaving || !createDraft.name.trim()">
                            <span v-if="!createSaving">create</span>
                            <span v-else>creating…</span>
                        </button>
                    </div>
                </form>
            </transition>

            <ul v-if="tags.length > 0" class="tag-list">
                <li v-for="tag in tags" :key="tag.id" class="tag-row" :class="{ editing: editingId === tag.id }">
                    <template v-if="editingId !== tag.id">
                        <span class="tag-row-swatch" :style="{ background: tag.color }"></span>
                        <span class="tag-row-name">{{ tag.name }}</span>
                        <span class="tag-row-color mono">{{ tag.color }}</span>
                        <div class="tag-row-actions">
                            <button type="button" class="row-btn" title="Edit tag" @click="startEdit(tag)">
                                <font-awesome-icon icon="pen" />
                            </button>
                            <button type="button" class="row-btn danger" title="Delete tag" @click="confirmDelete(tag)">
                                <font-awesome-icon icon="trash" />
                            </button>
                        </div>
                    </template>

                    <form
                        v-else
                        class="tag-form edit-form"
                        @submit.prevent="submitEdit"
                        @keydown.esc.prevent.stop="cancelEdit"
                    >
                        <div class="tag-form-body">
                            <input
                                v-model="editDraft.name"
                                type="text"
                                class="input"
                                placeholder="tag name"
                                autocomplete="off"
                                required
                            >
                            <ColorSwatches v-model="editDraft.color" />
                        </div>
                        <div class="tag-form-foot">
                            <span v-if="editError" class="form-error">{{ editError }}</span>
                            <button type="button" class="action ghost" :disabled="editSaving" @click="cancelEdit">cancel</button>
                            <button type="submit" class="action primary" :disabled="editSaving || !editDraft.name.trim()">
                                <span v-if="!editSaving">save</span>
                                <span v-else>saving…</span>
                            </button>
                        </div>
                    </form>
                </li>
            </ul>

            <div v-else-if="!creating" class="empty-state">
                <span class="empty-icon">
                    <font-awesome-icon icon="filter" />
                </span>
                <p class="empty-title">No tags yet</p>
                <p class="empty-sub">Tags help you bundle related monitors. Create one and assign it from any monitor's edit page.</p>
                <button type="button" class="action primary" @click="startCreate">
                    <font-awesome-icon icon="plus" />
                    <span>create your first tag</span>
                </button>
            </div>
        </div>

        <ConfirmV2
            :open="!!pendingDelete"
            tone="danger"
            title="delete tag"
            confirm-label="delete tag"
            busy-label="deleting…"
            :busy="deleteSaving"
            @cancel="cancelDelete"
            @confirm="confirmedDelete"
        >
            Remove <strong>{{ pendingDelete?.name }}</strong> from every monitor that uses it? This can't be undone.
        </ConfirmV2>
    </div>
</template>

<script>
import LoaderBars from "../LoaderBars.vue";
import ConfirmV2 from "../ConfirmV2.vue";
import ColorSwatches from "./ColorSwatches.vue";
import { TAG_COLORS } from "../MonitorFields.vue";

export default {
    name: "SettingsTags",
    components: { LoaderBars,
        ColorSwatches,
        ConfirmV2 },
    data() {
        return {
            tags: [],
            loading: true,
            error: null,

            creating: false,
            createDraft: { name: "",
                color: TAG_COLORS[0] },
            createSaving: false,
            createError: null,

            editingId: null,
            editDraft: { name: "",
                color: TAG_COLORS[0] },
            editSaving: false,
            editError: null,

            pendingDelete: null,
            deleteSaving: false,
        };
    },
    mounted() {
        this.fetchTags();
    },
    methods: {
        async fetchTags() {
            this.loading = true;
            this.error = null;
            try {
                const { data } = await this.$root.api.get("/tags");
                if (Array.isArray(data)) {
                    this.tags = data;
                } else if (Array.isArray(data?.tags)) {
                    this.tags = data.tags;
                } else {
                    this.tags = [];
                }
                this.tags.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
            } catch (e) {
                this.error = e?.response?.data?.detail || e?.message || "could not load tags";
            } finally {
                this.loading = false;
            }
        },
        startCreate() {
            this.creating = true;
            this.createDraft = { name: "",
                color: TAG_COLORS[0] };
            this.createError = null;
            this.editingId = null;
            this.$nextTick(() => {
                this.$refs.createNameInput?.focus();
            });
        },
        cancelCreate() {
            this.creating = false;
            this.createDraft = { name: "",
                color: TAG_COLORS[0] };
            this.createError = null;
        },
        async submitCreate() {
            const name = this.createDraft.name.trim();
            if (!name) {
                return;
            }
            this.createSaving = true;
            this.createError = null;
            try {
                const { data } = await this.$root.api.post("/tags", {
                    name,
                    color: this.createDraft.color,
                });
                const tag = data?.tag || data;
                if (!tag || !tag.id) {
                    this.createError = data?.msg || "could not create tag";
                    return;
                }
                this.tags = [ ...this.tags, tag ].sort(
                    (a, b) => (a.name || "").localeCompare(b.name || ""),
                );
                this.cancelCreate();
            } catch (e) {
                this.createError = e?.response?.data?.detail || e?.message || "request failed";
            } finally {
                this.createSaving = false;
            }
        },
        startEdit(tag) {
            this.editingId = tag.id;
            this.editDraft = { name: tag.name,
                color: tag.color || TAG_COLORS[0] };
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
            const name = this.editDraft.name.trim();
            if (!name) {
                return;
            }
            this.editSaving = true;
            this.editError = null;
            try {
                const { data } = await this.$root.api.post(
                    `/tags/${this.editingId}`,
                    { name,
                        color: this.editDraft.color },
                );
                const updated = data?.tag || data;
                if (!updated || !updated.id) {
                    this.editError = data?.msg || "could not save tag";
                    return;
                }
                this.tags = this.tags.map(t => (t.id === updated.id ? updated : t))
                    .sort((a, b) => (a.name || "").localeCompare(b.name || ""));
                this.cancelEdit();
            } catch (e) {
                this.editError = e?.response?.data?.detail || e?.message || "request failed";
            } finally {
                this.editSaving = false;
            }
        },
        confirmDelete(tag) {
            this.pendingDelete = { ...tag };
        },
        cancelDelete() {
            if (this.deleteSaving) {
                return;
            }
            this.pendingDelete = null;
        },
        async confirmedDelete() {
            const tag = this.pendingDelete;
            if (!tag) {
                return;
            }
            this.deleteSaving = true;
            try {
                await this.$root.api.delete(`/tags/${tag.id}`);
                this.tags = this.tags.filter(t => t.id !== tag.id);
                this.pendingDelete = null;
                if (this.editingId === tag.id) {
                    this.cancelEdit();
                }
            } catch (e) {
                this.error = e?.response?.data?.detail || e?.message || "could not delete tag";
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
        max-width: 50ch;
    }
}

.page-loading {
    display: flex;
    justify-content: center;
    padding: 40px 0;
}

.tags-pane {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.tag-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.tag-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
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
        background: var(--bg-soft);
        border-color: hsl(142 71% 45% / 0.45);
    }
}

.tag-row-swatch {
    width: 14px;
    height: 14px;
    border-radius: 4px;
    flex: none;
    box-shadow: 0 0 0 1px hsl(0 0% 100% / 0.06) inset;
}

.tag-row-name {
    flex: 1;
    font-size: 14px;
    font-weight: 500;
    color: var(--text);
}

.tag-row-color {
    font-size: 11px;
    color: var(--text-faint);
    font-variant-numeric: tabular-nums;
    text-transform: lowercase;

    &.mono {
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
    }
}

.tag-row-actions {
    display: inline-flex;
    align-items: center;
    gap: 4px;
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

.tag-form {
    display: flex;
    flex-direction: column;
}

.tag-form.create-form {
    background: hsl(142 71% 45% / 0.05);
    border: 1px solid hsl(142 71% 45% / 0.35);
    border-radius: 10px;
}

.tag-form-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
}

.tag-form-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    padding: 10px 14px;
    border-top: 1px solid var(--border);
    background: var(--bg-soft);
    border-radius: 0 0 10px 10px;

    .form-error {
        flex: 1;
        text-align: left;
        font-size: 12px;
        color: hsl(0 84% 65%);
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
}

/* Color swatch styles live in ColorSwatches.vue itself. */

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
        background: hsl(142 71% 45% / 0.08);
        color: hsl(142 71% 70%);
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
    transition: opacity 200ms $v2-ease, transform 200ms $v2-ease,
        max-height 220ms $v2-ease;
    max-height: 600px;
    overflow: hidden;
}

.inline-form-enter-from,
.inline-form-leave-to {
    opacity: 0;
    transform: translateY(-6px);
    max-height: 0;
}

@media (max-width: 540px) {
    .page-head {
        flex-direction: column;
        align-items: stretch;
    }

    .tag-row-color { display: none; }
}
</style>
