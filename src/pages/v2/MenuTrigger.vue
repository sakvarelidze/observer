<template>
    <button
        type="button"
        class="menu-trigger"
        :title="`Open menu (${shortcutLabel})`"
        @click="open"
    >
        <font-awesome-icon icon="bars" class="menu-trigger-icon" />
        <span class="menu-trigger-kbd">{{ shortcutLabel }}</span>
    </button>
</template>

<script>
export default {
    name: "MenuTrigger",
    computed: {
        shortcutLabel() {
            const isMac = typeof navigator !== "undefined"
                && /mac|iphone|ipad/i.test(navigator.platform || navigator.userAgent || "");
            return isMac ? "⌘K" : "Ctrl K";
        },
    },
    methods: {
        open() {
            this.$root.emitter?.emit?.("open-command-palette");
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.menu-trigger {
    appearance: none;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    color: var(--text-muted);
    border-radius: 8px;
    padding: 6px 10px 6px 8px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 11px;
    cursor: pointer;
    transition: background 140ms ease, border-color 140ms ease, color 140ms ease;

    &:hover {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        color: var(--text);
    }
}

.menu-trigger-icon {
    font-size: 12px;
}

.menu-trigger-kbd {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 18px;
    padding: 0 6px;
    border-radius: 4px;
    border: 1px solid var(--border);
    background: hsl(0 0% 5%);
    color: var(--text-muted);
    font-size: 11px;
    font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
        Monaco, Consolas, monospace;
    line-height: 1;
    letter-spacing: 0.04em;
}
</style>
