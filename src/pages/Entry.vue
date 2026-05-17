<template>
    <div>
        <StatusPage v-if="statusPageSlug" :override-slug="statusPageSlug" />
    </div>
</template>

<script>
// Public status pages now render through the v2 component. The old
// v1 StatusPage component is still in the tree for direct fallback
// access if needed, but Entry-level status-page-matched-domain hits
// the rewritten public surface.
import StatusPage from "./v2/PublicStatusPageV2.vue";

export default {
    components: {
        StatusPage,
    },
    data() {
        return {
            statusPageSlug: null,
        };
    },
    async mounted() {

        // There are only 3 cases that could come in here.
        // 1. Matched status Page domain name
        // 2. Vue Frontend Dev
        // 3. Vue Frontend Dev (not setup database yet)
        let res;
        try {
            // Database wizard takes priority — if the backend is on the
            // bootstrap DB, every other endpoint will 403 dbSetupNeeded.
            try {
                const dbInfo = (await this.$root.api.get("/setup-database-info")).data;
                if (dbInfo?.needsDbSetup) {
                    this.$router.push("/setup-database");
                    return;
                }
            } catch (e) {
                // Backend reachable but errored — fall through to the
                // normal entry-page logic which will surface a clearer
                // error if anything else is wrong.
            }
            res = (await this.$root.api.get("/entry-page")).data;

            if (res.type === "statusPageMatchedDomain") {
                this.statusPageSlug = res.statusPageSlug;
                this.$root.forceStatusPageTheme = true;

            } else {
                const setup = (await this.$root.api.get("/setup-needed")).data;
                if (setup.needSetup) {
                    this.$router.push("/setup");
                    return;
                }

                if (res.type === "entryPage") {          // Dev only. For production, the logic is in the server side
                    const entryPage = res.entryPage;
                    if (entryPage?.startsWith("statusPage-")) {
                        this.$router.push("/status/" + entryPage.replace("statusPage-", ""));
                    } else {
                        // should the old setting style still exist here?
                        this.$router.push("/dashboard");
                    }
                } else if (res.type === "setup-database") {
                    this.$router.push("/setup-database");
                } else {
                    this.$router.push("/dashboard");
                }
            }
        } catch (e) {
            alert("Cannot connect to the backend server. Did you start the backend server? (npm run start-server-dev)");
        }

    },

};
</script>
