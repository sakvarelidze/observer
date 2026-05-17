<template>
    <div class="v2-add">
        <header class="topbar">
            <router-link to="/dashboard" class="back" title="Cancel">
                <span class="back-arrow">←</span>
                <span class="back-label">cancel</span>
            </router-link>

            <h1 class="topbar-title">{{ cloneSource ? "clone monitor" : "add monitor" }}</h1>

            <div class="topbar-right">
                <div class="step-indicator">
                    <span class="step" :class="{ active: !typeChosen, done: typeChosen }">
                        <span class="step-num">1</span>
                        <span class="step-name">type</span>
                    </span>
                    <span class="step-divider"></span>
                    <span class="step" :class="{ active: typeChosen }">
                        <span class="step-num">2</span>
                        <span class="step-name">details</span>
                    </span>
                </div>
                <MenuTrigger />
            </div>
        </header>

        <transition name="step" mode="out-in">
            <section v-if="!typeChosen" key="picker" class="step-pane">
                <h2 class="step-title">what do you want to monitor?</h2>
                <p class="step-sub">pick a type to continue. more monitor types are coming — open an issue if there's a specific one you need.</p>

                <div class="type-grid">
                    <button
                        v-for="t in availableTypes"
                        :key="t.value"
                        type="button"
                        class="type-card"
                        @click="selectType(t.value)"
                    >
                        <span class="type-icon">
                            <font-awesome-icon :icon="t.icon" />
                        </span>
                        <span class="type-label">{{ t.label }}</span>
                        <span class="type-hint">{{ t.hint }}</span>
                    </button>
                </div>
            </section>

            <section v-else key="form" class="step-pane">
                <header class="form-pane-head">
                    <button type="button" class="step-back" @click="resetType">
                        <span>←</span>
                        <span>change type</span>
                    </button>
                    <span class="form-pane-type">
                        <font-awesome-icon :icon="selectedType.icon" />
                        {{ selectedType.label }}
                    </span>
                    <span v-if="cloneSource" class="form-pane-clone">
                        <font-awesome-icon icon="copy" />
                        <span>cloning from <strong>{{ cloneSource.name }}</strong></span>
                    </span>
                </header>

                <form class="form" @submit.prevent="onSubmit">
                    <MonitorFields
                        :form="form"
                        :monitor="null"
                        mode="create"
                        tls-mode="simple"
                        :show-active-toggle="false"
                        :name-placeholder="selectedType.namePlaceholder"
                    />

                    <footer class="form-foot">
                        <span v-if="error" class="form-error">{{ error }}</span>
                        <button
                            type="button"
                            class="action ghost"
                            :disabled="saving"
                            @click="onCancel"
                        >
                            cancel
                        </button>
                        <button
                            type="submit"
                            class="action primary"
                            :disabled="!canSubmit"
                        >
                            <span v-if="!saving">{{ cloneSource ? "create clone" : "add monitor" }}</span>
                            <span v-else>creating…</span>
                        </button>
                    </footer>
                </form>
            </section>
        </transition>

        <CommandPalette />
    </div>
</template>

<script>
import CommandPalette from "./CommandPalette.vue";
import MenuTrigger from "./MenuTrigger.vue";
import MonitorFields from "./MonitorFields.vue";

const TYPE_DEFS = [
    {
        value: "http",
        label: "http / https",
        hint: "ping a URL, expect 2xx",
        icon: "globe",
        namePlaceholder: "production website",
    },
    {
        value: "port",
        label: "tcp port",
        hint: "check if a port is open",
        icon: "plug",
        namePlaceholder: "redis primary",
    },
    {
        value: "ping",
        label: "ping",
        hint: "ICMP host reachability",
        icon: "wifi",
        namePlaceholder: "edge router",
    },
    {
        value: "push",
        label: "push",
        hint: "let your app push heartbeats",
        icon: "bullhorn",
        namePlaceholder: "cron job",
    },
];

/**
 * @param text
 */
function parseHeaders(text) {
    const txt = (text || "").trim();
    if (!txt) {
        return null;
    }
    const out = {};
    for (const line of txt.split(/\r?\n/)) {
        const t = line.trim();
        if (!t || t.startsWith("#")) {
            continue;
        }
        const idx = t.indexOf(":");
        if (idx <= 0) {
            continue;
        }
        const key = t.slice(0, idx).trim();
        const value = t.slice(idx + 1).trim();
        if (key) {
            out[key] = value;
        }
    }
    return out;
}

export default {
    name: "AddMonitorV2",
    components: { CommandPalette,
        MenuTrigger,
        MonitorFields },
    data() {
        return {
            availableTypes: TYPE_DEFS,
            form: this.emptyForm(),
            saving: false,
            error: null,
            cloneAttempted: false,
        };
    },
    computed: {
        typeChosen() {
            return !!this.form.type;
        },
        selectedType() {
            return TYPE_DEFS.find(t => t.value === this.form.type) || {};
        },
        cloneSourceId() {
            const raw = this.$route.query?.clone;
            if (raw == null) {
                return null;
            }
            const id = Number(raw);
            return Number.isFinite(id) ? id : null;
        },
        cloneSource() {
            const id = this.cloneSourceId;
            if (id == null) {
                return null;
            }
            return this.$root.monitorList?.[id] || null;
        },
        canSubmit() {
            if (this.saving) {
                return false;
            }
            if (!this.form.name?.trim()) {
                return false;
            }
            switch (this.form.type) {
                case "http":
                    return !!this.form.url.trim();
                case "port":
                    return !!this.form.hostname.trim() && Number.isFinite(this.form.port);
                case "ping":
                    return !!this.form.hostname.trim();
                case "push":
                    return true;
                default:
                    return false;
            }
        },
    },
    watch: {
        // The monitor list is populated asynchronously after the page mounts,
        // so reaching for `cloneSource` immediately may miss it. Watch both
        // the route query and the monitor list and hydrate as soon as the
        // source row appears.
        cloneSourceId: {
            immediate: true,
            handler() {
                this.tryHydrateFromClone();
            },
        },
        "$root.monitorList": {
            deep: false,
            handler() {
                this.tryHydrateFromClone();
            },
        },
    },
    methods: {
        emptyForm() {
            return {
                type: null,
                name: "",
                url: "",
                hostname: "",
                port: 443,
                interval: 60,
                maxretries: 3,
                maxredirects: 10,
                acceptedStatuscodes: [ "200-299" ],
                tlsVerifyMode: "system",
                expiryNotification: false,
                certExpiryThresholdDays: 14,
                slowResponseThresholdMs: null,
                slowResponseConsecutive: 3,
                notificationIDList: [],
                description: "",
                method: "GET",
                body: "",
                headersText: "",
                parent: null,
                tagIds: [],
            };
        },
        tryHydrateFromClone() {
            // Idempotent — bail once the form is filled, otherwise reactivity
            // on $root.monitorList would clobber user edits whenever a poll
            // refreshes the list.
            if (this.cloneAttempted) {
                return;
            }
            const id = this.cloneSourceId;
            if (id == null) {
                return;
            }
            const m = this.$root.monitorList?.[id];
            if (!m) {
                return;
            }
            if (!TYPE_DEFS.some(t => t.value === m.type)) {
                // Source monitor type isn't supported by the v2 add form
                // (e.g. keyword, json-query). Mark attempted to avoid
                // looping, surface a helpful note, and let the user pick
                // a type by hand.
                this.cloneAttempted = true;
                this.error = `cloning ${m.type} monitors isn't supported here yet — pick a type manually.`;
                return;
            }
            this.cloneAttempted = true;
            this.hydrateFromClone(m);
        },
        hydrateFromClone(m) {
            const codes = Array.isArray(m.accepted_statuscodes)
                ? m.accepted_statuscodes
                : Array.isArray(m.acceptedStatuscodes)
                    ? m.acceptedStatuscodes
                    : null;
            const headers = m.headers && typeof m.headers === "object"
                ? Object.entries(m.headers).map(([ k, v ]) => `${k}: ${v}`).join("\n")
                : "";
            const tagIds = Array.from(new Set(
                (Array.isArray(m.tags) ? m.tags : [])
                    .map(t => Number(t.tag_id ?? t.tagId ?? t.id))
                    .filter(Number.isFinite),
            ));
            const notifs = Array.isArray(m.notificationIDList)
                ? m.notificationIDList.map(Number).filter(Number.isFinite)
                : [];

            this.form = {
                ...this.emptyForm(),
                type: m.type,
                // Force a fresh name so the user can't accidentally save the
                // clone under the source's exact title.
                name: "",
                url: m.url ?? "",
                hostname: m.hostname ?? "",
                port: m.port ?? 443,
                interval: m.interval ?? 60,
                maxretries: m.maxretries ?? 3,
                maxredirects: m.maxredirects ?? 10,
                acceptedStatuscodes: codes && codes.length > 0 ? [ ...codes ] : [ "200-299" ],
                tlsVerifyMode: m.tlsVerifyMode ?? "system",
                expiryNotification: !!m.expiryNotification,
                certExpiryThresholdDays: m.certExpiryThresholdDays ?? 14,
                slowResponseThresholdMs: m.slowResponseThresholdMs
                    ?? m.slow_response_threshold_ms
                    ?? null,
                slowResponseConsecutive: m.slowResponseConsecutive
                    ?? m.slow_response_consecutive
                    ?? 3,
                notificationIDList: notifs,
                description: m.description ?? "",
                method: (m.method || "GET").toUpperCase(),
                body: m.body ?? "",
                headersText: headers,
                parent: m.parent ?? null,
                tagIds,
            };
        },
        selectType(type) {
            this.form.type = type;
            this.error = null;
            if (type === "port" && !this.form.port) {
                this.form.port = 443;
            }
        },
        resetType() {
            this.form.type = null;
            this.error = null;
        },
        onCancel() {
            this.$router.push("/dashboard");
        },
        async onSubmit() {
            if (!this.canSubmit) {
                return;
            }
            this.saving = true;
            this.error = null;
            try {
                const payload = this.buildPayload();
                const res = await this.$root.addMonitor(payload);
                if (!res?.ok) {
                    this.error = res?.msg || "could not add monitor";
                    return;
                }
                const newId = res.monitorID;
                if (newId != null) {
                    if (this.form.tagIds.length > 0) {
                        await this.attachTagsAfterCreate(newId);
                    }
                    this.$router.push(`/dashboard/${newId}`);
                } else {
                    this.$router.push("/dashboard");
                }
            } catch (e) {
                console.error("addMonitor failed", e);
                this.error = e?.response?.data?.detail || e?.message || "request failed";
            } finally {
                this.saving = false;
            }
        },
        buildPayload() {
            const f = this.form;
            const base = {
                type: f.type,
                name: f.name.trim(),
                interval: f.interval,
                description: f.description?.trim() || null,
                active: true,
                notificationIDList: [ ...f.notificationIDList ],
                slowResponseThresholdMs: f.slowResponseThresholdMs
                    && f.slowResponseThresholdMs > 0
                    ? f.slowResponseThresholdMs
                    : null,
                slowResponseConsecutive: Math.max(1, f.slowResponseConsecutive || 3),
            };
            base.parent = f.parent || null;

            if (f.type === "http") {
                base.url = f.url.trim();
                base.maxretries = f.maxretries;
                base.method = (f.method || "GET").toUpperCase();
                const bodyAllowed = [ "POST", "PUT", "PATCH", "DELETE" ].includes(base.method);
                base.body = bodyAllowed && f.body?.trim() ? f.body : null;
                base.headers = parseHeaders(f.headersText);
                base.maxredirects = f.maxredirects;
                base.accepted_statuscodes = f.acceptedStatuscodes.length > 0
                    ? [ ...f.acceptedStatuscodes ]
                    : [ "200-299" ];
                base.tlsVerifyMode = f.tlsVerifyMode;
                base.ignoreTls = f.tlsVerifyMode === "insecure";
                base.expiryNotification = f.tlsVerifyMode === "insecure"
                    ? false
                    : !!f.expiryNotification;
                base.certExpiryThresholdDays = f.certExpiryThresholdDays;
            } else if (f.type === "port") {
                base.hostname = f.hostname.trim();
                base.port = f.port;
                base.maxretries = f.maxretries;
            } else if (f.type === "ping") {
                base.hostname = f.hostname.trim();
                base.maxretries = f.maxretries;
            }
            return base;
        },
        async attachTagsAfterCreate(monitorId) {
            for (const tagId of this.form.tagIds) {
                try {
                    await this.$root.api.post("/monitor-tags", {
                        monitor_id: monitorId,
                        tag_id: tagId,
                        value: "",
                    });
                } catch (e) {
                    console.warn(`could not attach tag ${tagId}`, e);
                }
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@import "./_base.scss";

.v2-add {
    @include v2-surface-tokens;
    @include v2-shell-base;

    background:
        radial-gradient(circle at 12% -10%, hsl(142 71% 45% / 0.05), transparent 60%),
        radial-gradient(circle at 90% 0%, hsl(217 91% 60% / 0.04), transparent 55%),
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

    .back-arrow {
        font-size: 14px;
        line-height: 1;
        transition: transform 200ms $v2-ease;
    }

    &:hover .back-arrow {
        transform: translateX(-3px);
    }
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

.step-indicator {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    color: var(--text-faint);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;

    .step {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        opacity: 0.5;
        transition: opacity 180ms ease, color 180ms ease;

        &.active {
            opacity: 1;
            color: var(--text);
        }

        &.done {
            opacity: 1;
            color: hsl(142 71% 55%);
        }
    }

    .step-num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        border: 1px solid currentColor;
        font-size: 9px;
        line-height: 1;
        font-variant-numeric: tabular-nums;
    }

    .step-divider {
        width: 22px;
        height: 1px;
        background: var(--border);
    }
}

.step-pane {
    max-width: 720px;
    margin: 24px auto 0;
    animation: v2-up 320ms var(--enter-ease) both;
    animation-delay: 60ms;
}

.step-title {
    margin: 0 0 6px;
    font-size: clamp(22px, 3vw, 30px);
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--text);
}

.step-sub {
    margin: 0 0 28px;
    color: var(--text-muted);
    font-size: 13px;
}

.type-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
}

.type-card {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    padding: 18px 16px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 12px;
    color: var(--text);
    text-align: left;
    text-decoration: none;
    cursor: pointer;
    transition: transform 200ms $v2-ease, border-color 180ms ease,
        background 180ms ease, box-shadow 220ms ease;

    &:hover {
        transform: translateY(-2px);
        border-color: hsl(142 71% 45% / 0.45);
        background: var(--bg-hover);
        box-shadow: 0 6px 18px hsl(0 0% 0% / 0.35);
    }

    &:focus-visible {
        outline: none;
        border-color: hsl(142 71% 45%);
        box-shadow: 0 0 0 2px hsl(142 71% 45% / 0.25);
    }

    .type-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 34px;
        height: 34px;
        border-radius: 10px;
        background: hsl(142 71% 45% / 0.12);
        color: hsl(142 71% 60%);
        font-size: 14px;
    }

    .type-label {
        font-size: 15px;
        font-weight: 600;
        letter-spacing: -0.01em;
    }

    .type-hint {
        font-size: 12px;
        color: var(--text-muted);
        text-transform: lowercase;
    }
}

.form-pane-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 18px;
    flex-wrap: wrap;
}

.step-back {
    appearance: none;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    cursor: pointer;
    padding: 6px 10px;
    border-radius: 8px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: color 140ms ease, background 140ms ease;

    &:hover {
        color: var(--text);
        background: var(--bg-soft);
    }
}

.form-pane-type {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text);
    padding: 5px 10px;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--bg-soft);
}

.form-pane-clone {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: hsl(38 92% 70%);
    padding: 5px 10px;
    border: 1px solid hsl(38 92% 50% / 0.4);
    border-radius: 999px;
    background: hsl(38 92% 50% / 0.08);

    strong {
        color: hsl(38 92% 80%);
        font-weight: 600;
    }
}

.form {
    display: flex;
    flex-direction: column;
    gap: 18px;
}

.form-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 8px;

    .form-error {
        flex: 1;
        font-size: 12px;
        color: hsl(0 84% 65%);
        font-variant-numeric: tabular-nums;
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
    transition: background 140ms ease, color 140ms ease, border-color 140ms ease,
        transform 140ms ease;

    &:hover:not(:disabled) {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        color: var(--text);
    }

    &:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }

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

.step-enter-active,
.step-leave-active {
    transition: opacity 220ms $v2-ease, transform 220ms $v2-ease;
}

.step-enter-from {
    opacity: 0;
    transform: translateX(20px);
}

.step-leave-to {
    opacity: 0;
    transform: translateX(-20px);
}

@media (prefers-reduced-motion: reduce) {
    .v2-add,
    .step-pane {
        animation: none;
    }

    .step-enter-active,
    .step-leave-active {
        transition: none;
    }
}

@media (max-width: 760px) {
    .v2-add {
        padding: 0 16px 40px;
    }

    .topbar {
        grid-template-columns: auto 1fr;
        gap: 8px;

        .topbar-title { display: none; }
    }

    .topbar-right {
        grid-column: 1 / -1;
        order: 2;
        justify-content: flex-start;
        flex-wrap: wrap;
    }
}
</style>
