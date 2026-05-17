<template>
    <div v-if="monitor" class="v2-edit" :class="`status-${statusKey}`">
        <header class="topbar">
            <router-link :to="`/dashboard/${monitor.id}`" class="back" title="Back to monitor">
                <span class="back-arrow">←</span>
                <span class="back-label">cancel</span>
            </router-link>

            <div class="topbar-id">
                <span class="topbar-id-hash">#</span>
                <span class="topbar-id-num">{{ monitor.id }}</span>
            </div>

            <div class="topbar-right">
                <MenuTrigger />
            </div>
        </header>

        <section class="hero">
            <p class="hero-eyebrow">edit monitor</p>
            <h1 class="hero-name">
                <span class="status-dot"></span>
                {{ monitor.name }}
            </h1>
            <p class="hero-meta">
                <span class="type-badge">{{ monitor.type }}</span>
                <span class="dot-sep">·</span>
                <span>{{ statusWord }}</span>
                <span class="dot-sep">·</span>
                <span>checks every {{ monitor.interval }}s</span>
            </p>
        </section>

        <section v-if="!supportedType" class="unsupported">
            <div class="unsupported-icon">
                <font-awesome-icon icon="tools" />
            </div>
            <div class="unsupported-body">
                <h2>this type isn't editable yet</h2>
                <p>
                    Editing monitors of type <strong>{{ monitor.type }}</strong> isn't wired up here yet — HTTP, port, ping, and push are covered today; the rest land as we go.
                </p>
                <router-link :to="`/dashboard/${monitor.id}`" class="action">
                    ← back to monitor
                </router-link>
            </div>
        </section>

        <form v-else class="form" @submit.prevent="onSubmit">
            <MonitorFields
                :form="form"
                :monitor="monitor"
                mode="edit"
                tls-mode="full"
                :show-active-toggle="true"
            />

            <footer class="form-foot">
                <span v-if="error" class="form-error">{{ error }}</span>
                <span v-else-if="isDirty" class="form-dirty">unsaved changes</span>
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
                    <span v-if="!saving">save changes</span>
                    <span v-else>saving…</span>
                </button>
            </footer>
        </form>
    </div>

    <div v-else class="loading-shell">
        <LoaderBars size="md" />
        <p>Loading monitor…</p>
    </div>

    <CommandPalette />

    <ConfirmV2
        :open="!!pendingNavigation"
        tone="danger"
        title="discard unsaved changes?"
        body="You have unsaved edits on this monitor. Leave the page and lose them?"
        confirm-label="discard changes"
        cancel-label="stay on page"
        @cancel="onDiscardCancel"
        @confirm="onDiscardConfirm"
    />
</template>

<script>
import CommandPalette from "./CommandPalette.vue";
import ConfirmV2 from "./ConfirmV2.vue";
import LoaderBars from "./LoaderBars.vue";
import MenuTrigger from "./MenuTrigger.vue";
import MonitorFields from "./MonitorFields.vue";

const SUPPORTED_TYPES = new Set([ "http", "port", "ping", "push" ]);
const STATUS_WORD = {
    1: "up",
    0: "down",
    2: "pending",
    3: "maintenance",
};

// Same parsing rule as MonitorFields uses on input — we re-parse on
// save because the form holds the raw textarea string, not the parsed
// dict the backend expects.
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
    name: "EditMonitorV2",
    components: { CommandPalette,
        ConfirmV2,
        LoaderBars,
        MenuTrigger,
        MonitorFields },
    beforeRouteLeave(to, from, next) {
        if (this.isDirty && !this.justSaved) {
            // Defer the navigation; ConfirmV2 will resolve it once the
            // user picks discard or cancel.
            this.pendingNavigation = next;
        } else {
            next();
        }
    },
    data() {
        return {
            form: this.emptyForm(),
            initialSnapshot: null,
            initialTagAssignments: [],
            saving: false,
            error: null,
            justSaved: false,
            pendingNavigation: null,
        };
    },
    computed: {
        monitorId() {
            return Number(this.$route.params.id);
        },
        monitor() {
            return this.$root.monitorList?.[this.monitorId] || null;
        },
        supportedType() {
            return this.monitor && SUPPORTED_TYPES.has(this.monitor.type);
        },
        lastBeat() {
            return this.$root.lastHeartbeatList?.[this.monitorId] || null;
        },
        statusKey() {
            if (!this.monitor) {
                return "unknown";
            }
            if (!this.monitor.active) {
                return "paused";
            }
            if (!this.lastBeat) {
                return "unknown";
            }
            return STATUS_WORD[this.lastBeat.status] || "unknown";
        },
        statusWord() {
            return this.statusKey;
        },
        canSubmit() {
            if (this.saving || !this.supportedType) {
                return false;
            }
            if (!this.form.name?.trim()) {
                return false;
            }
            if (!this.isDirty) {
                return false;
            }
            switch (this.monitor.type) {
                case "http":
                    return !!this.form.url?.trim();
                case "port":
                    return !!this.form.hostname?.trim() && Number.isFinite(this.form.port);
                case "ping":
                    return !!this.form.hostname?.trim();
                case "push":
                    return true;
                default:
                    return false;
            }
        },
        isDirty() {
            if (!this.initialSnapshot) {
                return false;
            }
            return JSON.stringify(this.form) !== this.initialSnapshot;
        },
    },
    watch: {
        monitorId: {
            immediate: true,
            handler() {
                this.hydrateFromMonitor();
            },
        },
        "monitor.id"(id) {
            if (id != null && !this.initialSnapshot) {
                this.hydrateFromMonitor();
            }
        },
    },
    methods: {
        emptyForm() {
            return {
                name: "",
                url: "",
                hostname: "",
                port: null,
                interval: 60,
                maxretries: 0,
                maxredirects: 10,
                acceptedStatuscodes: [ "200-299" ],
                tlsVerifyMode: "system",
                expiryNotification: false,
                certExpiryThresholdDays: 14,
                slowResponseThresholdMs: null,
                slowResponseConsecutive: 3,
                notificationIDList: [],
                description: "",
                active: true,
                method: "GET",
                body: "",
                headersText: "",
                parent: null,
                tagIds: [],
                customCaSubject: null,
                customCaIssuer: null,
                customCaSha256: null,
                type: "http",
            };
        },
        hydrateFromMonitor() {
            const m = this.monitor;
            if (!m) {
                return;
            }
            const incomingCodes = Array.isArray(m.accepted_statuscodes)
                ? m.accepted_statuscodes
                : Array.isArray(m.acceptedStatuscodes)
                    ? m.acceptedStatuscodes
                    : null;
            const incomingNotifs = Array.isArray(m.notificationIDList)
                ? m.notificationIDList.map(Number).filter(Number.isFinite)
                : [];
            const incomingHeaders = m.headers
                || (m.headers_json ? safeParseJson(m.headers_json) : null);
            const headersText = incomingHeaders && typeof incomingHeaders === "object"
                ? Object.entries(incomingHeaders).map(([ k, v ]) => `${k}: ${v}`).join("\n")
                : "";
            const incomingTags = Array.isArray(m.tags) ? m.tags : [];
            this.initialTagAssignments = incomingTags.map(t => ({
                tag_id: Number(t.tag_id ?? t.tagId ?? t.id),
                value: t.value || "",
            })).filter(t => Number.isFinite(t.tag_id));
            const tagIds = Array.from(new Set(this.initialTagAssignments.map(t => t.tag_id)));

            this.form = {
                name: m.name ?? "",
                url: m.url ?? "",
                hostname: m.hostname ?? "",
                port: m.port ?? null,
                interval: m.interval ?? 60,
                maxretries: m.maxretries ?? 0,
                maxredirects: m.maxredirects ?? 10,
                acceptedStatuscodes: incomingCodes && incomingCodes.length > 0
                    ? [ ...incomingCodes ]
                    : [ "200-299" ],
                tlsVerifyMode: m.tlsVerifyMode ?? "system",
                expiryNotification: !!m.expiryNotification,
                certExpiryThresholdDays: m.certExpiryThresholdDays ?? 14,
                slowResponseThresholdMs: m.slowResponseThresholdMs
                    ?? m.slow_response_threshold_ms
                    ?? null,
                slowResponseConsecutive: m.slowResponseConsecutive
                    ?? m.slow_response_consecutive
                    ?? 3,
                notificationIDList: incomingNotifs,
                description: m.description ?? "",
                active: m.active !== false,
                method: (m.method || "GET").toUpperCase(),
                body: m.body ?? "",
                headersText,
                parent: m.parent ?? null,
                tagIds,
                customCaSubject: m.customCaSubject ?? m.custom_ca_subject ?? null,
                customCaIssuer: m.customCaIssuer ?? m.custom_ca_issuer ?? null,
                customCaSha256: m.customCaSha256 ?? m.custom_ca_sha256 ?? null,
                type: m.type,
            };
            this.initialSnapshot = JSON.stringify(this.form);
            this.error = null;
        },
        buildPayload() {
            const m = this.monitor;
            const f = this.form;
            // Spread the existing monitor first so v1-only fields we don't
            // surface (auth, cache busting, IP family, etc.) survive saves.
            const base = { ...m };
            base.name = f.name.trim();
            base.interval = f.interval;
            base.description = f.description?.trim() || null;
            base.active = !!f.active;
            base.parent = f.parent || null;
            base.notificationIDList = [ ...f.notificationIDList ];
            // Slow-response alert config — null threshold disables it.
            base.slowResponseThresholdMs = f.slowResponseThresholdMs
                && f.slowResponseThresholdMs > 0
                ? f.slowResponseThresholdMs
                : null;
            base.slowResponseConsecutive = Math.max(1, f.slowResponseConsecutive || 3);
            // Tags persist via separate /monitor-tags calls after save.
            delete base.tags;

            if (m.type === "http") {
                base.url = f.url.trim();
                base.maxretries = f.maxretries;
                base.maxredirects = f.maxredirects;
                base.accepted_statuscodes = f.acceptedStatuscodes.length > 0
                    ? [ ...f.acceptedStatuscodes ]
                    : [ "200-299" ];
                base.method = (f.method || "GET").toUpperCase();
                const bodyAllowed = [ "POST", "PUT", "PATCH", "DELETE" ].includes(base.method);
                base.body = bodyAllowed && f.body?.trim() ? f.body : null;
                base.headers = parseHeaders(f.headersText);
                base.tlsVerifyMode = f.tlsVerifyMode;
                base.ignoreTls = f.tlsVerifyMode === "insecure";
                base.expiryNotification = f.tlsVerifyMode === "insecure"
                    ? false
                    : !!f.expiryNotification;
                base.certExpiryThresholdDays = f.certExpiryThresholdDays;
            } else if (m.type === "port") {
                base.hostname = f.hostname.trim();
                base.port = f.port;
                base.maxretries = f.maxretries;
            } else if (m.type === "ping") {
                base.hostname = f.hostname.trim();
                base.maxretries = f.maxretries;
            }
            return base;
        },
        onCancel() {
            this.$router.push(`/dashboard/${this.monitorId}`);
        },
        onDiscardCancel() {
            if (this.pendingNavigation) {
                this.pendingNavigation(false);
                this.pendingNavigation = null;
            }
        },
        onDiscardConfirm() {
            if (this.pendingNavigation) {
                const next = this.pendingNavigation;
                this.pendingNavigation = null;
                next();
            }
        },
        async onSubmit() {
            if (!this.canSubmit) {
                return;
            }
            this.saving = true;
            this.error = null;
            try {
                const payload = this.buildPayload();
                const res = await this.$root.updateMonitor(this.monitorId, payload);
                if (!res?.ok) {
                    this.error = res?.msg || "could not save changes";
                    return;
                }
                await this.syncTagAssignments();
                try {
                    const fresh = await this.$root.getMonitor(this.monitorId);
                    if (fresh?.monitor) {
                        this.$root.monitorList[this.monitorId] = fresh.monitor;
                    }
                } catch (e) {
                    console.warn("could not refresh monitor after save", e);
                }
                this.justSaved = true;
                this.$router.push(`/dashboard/${this.monitorId}`);
            } catch (e) {
                console.error("updateMonitor failed", e);
                this.error = e?.response?.data?.detail || e?.message || "request failed";
            } finally {
                this.saving = false;
            }
        },
        async syncTagAssignments() {
            const initial = new Map();
            for (const t of this.initialTagAssignments) {
                initial.set(t.tag_id, t.value || "");
            }
            const target = new Set(this.form.tagIds);
            const monitorId = this.monitorId;

            const toRemove = [];
            for (const [ tagId, value ] of initial.entries()) {
                if (!target.has(tagId)) {
                    toRemove.push({ tagId,
                        value });
                }
            }
            const toAdd = [];
            for (const tagId of target) {
                if (!initial.has(tagId)) {
                    toAdd.push(tagId);
                }
            }

            for (const { tagId, value } of toRemove) {
                try {
                    await this.$root.api.delete("/monitor-tags", {
                        params: { monitor_id: monitorId,
                            tag_id: tagId,
                            value },
                    });
                } catch (e) {
                    console.warn(`could not detach tag ${tagId}`, e);
                }
            }
            for (const tagId of toAdd) {
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

/**
 * @param raw
 */
function safeParseJson(raw) {
    try {
        return typeof raw === "string" ? JSON.parse(raw) : raw;
    } catch (e) {
        return null;
    }
}
</script>

<style lang="scss" scoped>
@import "./_base.scss";

.v2-edit {
    @include v2-surface-tokens;
    @include v2-shell-base;
    @include v2-status-tokens(0.18);

    background:
        radial-gradient(circle at 0% 0%, var(--status-glow), transparent 55%),
        radial-gradient(circle at 100% -10%, hsl(0 0% 12% / 0.7), transparent 65%),
        var(--bg);
    padding: 0 32px 64px;
    transition: background 240ms ease;
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

.topbar-id {
    justify-self: center;
    font-size: 11px;
    color: var(--text-faint);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-variant-numeric: tabular-nums;
    .topbar-id-hash { opacity: 0.6; }
}

.topbar-right {
    display: inline-flex;
    align-items: center;
    gap: 8px;
}

.hero {
    margin: 24px auto 28px;
    max-width: 720px;
    animation: v2-up 320ms var(--enter-ease) both;
    animation-delay: 60ms;
}

.hero-eyebrow {
    margin: 0 0 6px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--text-faint);
}

.hero-name {
    margin: 0 0 8px;
    font-size: clamp(24px, 3.4vw, 34px);
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--text);
    display: inline-flex;
    align-items: center;
    gap: 14px;
}

.status-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--status);
    box-shadow: 0 0 0 4px hsl(0 0% 0% / 0.5);
}

.hero-meta {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;

    .type-badge {
        display: inline-flex;
        align-items: center;
        padding: 3px 8px;
        background: var(--bg-soft);
        border: 1px solid var(--border);
        border-radius: 999px;
        color: var(--text);
    }

    .dot-sep {
        margin: 0 8px;
        opacity: 0.5;
    }
}

.unsupported {
    max-width: 720px;
    margin: 0 auto;
    padding: 28px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 14px;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 18px;
    animation: v2-up 320ms var(--enter-ease) both;
    animation-delay: 100ms;

    .unsupported-icon {
        width: 48px;
        height: 48px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: hsl(217 91% 60% / 0.12);
        border-radius: 12px;
        color: hsl(217 91% 70%);
        font-size: 18px;
    }

    .unsupported-body {
        h2 {
            margin: 0 0 6px;
            font-size: 17px;
            font-weight: 600;
            letter-spacing: -0.01em;
        }
        p {
            margin: 0 0 16px;
            color: var(--text-muted);
            font-size: 13px;
            line-height: 1.55;
            strong { color: var(--text); }
        }
    }
}

.form {
    max-width: 720px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 18px;
    animation: v2-up 320ms var(--enter-ease) both;
    animation-delay: 100ms;
}

.form-foot {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 8px;

    .form-error,
    .form-dirty {
        flex: 1;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-variant-numeric: tabular-nums;
    }

    .form-error { color: hsl(0 84% 65%); }
    .form-dirty { color: hsl(38 92% 60%); }
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

.loading-shell {
    min-height: 60vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 20px;
    background: hsl(0 0% 5%);
    color: hsl(0 0% 60%);
}

@media (prefers-reduced-motion: reduce) {
    .v2-edit,
    .hero,
    .form,
    .unsupported {
        animation: none;
    }
}

@media (max-width: 760px) {
    .v2-edit {
        padding: 0 16px 40px;
    }

    .unsupported {
        grid-template-columns: 1fr;
    }
}
</style>
