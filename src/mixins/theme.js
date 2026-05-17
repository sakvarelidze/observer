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

