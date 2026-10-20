import Highcharts from "highcharts";
import HighchartsReact from "highcharts-react-official";

// Line/area chart of a variable's average at each time of day (x = minutes after local midnight).
function isMobile() {
    return typeof window !== "undefined" && window.innerWidth < 768;
}

export function hhmm(mins) {
    const m = ((Math.round(mins) % 1440) + 1440) % 1440;
    return String(Math.floor(m / 60)).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
}

export function DayProfileChart({ points, binMin, name, unitSymbol, precision, color, area, yMin, yMax, title, bands }) {
    const mobile = isMobile();
    const options = {
        credits: { href: null, text: "@rwcweather" },
        chart: { height: mobile ? 340 : 440, spacing: mobile ? [8, 4, 10, 0] : [15, 15, 15, 10], backgroundColor: "#fff",
            zoomType: "x" },
        title: { text: title, style: { fontSize: mobile ? "13px" : "16px" } },
        legend: { enabled: false },
        xAxis: {
            min: 0, max: 1440, tickInterval: mobile ? 240 : 120, crosshair: true, showLastLabel: !mobile,
            labels: { formatter() { return hhmm(this.value); }, style: { fontSize: mobile ? "10px" : "12px" } },
            title: { text: mobile ? null : "Time of day (Pacific)" },
        },
        yAxis: {
            min: yMin ?? null, max: yMax ?? null, title: { text: mobile ? null : unitSymbol }, plotBands: bands,
            labels: { format: "{value}" + (mobile ? "" : ""), style: { fontSize: mobile ? "10px" : "12px" } },
        },
        tooltip: {
            useHTML: true,
            formatter() {
                const p = this.point;
                return `<b>${hhmm(p.x)}–${hhmm(p.x + binMin)}</b><br/>${name}: <b>${Highcharts.numberFormat(p.y, precision)} ${unitSymbol}</b>` +
                    (p.n != null ? `<br/><span style="color:#666">${p.n.toLocaleString()} ${p.unitN}</span>` : "");
            },
        },
        plotOptions: { series: { marker: { enabled: false }, animation: false, turboThreshold: 0 } },
        series: [{
            type: area ? "area" : "line", name, color, lineWidth: 2,
            fillOpacity: area ? 0.35 : undefined, threshold: area ? 0 : null,
            data: points,
        }],
    };
    return <HighchartsReact highcharts={Highcharts} options={options} />;
}
