import { createRouter, createWebHistory } from "vue-router";

import Setup from "./pages/Setup.vue";
import SetupDatabase from "./pages/SetupDatabase.vue";
import Entry from "./pages/Entry.vue";
import NotFound from "./pages/NotFound.vue";
import Login from "./components/Login.vue";

const Dashboard = () => import("./pages/v2/DashboardV2.vue");
const Details = () => import("./pages/v2/DetailsV2.vue");
const AddMonitor = () => import("./pages/v2/AddMonitorV2.vue");
const EditMonitor = () => import("./pages/v2/EditMonitorV2.vue");
const Settings = () => import("./pages/v2/SettingsV2.vue");
const SettingsGeneral = () => import("./pages/v2/settings/General.vue");
const SettingsAppearance = () => import("./pages/v2/settings/Appearance.vue");
const SettingsTags = () => import("./pages/v2/settings/Tags.vue");
const SettingsNotifications = () => import("./pages/v2/settings/Notifications.vue");
const SettingsSecurity = () => import("./pages/v2/settings/Security.vue");
const SettingsApiKeys = () => import("./pages/v2/settings/ApiKeys.vue");
const SettingsUsers = () => import("./pages/v2/settings/Users.vue");
const SettingsLdap = () => import("./pages/v2/settings/Ldap.vue");
const SettingsMonitorHistory = () => import("./pages/v2/settings/MonitorHistory.vue");
const SettingsAbout = () => import("./pages/v2/settings/About.vue");
const SettingsReverseProxy = () => import("./pages/v2/settings/ReverseProxy.vue");
const PublicStatusPage = () => import("./pages/v2/PublicStatusPageV2.vue");
const StatusPagesList = () => import("./pages/v2/StatusPagesListV2.vue");
const StatusPageEdit = () => import("./pages/v2/StatusPageEditV2.vue");
const MaintenanceList = () => import("./pages/v2/MaintenanceListV2.vue");
const MaintenanceEdit = () => import("./pages/v2/MaintenanceEditV2.vue");
const EventsFeed = () => import("./pages/v2/EventsFeedV2.vue");

// Admin routes are gated by router.beforeEach below — every entry
// here is marked with meta.requiresAuth so the guard can match them
// without enumerating paths. Public routes (login, setup, status pages)
// omit the meta so they remain reachable without a token.
const adminMeta = { requiresAuth: true };

const routes = [
    {
        path: "/",
        component: Entry,
    },
    {
        path: "/login",
        component: Login,
    },
    {
        path: "/setup",
        component: Setup,
    },
    {
        path: "/setup-database",
        component: SetupDatabase,
    },

    // Admin surfaces (formerly /v2/*).
    {
        path: "/dashboard",
        component: Dashboard,
        meta: adminMeta,
    },
    {
        path: "/dashboard/:id",
        component: Details,
        meta: adminMeta,
    },
    {
        path: "/dashboard/:id/edit",
        component: EditMonitor,
        meta: adminMeta,
    },
    {
        path: "/add",
        component: AddMonitor,
        meta: adminMeta,
    },
    {
        path: "/status-pages",
        component: StatusPagesList,
        meta: adminMeta,
    },
    {
        path: "/status-pages/new",
        component: StatusPageEdit,
        meta: adminMeta,
    },
    {
        path: "/status-pages/:slug/edit",
        component: StatusPageEdit,
        meta: adminMeta,
    },
    {
        // /maintenance/new must come before /maintenance/:id/edit and
        // before the legacy /maintenance/:id redirect so the literal
        // "new" segment isn't captured as an :id.
        path: "/maintenance",
        component: MaintenanceList,
        meta: adminMeta,
    },
    {
        path: "/maintenance/new",
        component: MaintenanceEdit,
        meta: adminMeta,
    },
    {
        path: "/maintenance/:id/edit",
        component: MaintenanceEdit,
        meta: adminMeta,
    },
    {
        path: "/events",
        component: EventsFeed,
        meta: adminMeta,
    },
    {
        path: "/settings",
        component: Settings,
        meta: adminMeta,
        children: [
            {
                path: "",
                redirect: "/settings/general",
            },
            {
                path: "general",
                component: SettingsGeneral,
            },
            {
                path: "appearance",
                component: SettingsAppearance,
            },
            {
                path: "tags",
                component: SettingsTags,
            },
            {
                path: "notifications",
                component: SettingsNotifications,
            },
            {
                path: "security",
                component: SettingsSecurity,
            },
            {
                path: "api-keys",
                component: SettingsApiKeys,
            },
            {
                path: "users",
                component: SettingsUsers,
            },
            {
                path: "ldap",
                component: SettingsLdap,
            },
            {
                path: "monitor-history",
                component: SettingsMonitorHistory,
            },
            {
                path: "reverse-proxy",
                component: SettingsReverseProxy,
            },
            {
                path: "about",
                component: SettingsAbout,
            },
        ],
    },

    // Public status pages.
    {
        path: "/status-page",
        component: PublicStatusPage,
    },
    {
        path: "/status",
        component: PublicStatusPage,
    },
    {
        path: "/status/:slug",
        component: PublicStatusPage,
    },

    // Legacy v1 admin paths and historical /v2/* paths all redirect to
    // the new canonical routes. v1 source files remain in the tree for
    // rollback safety; nothing imports them anymore so they tree-shake.
    {
        path: "/dashboard/notifications",
        redirect: "/events",
    },
    {
        path: "/dashboard/:id/notifications",
        redirect: "/events",
    },
    {
        path: "/clone/:id",
        redirect: to => `/add?clone=${to.params.id}`,
    },
    {
        path: "/list",
        redirect: "/dashboard",
    },
    {
        // v2 doesn't have a separate Proxies page — bounce to settings home.
        path: "/settings/proxies",
        redirect: "/settings",
    },
    {
        path: "/manage-status-page",
        redirect: "/status-pages",
    },
    {
        path: "/add-status-page",
        redirect: "/status-pages/new",
    },
    {
        path: "/add-maintenance",
        redirect: "/maintenance/new",
    },
    {
        path: "/maintenance/edit/:id",
        redirect: to => `/maintenance/${to.params.id}/edit`,
    },
    {
        // Catch-all for /maintenance/:id when no /edit suffix — bounce
        // to the edit form. Must be declared after /maintenance/new and
        // /maintenance/:id/edit so those still match.
        path: "/maintenance/:id",
        redirect: to => `/maintenance/${to.params.id}/edit`,
    },

    // Anything that explicitly carries the historical /v2/ prefix gets
    // stripped and re-routed. Catches bookmarks made during the v2
    // prototype phase.
    {
        path: "/v2/:rest(.*)*",
        redirect: to => {
            const rest = to.params.rest;
            const tail = Array.isArray(rest) ? rest.join("/") : (rest || "");
            return `/${tail}`;
        },
    },

    {
        path: "/:pathMatch(.*)*",
        component: NotFound,
    },
];

export const router = createRouter({
    linkActiveClass: "active",
    history: createWebHistory(),
    routes,
});

// Admin surfaces don't render through any layout that gates on
// $root.loggedIn, so the guard runs here. Without it a logged-out
// visitor lands on an empty wall — every reactive list is empty
// until login. Fall back to /login if there's no token, preserving
// the requested path so we can return after sign-in.
router.beforeEach((to) => {
    if (!to.matched.some(r => r.meta?.requiresAuth)) {
        return true;
    }
    const token = typeof localStorage !== "undefined" ? localStorage.getItem("token") : null;
    if (token) {
        return true;
    }
    return {
        path: "/login",
        query: { next: to.fullPath },
    };
});
