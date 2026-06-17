<template>
    <Teleport to="body">
        <transition name="confirm">
            <div v-if="open" class="confirm-overlay" @click.self="cancel">
                <div
                    ref="dialog"
                    class="confirm-dialog"
                    role="dialog"
                    aria-modal="true"
                    tabindex="-1"
                    @keydown.tab="onTab"
                >
                    <h3 class="confirm-title">{{ title }}</h3>
                    <div class="confirm-body">
                        <slot>{{ body }}</slot>
                    </div>
                    <div class="confirm-actions">
                        <button
                            ref="cancelBtn"
                            type="button"
                            class="action ghost"
                            :disabled="busy"
                            @click="cancel"
                        >
                            {{ cancelLabel }}
                        </button>
                        <button
                            ref="confirmBtn"
                            type="button"
                            class="action"
                            :class="tone === 'danger' ? 'danger-solid' : 'primary'"
                            :disabled="busy"
                            @click="confirm"
                        >
                            <span v-if="!busy">{{ confirmLabel }}</span>
                            <span v-else>{{ busyLabel }}</span>
                        </button>
                    </div>
                </div>
            </div>
        </transition>
    </Teleport>
</template>

<script>
export default {
    name: "ConfirmV2",
    props: {
        open: { type: Boolean,
            default: false },
        title: { type: String,
            default: "Confirm" },
        body: { type: String,
            default: "" },
        confirmLabel: { type: String,
            default: "confirm" },
        busyLabel: { type: String,
            default: "working…" },
        cancelLabel: { type: String,
            default: "cancel" },
        // "danger" tints the confirm button red, anything else uses the
        // accent green. Pick "danger" for destructive irreversible
        // actions (delete, revoke, disable auth).
        tone: { type: String,
            default: "primary",
            validator: (v) => [ "primary", "danger" ].includes(v) },
        busy: { type: Boolean,
            default: false },
    },
    emits: [ "cancel", "confirm" ],
    data() {
        return {
            // Element to return focus to once the dialog closes — captured
            // at the moment of opening so it survives reactive re-renders.
            previouslyFocused: null,
        };
    },
    watch: {
        open: {
            immediate: true,
            handler(isOpen, wasOpen) {
                if (isOpen) {
                    this.attachKeydown();
                    this.previouslyFocused = (typeof document !== "undefined") ? document.activeElement : null;
                    // Wait for the teleported dialog to render before
                    // moving focus into it.
                    this.$nextTick(() => this.focusInitial());
                } else if (wasOpen) {
                    this.detachKeydown();
                    this.restoreFocus();
                }
            },
        },
    },
    beforeUnmount() {
        // If the parent unmounts while we're open (route change, etc.)
        // we still need to drop the document-level listener.
        this.detachKeydown();
    },
    methods: {
        cancel() {
            if (this.busy) {
                return;
            }
            this.$emit("cancel");
        },
        confirm() {
            if (this.busy) {
                return;
            }
            this.$emit("confirm");
        },
        onKeydown(e) {
            if (!this.open) {
                return;
            }
            if (e.key === "Escape") {
                e.preventDefault();
                e.stopPropagation();
                this.cancel();
            }
        },
        attachKeydown() {
            if (typeof document === "undefined") {
                return;
            }
            // Document-level so the listener fires regardless of which
            // element inside the dialog has focus, including the case
            // where focus drifted to the body via Teleport mounting.
            document.addEventListener("keydown", this.onKeydown, true);
        },
        detachKeydown() {
            if (typeof document === "undefined") {
                return;
            }
            document.removeEventListener("keydown", this.onKeydown, true);
        },
        focusInitial() {
            // Default to the cancel button so a stray Enter doesn't
            // immediately confirm a destructive action. Callers wanting
            // an embedded input slot (e.g. password challenge) provide
            // their own input, which Tab will reach next.
            const target = this.$refs.cancelBtn || this.$refs.dialog;
            if (target && typeof target.focus === "function") {
                target.focus();
            }
        },
        restoreFocus() {
            const el = this.previouslyFocused;
            this.previouslyFocused = null;
            if (el && typeof el.focus === "function" && document.body.contains(el)) {
                // Defer one tick so any v-if cleanup on the trigger
                // (e.g. inline form being torn down) doesn't race with
                // the focus call.
                this.$nextTick(() => el.focus());
            }
        },
        onTab(e) {
            // Trap Tab/Shift-Tab inside the dialog so focus can't fall
            // back into the page behind the modal. With only two
            // buttons + an optional slot input there's no real perf
            // concern; we just enumerate every tabbable child.
            const dialog = this.$refs.dialog;
            if (!dialog) {
                return;
            }
            const tabbables = dialog.querySelectorAll(
                "a[href], area[href], input:not([disabled]):not([type='hidden']), select:not([disabled]), textarea:not([disabled]), button:not([disabled]), [tabindex]:not([tabindex='-1'])"
            );
            if (tabbables.length === 0) {
                return;
            }
            const first = tabbables[0];
            const last = tabbables[tabbables.length - 1];
            const active = document.activeElement;
            if (e.shiftKey && active === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && active === last) {
                e.preventDefault();
                first.focus();
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.confirm-overlay {
    position: fixed;
    inset: 0;
    background: hsl(0 0% 0% / 0.55);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    padding: 24px;
    @include v2-surface-tokens;
}

.confirm-dialog {
    background: var(--bg-soft);
    border: 1px solid var(--border-strong);
    border-radius: 14px;
    padding: 24px;
    max-width: 440px;
    width: 100%;
    box-shadow: 0 24px 60px hsl(0 0% 0% / 0.5);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen,
        Ubuntu, Cantarell, "Helvetica Neue", sans-serif;
    letter-spacing: -0.005em;

    .confirm-title {
        margin: 0 0 8px;
        font-size: 16px;
        font-weight: 600;
    }

    .confirm-body {
        margin: 0 0 18px;
        color: var(--text-muted);
        font-size: 14px;
        line-height: 1.5;

        :deep(strong) { color: var(--text); }
        :deep(code) {
            font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
                Monaco, Consolas, monospace;
            font-size: 12.5px;
            padding: 1px 5px;
            background: var(--bg-soft);
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text);
        }
    }

    .confirm-actions {
        display: flex;
        justify-content: flex-end;
        gap: 8px;
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
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-family: inherit;
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

    &.danger-solid {
        background: hsl(0 84% 60% / 0.2);
        border-color: hsl(0 84% 60% / 0.55);
        color: hsl(0 84% 75%);

        &:hover:not(:disabled) {
            background: hsl(0 84% 60% / 0.3);
            border-color: hsl(0 84% 60% / 0.8);
            color: hsl(0 84% 85%);
            transform: translateY(-1px);
        }
    }
}

.confirm-enter-active,
.confirm-leave-active {
    transition: opacity 160ms $v2-ease;

    .confirm-dialog {
        transition: opacity 200ms $v2-ease, transform 200ms $v2-ease;
    }
}

.confirm-enter-from,
.confirm-leave-to {
    opacity: 0;

    .confirm-dialog {
        opacity: 0;
        transform: translateY(-8px) scale(0.97);
    }
}

@media (prefers-reduced-motion: reduce) {
    .confirm-enter-active,
    .confirm-leave-active {
        transition: none;

        .confirm-dialog {
            transition: none;
        }
    }

    .confirm-enter-from,
    .confirm-leave-to .confirm-dialog {
        transform: none;
    }
}
</style>
