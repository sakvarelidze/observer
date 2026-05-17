import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";
import { visualizer } from "rollup-plugin-visualizer";
import viteCompression from "vite-plugin-compression";
import postCssScss from "postcss-scss";
import postcssRTLCSS from "postcss-rtlcss";

const viteCompressionFilter = /\.(js|mjs|json|css|html|svg)$/i;

// https://vitejs.dev/config/
export default defineConfig({
    server: {
        port: 3000,
    },
    define: {
        "FRONTEND_VERSION": JSON.stringify(process.env.npm_package_version),
        "process.env": {},
    },
    plugins: [
        vue(),
        visualizer({
            filename: "tmp/dist-stats.html"
        }),
        viteCompression({
            algorithm: "gzip",
            filter: viteCompressionFilter,
        }),
        viteCompression({
            algorithm: "brotliCompress",
            filter: viteCompressionFilter,
        }),
    ],
    css: {
        postcss: {
            "parser": postCssScss,
            "map": false,
            "plugins": [ postcssRTLCSS ]
        }
    },
    build: {
        commonjsOptions: {
            include: [ /.js$/ ],
        },
        rollupOptions: {
            output: {
                // Split heavy / cacheable vendor libs out of the main
                // bundle. Each named chunk fetches in parallel with the
                // app entry and stays cached across deploys when the
                // dep version doesn't change.
                manualChunks: {
                    vue: [ "vue", "vue-router", "vue-i18n" ],
                    icons: [
                        "@fortawesome/fontawesome-svg-core",
                        "@fortawesome/free-regular-svg-icons",
                        "@fortawesome/free-solid-svg-icons",
                        "@fortawesome/vue-fontawesome",
                    ],
                },
            },
        },
    }
});
