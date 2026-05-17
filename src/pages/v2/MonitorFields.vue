<!-- eslint-disable vue/no-mutating-props -->
<template>
    <div class="monitor-fields">
        <!-- Name -->
        <label class="field">
            <span class="field-label">name <span class="req">*</span></span>
            <input
                v-model="form.name"
                type="text"
                class="input"
                required
                autocomplete="off"
                :placeholder="namePlaceholder"
            >
        </label>

        <!-- Type-specific basic fields -->
        <label v-if="form.type === 'http'" class="field">
            <span class="field-label">url <span class="req">*</span></span>
            <input
                v-model="form.url"
                type="url"
                class="input"
                required
                placeholder="https://example.com"
            >
        </label>

        <div v-if="form.type === 'port'" class="field-row">
            <label class="field flex-2">
                <span class="field-label">hostname <span class="req">*</span></span>
                <input
                    v-model="form.hostname"
                    type="text"
                    class="input"
                    required
                    placeholder="example.com"
                >
            </label>
            <label class="field">
                <span class="field-label">port <span class="req">*</span></span>
                <input
                    v-model.number="form.port"
                    type="number"
                    class="input"
                    min="1"
                    max="65535"
                    required
                    placeholder="443"
                >
            </label>
        </div>

        <label v-if="form.type === 'ping'" class="field">
            <span class="field-label">hostname <span class="req">*</span></span>
            <input
                v-model="form.hostname"
                type="text"
                class="input"
                required
                placeholder="example.com"
            >
        </label>

        <!-- Push URL panel (edit only, when monitor has a token) -->
        <div v-if="mode === 'edit' && form.type === 'push' && pushUrl" class="push-token">
            <span class="field-label">push url</span>
            <div class="push-token-row">
                <code class="push-token-value">{{ pushUrl }}</code>
                <button
                    type="button"
                    class="action ghost copy-btn"
                    :title="copied ? 'Copied' : 'Copy push URL'"
                    @click="copyPushUrl"
                >
                    <font-awesome-icon :icon="copied ? 'check' : 'copy'" />
                    <span>{{ copied ? "copied" : "copy" }}</span>
                </button>
            </div>
            <p class="push-help">your application sends GET requests to this URL on its own schedule. interval below is the expected period — we mark the monitor down if no push arrives in time.</p>
        </div>

        <!-- Push info (create only — token doesn't exist yet) -->
        <div v-if="mode === 'create' && form.type === 'push'" class="push-info">
            <p class="push-info-line">push monitors receive heartbeats from your application — no probe is sent.</p>
            <p class="push-info-line">we'll generate the push URL after creation.</p>
        </div>

        <!-- Interval + max retries -->
        <div class="field-row">
            <label class="field flex-1">
                <span class="field-label">interval</span>
                <span class="input-wrap">
                    <input
                        v-model.number="form.interval"
                        type="number"
                        class="input"
                        min="20"
                        required
                    >
                    <span class="input-suffix">seconds</span>
                </span>
            </label>
            <label v-if="form.type !== 'push'" class="field flex-1">
                <span class="field-label">max retries</span>
                <input
                    v-model.number="form.maxretries"
                    type="number"
                    class="input"
                    min="0"
                >
            </label>
        </div>

        <!-- Slow-response alert -->
        <div v-if="form.type !== 'push'" class="field-row">
            <label class="field flex-1">
                <span class="field-label">slow-alert threshold</span>
                <span class="input-wrap">
                    <input
                        v-model.number="form.slowResponseThresholdMs"
                        type="number"
                        class="input"
                        min="0"
                        placeholder="leave empty to disable"
                    >
                    <span class="input-suffix">ms</span>
                </span>
                <span class="field-help">notify when the response time exceeds this for a streak of probes. leave empty to disable.</span>
            </label>
            <label class="field flex-1">
                <span class="field-label">consecutive probes</span>
                <input
                    v-model.number="form.slowResponseConsecutive"
                    type="number"
                    class="input"
                    min="1"
                    :disabled="!form.slowResponseThresholdMs"
                >
                <span class="field-help">how many slow probes in a row before firing. defaults to 3.</span>
            </label>
        </div>

        <!-- Description -->
        <label class="field">
            <span class="field-label">description</span>
            <textarea
                v-model="form.description"
                class="input textarea"
                rows="2"
                placeholder="optional notes about this monitor"
            ></textarea>
        </label>

        <!-- HTTP-specific advanced settings -->
        <template v-if="form.type === 'http'">
            <div class="section-divider">
                <span class="section-divider-label">HTTP</span>
            </div>

            <div class="field-row">
                <label class="field flex-1">
                    <span class="field-label">method</span>
                    <select v-model="form.method" class="input">
                        <option value="GET">GET</option>
                        <option value="HEAD">HEAD</option>
                        <option value="POST">POST</option>
                        <option value="PUT">PUT</option>
                        <option value="PATCH">PATCH</option>
                        <option value="DELETE">DELETE</option>
                        <option value="OPTIONS">OPTIONS</option>
                    </select>
                </label>
                <label class="field flex-1">
                    <span class="field-label">max redirects</span>
                    <input
                        v-model.number="form.maxredirects"
                        type="number"
                        class="input"
                        min="0"
                    >
                </label>
            </div>

            <label v-if="bodyAllowed" class="field">
                <span class="field-label">request body</span>
                <textarea
                    v-model="form.body"
                    class="input textarea code-textarea"
                    rows="4"
                    placeholder="{ &quot;key&quot;: &quot;value&quot; }"
                ></textarea>
                <span class="field-help">raw request body. for json, set <code>Content-Type: application/json</code> in headers below.</span>
            </label>

            <label class="field">
                <span class="field-label">custom headers</span>
                <textarea
                    v-model="form.headersText"
                    class="input textarea code-textarea"
                    rows="3"
                    placeholder="Authorization: Bearer token&#10;Content-Type: application/json"
                ></textarea>
                <span class="field-help">one header per line in <code>Key: Value</code> format. blank lines and lines starting with <code>#</code> are ignored.</span>
            </label>

            <div class="field">
                <span class="field-label">accepted status codes</span>
                <div class="chips-input">
                    <span
                        v-for="code in form.acceptedStatuscodes"
                        :key="code"
                        class="chip"
                    >
                        <span class="chip-label">{{ code }}</span>
                        <button
                            type="button"
                            class="chip-remove"
                            :aria-label="`Remove ${code}`"
                            @click="removeCode(code)"
                        >×</button>
                    </span>
                    <input
                        v-model="codeDraft"
                        type="text"
                        class="chip-input"
                        placeholder="200, 200-299, …"
                        @keydown="onCodeKeydown"
                        @blur="commitCode"
                    >
                </div>
                <span class="field-help">single codes (e.g. <code>204</code>) or ranges (<code>200-299</code>). press enter to add.</span>
            </div>

            <div class="section-divider">
                <span class="section-divider-label">TLS</span>
            </div>

            <!-- Full 3-way mode (edit) — supports presented_ca pinning -->
            <div v-if="tlsMode === 'full'" class="field">
                <span class="field-label">verification</span>
                <div class="seg" role="radiogroup" aria-label="TLS verification mode">
                    <button
                        type="button"
                        class="seg-option"
                        :class="{ active: form.tlsVerifyMode === 'system' }"
                        role="radio"
                        :aria-checked="form.tlsVerifyMode === 'system' ? 'true' : 'false'"
                        :disabled="tlsTrusting"
                        @click="setTlsMode('system')"
                    >
                        <span class="seg-dot tone-up"></span>
                        <span class="seg-body">
                            <span class="seg-title">system trust</span>
                            <span class="seg-help">verify with the OS CA bundle (default).</span>
                        </span>
                    </button>
                    <button
                        type="button"
                        class="seg-option"
                        :class="{ active: form.tlsVerifyMode === 'presented_ca' }"
                        role="radio"
                        :aria-checked="form.tlsVerifyMode === 'presented_ca' ? 'true' : 'false'"
                        :disabled="tlsTrusting"
                        @click="setTlsMode('presented_ca')"
                    >
                        <span class="seg-dot tone-maintenance"></span>
                        <span class="seg-body">
                            <span class="seg-title">trust presented certificate</span>
                            <span class="seg-help">pin the cert chain currently served by the host. handles enterprise proxies that re-sign certs.</span>
                        </span>
                        <span v-if="tlsTrusting" class="seg-trusting">pinning…</span>
                    </button>
                    <button
                        type="button"
                        class="seg-option"
                        :class="{ active: form.tlsVerifyMode === 'insecure', danger: true }"
                        role="radio"
                        :aria-checked="form.tlsVerifyMode === 'insecure' ? 'true' : 'false'"
                        :disabled="tlsTrusting"
                        @click="setTlsMode('insecure')"
                    >
                        <span class="seg-dot tone-down"></span>
                        <span class="seg-body">
                            <span class="seg-title">ignore TLS errors</span>
                            <span class="seg-help">skip certificate verification entirely. dangerous in prod.</span>
                        </span>
                    </button>
                </div>
                <span v-if="tlsTrustError" class="field-error">{{ tlsTrustError }}</span>
            </div>

            <div v-if="tlsMode === 'full' && showTrustedCaPanel && form.customCaSha256" class="trust-panel">
                <header class="trust-head">
                    <span class="trust-title">pinned certificate</span>
                    <button type="button" class="trust-clear" @click="clearTrustedCa">clear trust</button>
                </header>
                <dl class="trust-grid">
                    <dt>subject</dt>
                    <dd>{{ form.customCaSubject || "—" }}</dd>
                    <dt>issuer</dt>
                    <dd>{{ form.customCaIssuer || "—" }}</dd>
                    <dt>sha-256</dt>
                    <dd class="mono">{{ form.customCaSha256 }}</dd>
                </dl>
            </div>

            <!-- Simple 2-way toggle (create) — no pinning UI -->
            <div v-if="tlsMode === 'simple'" class="field row-toggle">
                <div class="toggle-text">
                    <span class="field-label">ignore TLS errors</span>
                    <span class="field-help">skip certificate verification — useful for self-signed dev environments, dangerous in prod.</span>
                </div>
                <button
                    type="button"
                    class="toggle"
                    :class="{ on: form.tlsVerifyMode === 'insecure' }"
                    role="switch"
                    :aria-checked="form.tlsVerifyMode === 'insecure' ? 'true' : 'false'"
                    @click="form.tlsVerifyMode = form.tlsVerifyMode === 'insecure' ? 'system' : 'insecure'"
                >
                    <span class="toggle-track"><span class="toggle-thumb"></span></span>
                    <span class="toggle-label">{{ form.tlsVerifyMode === "insecure" ? "ignored" : "verifying" }}</span>
                </button>
            </div>

            <div
                class="field row-toggle"
                :class="{ 'is-disabled': form.tlsVerifyMode === 'insecure' }"
            >
                <div class="toggle-text">
                    <span class="field-label">certificate expiry alert</span>
                    <span class="field-help">notify when the cert is within the threshold of expiring.</span>
                </div>
                <button
                    type="button"
                    class="toggle"
                    :class="{ on: form.expiryNotification && form.tlsVerifyMode !== 'insecure' }"
                    role="switch"
                    :aria-checked="form.expiryNotification ? 'true' : 'false'"
                    :disabled="form.tlsVerifyMode === 'insecure'"
                    @click="form.expiryNotification = !form.expiryNotification"
                >
                    <span class="toggle-track"><span class="toggle-thumb"></span></span>
                    <span class="toggle-label">{{ form.expiryNotification ? "on" : "off" }}</span>
                </button>
            </div>

            <label v-if="form.expiryNotification && form.tlsVerifyMode !== 'insecure'" class="field">
                <span class="field-label">alert threshold</span>
                <span class="input-wrap">
                    <input
                        v-model.number="form.certExpiryThresholdDays"
                        type="number"
                        class="input"
                        min="1"
                    >
                    <span class="input-suffix">days</span>
                </span>
            </label>
        </template>

        <!-- Organization (group + tags) -->
        <div class="section-divider">
            <span class="section-divider-label">organization</span>
        </div>

        <div class="field">
            <span class="field-label">monitor group</span>
            <div class="select-with-action">
                <select v-model.number="form.parent" class="input">
                    <option :value="null">— no group —</option>
                    <option v-for="g in groupOptions" :key="g.id" :value="g.id">
                        {{ g.name }}
                    </option>
                </select>
                <button
                    type="button"
                    class="inline-add"
                    :class="{ active: createGroup.open }"
                    :title="createGroup.open ? 'Cancel' : 'New group'"
                    @click="toggleCreateGroup"
                >
                    <span>{{ createGroup.open ? "×" : "+" }}</span>
                    <span class="inline-add-label">new group</span>
                </button>
            </div>
            <span class="field-help">groups bundle related monitors so they show together on the dashboard.</span>

            <transition name="inline-form">
                <form
                    v-if="createGroup.open"
                    class="inline-form"
                    @submit.prevent="submitNewGroup"
                    @keydown.esc.prevent.stop="toggleCreateGroup"
                >
                    <input
                        v-model="createGroup.name"
                        type="text"
                        class="input"
                        placeholder="group name (e.g. production, internal)"
                        autocomplete="off"
                        required
                    >
                    <div class="inline-form-foot">
                        <span v-if="createGroup.error" class="form-error">{{ createGroup.error }}</span>
                        <button type="button" class="action ghost" :disabled="createGroup.saving" @click="toggleCreateGroup">cancel</button>
                        <button type="submit" class="action primary" :disabled="createGroup.saving || !createGroup.name.trim()">
                            <span v-if="!createGroup.saving">create group</span>
                            <span v-else>creating…</span>
                        </button>
                    </div>
                </form>
            </transition>
        </div>

        <div class="field">
            <span class="field-label">tags</span>
            <div class="tag-list">
                <button
                    v-for="t in allTags"
                    :key="t.id"
                    type="button"
                    class="tag-chip"
                    :class="{ on: form.tagIds.includes(t.id) }"
                    :style="{ '--tag-color': tagColor(t) }"
                    @click="toggleTagSelection(t.id)"
                >
                    <span class="tag-chip-dot"></span>
                    <span class="tag-chip-name">{{ t.name }}</span>
                </button>
                <button
                    type="button"
                    class="tag-chip ghost-chip"
                    :class="{ on: createTag.open }"
                    @click="toggleCreateTag"
                >
                    <span>{{ createTag.open ? "×" : "+" }}</span>
                    <span>{{ createTag.open ? "cancel" : "new tag" }}</span>
                </button>
            </div>

            <transition name="inline-form">
                <form
                    v-if="createTag.open"
                    class="inline-form"
                    @submit.prevent="submitNewTag"
                    @keydown.esc.prevent.stop="toggleCreateTag"
                >
                    <input
                        v-model="createTag.name"
                        type="text"
                        class="input"
                        placeholder="tag name"
                        autocomplete="off"
                        required
                    >
                    <div class="color-picker">
                        <span class="field-label">color</span>
                        <div class="color-swatches">
                            <button
                                v-for="c in tagColors"
                                :key="c"
                                type="button"
                                class="color-swatch"
                                :class="{ on: createTag.color === c }"
                                :style="{ '--swatch': c }"
                                :aria-label="`color ${c}`"
                                @click="createTag.color = c"
                            ></button>
                        </div>
                    </div>
                    <div class="inline-form-foot">
                        <span v-if="createTag.error" class="form-error">{{ createTag.error }}</span>
                        <button type="button" class="action ghost" :disabled="createTag.saving" @click="toggleCreateTag">cancel</button>
                        <button type="submit" class="action primary" :disabled="createTag.saving || !createTag.name.trim()">
                            <span v-if="!createTag.saving">create tag</span>
                            <span v-else>creating…</span>
                        </button>
                    </div>
                </form>
            </transition>
        </div>

        <!-- Notifications -->
        <div class="section-divider">
            <span class="section-divider-label">notifications</span>
        </div>

        <div class="notif-list">
            <button
                v-for="n in notificationOptions"
                :key="n.id"
                type="button"
                class="notif-chip"
                :class="{
                    on: form.notificationIDList.includes(n.id),
                    inactive: !n.active,
                }"
                :disabled="!n.active"
                @click="toggleNotification(n.id)"
            >
                <span class="notif-chip-dot" :class="{ on: form.notificationIDList.includes(n.id) }"></span>
                <span class="notif-chip-name">{{ n.name }}</span>
                <span v-if="!n.active" class="notif-chip-tag">disabled</span>
            </button>
            <button
                type="button"
                class="notif-chip ghost-chip"
                :class="{ on: createNotif.open }"
                @click="toggleCreateNotif"
            >
                <span>{{ createNotif.open ? "×" : "+" }}</span>
                <span>{{ createNotif.open ? "cancel" : "new channel" }}</span>
            </button>
        </div>

        <transition name="inline-form">
            <form
                v-if="createNotif.open"
                class="inline-form notif-form"
                @submit.prevent="submitNewNotif"
                @keydown.esc.prevent.stop="toggleCreateNotif"
            >
                <div class="field-row">
                    <label class="field flex-1">
                        <span class="field-label">type</span>
                        <select v-model="createNotif.type" class="input" @change="onNotifTypeChange">
                            <option v-for="p in notifProviders" :key="p.type" :value="p.type">
                                {{ p.label }}
                            </option>
                        </select>
                    </label>
                    <label class="field flex-2">
                        <span class="field-label">name</span>
                        <input
                            v-model="createNotif.name"
                            type="text"
                            class="input"
                            placeholder="e.g. team-alerts"
                            required
                        >
                    </label>
                </div>
                <label v-for="f in currentNotifFields" :key="f.key" class="field">
                    <span class="field-label">{{ f.label }}<span v-if="f.required" class="req">*</span></span>
                    <input
                        v-model="createNotif.fields[f.key]"
                        :type="f.secret ? 'password' : 'text'"
                        class="input"
                        :placeholder="f.placeholder || ''"
                        :required="f.required"
                        autocomplete="off"
                    >
                </label>
                <div class="inline-form-foot">
                    <span v-if="createNotif.error" class="form-error">{{ createNotif.error }}</span>
                    <button type="button" class="action ghost" :disabled="createNotif.saving" @click="toggleCreateNotif">cancel</button>
                    <button type="submit" class="action primary" :disabled="!canSubmitNewNotif">
                        <span v-if="!createNotif.saving">create channel</span>
                        <span v-else>creating…</span>
                    </button>
                </div>
            </form>
        </transition>

        <!-- Active toggle (edit only) -->
        <div v-if="showActiveToggle" class="field row-toggle">
            <div class="toggle-text">
                <span class="field-label">monitor active</span>
                <span class="field-help">running monitors fire probes on every interval. paused monitors stop entirely.</span>
            </div>
            <button
                type="button"
                class="toggle"
                :class="{ on: form.active }"
                role="switch"
                :aria-checked="form.active ? 'true' : 'false'"
                @click="form.active = !form.active"
            >
                <span class="toggle-track"><span class="toggle-thumb"></span></span>
                <span class="toggle-label">{{ form.active ? "running" : "paused" }}</span>
            </button>
        </div>
    </div>
</template>

<script>
// MonitorFields intentionally mutates the parent's reactive `form` object
// to keep the API ergonomic — Vue 3 reactivity propagates property
// mutations on shared object references, so a v-model-per-field roundtrip
// would be both noisier and slower. Disable the rule file-wide rather
// than per-line.
/* eslint-disable vue/no-mutating-props */

// Predefined tag colors. Matches the palette v1's tag picker uses so a
// v2-created tag looks indistinguishable in either UI.
export const TAG_COLORS = [
    "hsl(0 84% 60%)",
    "hsl(28 92% 55%)",
    "hsl(48 92% 55%)",
    "hsl(142 71% 45%)",
    "hsl(174 72% 45%)",
    "hsl(217 91% 60%)",
    "hsl(265 78% 60%)",
    "hsl(330 75% 60%)",
    "hsl(0 0% 50%)",
];

// Notification provider catalog. Each entry lists the minimum required
// fields for native creation. Add an entry to wire up another provider.
export const NOTIF_PROVIDERS = [
    { type: "discord",
        label: "Discord",
        fields: [
            { key: "webhookUrl",
                label: "Webhook URL",
                placeholder: "https://discord.com/api/webhooks/…",
                required: true }
        ] },
    { type: "slack",
        label: "Slack",
        fields: [
            { key: "slackwebhookURL",
                label: "Webhook URL",
                placeholder: "https://hooks.slack.com/services/…",
                required: true }
        ] },
    { type: "teams",
        label: "Microsoft Teams",
        fields: [
            { key: "webhookUrl",
                label: "Webhook URL",
                placeholder: "https://outlook.office.com/webhook/…",
                required: true }
        ] },
    { type: "telegram",
        label: "Telegram",
        fields: [
            { key: "botToken",
                label: "Bot token",
                placeholder: "123456:ABC-DEF…",
                required: true,
                secret: true },
            { key: "chatId",
                label: "Chat ID",
                placeholder: "-1001234567890",
                required: true }
        ] },
    { type: "ntfy",
        label: "ntfy",
        fields: [
            { key: "ntfyserverurl",
                label: "Server URL",
                placeholder: "https://ntfy.sh",
                required: true },
            { key: "ntfytopic",
                label: "Topic",
                placeholder: "alerts",
                required: true }
        ] },
    { type: "pagerduty",
        label: "PagerDuty",
        fields: [
            { key: "pagerdutyIntegrationKey",
                label: "Integration key",
                required: true,
                secret: true }
        ] },
    { type: "grafana-oncall",
        label: "Grafana OnCall",
        fields: [
            { key: "url",
                label: "Webhook URL",
                placeholder: "https://oncall.grafana.com/integrations/v1/…",
                required: true }
        ] },
    { type: "twilio",
        label: "Twilio (SMS)",
        fields: [
            { key: "accountSid",
                label: "Account SID",
                placeholder: "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                required: true },
            { key: "authToken",
                label: "Auth token",
                required: true,
                secret: true },
            { key: "fromNumber",
                label: "From number",
                placeholder: "+15551234567",
                required: true },
            { key: "toNumber",
                label: "To number",
                placeholder: "+15557654321",
                required: true }
        ] },
];

export default {
    name: "MonitorFields",
    props: {
        // The form state. Mutated in place — the parent owns the object,
        // we just write into its fields. Vue 3 reactivity propagates the
        // changes without needing a v-model emit per keystroke.
        form: {
            type: Object,
            required: true,
        },
        // The source monitor for edit, used only for: 1) deriving pushUrl
        // (push monitors only have a token after save), 2) excluding self
        // from groupOptions. Pass null on create.
        monitor: {
            type: Object,
            default: null,
        },
        mode: {
            type: String,
            required: true,
            validator: (v) => [ "create", "edit" ].includes(v),
        },
        // "simple" hides presented_ca and the trust panel (used on create
        // because pinning needs a saved monitor to connect to). "full"
        // shows the 3-way segmented control + trust panel.
        tlsMode: {
            type: String,
            default: "full",
            validator: (v) => [ "simple", "full" ].includes(v),
        },
        showActiveToggle: {
            type: Boolean,
            default: false,
        },
        namePlaceholder: {
            type: String,
            default: "",
        },
    },
    data() {
        return {
            codeDraft: "",
            allTags: [],
            createGroup: { open: false,
                name: "",
                saving: false,
                error: null },
            createTag: { open: false,
                name: "",
                color: TAG_COLORS[0],
                saving: false,
                error: null },
            createNotif: this.emptyNotifDraft(),
            tlsTrusting: false,
            tlsTrustError: null,
            copied: false,
            copiedTimer: null,
        };
    },
    computed: {
        bodyAllowed() {
            return this.form.type === "http"
                && [ "POST", "PUT", "PATCH", "DELETE" ].includes(this.form.method);
        },
        groupOptions() {
            const list = Object.values(this.$root.monitorList || {});
            const selfId = this.monitor?.id;
            return list
                .filter(m => m && m.type === "group" && m.id !== selfId)
                .sort((a, b) => (a.name || "").localeCompare(b.name || ""));
        },
        notificationOptions() {
            const list = this.$root.notificationList || [];
            return Array.isArray(list) ? list : [];
        },
        pushUrl() {
            const m = this.monitor;
            if (!m || m.type !== "push" || !m.pushToken) {
                return "";
            }
            const base = this.$root.baseURL
                || (typeof window !== "undefined" ? window.location.origin : "");
            return `${base}/api/push/${m.pushToken}?status=up&msg=OK&ping=`;
        },
        showTrustedCaPanel() {
            return this.form.type === "http"
                && this.form.tlsVerifyMode === "presented_ca";
        },
        tagColors() {
            return TAG_COLORS;
        },
        notifProviders() {
            return NOTIF_PROVIDERS;
        },
        currentNotifFields() {
            const provider = NOTIF_PROVIDERS.find(p => p.type === this.createNotif.type);
            return provider?.fields || [];
        },
        canSubmitNewNotif() {
            if (this.createNotif.saving) {
                return false;
            }
            if (!this.createNotif.name?.trim() || !this.createNotif.type) {
                return false;
            }
            return this.currentNotifFields.every(f => {
                if (!f.required) {
                    return true;
                }
                const val = this.createNotif.fields?.[f.key];
                return typeof val === "string" && val.trim();
            });
        },
    },
    mounted() {
        this.fetchTags();
    },
    beforeUnmount() {
        clearTimeout(this.copiedTimer);
    },
    methods: {
        emptyNotifDraft() {
            return {
                open: false,
                type: "discord",
                name: "",
                fields: {},
                saving: false,
                error: null,
            };
        },
        tagColor(tag) {
            const c = tag?.color;
            if (typeof c === "string" && c.trim()) {
                return c;
            }
            return "hsl(0 0% 38%)";
        },
        async fetchTags() {
            try {
                const { data } = await this.$root.api.get("/tags");
                if (Array.isArray(data)) {
                    this.allTags = data;
                } else if (Array.isArray(data?.tags)) {
                    this.allTags = data.tags;
                }
            } catch (e) {
                console.warn("could not load tag list", e);
            }
        },
        toggleTagSelection(tagId) {
            const set = new Set(this.form.tagIds);
            if (set.has(tagId)) {
                set.delete(tagId);
            } else {
                set.add(tagId);
            }
            this.form.tagIds = Array.from(set);
        },
        toggleNotification(id) {
            const set = new Set(this.form.notificationIDList);
            if (set.has(id)) {
                set.delete(id);
            } else {
                set.add(id);
            }
            this.form.notificationIDList = Array.from(set);
        },
        onCodeKeydown(e) {
            if (e.key === "Enter" || e.key === ",") {
                e.preventDefault();
                this.commitCode();
            } else if (e.key === "Backspace" && !this.codeDraft && this.form.acceptedStatuscodes.length > 0) {
                e.preventDefault();
                const next = [ ...this.form.acceptedStatuscodes ];
                next.pop();
                this.form.acceptedStatuscodes = next;
            }
        },
        commitCode() {
            const v = this.codeDraft.trim().replace(/,$/, "");
            if (!v) {
                this.codeDraft = "";
                return;
            }
            if (!/^\d{3}(-\d{3})?$/.test(v)) {
                return;
            }
            if (!this.form.acceptedStatuscodes.includes(v)) {
                this.form.acceptedStatuscodes = [ ...this.form.acceptedStatuscodes, v ];
            }
            this.codeDraft = "";
        },
        removeCode(code) {
            this.form.acceptedStatuscodes = this.form.acceptedStatuscodes.filter(c => c !== code);
        },
        toggleCreateGroup() {
            this.createGroup.open = !this.createGroup.open;
            if (!this.createGroup.open) {
                this.createGroup.name = "";
                this.createGroup.error = null;
            }
        },
        async submitNewGroup() {
            const name = this.createGroup.name?.trim();
            if (!name) {
                return;
            }
            this.createGroup.saving = true;
            this.createGroup.error = null;
            try {
                const res = await this.$root.addMonitor({
                    type: "group",
                    name,
                    interval: 60,
                    active: true,
                });
                if (!res?.ok) {
                    this.createGroup.error = res?.msg || "could not create group";
                    return;
                }
                if (res.monitorID != null) {
                    this.form.parent = res.monitorID;
                }
                this.createGroup.open = false;
                this.createGroup.name = "";
            } catch (e) {
                this.createGroup.error = e?.response?.data?.detail || e?.message || "request failed";
            } finally {
                this.createGroup.saving = false;
            }
        },
        toggleCreateTag() {
            this.createTag.open = !this.createTag.open;
            if (!this.createTag.open) {
                this.createTag.name = "";
                this.createTag.color = TAG_COLORS[0];
                this.createTag.error = null;
            }
        },
        async submitNewTag() {
            const name = this.createTag.name?.trim();
            if (!name) {
                return;
            }
            this.createTag.saving = true;
            this.createTag.error = null;
            try {
                const { data } = await this.$root.api.post("/tags", {
                    name,
                    color: this.createTag.color,
                });
                const tag = data?.tag || data;
                if (!tag || !tag.id) {
                    this.createTag.error = data?.msg || "could not create tag";
                    return;
                }
                this.allTags = [ ...this.allTags, tag ];
                if (!this.form.tagIds.includes(tag.id)) {
                    this.form.tagIds = [ ...this.form.tagIds, tag.id ];
                }
                this.createTag.open = false;
                this.createTag.name = "";
                this.createTag.color = TAG_COLORS[0];
            } catch (e) {
                this.createTag.error = e?.response?.data?.detail || e?.message || "request failed";
            } finally {
                this.createTag.saving = false;
            }
        },
        toggleCreateNotif() {
            if (this.createNotif.open) {
                Object.assign(this.createNotif, this.emptyNotifDraft());
            } else {
                this.createNotif.open = true;
            }
        },
        onNotifTypeChange() {
            this.createNotif.fields = {};
            this.createNotif.error = null;
        },
        async submitNewNotif() {
            if (!this.canSubmitNewNotif) {
                return;
            }
            this.createNotif.saving = true;
            this.createNotif.error = null;
            try {
                const payload = {
                    name: this.createNotif.name.trim(),
                    type: this.createNotif.type,
                    active: true,
                    is_default: false,
                    config: { ...this.createNotif.fields },
                };
                const { data } = await this.$root.api.post("/notifications", payload);
                if (!data?.ok && !data?.id && !data?.notificationID) {
                    this.createNotif.error = data?.msg || "could not create channel";
                    return;
                }
                if (typeof this.$root.loadNotifications === "function") {
                    await this.$root.loadNotifications();
                }
                const newId = data?.id ?? data?.notificationID ?? data?.notification?.id;
                if (newId != null && !this.form.notificationIDList.includes(newId)) {
                    this.form.notificationIDList = [ ...this.form.notificationIDList, newId ];
                }
                Object.assign(this.createNotif, this.emptyNotifDraft());
            } catch (e) {
                this.createNotif.error = e?.response?.data?.detail || e?.message || "request failed";
            } finally {
                this.createNotif.saving = false;
            }
        },
        async setTlsMode(mode) {
            if (this.form.tlsVerifyMode === mode || this.tlsTrusting) {
                return;
            }
            this.tlsTrustError = null;
            if (mode !== "presented_ca") {
                this.form.tlsVerifyMode = mode;
                return;
            }
            // Switching INTO presented_ca pins the chain server-side. Skip
            // the call if we already have a pinned cert (user toggled away
            // and back without saving in between).
            if (this.form.customCaSha256) {
                this.form.tlsVerifyMode = mode;
                return;
            }
            const monitorId = this.monitor?.id;
            if (!monitorId) {
                this.tlsTrustError = "save the monitor first, then pin its certificate";
                return;
            }
            this.tlsTrusting = true;
            try {
                const { data } = await this.$root.api.post(
                    `/monitors/${monitorId}/trust-presented-ca`,
                );
                if (data?.ok) {
                    this.form.customCaSubject = data.subject || null;
                    this.form.customCaIssuer = data.issuer || null;
                    this.form.customCaSha256 = data.sha256 || null;
                    this.form.tlsVerifyMode = "presented_ca";
                } else {
                    this.tlsTrustError = data?.msg || "could not pin presented certificate";
                }
            } catch (e) {
                const detail = e?.response?.data?.detail
                    || e?.response?.data?.msg
                    || e?.message
                    || "";
                this.tlsTrustError = `couldn't pin certificate: ${detail || "request failed"}`;
            } finally {
                this.tlsTrusting = false;
            }
        },
        async clearTrustedCa() {
            const monitorId = this.monitor?.id;
            if (!monitorId) {
                return;
            }
            try {
                await this.$root.api.post(`/monitors/${monitorId}/clear-trusted-ca`);
                this.form.tlsVerifyMode = "system";
                this.form.customCaSubject = null;
                this.form.customCaIssuer = null;
                this.form.customCaSha256 = null;
                this.tlsTrustError = null;
            } catch (e) {
                console.warn("could not clear trusted CA", e);
            }
        },
        async copyPushUrl() {
            if (!this.pushUrl) {
                return;
            }
            try {
                await navigator.clipboard?.writeText?.(this.pushUrl);
                this.copied = true;
                clearTimeout(this.copiedTimer);
                this.copiedTimer = setTimeout(() => {
                    this.copied = false;
                }, 1500);
            } catch (e) {
                console.warn("clipboard write failed", e);
            }
        },
    },
};
</script>

<style lang="scss" scoped>
@import "./_base.scss";

.monitor-fields {
    display: flex;
    flex-direction: column;
    gap: 18px;
}

.field {
    display: flex;
    flex-direction: column;
    gap: 6px;

    .req {
        color: hsl(0 84% 60%);
        margin-left: 2px;
    }
}

.field-row {
    display: flex;
    gap: 12px;

    .field { flex: 1; }
    .flex-2 { flex: 2; }
    .flex-1 { flex: 1; }
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
    margin-top: 4px;
    line-height: 1.5;

    code {
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 10.5px;
        padding: 1px 5px;
        background: var(--bg-soft);
        border: 1px solid var(--border);
        border-radius: 4px;
        color: var(--text-muted);
    }
}

.field-error {
    font-size: 12px;
    color: hsl(0 84% 65%);
    margin-top: 4px;
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
    transition: border-color 140ms ease, background 140ms ease,
        box-shadow 140ms ease;

    &::placeholder { color: var(--text-faint); }
    &:hover { border-color: var(--border-strong); }
    &:focus {
        outline: none;
        background: var(--bg-hover);
        border-color: hsl(142 71% 45%);
        box-shadow: 0 0 0 3px hsl(142 71% 45% / 0.15);
    }

    &.textarea {
        resize: vertical;
        min-height: 60px;
    }
}

.input-wrap {
    position: relative;
    display: flex;
    align-items: center;

    .input {
        flex: 1;
        padding-right: 76px;
    }

    .input-suffix {
        position: absolute;
        right: 12px;
        font-size: 12px;
        color: var(--text-faint);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        pointer-events: none;
    }
}

.code-textarea {
    font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
        Monaco, Consolas, monospace;
    font-size: 12.5px;
    min-height: 80px;
}

.section-divider {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 12px 0 -2px;
    color: var(--text-faint);

    &::before,
    &::after {
        content: "";
        flex: 1;
        height: 1px;
        background: var(--border);
    }

    .section-divider-label {
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.18em;
        font-weight: 600;
    }
}

.row-toggle {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;
    gap: 16px;

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

.chips-input {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px;
    min-height: 42px;
    transition: border-color 140ms ease, background 140ms ease,
        box-shadow 140ms ease;

    &:focus-within {
        background: var(--bg-hover);
        border-color: hsl(142 71% 45%);
        box-shadow: 0 0 0 3px hsl(142 71% 45% / 0.15);
    }
}

.chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 4px 3px 10px;
    background: hsl(142 71% 45% / 0.14);
    border: 1px solid hsl(142 71% 45% / 0.32);
    border-radius: 999px;
    font-size: 12px;
    color: hsl(142 71% 75%);
    font-variant-numeric: tabular-nums;
    line-height: 1;

    .chip-label { padding-right: 2px; }

    .chip-remove {
        appearance: none;
        background: transparent;
        border: none;
        color: inherit;
        font-size: 14px;
        line-height: 1;
        padding: 0;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        cursor: pointer;
        opacity: 0.75;

        &:hover {
            opacity: 1;
            background: hsl(142 71% 45% / 0.25);
        }
    }
}

.chip-input {
    appearance: none;
    flex: 1;
    min-width: 140px;
    background: transparent;
    border: none;
    color: var(--text);
    font-size: 13px;
    font-family: inherit;
    padding: 4px 6px;

    &::placeholder { color: var(--text-faint); }
    &:focus { outline: none; }
}

.seg {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.seg-option {
    appearance: none;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
    color: var(--text-muted);
    font-family: inherit;
    text-align: left;
    cursor: pointer;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    transition: background 140ms ease, border-color 140ms ease, color 140ms ease;

    &:hover:not(:disabled) {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        color: var(--text);
    }

    &:disabled {
        opacity: 0.55;
        cursor: not-allowed;
    }

    &.active {
        border-color: hsl(142 71% 45% / 0.55);
        background: hsl(142 71% 45% / 0.08);
        color: var(--text);

        &.danger {
            border-color: hsl(0 84% 60% / 0.55);
            background: hsl(0 84% 60% / 0.08);
        }
    }

    .seg-dot {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        margin-top: 5px;
        flex: none;
        background: hsl(0 0% 40%);

        &.tone-up { background: hsl(142 71% 45%); }
        &.tone-down { background: hsl(0 84% 60%); }
        &.tone-maintenance { background: hsl(217 91% 60%); }
    }

    .seg-body {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 3px;
    }

    .seg-title {
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-weight: 600;
    }

    .seg-help {
        font-size: 12px;
        color: var(--text-faint);
        line-height: 1.5;
    }

    .seg-trusting {
        align-self: center;
        font-size: 11px;
        color: var(--text-muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        animation: v2-fade-in 220ms ease both;
    }
}

.trust-panel {
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-left: 3px solid hsl(217 91% 60% / 0.6);
    border-radius: 10px;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;

    .trust-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .trust-title {
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--text-muted);
        font-weight: 600;
    }

    .trust-clear {
        appearance: none;
        background: transparent;
        border: 1px solid hsl(0 84% 60% / 0.4);
        color: hsl(0 84% 65%);
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        cursor: pointer;
        transition: background 140ms ease, color 140ms ease, border-color 140ms ease;

        &:hover {
            background: hsl(0 84% 60% / 0.12);
            border-color: hsl(0 84% 60% / 0.7);
            color: hsl(0 84% 75%);
        }
    }

    .trust-grid {
        display: grid;
        grid-template-columns: 78px 1fr;
        gap: 4px 14px;
        margin: 0;

        dt {
            font-size: 10.5px;
            color: var(--text-faint);
            text-transform: uppercase;
            letter-spacing: 0.1em;
            padding-top: 1px;
        }

        dd {
            margin: 0;
            font-size: 12.5px;
            color: var(--text);
            overflow-wrap: anywhere;

            &.mono {
                font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono",
                    Menlo, Monaco, Consolas, monospace;
                font-size: 11.5px;
                color: var(--text-muted);
            }
        }
    }
}

.push-token {
    background: hsl(217 91% 60% / 0.06);
    border: 1px solid hsl(217 91% 60% / 0.22);
    border-radius: 10px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.push-token-row {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 8px 8px 8px 12px;

    .push-token-value {
        flex: 1;
        font-family: ui-monospace, "SFMono-Regular", "JetBrains Mono", Menlo,
            Monaco, Consolas, monospace;
        font-size: 12px;
        color: var(--text);
        white-space: nowrap;
        overflow-x: auto;
        overscroll-behavior-x: contain;
    }

    .copy-btn { flex: none; }
}

.push-help {
    margin: 0;
    font-size: 12px;
    color: var(--text-muted);
    line-height: 1.5;
}

.push-info {
    padding: 14px 16px;
    background: hsl(217 91% 60% / 0.08);
    border: 1px solid hsl(217 91% 60% / 0.25);
    border-radius: 10px;
    color: var(--text-muted);
    font-size: 13px;

    .push-info-line { margin: 0; }
    .push-info-line + .push-info-line { margin-top: 4px; }
}

.select-with-action {
    display: flex;
    gap: 6px;
    align-items: stretch;

    .input { flex: 1; }
}

.inline-add {
    appearance: none;
    background: hsl(142 71% 45% / 0.10);
    border: 1px solid hsl(142 71% 45% / 0.4);
    color: hsl(142 71% 70%);
    border-radius: 8px;
    padding: 0 12px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: background 140ms ease, border-color 140ms ease, color 140ms ease;

    &:hover {
        background: hsl(142 71% 45% / 0.18);
        border-color: hsl(142 71% 45% / 0.6);
        color: hsl(142 71% 80%);
    }

    &.active {
        background: hsl(0 0% 14%);
        border-color: var(--border-strong);
        color: var(--text);
    }

    .inline-add-label { font-weight: 600; }
}

.inline-form {
    margin-top: 10px;
    padding: 14px;
    background: var(--bg-soft);
    border: 1px solid var(--border-strong);
    border-radius: 10px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    transform-origin: top center;
}

.inline-form.notif-form {
    border-color: hsl(217 91% 60% / 0.35);
    background: hsl(217 91% 60% / 0.04);
}

.inline-form-foot {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 8px;
    margin-top: 4px;

    .form-error {
        flex: 1;
        text-align: left;
        font-size: 12px;
        color: hsl(0 84% 65%);
    }
}

.inline-form-enter-active,
.inline-form-leave-active {
    transition: opacity 200ms $v2-ease, transform 200ms $v2-ease,
        max-height 220ms $v2-ease;
    max-height: 600px;
    overflow: hidden;
}

.inline-form-enter-from,
.inline-form-leave-to {
    opacity: 0;
    transform: translateY(-6px);
    max-height: 0;
}

.color-picker {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

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
    transition: transform 140ms ease, border-color 140ms ease,
        box-shadow 140ms ease;

    &:hover { transform: scale(1.08); }

    &.on {
        border-color: var(--text);
        box-shadow: 0 0 0 2px var(--bg) inset, 0 0 0 1px var(--border) inset;
        transform: scale(1.08);
    }
}

.tag-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.tag-chip {
    --tag-color: hsl(0 0% 38%);

    appearance: none;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px 6px 10px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--text-muted);
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
    transition: background 140ms ease, border-color 140ms ease, color 140ms ease;

    &:hover:not(:disabled) {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        color: var(--text);
    }

    &.on {
        background: color-mix(in oklab, var(--tag-color) 18%, var(--bg-soft));
        border-color: var(--tag-color);
        color: var(--text);
    }

    .tag-chip-dot {
        width: 9px;
        height: 9px;
        border-radius: 2px;
        background: var(--tag-color);
    }

    .tag-chip-name { font-weight: 500; }
}

.notif-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.notif-chip {
    appearance: none;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px 6px 8px;
    background: var(--bg-soft);
    border: 1px solid var(--border);
    border-radius: 999px;
    color: var(--text-muted);
    font-size: 12px;
    cursor: pointer;
    font-family: inherit;
    transition: background 140ms ease, border-color 140ms ease, color 140ms ease;

    &:hover:not(:disabled) {
        background: var(--bg-hover);
        border-color: var(--border-strong);
        color: var(--text);
    }

    &.on {
        background: hsl(142 71% 45% / 0.16);
        border-color: hsl(142 71% 45% / 0.5);
        color: hsl(142 71% 80%);
    }

    &:disabled {
        opacity: 0.45;
        cursor: not-allowed;
    }

    .notif-chip-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: hsl(0 0% 28%);
        transition: background 140ms ease;
    }

    .notif-chip-dot.on { background: hsl(142 71% 55%); }

    .notif-chip-tag {
        font-size: 9.5px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        padding: 2px 5px;
        border-radius: 4px;
        background: hsl(0 0% 14%);
        border: 1px solid var(--border);
    }
}

.ghost-chip {
    background: transparent !important;
    border-style: dashed !important;
    border-color: var(--border-strong) !important;
    color: var(--text-muted) !important;

    &:hover {
        border-style: solid !important;
        background: var(--bg-soft) !important;
        color: var(--text) !important;
    }

    &.on {
        background: var(--bg-soft) !important;
        border-style: solid !important;
        border-color: var(--text-faint) !important;
        color: var(--text) !important;
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

@media (max-width: 760px) {
    .field-row { flex-direction: column; }
}
</style>
