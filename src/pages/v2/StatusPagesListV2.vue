<template>
    <div class="v2-status-pages">
        <header class="topbar">
            <router-link to="/dashboard" class="back" title="Back to dashboard">
                <span class="back-arrow">←</span>
                <span class="back-label">dashboard</span>
            </router-link>

            <h1 class="topbar-title">status pages</h1>

            <div class="topbar-right">
                <MenuTrigger />
            </div>
        </header>

        <main class="main">
            <header class="page-head">
                <p class="page-sub">public dashboards your users can subscribe to. each one is a curated subset of your monitors.</p>
                <router-link to="/status-pages/new" class="action primary">
                    <font-awesome-icon icon="plus" />
                    <span>new page</span>
                </router-link>
            </header>

            <div v-if="loading" class="page-loading">
                <LoaderBars size="md" />
            </div>

            <ul v-else-if="pages.length > 0" class="pages-list">
                <li
                    v-for="page in pages"
                    :key="page.slug"
                    class="page-row"
                    @click="$router.push(`/status-pages/${page.slug}/edit`)"
                >
                    <span class="page-mark">
                        <img v-if="page.config?.icon" :src="page.config.icon" :alt="page.title || page.slug">
                        <span v-else class="page-mark-letter">{{ initial(page.title || page.slug) }}</span>
                    </span>
                    <div class="page-body">
                        <div class="page-row-head">
                            <span class="page-title-text">{{ page.title || page.slug }}</span>
                            <span class="page-badge" :class="page.public ? 'public' : 'private'">
                                <font-awesome-icon :icon="page.public ? 'eye' : 'eye-slash'" />
                                <span>{{ page.public ? "public" : "private" }}</span>
                            </span>
                        </div>
                        <code class="page-slug">/status/{{ page.slug }}</code>
                    </div>
                    <div class="page-actions" @click.stop>
                        <a
                            :href="`/status/${page.slug}`"
                            target="_blank"
                            rel="noopener noreferrer"
                            class="row-btn"
                            title="Open public page"
                        >
                            <font-awesome-icon icon="external-link-square-alt" />
                        </a>
                        <router-link
                            :to="`/status-pages/${page.slug}/edit`"
                            class="row-btn"
                            title="Edit"
                        >
                            <font-awesome-icon icon="pen" />
                        </router-link>
                        <button
                            type="button"
                            class="row-btn danger"
                            title="Delete"
                            @click="confirmDelete(page)"
                        >
                            <font-awesome-icon icon="trash" />
                        </button>
                    </div>
                </li>
            </ul>

            <div v-else class="empty-state">
                <span class="empty-icon">
                    <font-awesome-icon icon="rectangle-list" />
                </span>
                <p class="empty-title">No status pages yet</p>
                <p class="empty-sub">Create one and pick which monitors to show — visitors get a clean public view of system health.</p>
                <router-link to="/status-pages/new" class="action primary">
                    <font-awesome-icon icon="plus" />
                    <span>create your first page</span>
                </router-link>
            </div>
        </main>

        <CommandPalette />

        <ConfirmV2
            :open="!!pendingDelete"
            tone="danger"
            title="delete status page"
            confirm-label="delete page"
            busy-label="deleting…"
            :busy="deleteSaving"
            @cancel="cancelDelete"
            @confirm="confirmedDelete"
        >
            Permanently delete the page at <code>/status/{{ pendingDelete?.slug }}</code>? Visitors hitting that URL will see a 404. Monitors aren't affected.
        </ConfirmV2>
    </div>
</template>

<script>
import CommandPalette from "./CommandPalette.vue";
import ConfirmV2 from "./ConfirmV2.vue";
import LoaderBars from "./LoaderBars.vue";
import MenuTrigger from "./MenuTrigger.vue";

export default {
    name: "StatusPagesListV2",
    components: { CommandPalette,
        ConfirmV2,
        LoaderBars,
        MenuTrigger },
    data() {
        return {
            pages: [],
            loading: true,
            pendingDelete: null,
            deleteSaving: false,
        };
    },
    mounted() {
        this.fetchPages();
    },
    methods: {
        initial(s) {
            return (s || "?").trim().charAt(0).toUpperCase();
        },
        async fetchPages() {
            this.loading = true;
            try {
                const { data } = await this.$root.api.get("/status-page");
                const list = Array.isArray(data) ? data : (data?.pages || []);
                this.pages = list.sort((a, b) => (a.title || a.slug || "").localeCompare(b.title || b.slug || ""));
            } catch (e) {
                console.warn("could not load status pages", e);
                this.pages = [];
            } finally {
                this.loading = false;
            }
        },
        confirmDelete(page) {
            this.pendingDelete = { ...page };
        },
        cancelDelete() {
            if (this.deleteSaving) {
                return;
            }
            this.pendingDelete = null;
        },
        async confirmedDelete() {
            const page = this.pendingDelete;
            if (!page) {
                return;
            }
            this.deleteSaving = true;
            try {
                await this.$root.api.delete(`/status-page/${page.slug}`);
                await this.fetchPages();
                this.pendingDelete = null;
            } catch (e) {
                console.warn("could not delete page", e);
            } finally {
                this.deleteSaving = false;
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.v2-status-pages {
    @include v2-surface-tokens;
    @include v2-shell-base;

    background:
        radial-gradient(circle at 12% -10%, hsl(217 91% 60% / 0.05), transparent 60%),
        var(--bg);
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
    gap: 12px;
}

.main {
    max-width: 920px;
    margin: 24px auto 0;
    display: flex;
    flex-direction: column;
    gap: 24px;
    animation: v2-up 320ms var(--enter-ease) both;
    animation-delay: 60ms;
}

.page-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;

    .page-sub {
        margin: 0;
        color: var(--text-muted);
        font-size: 13px;
        max-width: 60ch;
        line-height: 1.55;
    }
}

.page-loading {
    display: flex;
    justify-content: center;
    padding: 40px 0;
}

.pages-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.page-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 14px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 12px;
    cursor: pointer;
    transition: background 140ms ease, border-color 140ms ease, transform 140ms ease;

    &:hover {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        transform: translateY(-1px);
    }
}

.page-mark {
    width: 38px;
    height: 38px;
    flex: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: var(--control);
    border-radius: 10px;
    color: var(--text);
    font-size: 14px;
    overflow: hidden;

    img {
        width: 100%;
        height: 100%;
        object-fit: contain;
    }

    .page-mark-letter {
        font-weight: 600;
    }
}

.page-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 4px;
    min-width: 0;
}

.page-row-head {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}

.page-title-text {
    font-size: 14.5px;
    font-weight: 600;
    color: var(--text);
}

.page-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border: 1px solid var(--border);
    background: var(--control);
    color: var(--text-faint);

    &.public {
        background: hsl(142 71% 45% / 0.12);
        border-color: hsl(142 71% 45% / 0.4);
        color: hsl(142 71% 75%);
    }
}

.page-slug {
    font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
        Monaco, Consolas, monospace;
    font-size: 11.5px;
    color: var(--text-faint);
}

.page-actions {
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.row-btn {
    appearance: none;
    background: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    width: 32px;
    height: 32px;
    border-radius: 7px;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    text-decoration: none;
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
    padding: 60px 20px;
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
        background: hsl(217 91% 60% / 0.12);
        color: hsl(217 91% 75%);
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
        max-width: 50ch;
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

@media (max-width: 640px) {
    .v2-status-pages { padding: 0 16px 40px; }

    .page-head {
        flex-direction: column;
        align-items: stretch;
    }

    .page-row {
        flex-wrap: wrap;
    }

    .page-actions {
        width: 100%;
        justify-content: flex-end;
    }
}
</style>
