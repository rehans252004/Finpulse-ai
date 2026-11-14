const TRADINGVIEW_SYMBOLS = {
    AAPL: "NASDAQ:AAPL",
    MSFT: "NASDAQ:MSFT",
    NVDA: "NASDAQ:NVDA",
    JPM: "NYSE:JPM",
    BAC: "NYSE:BAC",
    GS: "NYSE:GS",
    XOM: "NYSE:XOM",
    TSLA: "NASDAQ:TSLA",
    RELIANCE: "NSE:RELIANCE",
    TCS: "NSE:TCS",
    INFY: "NSE:INFY",
    HDFCBANK: "NSE:HDFCBANK",
    ICICIBANK: "NSE:ICICIBANK",
    SBIN: "NSE:SBIN",
    SPX: "SP:SPX",
    NDX: "NASDAQ:NDX",
    DJI: "DJ:DJI",
    SPY: "AMEX:SPY",
    QQQ: "NASDAQ:QQQ",
    EURUSD: "FX:EURUSD",
    GBPUSD: "FX:GBPUSD",
    USDJPY: "FX:USDJPY",
    USDINR: "FX:USDINR",
    AUDUSD: "FX:AUDUSD",
    USDCAD: "FX:USDCAD",
    USDCHF: "FX:USDCHF",
    NZDUSD: "FX:NZDUSD",
    GOLD: "COMEX:GC1!"
};

function showTradingViewChart(
    symbol = "AAPL",
    style = "1",
    containerId = "tradingview-chart",
    interval = "D"
) {
    const container = document.getElementById(containerId);

    if (!container) {
        console.error(`Missing element: <div id="${containerId}"></div>`);
        return;
    }

    const normalizedSymbol = symbol.toUpperCase();
    if (!/^[A-Z0-9._-]{1,15}(?::[A-Z0-9._-]{1,20})?$/.test(normalizedSymbol)) {
        container.textContent = `Invalid chart symbol: ${symbol}.`;
        return;
    }
    const tradingViewSymbol =
        TRADINGVIEW_SYMBOLS[normalizedSymbol] ||
        normalizedSymbol;
    const fullChartLink =
        `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tradingViewSymbol)}` +
        `&interval=${encodeURIComponent(interval)}`;

    container.replaceChildren();

    const widget = document.createElement("div");
    widget.className = "tradingview-widget-container";

    const chart = document.createElement("div");
    chart.className = "tradingview-widget-container__widget";
    chart.id = `tradingview-widget-${containerId}-${Date.now()}-${Math.random().toString(16).slice(2)}`;

    const attribution = document.createElement("div");
    attribution.className = "tradingview-attribution";

    const link = document.createElement("a");
    link.href = fullChartLink;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Open full chart on TradingView";

    const tradingLink = document.getElementById("tradingviewTradingLink");
    if (tradingLink && containerId === "tradingview-chart") {
        tradingLink.href = fullChartLink;
        ["tradingviewBuyMarket", "tradingviewSellMarket"].forEach((id) => {
            const orderLink = document.getElementById(id);
            if (orderLink) orderLink.href = fullChartLink;
        });
    }
    const overviewTradingLink = document.getElementById("overviewTradingViewFullLink");
    if (overviewTradingLink && containerId === "overview-tradingview-chart") {
        overviewTradingLink.href = fullChartLink;
    }

    attribution.appendChild(link);
    widget.append(chart, attribution);
    container.appendChild(widget);

    const config = {
        autosize: true,
        symbol: tradingViewSymbol,
        interval,
        timezone: "Asia/Kolkata",
        theme: document.documentElement.dataset.theme === "light"
            ? "light"
            : "dark",
        style: style === "3" ? "3" : "1",
        locale: "en",
        allow_symbol_change: true,
        calendar: false,
        withdateranges: true,
        hide_side_toolbar: false,
        details: true,
        container_id: chart.id,
        support_host: "https://www.tradingview.com"
    };

    const loaderScript = document.createElement("script");
    loaderScript.src =
        "https://s3.tradingview.com/tv.js";
    loaderScript.async = true;
    loaderScript.onload = () => {
        const widgetScript = document.createElement("script");
        widgetScript.type = "text/javascript";
        widgetScript.textContent = `new TradingView.widget(${JSON.stringify(config)});`;
        widget.appendChild(widgetScript);
    };
    loaderScript.onerror = () => {
        chart.textContent = "TradingView could not load the chart.";
    };

    widget.appendChild(loaderScript);
}

window.showTradingViewChart = showTradingViewChart;

document.addEventListener("DOMContentLoaded", () => {
    const selector = document.getElementById("tradingviewSymbolSelector");
    const styleSelector = document.getElementById("tradingviewStyleSelector");

    if (!selector) return;

    const renderChart = () => {
        showTradingViewChart(selector.value, styleSelector?.value || "1");
    };

    selector.addEventListener("change", renderChart);
    styleSelector?.addEventListener("change", renderChart);

    const stockOptions = document.getElementById("tradingviewStockOptions");
    if (stockOptions && !stockOptions.children.length) {
        Object.entries(TRADINGVIEW_SYMBOLS)
            .filter(([symbol]) => [
                "AAPL", "MSFT", "NVDA", "JPM", "BAC", "GS", "XOM", "TSLA"
            ].includes(symbol))
            .forEach(([symbol]) => {
                const option = document.createElement("option");
                option.value = symbol;
                option.textContent = symbol;
                stockOptions.appendChild(option);
            });
    }

    if (document.getElementById("marketTable")) {
        renderChart();
    }

    document.getElementById("overviewTradingViewSymbol")?.addEventListener(
        "change",
        (event) => {
            showTradingViewChart(
                event.target.value,
                "1",
                "overview-tradingview-chart"
            );
        }
    );
});