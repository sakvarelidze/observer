<template>
    <div class="v2-status-edit">
        <header class="topbar">
            <router-link to="/status-pages" class="back" title="Back to status pages">
                <span class="back-arrow">←</span>
                <span class="back-label">all pages</span>
            </router-link>

            <h1 class="topbar-title">{{ mode === "create" ? "new status page" : "edit status page" }}</h1>

            <div class="topbar-right">
                <a
                    v-if="mode === 'edit' && form.slug"
                    :href="`/status/${form.slug}`"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="action ghost"
                    title="Open public page"
                >
                    <font-awesome-icon icon="external-link-square-alt" />
                    <span>view</span>
                </a>
                <MenuTrigger />
            </div>
        </header>

        <main class="main">
            <div v-if="loading" class="page-loading">
                <LoaderBars size="md" />
            </div>

            <form v-else class="form" @submit.prevent="onSave">
                <!-- General -->
                <section class="block">
                    <h3 class="block-title">general</h3>
                    <div class="block-body">
                        <label class="field">
                            <span class="field-label">title <span class="req">*</span></span>
                            <input
                                v-model="form.title"
                                type="text"
                                class="input"
                                placeholder="System Status"
                                required
                                autocomplete="off"
                            >
                        </label>
                        <div class="field-row">
                            <label class="field flex-2">
                                <span class="field-label">URL slug <span class="req">*</span></span>
                                <span class="slug-input">
                                    <span class="slug-prefix">/status/</span>
                                    <input
                                        v-model="form.slug"
                                        type="text"
                                        class="input slug"
                                        placeholder="prod"
                                        required
                                        pattern="[a-z0-9][a-z0-9-]*"
                                        autocomplete="off"
                                        @input="onSlugInput"
                                    >
                                </span>
                                <span class="field-help">lowercase letters, numbers, dashes. visitors will reach the page at this URL.</span>
                            </label>
                            <div class="field flex-1">
                                <span class="field-label">visibility</span>
                                <div class="row-toggle">
                                    <span class="toggle-label-text">{{ form.public ? "public" : "private" }}</span>
                                    <button
                                        type="button"
                                        class="toggle"
                                        :class="{ on: form.public }"
                                        role="switch"
                                        :aria-checked="form.public ? 'true' : 'false'"
                                        @click="form.public = !form.public"
                                    >
                                        <span class="toggle-track"><span class="toggle-thumb"></span></span>
                                    </button>
                                </div>
                                <span class="field-help">private pages still resolve at the URL but require a logged-in admin.</span>
                            </div>
                        </div>
                        <label class="field">
                            <span class="field-label">footer text</span>
                            <input
                                v-model="form.footerText"
                                type="text"
                                class="input"
                                placeholder="e.g. &quot;powered by acme corp.&quot;"
                                autocomplete="off"
                            >
                        </label>
                        <label class="field">
                            <span class="field-label">icon URL</span>
                            <input
                                v-model="form.icon"
                                type="text"
                                class="input mono"
                                placeholder="/icon.svg or https://..."
                                autocomplete="off"
                            >
                            <span class="field-help">small image rendered next to the title on the public page.</span>
                        </label>
                    </div>
                </section>

                <!-- Monitor groups -->
                <section class="block">
                    <header class="block-head">
                        <h3 class="block-title-row">monitors</h3>
                        <button
                            type="button"
                            class="action ghost small"
                            @click="addGroup"
                        >
                            <font-awesome-icon icon="plus" />
                            <span>new group</span>
                        </button>
                    </header>
                    <div class="block-body groups-body">
                        <p v-if="form.groups.length === 0" class="block-empty">
                            No groups yet. Groups bundle related monitors so visitors can scan them together.
                        </p>

                        <div
                            v-for="(group, gIndex) in form.groups"
                            :key="group._key"
                            class="group-card"
                        >
                            <div class="group-card-head">
                                <input
                                    v-model="group.name"
                                    type="text"
                                    class="input group-name-input"
                                    placeholder="group name"
                                >
                                <div class="group-card-actions">
                                    <button
                                        type="button"
                                        class="row-btn"
                                        :disabled="gIndex === 0"
                                        title="Move up"
                                        @click="moveGroup(gIndex, -1)"
                                    >
                                        ↑
                                    </button>
                                    <button
                                        type="button"
                                        class="row-btn"
                                        :disabled="gIndex === form.groups.length - 1"
                                        title="Move down"
                                        @click="moveGroup(gIndex, 1)"
                                    >
                                        ↓
                                    </button>
                                    <button
                                        type="button"
                                        class="row-btn danger"
                                        title="Remove group"
                                        @click="removeGroup(gIndex)"
                                    >
                                        <font-awesome-icon icon="trash" />
                                    </button>
                                </div>
                            </div>

                            <div class="group-monitors">
                                <span
                                    v-for="m in group.monitors"
                                    :key="m.id"
                                    class="monitor-chip"
                                >
                                    <span class="monitor-chip-dot" :class="`tone-${chipStatus(m.id)}`"></span>
                                    <span class="monitor-chip-name">{{ m.name }}</span>
                                    <button
                                        type="button"
                                        class="monitor-chip-x"
                                        title="Remove from group"
                                        @click="removeMonitor(gIndex, m.id)"
                                    >×</button>
                                </span>
                                <select
                                    class="input monitor-select"
                                    :value="''"
                                    @change="addMonitor(gIndex, $event)"
                                >
                                    <option value="">+ add monitor…</option>
                                    <option
                                        v-for="m in unselectedMonitors(gIndex)"
                                        :key="m.id"
                                        :value="m.id"
                                    >
                                        {{ m.name }}
                                    </option>
                                </select>
                            </div>
                        </div>
                    </div>
                </section>

                <footer class="form-foot">
                    <span v-if="error" class="form-error">{{ error }}</span>
                    <span v-else-if="savedRecently" class="form-saved">saved</span>

                    <button
                        v-if="mode === 'edit'"
                        type="button"
                        class="action danger-outline"
                        :disabled="saving || deleteSaving"
                        @click="askDelete"
                    >
                        <font-awesome-icon icon="trash" />
                        <span>delete page</span>
                    </button>
                    <button
                        type="button"
                        class="action ghost"
                        :disabled="saving"
                        @click="onCancel"
                    >
                        cancel
                    </button>
                    <button
                        type="submit"
                        class="action primary"
                        :disabled="saving || !canSave"
                    >
                        <span v-if="!saving">{{ mode === "edit" ? "save changes" : "create page" }}</span>
                        <span v-else>saving…</span>
                    </button>
                </footer>
            </form>
        </main>

        <CommandPalette />

        <ConfirmV2
            :open="pendingDelete"
            tone="danger"
            title="delete status page"
            confirm-label="delete page"
            busy-label="deleting…"
            :busy="deleteSaving"
            @cancel="cancelDelete"
            @confirm="confirmDelete"
        >
            Permanently delete <strong>{{ form.title }}</strong>? Visitors hitting <code>/status/{{ form.slug }}</code> will see a 404. Monitors aren't affected.
        </ConfirmV2>
    </div>
</template>

<script>
import CommandPalette from "./CommandPalette.vue";
import ConfirmV2 from "./ConfirmV2.vue";
import LoaderBars from "./LoaderBars.vue";
import MenuTrigger from "./MenuTrigger.vue";

const STATUS_KEY_BY_NUM = {
    1: "up",
    0: "down",
    2: "pending",
    3: "maintenance",
};

let groupKeyCounter = 0;
/**
 *
 */
function nextGroupKey() {
    groupKeyCounter += 1;
    return `g_${groupKeyCounter}`;
}

export default {
    name: "StatusPageEditV2",
    components: { CommandPalette,
        ConfirmV2,
        LoaderBars,
        MenuTrigger },
    props: {
        slug: {
            type: String,
            default: null,
        },
    },
    data() {
        return {
            form: this.emptyForm(),
            originalSlug: null,
            loading: true,
            saving: false,
            error: null,
            savedRecently: false,
            savedTimer: null,
            pendingDelete: false,
            deleteSaving: false,
            slugTouched: false,
        };
    },
    computed: {
        mode() {
            return this.routeSlug ? "edit" : "create";
        },
        routeSlug() {
            return this.slug || this.$route.params.slug || null;
        },
        canSave() {
            return !!this.form.title?.trim() && /^[a-z0-9][a-z0-9-]*$/.test(this.form.slug || "");
        },
        availableMonitors() {
            const list = Object.values(this.$root.monitorList || {});
            return list.filter(m => m && m.type !== "group");
        },
    },
    watch: {
        routeSlug: {
            immediate: true,
            handler() {
                this.hydrate();
            },
        },
        "form.title"(v) {
            // Auto-suggest a slug from the title until the user manually
            // edits the slug field for the first time on a new page.
            if (this.mode === "create" && !this.slugTouched) {
                this.form.slug = (v || "")
                    .toLowerCase()
                    .replace(/[^a-z0-9-]+/g, "-")
                    .replace(/-{2,}/g, "-")
                    .replace(/^-+|-+$/g, "");
            }
        },
    },
    beforeUnmount() {
        clearTimeout(this.savedTimer);
    },
    methods: {
        emptyForm() {
            return {
                title: "",
                slug: "",
                public: true,
                icon: "/icon.svg",
                footerText: "",
                groups: [],
            };
        },
        async hydrate() {
            this.loading = true;
            this.error = null;
            this.slugTouched = this.mode === "edit";
            try {
                if (this.mode === "edit") {
                    const slug = this.routeSlug;
                    const { data } = await this.$root.api.get(`/status-page/${slug}`);
                    if (!data?.ok) {
                        this.error = "could not load status page";
                        return;
                    }
                    const cfg = data.config || {};
                    this.originalSlug = slug;
                    const groups = (data.publicGroupList || cfg.publicGroupList || [])
                        .map(g => ({
                            _key: nextGroupKey(),
                            name: g.name || "Main",
                            monitors: (g.monitorList || [])
                                .filter(m => m && m.id != null)
                                .map(m => ({ id: Number(m.id),
                                    name: m.name || `monitor #${m.id}` })),
                        }));
                    this.form = {
                        title: cfg.title || data.title || slug,
                        slug,
                        public: data.public !== false,
                        icon: cfg.icon || "/icon.svg",
                        footerText: cfg.footerText || cfg.footer || "",
                        groups,
                    };
                } else {
                    this.form = this.emptyForm();
                    this.form.groups = [
                        { _key: nextGroupKey(),
                            name: "Main",
                            monitors: [] },
                    ];
                    this.originalSlug = null;
                }
            } catch (e) {
                console.warn("hydrate failed", e);
                this.error = e?.response?.data?.detail || "could not load status page";
            } finally {
                this.loading = false;
            }
        },
        onSlugInput() {
            this.slugTouched = true;
        },
        addGroup() {
            this.form.groups.push({
                _key: nextGroupKey(),
                name: `Group ${this.form.groups.length + 1}`,
                monitors: [],
            });
        },
        removeGroup(index) {
            this.form.groups.splice(index, 1);
        },
        moveGroup(index, delta) {
            const next = index + delta;
            if (next < 0 || next >= this.form.groups.length) {
                return;
            }
            const arr = this.form.groups;
            [ arr[index], arr[next] ] = [ arr[next], arr[index] ];
        },
        addMonitor(groupIndex, e) {
            const id = Number(e.target?.value);
            if (!Number.isFinite(id)) {
                return;
            }
            const monitor = this.availableMonitors.find(m => m.id === id);
            if (!monitor) {
                return;
            }
            this.form.groups[groupIndex].monitors.push({
                id: monitor.id,
                name: monitor.name,
            });
            // Reset the select.
            if (e.target) {
                e.target.value = "";
            }
        },
        removeMonitor(groupIndex, monitorId) {
            const group = this.form.groups[groupIndex];
            group.monitors = group.monitors.filter(m => m.id !== monitorId);
        },
        unselectedMonitors(groupIndex) {
            // Allow a monitor to appear in multiple groups (matches v1 behavior),
            // but exclude monitors already in *this* group from its own picker.
            const inThisGroup = new Set((this.form.groups[groupIndex]?.monitors || []).map(m => m.id));
            return this.availableMonitors
                .filter(m => !inThisGroup.has(m.id))
                .sort((a, b) => (a.name || "").localeCompare(b.name || ""));
        },
        chipStatus(monitorId) {
            const last = this.$root.lastHeartbeatList?.[monitorId];
            if (!last) {
                return "unknown";
            }
            return STATUS_KEY_BY_NUM[last.status] || "unknown";
        },
        buildPayload() {
            const f = this.form;
            const cfg = {
                title: f.title.trim(),
                slug: f.slug.trim(),
                icon: f.icon || "/icon.svg",
                footerText: f.footerText || "",
                publicGroupList: f.groups.map(g => ({
                    name: g.name?.trim() || "Main",
                    monitorList: g.monitors.map(m => ({ id: m.id,
                        name: m.name })),
                })),
            };
            return {
                title: f.title.trim(),
                public: !!f.public,
                config: cfg,
            };
        },
        async onSave() {
            if (!this.canSave || this.saving) {
                return;
            }
            this.saving = true;
            this.error = null;
            this.savedRecently = false;
            try {
                const payload = this.buildPayload();
                if (this.mode === "create") {
                    // POST /status-page expects { title, slug, config, public, monitors }
                    const { data } = await this.$root.api.post("/status-page", {
                        title: payload.title,
                        slug: this.form.slug.trim(),
                        public: payload.public,
                        config: payload.config,
                        monitors: payload.config.publicGroupList,
                    });
                    if (data?.ok === false) {
                        this.error = data?.msg || "could not create status page";
                        return;
                    }
                    this.$router.push(`/status-pages/${this.form.slug}/edit`);
                } else {
                    // POST /status-page/{slug} updates by current slug; the
                    // server reads cfg.slug to perform a rename if it changed.
                    const targetSlug = this.originalSlug || this.routeSlug;
                    const { data } = await this.$root.api.post(
                        `/status-page/${targetSlug}`,
                        payload,
                    );
                    if (data?.ok === false) {
                        this.error = data?.msg || "could not save changes";
                        return;
                    }
                    const newSlug = data?.slug || this.form.slug.trim();
                    if (newSlug !== this.originalSlug) {
                        // Slug changed — route to the new edit URL so the
                        // browser bar reflects reality.
                        this.$router.replace(`/status-pages/${newSlug}/edit`);
                        this.originalSlug = newSlug;
                    } else {
                        this.savedRecently = true;
                        clearTimeout(this.savedTimer);
                        this.savedTimer = setTimeout(() => {
                            this.savedRecently = false;
                        }, 2400);
                    }
                }
            } catch (e) {
                this.error = e?.response?.data?.detail || e?.message || "request failed";
            } finally {
                this.saving = false;
            }
        },
        onCancel() {
            this.$router.push("/status-pages");
        },
        askDelete() {
            this.pendingDelete = true;
        },
        cancelDelete() {
            if (this.deleteSaving) {
                return;
            }
            this.pendingDelete = false;
        },
        async confirmDelete() {
            const slug = this.originalSlug || this.routeSlug;
            if (!slug) {
                return;
            }
            this.deleteSaving = true;
            try {
                await this.$root.api.delete(`/status-page/${slug}`);
                this.$router.push("/status-pages");
            } catch (e) {
                this.error = e?.response?.data?.detail || e?.message || "could not delete";
                this.deleteSaving = false;
                this.pendingDelete = false;
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.v2-status-edit {
    @include v2-surface-tokens;
    @include v2-shell-base;

    background: var(--bg);
    padding: 0 32px 64px;
    animation: v2-fade-in 280ms var(--enter-ease) both;
}

.topbar {
    @include v2-sticky-topbar(16px);
}

.back {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: var(--text-muted);
    text-decoration: none;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 6px 10px;
    border-radius: 8px;
    border: 1px solid transparent;
    transition: color 140ms ease, background 140ms ease, border-color 140ms ease;

    &:hover {
        color: var(--text);
        background: var(--bg-soft);
        border-color: var(--border);
    }

    .back-arrow { transition: transform 200ms $v2-ease; }
    &:hover .back-arrow { transform: translateX(-3px); }
}

.topbar-title {
    justify-self: center;
    margin: 0;
    font-size: 14px;
    font-weight: 500;
    text-transform: lowercase;
    letter-spacing: 0.02em;
    color: var(--text);
}

.topbar-right {
    display: inline-flex;
    align-items: center;
    gap: 8px;
}

.main {
    max-width: 920px;
    margin: 24px auto 0;
    animation: v2-up 320ms var(--enter-ease) both;
    animation-delay: 60ms;
}

.page-loading {
    display: flex;
    justify-content: center;
    padding: 80px 0;
}

.form {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.block {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
}

.block-title,
.block-title-row {
    margin: 0;
    padding: 14px 18px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-faint);
    font-weight: 600;
    border-bottom: 1px solid var(--border);
}

.block-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);

    .block-title-row {
        border-bottom: none;
        padding-bottom: 14px;
    }
}

.block-body {
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 14px;
}

.block-empty {
    margin: 0;
    color: var(--text-muted);
    font-size: 13px;
    line-height: 1.55;
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

.field-row {
    display: flex;
    gap: 12px;
    align-items: stretch;

    .field { flex: 1; }
    .flex-1 { flex: 1; }
    .flex-2 { flex: 2; }
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

.slug-input {
    display: flex;
    align-items: stretch;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
    transition: border-color 140ms ease, box-shadow 140ms ease, background 140ms ease;

    &:focus-within {
        background: var(--bg-hover);
        border-color: hsl(142 71% 45%);
        box-shadow: 0 0 0 3px hsl(142 71% 45% / 0.15);
    }

    .slug-prefix {
        padding: 10px 0 10px 12px;
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 13px;
        color: var(--text-faint);
    }

    .slug {
        background: transparent;
        border: none;
        padding-left: 0;
        flex: 1;
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 13px;

        &:focus {
            background: transparent;
            border: none;
            box-shadow: none;
        }
    }
}

.row-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 12px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;

    .toggle-label-text {
        font-size: 12.5px;
        color: var(--text);
    }
}

.toggle {
    appearance: none;
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0;

    .toggle-track {
        position: relative;
        width: 38px;
        height: 22px;
        background: var(--control);
        border: 1px solid var(--border);
        border-radius: 999px;
        transition: background 160ms ease, border-color 160ms ease;
        display: inline-block;
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

    &.on .toggle-track {
        background: hsl(142 71% 45% / 0.22);
        border-color: hsl(142 71% 45% / 0.5);
    }

    &.on .toggle-thumb {
        transform: translateX(16px);
        background: hsl(142 71% 60%);
    }
}

.groups-body {
    gap: 16px;
}

.group-card {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.group-card-head {
    display: flex;
    align-items: center;
    gap: 8px;
}

.group-name-input {
    flex: 1;
    background: var(--bg-soft);
}

.group-card-actions {
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.row-btn {
    appearance: none;
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-muted);
    width: 32px;
    height: 32px;
    border-radius: 7px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease;

    &:hover:not(:disabled) {
        background: var(--bg-hover);
        color: var(--text);
        border-color: var(--border-strong);
    }

    &:disabled { opacity: 0.4; cursor: not-allowed; }

    &.danger:hover:not(:disabled) {
        background: hsl(0 84% 60% / 0.12);
        color: hsl(0 84% 70%);
        border-color: hsl(0 84% 60% / 0.4);
    }
}

.group-monitors {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.monitor-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 4px 4px 10px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 999px;
    font-size: 12px;
    color: var(--text);

    .monitor-chip-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: var(--text-faint);

        &.tone-up { background: hsl(142 71% 45%); }
        &.tone-down { background: hsl(0 84% 60%); }
        &.tone-pending { background: hsl(38 92% 55%); }
        &.tone-maintenance { background: hsl(217 91% 60%); }
    }

    .monitor-chip-x {
        appearance: none;
        background: transparent;
        border: none;
        color: var(--text-faint);
        font-size: 14px;
        line-height: 1;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        cursor: pointer;

        &:hover {
            background: var(--bg-hover);
            color: var(--text);
        }
    }
}

.monitor-select {
    background: var(--bg-soft);
    font-size: 12px;
    padding: 5px 10px;
    border-radius: 999px;
    color: var(--text-muted);
    border: 1px dashed var(--border-strong);
    cursor: pointer;
    min-width: 160px;

    &:hover {
        background: var(--bg-hover);
        color: var(--text);
        border-style: solid;
    }
}

.form-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 4px;

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

    &.small { padding: 6px 12px; font-size: 11px; }

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

@media (max-width: 760px) {
    .v2-status-edit { padding: 0 16px 40px; }

    .field-row { flex-direction: column; }

    .form-foot {
        flex-wrap: wrap;
        justify-content: stretch;

        .form-error,
        .form-saved {
            flex-basis: 100%;
        }
    }
}
</style>
