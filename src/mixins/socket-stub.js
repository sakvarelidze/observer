import { useToast } from "vue-toastification";
import mitt from "mitt";
import axios from "axios";

const toast = useToast();
const emitter = mitt();

export default {
    data() {
        return {
            emitter,
        };
    },
    methods: {
        /**
         * Return the current storage (local or session)
         * depending on remember flag.
         * @returns {Storage}
         */
        storage() {
            return this.remember ? localStorage : sessionStorage;
        },

        /**
         * Stub for socket communication.
         * @returns {object} Socket stub
         */
        getSocket() {
            const api = this.api || axios.create({ baseURL: "/api" });
            const root = this;
            const ensureCloudflaredState = () => {
                if (!root.cloudflared) {
                    root.cloudflared = {
                        installed: null,
                        running: false,
                        errorMessage: "",
                        message: "",
                        cloudflareTunnelToken: "",
                        currentPassword: "",
                    };
                }
                return root.cloudflared;
            };
            const updateCloudflared = (payload = {}) => {
                const state = ensureCloudflaredState();
                if (Object.prototype.hasOwnProperty.call(payload, "installed")) {
                    state.installed = payload.installed;
                }
                if (Object.prototype.hasOwnProperty.call(payload, "running")) {
                    state.running = payload.running;
                }
                if (Object.prototype.hasOwnProperty.call(payload, "errorMessage")) {
                    state.errorMessage = payload.errorMessage || "";
                }
                if (Object.prototype.hasOwnProperty.call(payload, "message")) {
                    state.message = payload.message || "";
                }
                if (Object.prototype.hasOwnProperty.call(payload, "token")) {
                    state.cloudflareTunnelToken = payload.token || "";
                }
            };
            return {
                async emit(event, ...args) {
                    const cb = typeof args[args.length - 1] === "function" ? args.pop() : null;
                    try {
                        let res;
                        if (event === "addNotification") {
                            const payload = args[0];
                            const id = args[1];
                            if (id) {
                                res = await api.post(`/notifications/${id}`, payload);
                            } else {
                                res = await api.post("/notifications", payload);
                            }
                        } else if (event === "deleteNotification") {
                            const id = args[0];
                            res = await api.delete(`/notifications/${id}`);
                        } else if (event === "testNotification") {
                            let payload = args[0];
                            payload = root.toAPIPayload ? root.toAPIPayload(payload) : payload;
                            res = await api.post("/notifications/test", payload);
                        } else if (event === "getTags") {
                            res = await api.get("/tags");
                        } else if (event === "addTag") {
                            const payload = args[0];
                            res = await api.post("/tags", payload);
                        } else if (event === "editTag") {
                            const payload = args[0];
                            res = await api.post(`/tags/${payload.id}`, payload);
                        } else if (event === "deleteTag") {
                            const id = args[0];
                            res = await api.delete(`/tags/${id}`);
                        } else if (event === "addMonitorTag") {
                            const tagId = args[0];
                            const monitorId = args[1];
                            const value = args[2];
                            res = await api.post("/monitor-tags", {
                                tagId,
                                monitorId,
                                value,
                            });
                        } else if (event === "deleteMonitorTag") {
                            const tagId = args[0];
                            const monitorId = args[1];
                            const value = args[2] ?? "";
                            const params = new URLSearchParams({
                                tag_id: tagId,
                                monitor_id: monitorId,
                                value,
                            });
                            res = await api.delete(`/monitor-tags?${params.toString()}`);
                        } else if (event === "pauseMonitor") {
                            const id = args[0];
                            res = await api.post(`/monitors/${id}/pause`);
                        } else if (event === "resumeMonitor") {
                            const id = args[0];
                            res = await api.post(`/monitors/${id}/resume`);
                        } else if (event === "changePassword") {
                            const payload = args[0];
                            res = await api.post("/change-password", payload);
                        } else if (event === "disableAPIKey") {
                            const id = args[0];
                            res = await api.post(`/api-keys/${id}/disable`);
                            await root.loadAPIKeys();
                        } else if (event === "enableAPIKey") {
                            const id = args[0];
                            res = await api.post(`/api-keys/${id}/enable`);
                            await root.loadAPIKeys();
                        } else if (event === "getDatabaseSize") {
                            res = { data: { ok: true, size: 0 } };
                        } else if (event === "shrinkDatabase") {
                            res = { data: { ok: true } };
                        } else if (event === "twoFAStatus") {
                            res = await api.get("/twofa/status");
                        } else if (event === "prepare2FA") {
                            const currentPassword = args[0];
                            res = await api.post("/twofa/prepare", {
                                currentPassword,
                            });
                        } else if (event === "verifyToken") {
                            const token = args[0];
                            const currentPassword = args[1];
                            res = await api.post("/twofa/verify", {
                                token,
                                currentPassword,
                            });
                        } else if (event === "save2FA") {
                            const currentPassword = args[0];
                            const token = args[1];
                            res = await api.post("/twofa/enable", {
                                currentPassword,
                                token,
                            });
                        } else if (event === "disable2FA") {
                            const currentPassword = args[0];
                            res = await api.post("/twofa/disable", {
                                currentPassword,
                            });
                        } else if (event === "cloudflared_join") {
                            res = await api.get("/reverse-proxy/cloudflared");
                            updateCloudflared(res?.data?.data || {});
                        } else if (event === "cloudflared_start") {
                            const token = args[0];
                            res = await api.post("/reverse-proxy/cloudflared/start", { token });
                            updateCloudflared(res?.data?.data || {});
                        } else if (event === "cloudflared_stop") {
                            const currentPassword = args[0];
                            res = await api.post("/reverse-proxy/cloudflared/stop", { currentPassword });
                            updateCloudflared(res?.data?.data || {});
                        } else if (event === "cloudflared_removeToken") {
                            res = await api.delete("/reverse-proxy/cloudflared/token");
                            updateCloudflared(res?.data?.data || {});
                        } else {
                            res = { data: { ok: false, msg: "Not implemented" } };
                        }
                        let data = res && res.data ? root.camelCaseKeysDeep(res.data) : res.data;
                        if (data && typeof data === "object") {
                            data = root.normalizeDeepBooleans(data);
                        }
                        cb && cb(data);
                    } catch (error) {
                        let msg = error.message;
                        if (error.response && error.response.data) {
                            msg = error.response.data.detail || msg;
                        }
                        cb && cb({ ok: false, msg });
                    }
                },
                on() {},
                off() {},
            };
        },

        /**
         * Socket initialization placeholder.
         * @returns {void}
         */
        initSocketIO() {
            // no-op
        },

        /**
         * Show a toast based on API response.
         * @param {object} res Response object
         * @returns {void}
         */
        toastRes(res) {
            if (!res) {
                return;
            }

            // Do not show a toast if there is no message to display
            if (!res.msg && !res.msgi18n) {
                return;
            }

            let msg = res.msg;
            if (res.msgi18n) {
                const t = res.msgi18n;
                if (typeof t === "object") {
                    msg = this.$t(t.key, t.values);
                } else {
                    msg = this.$t(t);
                }
            }

            if (res.ok) {
                toast.success(msg);
            } else {
                toast.error(msg);
            }
        },

        /**
         * Show success toast.
         * @param {string} msg Message key
         * @returns {void}
         */
        toastSuccess(msg) {
            toast.success(this.$t(msg));
        },

        /**
         * Show error toast.
         * @param {string} msg Message key
         * @returns {void}
         */
        toastError(msg) {
            toast.error(this.$t(msg));
        },
    },
};
