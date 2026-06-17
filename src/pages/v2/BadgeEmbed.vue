<template>
    <Teleport to="body">
        <transition name="badge-modal">
            <div v-if="open" class="badge-overlay" @click.self="$emit('close')">
                <div
                    class="badge-dialog"
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="badge-title"
                    @keydown.escape.stop="$emit('close')"
                >
                    <header class="badge-head">
                        <div class="badge-titles">
                            <h3 id="badge-title" class="badge-title">Embed badge</h3>
                            <p class="badge-sub">paste this in a README or status page — the badge re-fetches uptime each time it loads.</p>
                        </div>
                        <button
                            type="button"
                            class="badge-close"
                            aria-label="Close"
                            @click="$emit('close')"
                        >×</button>
                    </header>

                    <div class="badge-periods" role="tablist">
                        <button
                            v-for="p in periods"
                            :key="p"
                            type="button"
                            class="badge-period"
                            :class="{ active: period === p }"
                            role="tab"
                            :aria-selected="period === p"
                            @click="period = p"
                        >{{ p }}</button>
                    </div>

                    <div class="badge-preview">
                        <img :src="badgeUrl" :alt="`observer uptime ${period}`">
                    </div>

                    <div class="snippets">
                        <label class="snippet">
                            <span class="snippet-label">URL</span>
                            <span class="snippet-row">
                                <input ref="urlInput" type="text" class="snippet-input" :value="badgeUrl" readonly>
                                <button type="button" class="copy-btn" @click="copy('url')">
                                    {{ copied === 'url' ? 'copied' : 'copy' }}
                                </button>
                            </span>
                        </label>
                        <label class="snippet">
                            <span class="snippet-label">Markdown</span>
                            <span class="snippet-row">
                                <input type="text" class="snippet-input" :value="markdown" readonly>
                                <button type="button" class="copy-btn" @click="copy('md')">
                                    {{ copied === 'md' ? 'copied' : 'copy' }}
                                </button>
                            </span>
                        </label>
                        <label class="snippet">
                            <span class="snippet-label">HTML</span>
                            <span class="snippet-row">
                                <input type="text" class="snippet-input" :value="html" readonly>
                                <button type="button" class="copy-btn" @click="copy('html')">
                                    {{ copied === 'html' ? 'copied' : 'copy' }}
                                </button>
                            </span>
                        </label>
                    </div>
                </div>
            </div>
        </transition>
    </Teleport>
</template>

<script>
export default {
    name: "BadgeEmbed",
    props: {
        open: { type: Boolean,
            default: false },
        monitorId: { type: Number,
            required: true },
    },
    emits: [ "close" ],
    data() {
        return {
            period: "24h",
            periods: [ "24h", "7d", "30d", "90d" ],
            copied: null,
            copiedTimer: null,
        };
    },
    computed: {
        baseUrl() {
            try {
                const u = new URL(window.location.href);
                if (u.port === "3000") {
                    u.port = "3001";
                }
                return `${u.protocol}//${u.host}`;
            } catch (e) {
                return "";
            }
        },
        badgeUrl() {
            return `${this.baseUrl}/api/badges/${this.monitorId}.svg?period=${this.period}`;
        },
        markdown() {
            return `![observer-uptime](${this.badgeUrl})`;
        },
        html() {
            return `<img src="${this.badgeUrl}" alt="observer-uptime">`;
        },
    },
    watch: {
        open(isOpen) {
            // Window-level ESC fallback so the dialog can close from
            // anywhere even when focus is in an input. Bound while open
            // and cleaned up on close, so we don't accumulate listeners.
            if (isOpen) {
                window.addEventListener("keydown", this.onKey);
            } else {
                window.removeEventListener("keydown", this.onKey);
            }
        },
    },
    beforeUnmount() {
        clearTimeout(this.copiedTimer);
        window.removeEventListener("keydown", this.onKey);
    },
    methods: {
        onKey(e) {
            if (e.key === "Escape") {
                this.$emit("close");
            }
        },
        async copy(kind) {
            const text = kind === "url" ? this.badgeUrl
                : kind === "md" ? this.markdown
                    : this.html;
            try {
                await navigator.clipboard.writeText(text);
            } catch (e) {
                if (this.$refs.urlInput) {
                    this.$refs.urlInput.select();
                }
            }
            this.copied = kind;
            clearTimeout(this.copiedTimer);
            this.copiedTimer = setTimeout(() => {
                this.copied = null;
            }, 1400);
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.badge-overlay {
    @include v2-surface-tokens;

    position: fixed;
    inset: 0;
    z-index: 80;
    background: hsl(0 0% 0% / 0.55);
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
}

.badge-dialog {
    width: 100%;
    max-width: 540px;
    background: var(--bg-soft);
    border: 1px solid var(--border-strong);
    border-radius: 14px;
    padding: 22px 22px 20px;
    box-shadow: 0 24px 60px hsl(0 0% 0% / 0.5);
    color: var(--text);
    max-height: calc(100vh - 48px);
    overflow-y: auto;
}

.badge-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
    margin-bottom: 14px;
}

.badge-titles {
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
}

.badge-title {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
}

.badge-sub {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.45;
}

.badge-close {
    appearance: none;
    background: transparent;
    border: none;
    color: var(--text-faint);
    font-size: 20px;
    line-height: 1;
    width: 28px;
    height: 28px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 120ms ease, color 120ms ease;
    flex: none;

    &:hover {
        color: var(--text);
        background: var(--bg-hover);
    }
}

.badge-periods {
    display: inline-flex;
    gap: 2px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 2px;
    margin-bottom: 12px;
}

.badge-period {
    appearance: none;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-family: inherit;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 4px 10px;
    border-radius: 6px;
    cursor: pointer;
    transition: background 120ms ease, color 120ms ease;

    &:hover { color: var(--text); }
    &.active {
        background: hsl(142 71% 45% / 0.16);
        color: hsl(142 71% 70%);
    }
}

.badge-preview {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 14px;
    min-height: 60px;

    img {
        height: 20px;
    }
}

.snippets {
    display: flex;
    flex-direction: column;
    gap: 10px;
}

.snippet {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.snippet-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-faint);
}

.snippet-row {
    display: flex;
    gap: 6px;
}

.snippet-input {
    appearance: none;
    flex: 1;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 10px;
    color: var(--text);
    font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo, monospace;
    font-size: 11px;
    box-sizing: border-box;

    &:focus {
        outline: none;
        border-color: hsl(142 71% 45% / 0.6);
    }
}

.copy-btn {
    appearance: none;
    background: hsl(142 71% 45% / 0.14);
    border: 1px solid hsl(142 71% 45% / 0.45);
    color: hsl(142 71% 70%);
    font-family: inherit;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 7px 12px;
    border-radius: 8px;
    cursor: pointer;
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease;
    flex: none;

    &:hover {
        background: hsl(142 71% 45% / 0.22);
        border-color: hsl(142 71% 45% / 0.7);
        color: hsl(142 71% 80%);
    }
}

.badge-modal-enter-active,
.badge-modal-leave-active {
    transition: opacity 180ms $v2-ease;

    .badge-dialog {
        transition: opacity 200ms $v2-ease, transform 200ms $v2-ease;
    }
}

.badge-modal-enter-from,
.badge-modal-leave-to {
    opacity: 0;

    .badge-dialog {
        opacity: 0;
        transform: translateY(8px) scale(0.98);
    }
}

@media (prefers-reduced-motion: reduce) {
    .badge-modal-enter-active,
    .badge-modal-leave-active {
        transition: none;

        .badge-dialog {
            transition: none;
            transform: none;
        }
    }
}
</style>
