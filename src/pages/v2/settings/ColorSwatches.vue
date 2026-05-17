<template>
    <div class="color-swatches">
        <button
            v-for="c in colors"
            :key="c"
            type="button"
            class="color-swatch"
            :class="{ on: modelValue === c }"
            :style="{ '--swatch': c }"
            :aria-label="'color ' + c"
            @click="select(c)"
        ></button>
    </div>
</template>

<script>
import { TAG_COLORS } from "../MonitorFields.vue";

export default {
    name: "ColorSwatches",
    props: {
        modelValue: {
            type: String,
            default: TAG_COLORS[0],
        },
    },
    emits: [ "update:modelValue" ],
    computed: {
        colors() {
            return TAG_COLORS;
        },
    },
    methods: {
        select(c) {
            this.$emit("update:modelValue", c);
        },
    },
};
</script>

<style lang="scss" scoped>
.color-swatches {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.color-swatch {
    --swatch: hsl(0 0% 50%);

    appearance: none;
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: var(--swatch);
    border: 2px solid transparent;
    box-shadow: 0 0 0 1px var(--border) inset;
    cursor: pointer;
    transition: transform 140ms ease, border-color 140ms ease, box-shadow 140ms ease;

    &:hover { transform: scale(1.08); }

    &.on {
        border-color: var(--text);
        box-shadow: 0 0 0 2px var(--bg) inset, 0 0 0 1px var(--border) inset;
        transform: scale(1.08);
    }
}
</style>
