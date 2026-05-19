<template>
    <div class="settings-page">
        <header class="page-head">
            <h2 class="page-title">About</h2>
            <p class="page-sub">version info, update preferences, links.</p>
        </header>

        <div v-if="loading" class="page-loading">
            <LoaderBars size="md" />
        </div>

        <template v-else>
            <section class="block">
                <h3 class="block-title">version</h3>
                <div class="block-body">
                    <div class="version-grid">
                        <span class="version-label">backend</span>
                        <code class="version-value">{{ backendVersion || "—" }}</code>

                        <span class="version-label">frontend</span>
                        <code class="version-value">{{ frontendVersion || "—" }}</code>

                        <span v-if="versionMismatch" class="version-warn">
                            <font-awesome-icon icon="exclamation-circle" />
                            <span>frontend and backend versions don't match — you may need to hard-refresh your browser to pick up the latest UI build.</span>
                        </span>
                    </div>
                </div>
            </section>

            <section class="block">
                <h3 class="block-title">update notifications</h3>
                <div class="block-body settings-rows">
                    <div class="row-toggle">
                        <div class="toggle-text">
                            <span class="field-label">check for updates</span>
                            <span class="field-help">poll the upstream releases page periodically and show a banner when a newer version is available.</span>
                        </div>
                        <button
                            type="button"
                            class="toggle"
                            :class="{ on: !!settings.checkUpdate }"
                            role="switch"
                            :aria-checked="settings.checkUpdate ? 'true' : 'false'"
                            @click="toggle('checkUpdate')"
                        >
                            <span class="toggle-track"><span class="toggle-thumb"></span></span>
                            <span class="toggle-label">{{ settings.checkUpdate ? "on" : "off" }}</span>
                        </button>
                    </div>
                    <div class="row-toggle" :class="{ 'is-disabled': !settings.checkUpdate }">
                        <div class="toggle-text">
                            <span class="field-label">include beta releases</span>
                            <span class="field-help">flag pre-release builds in the same banner. only meaningful when "check for updates" is on.</span>
                        </div>
                        <button
                            type="button"
                            class="toggle"
                            :class="{ on: !!settings.checkBeta && !!settings.checkUpdate }"
                            role="switch"
                            :aria-checked="settings.checkBeta ? 'true' : 'false'"
                            :disabled="!settings.checkUpdate"
                            @click="toggle('checkBeta')"
                        >
                            <span class="toggle-track"><span class="toggle-thumb"></span></span>
                            <span class="toggle-label">{{ settings.checkBeta ? "on" : "off" }}</span>
                        </button>
                    </div>
                    <span v-if="error" class="form-error">{{ error }}</span>
                    <span v-else-if="savedRecently" class="form-saved">saved</span>
                </div>
            </section>

            <section class="block">
                <h3 class="block-title">links</h3>
                <div class="block-body links-list">
                    <a
                        v-for="link in links"
                        :key="link.href"
                        :href="link.href"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="link-row"
                    >
                        <span class="link-icon">
                            <font-awesome-icon :icon="link.icon" />
                        </span>
                        <span class="link-body">
                            <span class="link-label">{{ link.label }}</span>
                            <span class="link-help">{{ link.help }}</span>
                        </span>
                        <span class="link-arrow">↗</span>
                    </a>
                </div>
            </section>
        </template>
    </div>
</template>

<script>
import LoaderBars from "../LoaderBars.vue";

export default {
    name: "SettingsAbout",
    components: { LoaderBars },
    data() {
        return {
            settings: { checkUpdate: false,
                checkBeta: false },
            loading: true,
            error: null,
            savedRecently: false,
            savedTimer: null,
            links: [
                {
                    label: "Source code",
                    help: "this fork on GitHub.",
                    href: "https://github.com/sakvarelidze/observer",
                    icon: "external-link-square-alt",
                },
                {
                    label: "Report an issue",
                    help: "bugs, feature requests, paper cuts.",
                    href: "https://github.com/sakvarelidze/observer/issues",
                    icon: "exclamation-circle",
                },
                {
                    label: "Releases",
                    help: "changelog and release notes.",
                    href: "https://github.com/sakvarelidze/observer/releases",
                    icon: "arrow-alt-circle-up",
                },
            ],
        };
    },
    computed: {
        backendVersion() {
            return this.$root.info?.version || "";
        },
        frontendVersion() {
            return this.$root.frontendVersion || "";
        },
        versionMismatch() {
            // Both available, both non-empty, and mismatched.
            const back = this.backendVersion;
            const front = this.frontendVersion;
            if (!back || !front) {
                return false;
            }
            if (this.$root.isFrontendBackendVersionMatched === false) {
                return true;
            }
            return back !== front;
        },
    },
    mounted() {
        this.fetchSettings();
    },
    beforeUnmount() {
        clearTimeout(this.savedTimer);
    },
    methods: {
        async fetchSettings() {
            this.loading = true;
            this.error = null;
            try {
                const { data } = await this.$root.api.get("/settings");
                const incoming = data?.data || {};
                this.settings = {
                    checkUpdate: !!incoming.checkUpdate,
                    checkBeta: !!incoming.checkBeta,
                };
            } catch (e) {
                this.error = e?.response?.data?.detail || e?.message || "could not load settings";
            } finally {
                this.loading = false;
            }
        },
        async toggle(key) {
            const next = !this.settings[key];
            const original = this.settings[key];
            // Optimistic flip — roll back on save failure.
            this.settings[key] = next;
            // If turning off checkUpdate, also turn off checkBeta server-side
            // so we don't leave a meaningless setting set.
            const payloadSettings = { ...this.settings };
            if (!payloadSettings.checkUpdate) {
                payloadSettings.checkBeta = false;
                this.settings.checkBeta = false;
            }
            await this.persist(payloadSettings, () => {
                this.settings[key] = original;
            });
        },
        async persist(settings, onError) {
            this.error = null;
            this.savedRecently = false;
            try {
                await this.$root.api.post("/settings", { settings });
                this.savedRecently = true;
                clearTimeout(this.savedTimer);
                this.savedTimer = setTimeout(() => {
                    this.savedRecently = false;
                }, 2000);
            } catch (e) {
                this.error = e?.response?.data?.detail || e?.message || "could not save";
                if (onError) {
                    onError();
                }
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
    flex-direction: column;
    gap: 4px;

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
    }
}

.page-loading {
    display: flex;
    justify-content: center;
    padding: 40px 0;
}

.block {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 14px;
    overflow: hidden;
}

.block-title {
    margin: 0;
    padding: 14px 18px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-faint);
    font-weight: 600;
    border-bottom: 1px solid var(--border);
}

.block-body {
    padding: 18px;
}

.settings-rows {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.version-grid {
    display: grid;
    grid-template-columns: 100px 1fr;
    column-gap: 16px;
    row-gap: 8px;
    align-items: center;
}

.version-label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-faint);
}

.version-value {
    font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
        Monaco, Consolas, monospace;
    font-size: 13px;
    color: var(--text);
}

.version-warn {
    grid-column: 1 / -1;
    display: flex;
    align-items: flex-start;
    gap: 8px;
    margin-top: 4px;
    padding: 10px 12px;
    background: hsl(38 92% 50% / 0.08);
    border: 1px solid hsl(38 92% 50% / 0.4);
    border-radius: 8px;
    color: hsl(38 92% 70%);
    font-size: 12.5px;
    line-height: 1.5;
}

.row-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 12px 14px;
    background: hsl(0 0% 6%);
    border: 1px solid var(--border);
    border-radius: 10px;

    .toggle-text {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    &.is-disabled {
        opacity: 0.5;
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

.toggle {
    appearance: none;
    background: transparent;
    border: none;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: var(--text-muted);
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

    &:disabled { cursor: not-allowed; }
}

.form-error,
.form-saved {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

.form-error { color: hsl(0 84% 65%); }
.form-saved { color: hsl(142 71% 65%); }

.links-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.link-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 14px;
    background: hsl(0 0% 6%);
    border: 1px solid var(--border);
    border-radius: 10px;
    text-decoration: none;
    color: var(--text);
    transition: background 140ms ease, border-color 140ms ease, transform 140ms ease;

    &:hover {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        transform: translateY(-1px);
    }

    .link-icon {
        width: 32px;
        height: 32px;
        flex: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        background: hsl(217 91% 60% / 0.12);
        color: hsl(217 91% 75%);
        font-size: 13px;
    }

    .link-body {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .link-label {
        font-size: 13px;
        font-weight: 600;
        color: var(--text);
    }

    .link-help {
        font-size: 11px;
        color: var(--text-faint);
        text-transform: lowercase;
    }

    .link-arrow {
        color: var(--text-faint);
        font-size: 14px;
    }
}
</style>
