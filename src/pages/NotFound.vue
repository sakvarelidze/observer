<template>
    <div class="v2-not-found">
        <div class="v2-auth-card">
            <header class="v2-auth-brand">
                <object class="v2-auth-mark" data="/icon.svg" />
                <span class="v2-auth-name">Observer</span>
                <span class="v2-auth-tag">{{ $t("Page Not Found") }}</span>
            </header>

            <div class="message">
                <p class="lead">404</p>
                <p class="sub">{{ $t("The resource is no longer available.") }}</p>
            </div>

            <ul class="hint-list">
                <li>{{ $t("Retype the address.") }}</li>
                <li>{{ $t("There might be a typing error in the address.") }}</li>
            </ul>

            <div class="actions">
                <button type="button" class="btn-secondary" @click="goBack">
                    {{ $t("Go back to the previous page.") }}
                </button>
                <router-link to="/dashboard" class="btn-primary">
                    {{ $t("Go back to home page.") }}
                </router-link>
            </div>
        </div>
    </div>
</template>

<script>
export default {
    methods: {
        goBack() {
            history.back();
        },
    },
};
</script>

<style lang="scss" scoped>
@import "./v2/_auth.scss";

.v2-not-found { @include v2-auth-shell; }
.v2-auth-card { @include v2-auth-card; }
.v2-auth-brand { @include v2-auth-brand; }

.message {
    text-align: center;
    display: flex;
    flex-direction: column;
    gap: 4px;

    .lead {
        margin: 0;
        font-size: 56px;
        font-weight: 700;
        letter-spacing: -0.04em;
        color: var(--text);
        font-feature-settings: "tnum";
    }

    .sub {
        margin: 0;
        font-size: 14px;
        color: var(--text-muted);
    }
}

.hint-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-size: 12px;
    color: var(--text-faint);
    text-align: center;

    li {
        padding: 6px 12px;
        background: hsl(0 0% 6%);
        border: 1px solid var(--border);
        border-radius: 6px;
    }
}

.actions {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.btn-primary {
    @include v2-auth-button;

    text-align: center;
    text-decoration: none;
}

.btn-secondary {
    appearance: none;
    background: var(--bg-hover);
    border: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    padding: 11px 16px;
    border-radius: 9px;
    cursor: pointer;
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease;

    &:hover {
        background: hsl(0 0% 14%);
        color: var(--text);
        border-color: var(--border-strong);
    }
}
</style>
