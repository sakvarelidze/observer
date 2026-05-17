// Single registration site for Chart.js — every v2 chart imports this
// once and the registry is set up before the first render. Keeping the
// imports minimal (vs. `...registerables`) trims the bundle.
import {
    Chart,
    LineController,
    BarController,
    LineElement,
    BarElement,
    PointElement,
    LinearScale,
    TimeScale,
    CategoryScale,
    Tooltip,
    Filler,
} from "chart.js";
import "chartjs-adapter-date-fns";

let registered = false;

export function ensureChartsRegistered() {
    if (registered) {
        return;
    }
    Chart.register(
        LineController,
        BarController,
        LineElement,
        BarElement,
        PointElement,
        LinearScale,
        TimeScale,
        CategoryScale,
        Tooltip,
        Filler,
    );
    // v2 dark-surface defaults so individual charts don't repeat the same
    // overrides. Per-chart configs can still override via dataset/options.
    Chart.defaults.color = "hsl(0 0% 62%)";
    Chart.defaults.borderColor = "hsl(0 0% 16%)";
    Chart.defaults.font.family =
        "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    Chart.defaults.font.size = 11;
    Chart.defaults.plugins.tooltip.backgroundColor = "hsl(0 0% 8%)";
    Chart.defaults.plugins.tooltip.borderColor = "hsl(0 0% 26%)";
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.titleColor = "hsl(0 0% 96%)";
    Chart.defaults.plugins.tooltip.bodyColor = "hsl(0 0% 80%)";
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.titleFont = { weight: "600",
        size: 12 };
    Chart.defaults.plugins.tooltip.bodyFont = { size: 11 };
    Chart.defaults.plugins.tooltip.displayColors = false;
    registered = true;
}
