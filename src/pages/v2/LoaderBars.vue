<template>
    <div class="loader-bars" :class="`size-${size}`" aria-hidden="true">
        <span></span>
        <span></span>
        <span></span>
    </div>
</template>

<script>
export default {
    name: "LoaderBars",
    props: {
        size: {
            type: String,
            default: "md",
            validator: (v) => [ "sm", "md", "lg" ].includes(v),
        },
    },
};
</script>

<style lang="scss" scoped>
@use "./_base" as *;

.loader-bars {
    display: inline-flex;
    gap: 6px;

    span {
        display: block;
        background: var(--border-strong, hsl(0 0% 26%));
        border-radius: 3px;
        animation: v2-loader-bar 1.4s ease-in-out infinite;
    }

    span:nth-child(2) { animation-delay: 0.18s; }
    span:nth-child(3) { animation-delay: 0.36s; }
}

.size-sm span {
    width: 6px;
    height: 18px;
}

.size-md span {
    width: 8px;
    height: 24px;
}

.size-lg span {
    width: 10px;
    height: 32px;
}

@media (prefers-reduced-motion: reduce) {
    .loader-bars span {
        animation: none;
        opacity: 0.7;
    }
}
</style>
