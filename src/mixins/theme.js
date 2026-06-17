export default {

    data() {
        return {
            system: (window.matchMedia("(prefers-color-scheme: dark)").matches) ? "dark" : "light",
            userTheme: localStorage.theme,
            styleElapsedTime: localStorage.styleElapsedTime,
            primaryColor: localStorage.primaryColor || "#5cdd8b",
            accentColor: localStorage.accentColor || "#7ce8a4",
            statusPageTheme: "light",
            forceStatusPageTheme: false,
            path: "",
        };
    },

    mounted() {
        if (!this.userTheme) {
            this.userTheme = "auto";
        }
        if (!this.styleElapsedTime) {
            this.styleElapsedTime = "no-line";
        }

        // Keep `system` in sync with the OS preference so "auto" reacts
        // live instead of being frozen at page-load time.
        const mq = window.matchMedia("(prefers-color-scheme: dark)");
        const onSystemChange = (e) => {
            this.system = e.matches ? "dark" : "light";
        };
        if (mq.addEventListener) {
            mq.addEventListener("change", onSystemChange);
        } else if (mq.addListener) {
            mq.addListener(onSystemChange);
        }

        this.applyTheme();
        this.updateThemeColorMeta();
    },

    computed: {
        theme() {
            // As entry can be status page now, set forceStatusPageTheme to true to use status page theme
            if (this.forceStatusPageTheme) {
                if (this.statusPageTheme === "auto") {
                    return this.system;
                }
                return this.statusPageTheme;
            }

            // Entry no need dark
            if (this.path === "") {
                return "light";
            }

            if (this.path.startsWith("/status-page") || this.path.startsWith("/status")) {
                if (this.statusPageTheme === "auto") {
                    return this.system;
                }
                return this.statusPageTheme;
            } else {
                if (this.userTheme === "auto") {
                    return this.system;
                }
                return this.userTheme;
            }
        },

        isDark() {
            return this.theme === "dark";
        }
    },

    watch: {
        "$route.fullPath"(path) {
            this.path = path;
        },

        userTheme(to, from) {
            localStorage.theme = to;
        },

        styleElapsedTime(to, from) {
            localStorage.styleElapsedTime = to;
        },

        theme() {
            this.applyTheme();
            this.updateThemeColorMeta();
        },

        primaryColor(to) {
            localStorage.primaryColor = to;
            this.updateThemeColorMeta();
        },

        accentColor(to) {
            localStorage.accentColor = to;
        },
    },

    methods: {
        /**
         * Reflect the resolved theme onto the document root so the themed
         * CSS custom properties (defined in app.scss under
         * :root[data-theme="..."]) take effect across the whole app,
         * including teleported overlays (modals, toasts, command palette).
         * @returns {void}
         */
        applyTheme() {
            document.documentElement.setAttribute("data-theme", this.theme);
        },

        /**
         * Update the theme color meta tag
         * @returns {void}
         */
        updateThemeColorMeta() {
            if (this.theme === "dark") {
                document.querySelector("#theme-color").setAttribute("content", "#161B22");
            } else {
                document.querySelector("#theme-color").setAttribute("content", this.primaryColor);
            }
        }
    }
};

