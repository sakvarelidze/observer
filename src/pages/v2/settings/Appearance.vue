<template>
    <div class="settings-page">
        <header class="page-head">
            <h2 class="page-title">Appearance</h2>
            <p class="page-sub">theme, language, and small visual preferences. saved per-browser.</p>
        </header>

        <div class="form">
            <div class="field">
                <span class="field-label">theme</span>
                <div class="theme-grid">
                    <button
                        v-for="opt in themeOptions"
                        :key="opt.value"
                        type="button"
                        class="theme-card"
                        :class="{ active: $root.userTheme === opt.value }"
                        @click="$root.userTheme = opt.value"
                    >
                        <span class="theme-card-icon" :class="`tone-${opt.value}`">
                            <font-awesome-icon :icon="opt.icon" />
                        </span>
                        <span class="theme-card-body">
                            <span class="theme-card-label">{{ opt.label }}</span>
                            <span class="theme-card-help">{{ opt.help }}</span>
                        </span>
                    </button>
                </div>
            </div>

            <label class="field">
                <span class="field-label">language</span>
                <select v-model="$root.language" class="input">
                    <option
                        v-for="lang in languageOptions"
                        :key="lang.code"
                        :value="lang.code"
                    >
                        {{ lang.name }}
                    </option>
                </select>
            </label>

            <div class="field">
                <span class="field-label">elapsed time</span>
                <div class="seg" role="radiogroup" aria-label="Elapsed time style">
                    <button
                        v-for="opt in elapsedTimeOptions"
                        :key="opt.value"
                        type="button"
                        class="seg-option"
                        :class="{ active: $root.styleElapsedTime === opt.value }"
                        role="radio"
                        :aria-checked="$root.styleElapsedTime === opt.value ? 'true' : 'false'"
                        @click="$root.styleElapsedTime = opt.value"
                    >
                        <span class="seg-option-label">{{ opt.label }}</span>
                    </button>
                </div>
                <span class="field-help">how the heartbeat bar shows time-since-first / time-since-last beat.</span>
            </div>
        </div>
    </div>
</template>

<script>
export default {
    name: "SettingsAppearance",
    computed: {
        themeOptions() {
            return [
                { value: "light",
                    label: "light",
                    help: "always bright.",
                    icon: "sun" },
                { value: "dark",
                    label: "dark",
                    help: "always dim.",
                    icon: "moon" },
                { value: "auto",
                    label: "auto",
                    help: "match system preference.",
                    icon: "desktop" },
            ];
        },
        languageOptions() {
            const i18n = this.$i18n;
            if (!i18n) {
                return [];
            }
            const locales = i18n.availableLocales || [];
            return locales.map(code => {
                const name = i18n.messages?.[code]?.languageName || code;
                return { code,
                    name };
            });
        },
        elapsedTimeOptions() {
            return [
                { value: "no-line",
                    label: "no line" },
                { value: "with-line",
                    label: "with line" },
                { value: "none",
                    label: "none" },
            ];
        },
    },
};
</script>

<style lang="scss" scoped>
@import "../_base.scss";

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

.form {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.field {
    display: flex;
    flex-direction: column;
    gap: 8px;
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

    &:hover { border-color: var(--border-strong); }
    &:focus {
        outline: none;
        background: var(--bg-hover);
        border-color: hsl(142 71% 45%);
        box-shadow: 0 0 0 3px hsl(142 71% 45% / 0.15);
    }
}

.theme-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 8px;
}

.theme-card {
    appearance: none;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px;
    color: var(--text-muted);
    cursor: pointer;
    text-align: left;
    display: flex;
    align-items: center;
    gap: 12px;
    font-family: inherit;
    transition: background 140ms ease, border-color 140ms ease, color 140ms ease,
        transform 200ms $v2-ease;

    &:hover {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        color: var(--text);
        transform: translateY(-1px);
    }

    &.active {
        background: hsl(142 71% 45% / 0.10);
        border-color: hsl(142 71% 45% / 0.55);
        color: var(--text);
    }

    .theme-card-icon {
        width: 36px;
        height: 36px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 10px;
        background: hsl(0 0% 14%);
        color: var(--text);
        font-size: 14px;
        flex: none;

        &.tone-light {
            background: hsl(48 92% 50% / 0.18);
            color: hsl(48 92% 70%);
        }

        &.tone-dark {
            background: hsl(217 91% 60% / 0.18);
            color: hsl(217 91% 70%);
        }

        &.tone-auto {
            background: hsl(0 0% 18%);
            color: var(--text-muted);
        }
    }

    .theme-card-body {
        display: flex;
        flex-direction: column;
        gap: 2px;
    }

    .theme-card-label {
        font-size: 14px;
        font-weight: 600;
        letter-spacing: -0.01em;
    }

    .theme-card-help {
        font-size: 11px;
        color: var(--text-faint);
        text-transform: lowercase;
    }
}

.seg {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 4px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 4px;
}

.seg-option {
    appearance: none;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 8px 12px;
    color: var(--text-muted);
    font-family: inherit;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 2px;
    text-align: left;
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease;

    &:hover {
        background: var(--bg-hover);
        color: var(--text);
    }

    &.active {
        background: hsl(142 71% 45% / 0.14);
        border-color: hsl(142 71% 45% / 0.45);
        color: var(--text);
    }

    .seg-option-label {
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 600;
    }

    .seg-option-help {
        font-size: 11px;
        color: var(--text-faint);
        text-transform: lowercase;
    }
}
</style>
