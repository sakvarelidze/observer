<!-- eslint-disable vue/no-mutating-props -->
<template>
    <form
        class="channel-form"
        :class="mode"
        @submit.prevent="$emit('submit')"
        @keydown.esc.prevent.stop="onEsc"
    >
        <div class="channel-form-body">
            <div class="form-row">
                <label class="field flex-1">
                    <span class="field-label">type</span>
                    <select v-model="draft.type" class="input" @change="onTypeChange">
                        <option v-for="p in providerCatalog" :key="p.type" :value="p.type">{{ p.label }}</option>
                    </select>
                </label>
                <label class="field flex-2">
                    <span class="field-label">name</span>
                    <input
                        v-model="draft.name"
                        type="text"
                        class="input"
                        placeholder="e.g. team-alerts"
                        required
                        autocomplete="off"
                    >
                </label>
            </div>

            <label v-for="f in currentFields" :key="f.key" class="field">
                <span class="field-label">
                    {{ f.label }}<span v-if="f.required" class="req">*</span>
                </span>
                <input
                    v-model="draft.fields[f.key]"
                    :type="f.secret ? 'password' : 'text'"
                    class="input"
                    :placeholder="f.placeholder || ''"
                    :required="f.required"
                    autocomplete="off"
                >
            </label>

            <div class="toggle-row">
                <button
                    type="button"
                    class="form-toggle"
                    :class="{ on: draft.active }"
                    role="switch"
                    :aria-checked="draft.active ? 'true' : 'false'"
                    @click="draft.active = !draft.active"
                >
                    <span class="toggle-track"><span class="toggle-thumb"></span></span>
                    <span class="toggle-label">{{ draft.active ? "active" : "disabled" }}</span>
                </button>
                <button
                    type="button"
                    class="form-toggle"
                    :class="{ on: draft.isDefault }"
                    role="switch"
                    :aria-checked="draft.isDefault ? 'true' : 'false'"
                    @click="draft.isDefault = !draft.isDefault"
                >
                    <span class="toggle-track"><span class="toggle-thumb"></span></span>
                    <span class="toggle-label">default</span>
                </button>
                <span class="toggle-help">a "default" channel is auto-attached to new monitors that don't pick any.</span>
            </div>
        </div>

        <div class="channel-form-foot">
            <span v-if="error" class="form-error">{{ error }}</span>
            <button
                type="button"
                class="action ghost"
                :disabled="!canTest"
                @click="$emit('test')"
            >
                <font-awesome-icon :icon="testing ? 'spinner' : 'bullhorn'" :spin="testing" />
                <span v-if="!testing">test</span>
                <span v-else>sending…</span>
            </button>
            <button
                type="button"
                class="action ghost"
                :disabled="saving"
                @click="$emit('cancel')"
            >
                cancel
            </button>
            <button type="submit" class="action primary" :disabled="!canSubmit">
                <span v-if="!saving">{{ mode === "edit" ? "save" : "create" }}</span>
                <span v-else>saving…</span>
            </button>
        </div>
    </form>
</template>

<script>
export default {
    name: "ChannelForm",
    props: {
        mode: { type: String,
            required: true },
        draft: { type: Object,
            required: true },
        providerCatalog: { type: Array,
            required: true },
        saving: { type: Boolean,
            default: false },
        testing: { type: Boolean,
            default: false },
        error: { type: String,
            default: null },
    },
    emits: [ "cancel", "submit", "test" ],
    computed: {
        currentFields() {
            const provider = this.providerCatalog.find(p => p.type === this.draft.type);
            return provider?.fields || [];
        },
        canSubmit() {
            if (this.saving || !this.draft.name?.trim() || !this.draft.type) {
                return false;
            }
            return this.currentFields.every(f => {
                if (!f.required) {
                    return true;
                }
                const val = this.draft.fields?.[f.key];
                return typeof val === "string" && val.trim();
            });
        },
        canTest() {
            return !this.testing && this.canSubmit;
        },
    },
    methods: {
        onTypeChange() {
            // Clear provider-specific fields when type changes so the
            // user doesn't accidentally submit fields from another type.
            // eslint-disable-next-line vue/no-mutating-props
            this.draft.fields = {};
        },
        onEsc() {
            // Mirror the cancel button — same disabled-while-saving check.
            if (this.saving) {
                return;
            }
            this.$emit("cancel");
        },
    },
};
</script>

<style lang="scss" scoped>
@import "../_base.scss";

.channel-form {
    display: flex;
    flex-direction: column;
    background: hsl(217 91% 60% / 0.04);
    border-radius: 10px;
    border: 1px solid hsl(217 91% 60% / 0.35);

    &.create {
        margin-bottom: 6px;
    }
}

.channel-form-body {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
}

.form-row {
    display: flex;
    gap: 12px;

    .field { flex: 1; }
    .flex-1 { flex: 1; }
    .flex-2 { flex: 2; }
}

.field {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.field-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);

    .req { color: hsl(0 84% 60%); margin-left: 2px; }
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

.toggle-row {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

.form-toggle {
    appearance: none;
    background: transparent;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 8px;
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

.toggle-help {
    flex-basis: 100%;
    font-size: 11px;
    color: var(--text-faint);
    line-height: 1.5;
}

.channel-form-foot {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 8px;
    padding: 10px 14px;
    border-top: 1px solid var(--border);
    background: hsl(0 0% 6%);
    border-radius: 0 0 10px 10px;

    .form-error {
        flex: 1;
        text-align: left;
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
}
</style>
