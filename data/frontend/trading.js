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
    HDFCBANK: "NSE:HDFCBANK"
};

function showTradingViewChart(symbol = "AAPL") {
    const container = document.getElementById("tradingview-chart");

    if (!container) {
        console.error('Missing element: <div id="tradingview-chart"></div>');
        return;
    }

    const tradingViewSymbol = TRADINGVIEW_SYMBOLS[symbol.toUpperCase()];

    if (!tradingViewSymbol) {
        container.textContent =
            `TradingView symbol is not configured for ${symbol}.`;
        return;
    }

    container.replaceChildren();

    const widget = document.createElement("div");
    widget.className = "tradingview-widget-container";

    const chart = document.createElement("div");
    chart.className = "tradingview-widget-container__widget";

    const attribution = document.createElement("div");
    attribution.className = "tradingview-attribution";

    const link = document.createElement("a");
    link.href = `https://www.tradingview.com/symbols/${tradingViewSymbol.replace(":", "-")}/`;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "View on TradingView";

    attribution.appendChild(link);
    widget.append(chart, attribution);
    container.appendChild(widget);

    const script = document.createElement("script");
    script.src =
        "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.async = true;
    script.textContent = JSON.stringify({
        autosize: true,
        symbol: tradingViewSymbol,
        interval: "D",
        timezone: "Asia/Kolkata",
        theme: "dark",
        style: "1",
        locale: "en",
        allow_symbol_change: true,
        calendar: false,
        support_host: "https://www.tradingview.com"
    });

    widget.appendChild(script);
}

window.showTradingViewChart = showTradingViewChart;

document.addEventListener("DOMContentLoaded", () => {
    const selector = document.getElementById("tradingviewSymbolSelector");

    if (!selector) return;

    selector.addEventListener("change", () => {
        showTradingViewChart(selector.value);
    });
});