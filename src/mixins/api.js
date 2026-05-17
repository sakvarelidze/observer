import axios from "axios";
import { router } from "../router";
import { getResBaseURL } from "../util-frontend";
// Keep keys in snake_case only if the frontend expects them as such
// `accepted_statuscodes` is used directly by the UI, so do not convert it
const KEEP_SNAKE_CASE = new Set([
    "accepted_statuscodes",
    "dns_resolve_type",
    "dns_resolve_server",
    "basic_auth_user",
    "basic_auth_pass",
    "oauth_auth_method",
    "oauth_token_url",
    "oauth_client_id",
    "oauth_client_secret",
    "oauth_scopes",
    "remote_browser",
    "manual_status",
]);

export default {
    data() {
        return {
            api: axios.create({
                baseURL: getResBaseURL() + "/api",
            }),
            token: localStorage.getItem("token") || null,
            username: localStorage.getItem("username") || null,
        };
    },
    created() {
        // Auto-convert all API responses to camelCase so individual components
        // don't need to remember to call camelCaseKeys()
        this.api.interceptors.response.use((resp) => {
            if (resp.data && typeof resp.data === "object") {
                let data = this.camelCaseKeysDeep(resp.data);
                data = this.normalizeDeepBooleans(data);
                this.ensureTrustedCAConsistency(data);
                resp.data = data;
            }
            return resp;
        }, (error) => {
            if (error.response && error.response.status === 401) {
                this.logout();
                router.push("/login");
            }
            return Promise.reject(error);
        });
        if (this.token) {
            this.api.defaults.headers.common["Authorization"] = `Bearer ${this.token}`;
        }
    },
    computed: {
        loggedIn() {
            return !!this.token;
        },
    },
    watch: {
        token(newToken) {
            if (newToken) {
                localStorage.setItem("token", newToken);
                this.api.defaults.headers.common["Authorization"] = `Bearer ${newToken}`;
            } else {
                localStorage.removeItem("token");
                delete this.api.defaults.headers.common["Authorization"];
            }
        },
        username(name) {
            if (name) {
                localStorage.setItem("username", name);
            } else {
                localStorage.removeItem("username");
            }
        },
    },
    methods: {
        async login(username, password, token) {
            const payload = {
                username,
                password,
            };
            if (token !== undefined) {
                payload.token = token;
            }
            const res = await this.api.post("/login", payload);
            this.token = res.data.token;
            this.username = username;
            this.api.defaults.headers.common["Authorization"] = `Bearer ${this.token}`;
            return res.data;
        },
        logout() {
            this.token = null;
            this.username = null;
        },
        camelCaseKeys(obj) {
            const newObj = {};
            for (const [ k, v ] of Object.entries(obj)) {
                let camelKey = KEEP_SNAKE_CASE.has(k)
                    ? k
                    : k.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
                // normalize legacy Discord field
                if (camelKey === "discordWebhookUrl") {
                    camelKey = "webhookUrl";
                }
                newObj[camelKey] = v;
            }
            return this.normalizeDeepBooleans(newObj);
        },

        snakeCaseKeys(obj) {
            const newObj = {};
            for (const [ k, v ] of Object.entries(obj)) {
                let snakeKey = KEEP_SNAKE_CASE.has(k)
                    ? k
                    : k.replace(/([A-Z])/g, "_$1").toLowerCase();
                if (snakeKey === "discord_webhook_url") {
                    snakeKey = "webhook_url";
                }
                newObj[snakeKey] = v;
            }
            return this.normalizeDeepBooleans(newObj);
        },

        sanitizeMaintenance(obj) {
            if (obj && typeof obj === "object" && typeof obj.data === "string") {
                try {
                    const parsed = JSON.parse(obj.data);
                    obj = {
                        ...obj,
                        ...parsed,
                    };
                    delete obj.data;
                } catch (e) {
                    console.warn("Invalid maintenance data", e);
                }
            }
            const result = this.normalizeDeepBooleans(this.camelCaseKeysDeep(obj));
            if (!result.status) {
                result.status = "unknown";
            }
            return result;
        },

        /**
         * Recursively convert all keys in an object or array to camelCase.
         * @param {any} data Data to convert
         * @returns {any} Converted data
         */
        camelCaseKeysDeep(data) {
            if (Array.isArray(data)) {
                return data.map(item => this.camelCaseKeysDeep(item));
            }
            if (data && typeof data === "object") {
                const converted = this.camelCaseKeys(data);
                for (const key of Object.keys(converted)) {
                    converted[key] = this.camelCaseKeysDeep(converted[key]);
                }
                return this.coerceBooleans(converted);
            }
            return this.coerceBooleans(data);
        },

        ensureTrustedCAConsistency(target) {
            const sync = (obj) => {
                if (!obj || typeof obj !== "object") {
                    return;
                }
                if (Array.isArray(obj)) {
                    for (const item of obj) {
                        sync(item);
                    }
                    return;
                }

                const hasSubject = Object.prototype.hasOwnProperty.call(obj, "customCaSubject")
                    || Object.prototype.hasOwnProperty.call(obj, "custom_ca_subject");
                const hasIssuer = Object.prototype.hasOwnProperty.call(obj, "customCaIssuer")
                    || Object.prototype.hasOwnProperty.call(obj, "custom_ca_issuer");
                const hasSha = Object.prototype.hasOwnProperty.call(obj, "customCaSha256")
                    || Object.prototype.hasOwnProperty.call(obj, "custom_ca_sha256");

                if (hasSubject || hasIssuer || hasSha) {
                    const subject = obj.customCaSubject ?? obj.custom_ca_subject ?? null;
                    const issuer = obj.customCaIssuer ?? obj.custom_ca_issuer ?? null;
                    const sha256 = obj.customCaSha256 ?? obj.custom_ca_sha256 ?? null;

                    obj.customCaSubject = subject;
                    obj.custom_ca_subject = subject;
                    obj.customCaIssuer = issuer;
                    obj.custom_ca_issuer = issuer;
                    obj.customCaSha256 = sha256;
                    obj.custom_ca_sha256 = sha256;
                }

                for (const key of Object.keys(obj)) {
                    sync(obj[key]);
                }
            };

            sync(target);
            return target;
        },

        /**
         * Convert boolean-like string values into real booleans.
         * Numeric values are left untouched so IDs are not affected.
         * @param {any} value Any value to convert
         * @returns {any} Converted value
         */
        coerceBooleans(value) {
            if (Array.isArray(value)) {
                return value.map(v => this.coerceBooleans(v));
            }
            if (value && typeof value === "object") {
                for (const k of Object.keys(value)) {
                    value[k] = this.coerceBooleans(value[k]);
                }
                return value;
            }
            if (typeof value === "string") {
                const lower = value.toLowerCase();
                if (lower === "true") {
                    return true;
                }
                if (lower === "false") {
                    return false;
                }
                if (/^-?\d+$/.test(value)) {
                    const num = Number(value);
                    return isNaN(num) ? value : num;
                }
            }
            return value;
        },

        /**
         * Prepare data for API submission.
         * Converts any legacy snake_case keys to camelCase and
         * normalizes boolean fields so the backend receives the
         * expected values.
         * @param {object} obj Object to convert
         * @returns {object} New object ready for the backend
         */
        toAPIPayload(obj) {
            const src = { ...obj };

            // ---- Begin acronym normalization (avoids webhook_u_r_l etc.) ----
            const normalizeAcronyms = (o) => {
                if (!o || typeof o !== "object") return;
                const renames = [
                    ["notificationIDList", "notificationIdList"],  // already needed elsewhere
                    ["webhookURL", "webhookUrl"],
                    ["WebhookURL", "webhookUrl"],
                    ["URL", "url"],
                    ["SSL", "ssl"],
                    ["TLS", "tls"],
                    ["HTTP", "http"],
                    ["HTTPS", "https"],
                ];
                for (const [from, to] of renames) {
                    if (Object.prototype.hasOwnProperty.call(o, from) && !Object.prototype.hasOwnProperty.call(o, to)) {
                        o[to] = o[from];
                        delete o[from];
                    }
                }
                // recurse shallowly on known nested payloads
                if (o.config && typeof o.config === "object") normalizeAcronyms(o.config);
            };
            normalizeAcronyms(src);
            // ---- End acronym normalization ----

            // Convert the payload to snake_case before sending it to the API
            return this.normalizeBooleans(this.snakeCaseKeys(src));
        },

        normalizeBooleans(obj) {
            const boolKeys = [
                "active",
                "expiryNotification",
                "cacheBust",
                "upsideDown",
                "important",
                "isDefault",
                "invertKeyword",
                "grpcEnableTls",
                "grpc_enable_tls",
            ];
            const boolSet = new Set(boolKeys);
            // ensure all expected boolean flags exist
            for (const flag of boolKeys) {
                if (!(flag in obj)) {
                    obj[flag] = false;
                }
            }
            for (const key in obj) {
                const val = obj[key];
                if (boolSet.has(key) || /^is[A-Z]/.test(key) || /^has[A-Z]/.test(key)) {
                    if (val === true || val === false) {
                        obj[key] = val;
                    } else if (val === 1 || val === "1" || val === "true" || val === "True") {
                        obj[key] = true;
                    } else if (val === 0 || val === "0" || val === "false" || val === "False") {
                        obj[key] = false;
                    } else if (val === null || val === undefined) {
                        obj[key] = false;
                    } else {
                        obj[key] = Boolean(val);
                    }
                }
            }
            if ("pingNumeric" in obj && !("ping_numeric" in obj)) {
                obj.ping_numeric = obj.pingNumeric;
            } else if ("ping_numeric" in obj && !("pingNumeric" in obj)) {
                obj.pingNumeric = obj.ping_numeric;
            }
            return obj;
        },

        async getMonitors() {
            const res = await this.api.get("/monitors");
            const monitors = res.data.monitors || res.data;
            if (Array.isArray(monitors)) {
                return monitors.map(m => {
                    const normalized = this.normalizeDeepBooleans(this.camelCaseKeysDeep(m));
                    this.ensureTrustedCAConsistency(normalized);
                    if (!Array.isArray(normalized.notificationIDList)) {
                        normalized.notificationIDList = Object.keys(normalized.notificationIDList || {})
                            .filter(id => normalized.notificationIDList[id])
                            .map(id => Number(id));
                    }
                    return normalized;
                });
            }
            return res.data;
        },

        async getMonitor(id) {
            // backend expects singular /monitor path
            const res = await this.api.get(`/monitor/${id}`);
            if (res.data.monitor) {
                const normalized = this.normalizeDeepBooleans(this.camelCaseKeysDeep(res.data.monitor));
                this.ensureTrustedCAConsistency(normalized);
                if (!Array.isArray(normalized.notificationIDList)) {
                    normalized.notificationIDList = Object.keys(normalized.notificationIDList || {})
                        .filter(id => normalized.notificationIDList[id])
                        .map(id => Number(id));
                }
                res.data.monitor = normalized;
            }
            return res.data;
        },
        async addMonitor(monitor) {
            monitor = this.toAPIPayload(monitor);
            console.log("Mixin addMonitor payload", monitor);
            const res = await this.api.post("/monitors", monitor);
            console.log("Mixin addMonitor response", res.data);
            return res.data;
        },

        async updateMonitor(id, monitor) {
            monitor = this.toAPIPayload(monitor);
            // backend expects singular /monitor path
            console.log("Mixin updateMonitor payload", monitor);
            const res = await this.api.post(`/monitor/${id}`, monitor);
            console.log("Mixin updateMonitor response", res.data);
            return res.data;
        },
        async getNotifications() {
            const res = await this.api.get("/notifications");
            const list = res.data;
            return list.map(n =>
                this.normalizeDeepBooleans(
                    this.camelCaseKeysDeep(n)
                )
            );
        },

        async getUsers() {
            const res = await this.api.get("/users");
            return res.data;
        },

        async addUser(user) {
            const res = await this.api.post("/users", user);
            return res.data;
        },

        async deactivateUser(id, adminPassword) {
            const res = await this.api.post(`/users/${id}/deactivate`, { adminPassword });
            return res.data;
        },

        async activateUser(id, adminPassword) {
            const res = await this.api.post(`/users/${id}/activate`, { adminPassword });
            return res.data;
        },

        async deleteUser(id, adminPassword) {
            const res = await this.api.delete(`/users/${id}`, { data: { adminPassword } });
            return res.data;
        },

        async changePassword(payload) {
            const res = await this.api.post("/change-password", payload);
            return res.data;
        },

        async getAPIKeys() {
            const res = await this.api.get("/api-keys");
            return res.data;
        },

        async apiAddAPIKey(payload) {
            const res = await this.api.post("/api-keys", payload);
            return res.data;
        },

        async apiDeleteAPIKey(id) {
            const res = await this.api.delete(`/api-keys/${id}`);
            return res.data;
        },

        async apiEnableAPIKey(id) {
            const res = await this.api.post(`/api-keys/${id}/enable`);
            return res.data;
        },

        async apiDisableAPIKey(id) {
            const res = await this.api.post(`/api-keys/${id}/disable`);
            return res.data;
        },
    },
};
