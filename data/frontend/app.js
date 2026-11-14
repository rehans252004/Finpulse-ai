(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);

  function getThemeColor(variable) {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(variable)
      .trim();
  }

  function updateMarketChartTheme() {
    const textColor = getThemeColor('--muted');
    const gridColor = getThemeColor('--table-rule');
    if (marketChart) {
      marketChart.options.scales.x.ticks.color = textColor;
      marketChart.options.scales.x.grid.color = gridColor;
      marketChart.options.scales.y.ticks.color = textColor;
      marketChart.options.scales.y.grid.color = gridColor;
      marketChart.options.plugins.legend.labels.color = textColor;
      marketChart.update('none');
    }
    if (portfolioAllocationChart) {
      portfolioAllocationChart.data.datasets[0].borderColor = getThemeColor('--surface');
      portfolioAllocationChart.update('none');
    }
  }

  function updateTradingViewTheme() {
    if (typeof window.showTradingViewChart !== 'function') return;

    const charts = [
      {
        container: 'overview-tradingview-chart',
        symbolSelector: '#overviewTradingViewSymbol',
        style: '1',
      },
      {
        container: 'tradingview-chart',
        symbolSelector: '#tradingviewSymbolSelector',
        styleSelector: '#tradingviewStyleSelector',
      },
      {
        container: 'supply-demand-tradingview-chart',
        symbolSelector: '#supplyDemandSymbol',
        style: '1',
        intervalSelector: '#supplyDemandTimeframe',
      },
    ];

    charts.forEach(({ container, symbolSelector, style, styleSelector, intervalSelector }) => {
      const chartContainer = document.getElementById(container);
      if (!chartContainer?.querySelector('.tradingview-widget-container')) return;

      window.showTradingViewChart(
        $(symbolSelector)?.value || 'AAPL',
        styleSelector ? $(styleSelector)?.value || '1' : style,
        container,
        intervalSelector
          ? tradingViewIntervals[$(intervalSelector)?.value] || '5'
          : 'D'
      );
    });
  }

  function setTheme(theme) {
    const normalizedTheme = theme === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.theme = normalizedTheme;
    const isLight = normalizedTheme === 'light';
    const button = $('#themeToggle');
    button.setAttribute('aria-pressed', String(isLight));
    button.setAttribute(
      'aria-label',
      `Switch to ${isLight ? 'dark' : 'light'} theme`
    );
    $('#themeToggleLabel').textContent =
      `${isLight ? '☾' : '☀'} ${isLight ? 'Dark' : 'Light'} theme`;
    document.querySelector('meta[name="theme-color"]')
      .setAttribute('content', isLight ? '#f1f6fc' : '#080d18');
    try {
      localStorage.setItem('finpulse-theme', normalizedTheme);
    } catch {
      // The selected theme remains active for this page even if it cannot persist.
    }
    updateMarketChartTheme();
    updateTradingViewTheme();
  }

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[char]);

  const sections = [
    'overview',
    'market',
    'heatmap',
    'correlation',
    'supplyDemand',
    'portfolio',
    'careers',
    'propMatch',
    'news',
    'profile',
  ];

  let marketData = [];
  let marketChart;
  let portfolioAllocationChart;
  let latestPortfolioPayload;
  let voiceRecognition = null;
  let priceAlertLiveState = {};
  let careerPage = 1;
  const assistantHistory = [];
  const assistantWelcome =
    'Hello! I’m Jarvis. I can navigate FinPulse, filter markets, compare companies, ' +
    'find supply and demand zones, ' +
    'search careers and news, refresh data, and download reports. Try “show banking ' +
    'sector” or “find data analyst jobs in Mumbai.” I’ll remember this chat while ' +
    'it’s open. Use New chat to clear its context.';

  const defaultSupplyDemandSymbol = 'AAPL';
  const supplyDemandIndianCompanies = {
    RELIANCE: 'Reliance Industries (NSE)',
    TCS: 'Tata Consultancy Services (NSE)',
    INFY: 'Infosys (NSE)',
    HDFCBANK: 'HDFC Bank (NSE)',
    ICICIBANK: 'ICICI Bank (NSE)',
    SBIN: 'State Bank of India (NSE)',
  };
  const supplyDemandTimeframeLabels = {
    '5m': '5-minute',
    '15m': '15-minute',
    '1h': '1-hour',
    '1d': 'daily',
  };
  const tradingViewIntervals = {
    '5m': '5',
    '15m': '15',
    '1h': '60',
    '1d': 'D',
  };
  const supplyDemandForexPairs = {
    EURUSD: 'EUR/USD',
    GBPUSD: 'GBP/USD',
    USDJPY: 'USD/JPY',
    USDINR: 'USD/INR',
    AUDUSD: 'AUD/USD',
    USDCAD: 'USD/CAD',
    USDCHF: 'USD/CHF',
    NZDUSD: 'NZD/USD',
  };
  const indianCompanies = {
    RELIANCE: 'Reliance Industries',
    TCS: 'Tata Consultancy Services',
    INFY: 'Infosys',
    HDFCBANK: 'HDFC Bank',
  };
  const propFirms = [
    {
      name: 'FTMO',
      programs: [
        {
          market: 'forex',
          accounts: '1-Step, 2-Step, and Instant',
          sizes: 'Up to $200,000 simulated capital',
          url: 'https://ftmo.com/en/#pricing',
        },
        {
          market: 'futures',
          accounts: 'Growth and Pro',
          sizes: 'Current size options are shown in the official account selector',
          url: 'https://ftmo.com/en/futures/',
        },
      ],
    },
    {
      name: 'The5ers',
      programs: [
        {
          market: 'forex',
          accounts: 'High Stakes, Bootcamp, and Hyper Growth',
          sizes: 'Select an available size on the official program page',
          url: 'https://the5ers.com/',
        },
      ],
    },
    {
      name: 'FundedNext',
      programs: [
        {
          market: 'forex',
          accounts: 'Stellar challenge programs',
          sizes: 'Select an available size on the official program page',
          url: 'https://fundednext.com/',
        },
        {
          market: 'futures',
          accounts: 'Flex, Rapid, and Direct',
          sizes: 'Current size options are shown in the official program selector',
          url: 'https://fundednext.com/futures/',
        },
      ],
    },
    {
      name: 'Topstep',
      programs: [
        {
          market: 'futures',
          accounts: 'Trading Combine',
          sizes: 'See current account sizes and pricing on the official program page',
          url: 'https://www.topstep.com/our-program/',
        },
      ],
    },
    {
      name: 'Apex Trader Funding',
      programs: [
        {
          market: 'futures',
          accounts: 'Intraday and End-of-Day evaluation programs',
          sizes: 'See current account sizes and pricing on the official site',
          url: 'https://apextraderfunding.com/',
        },
      ],
    },
    {
      name: 'Take Profit Trader',
      programs: [
        {
          market: 'futures',
          accounts: 'Test evaluation',
          sizes: 'See current account sizes and pricing on the official site',
          url: 'https://takeprofittrader.com/',
        },
      ],
    },
  ];

  function getPropFirmChecklist(style, budget, size) {
    const checklist = {
      intraday: [
        'Confirm the daily loss limit and how open positions are treated.',
        'Check commissions, data fees, and any minimum trading-day rule.',
      ],
      swing: [
        'Confirm overnight and weekend holding rules.',
        'Check whether positions must be closed before news or market breaks.',
      ],
      news: [
        'Read the exact high-impact news trading restrictions and time windows.',
        'Confirm whether news restrictions differ during evaluation and payout.',
      ],
    }[style];

    checklist.push(
      budget
        ? `Compare the full checkout cost with your $${budget} USD fee limit, including activation, reset, and data fees.`
        : 'Compare the full checkout cost, including activation, reset, and data fees.'
    );
    const sizeCheck = {
      unsure: 'Compare drawdown allowance and contract limits, not just the advertised account balance.',
      small: 'For a smaller advertised size, check its drawdown allowance, contract cap, and payout rules before paying.',
      medium: 'For a mid-size evaluation, compare the drawdown allowance and contract cap with your planned risk per trade.',
      large: 'A larger advertised balance does not mean a larger usable loss limit; verify drawdown, contract caps, and fees.',
    };
    checklist.push(sizeCheck[size] || sizeCheck.unsure);
    return checklist;
  }

  function renderPropFirmMatches(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const markets = [...form.querySelectorAll('input[name="market"]:checked')]
      .map((input) => input.value);
    const status = $('#propMatchStatus');
    const results = $('#propMatchResults');

    if (!markets.length) {
      status.textContent = 'Select Forex / CFDs, Futures, or both to continue.';
      results.replaceChildren();
      return;
    }

    const budget = $('#propMatchBudget').value.trim();
    const style = $('#propMatchStyle').value;
    const size = $('#propMatchSize').value;
    const matches = propFirms.flatMap((firm) => {
      const programs = firm.programs.filter((program) =>
        markets.includes(program.market)
      );
      return programs.length ? [{ ...firm, programs }] : [];
    });
    const checklist = getPropFirmChecklist(style, budget, size);
    const marketLabels = {
      forex: 'Forex / CFDs',
      futures: 'Futures',
    };

    status.textContent =
      `${matches.length} listed firms for ${markets.map((market) => marketLabels[market]).join(' and ')}. ` +
      'This is a selected directory, not every prop firm worldwide. Programs, account sizes, prices, eligibility, and rules can change; confirm them on each firm’s official site.';
    const firmCards = matches.map((firm) => `
      <article class="prop-firm-card">
        <h4>${escapeHtml(firm.name)}</h4>
        ${firm.programs.map((program) => `
          <section class="prop-firm-program">
            <span class="prop-firm-market">${marketLabels[program.market]}</span>
            <p><strong>Programs:</strong> ${escapeHtml(program.accounts)}</p>
            <p><strong>Account sizes:</strong> ${escapeHtml(program.sizes)}</p>
            <a class="prop-firm-link"
               href="${escapeHtml(program.url)}"
               target="_blank"
               rel="noopener noreferrer">
              View ${escapeHtml(firm.name)} ${marketLabels[program.market]} accounts ↗
            </a>
          </section>
        `).join('')}
        <h5>Before paying, check</h5>
        <ul>
          ${checklist.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}
        </ul>
      </article>
    `).join('');
    const directLinks = matches.flatMap((firm) =>
      firm.programs.map((program) => `
        <a class="prop-firm-direct-link"
           href="${escapeHtml(program.url)}"
           target="_blank"
           rel="noopener noreferrer">
          ${escapeHtml(firm.name)} · ${marketLabels[program.market]} ↗
        </a>
      `)
    ).join('');
    results.innerHTML = `
      ${firmCards}
      <section class="prop-firm-direct-links" aria-label="Direct official firm links">
        <h4>Direct links to all listed account programs</h4>
        <div>${directLinks}</div>
      </section>
    `;
  }

  async function getJson(url, options) {
    const response = await fetch(url, options);
    const payload = await response.json();

    if (!response.ok) {
      throw new Error(payload.error || 'Request failed.');
    }

    return payload;
  }

  function navigate(sectionId) {
    if (!sections.includes(sectionId)) return;

    document.querySelectorAll('.page-section').forEach((section) => {
      section.classList.toggle('hidden', section.id !== sectionId);
    });

    document.querySelectorAll('.nav-button[data-section]').forEach((button) => {
      button.classList.toggle(
        'active',
        button.dataset.section === sectionId
      );
    });

    const heading = $(`#${sectionId} h1, #${sectionId} h2, #${sectionId} h3`);

    $('#pageTitle').textContent = sectionId === 'overview'
      ? 'Financial Intelligence Dashboard'
      : heading?.textContent || sectionId;

    // Rebuild the chart after its hidden Market Analytics panel is shown.
    if (sectionId === 'market') {
      requestAnimationFrame(() => {
        const selector = $('#tradingviewSymbolSelector');
        const styleSelector = $('#tradingviewStyleSelector');

        if (typeof window.showTradingViewChart === 'function') {
          window.showTradingViewChart(
            selector?.value || 'AAPL',
            styleSelector?.value || '1'
          );
        }

      });
    }

    if (sectionId === 'supplyDemand') {
      requestAnimationFrame(renderSupplyDemandTradingViewChart);
    }

    if (sectionId === 'portfolio') {
      loadPortfolio().catch((error) => {
        $('#portfolioNotice').textContent = error.message;
      });
      checkPriceAlerts().catch((error) => {
        $('#priceAlertStatus').textContent = error.message;
      });
    }
  }

  function addAssistantMessage(text, role) {
    const node = document.createElement('div');
    node.className = `message ${role}`;
    node.textContent = text;
    $('#assistantMessages').append(node);
    $('#assistantMessages').scrollTop = $('#assistantMessages').scrollHeight;
  }

  function renderMarket(rows = marketData) {
    $('#marketTable').innerHTML = rows.map((row) => `
      <tr>
        <td>${escapeHtml(row.symbol)}</td>
        <td>${escapeHtml(row.company)}</td>
        <td>${escapeHtml(row.sector)}</td>
        <td>$${Number(row.price).toFixed(2)}</td>
        <td class="${Number(row.change) >= 0 ? 'positive' : 'negative'}">
          ${Number(row.change) > 0 ? '+' : ''}${Number(row.change).toFixed(2)}%
        </td>
        <td>${escapeHtml(row.price_source || 'Illustrative data')}</td>
        <td>
          <button class="market-chart-button"
                  type="button"
                  data-chart-symbol="${escapeHtml(row.symbol)}">
            View chart
          </button>
        </td>
      </tr>
    `).join('');
  }

  function formatChange(value) {
    const change = Number(value);
    return `${change > 0 ? '+' : ''}${change.toFixed(2)}%`;
  }

  function renderOverviewCompanies() {
    const query = $('#overviewCompanySearch').value.trim().toLowerCase();
    const rows = [...marketData]
      .sort((a, b) => Number(b.change) - Number(a.change))
      .filter((row) => (
        !query ||
        [row.company, row.symbol, row.sector]
          .some((value) => String(value).toLowerCase().includes(query))
      ));

    $('#overviewCompanyCount').textContent = query
      ? `Showing ${rows.length} of ${marketData.length} tracked companies.`
      : `${marketData.length} tracked companies, ordered by daily change.`;
    $('#overviewCompanyTable').innerHTML = rows.length
      ? rows.map((row) => `
          <tr>
            <td>${escapeHtml(row.company)}</td>
            <td>${escapeHtml(row.symbol)}</td>
            <td>${escapeHtml(row.sector)}</td>
            <td>$${Number(row.price).toFixed(2)}</td>
            <td class="${Number(row.change) > 0 ? 'positive' : Number(row.change) < 0 ? 'negative' : 'neutral'}">
              ${formatChange(row.change)}
            </td>
          </tr>
        `).join('')
      : '<tr><td colspan="5">No tracked companies match your search.</td></tr>';
  }

  function tradingViewSymbol(symbol) {
    const exchanges = {
      RELIANCE: 'NSE',
      TCS: 'NSE',
      INFY: 'NSE',
      HDFCBANK: 'NSE',
      JPM: 'NYSE',
      BAC: 'NYSE',
      GS: 'NYSE',
      XOM: 'NYSE',
    };
    const exchange = exchanges[symbol] || 'NASDAQ';
    return `${exchange}:${symbol}`;
  }

  function renderMarketMoverLinks(movers) {
    $('#marketMoverLinks').innerHTML = movers.map((row) => {
      const direction = Number(row.change) >= 0 ? 'positive' : 'negative';
      const change = `${Number(row.change) > 0 ? '+' : ''}${Number(row.change).toFixed(2)}%`;
      const chartUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tradingViewSymbol(row.symbol))}`;
      return `
        <article class="market-mover-link-card">
          <div>
            <strong>${escapeHtml(row.symbol)}</strong>
            <span class="${direction}">${change}</span>
          </div>
          <a href="${chartUrl}"
             target="_blank"
             rel="noopener noreferrer">TradingView chart ↗</a>
        </article>
      `;
    }).join('');
  }

  function renderHeatmap() {
    const liveRows = marketData.filter((row) => row.price_source === 'Finnhub');
    const sectorNames = [...new Set(
      marketData.map((row) => row.sector)
    )].sort();

    const tiles = sectorNames.map((sector) => {
      const liveSectorRows = liveRows.filter((row) => row.sector === sector);
      const rows = liveSectorRows.length
        ? liveSectorRows
        : marketData.filter((row) => row.sector === sector);
      const average = rows.reduce(
        (sum, row) => sum + Number(row.change),
        0
      ) / rows.length;
      const scoredRows = rows.filter((row) => row.momentum);
      const momentum = scoredRows.length
        ? {
          score: scoredRows.reduce(
            (sum, row) => sum + row.momentum.score,
            0
          ) / scoredRows.length,
          technical: scoredRows.reduce(
            (sum, row) => sum + row.momentum.technical_score,
            0
          ) / scoredRows.length,
          fundamental: scoredRows.reduce(
            (sum, row) => sum + row.momentum.fundamental_score,
            0
          ) / scoredRows.length,
        }
        : null;

      return {
        sector,
        average,
        momentum,
        usesIllustrativeChanges: liveSectorRows.length === 0,
      };
    });

    const maxMagnitude = Math.max(
      1,
      ...tiles.map((tile) => Math.abs(tile.average))
    );

    $('#heatmapGrid').innerHTML = tiles.map(({
      sector,
      average,
      momentum,
      usesIllustrativeChanges,
    }) => {
      const strength = Math.round(
        25 + (Math.abs(average) / maxMagnitude) * 25
      );

      const color = average >= 0
        ? `hsl(160, 55%, ${strength}%)`
        : `hsl(0, 65%, ${strength}%)`;

      return `
        <button class="heat-tile${usesIllustrativeChanges ? ' heat-tile-illustrative' : ''}"
                data-sector="${escapeHtml(sector)}"
                style="background:${color}"
                aria-label="${escapeHtml(sector)} sector, daily average ${average.toFixed(2)} percent, ${
                  momentum
                    ? `momentum score ${Math.round(momentum.score)} out of 100`
                    : `momentum score unavailable${usesIllustrativeChanges ? ', illustrative daily data' : ''}`
                }">
          <strong>${escapeHtml(sector)}</strong>
          ${usesIllustrativeChanges ? '<span class="heatmap-data-source">Illustrative</span>' : ''}
          <span class="heatmap-daily-change">
            Daily avg ${average > 0 ? '+' : ''}${average.toFixed(2)}%
          </span>
          <span class="heatmap-momentum-score">
            ${momentum ? `Momentum ${Math.round(momentum.score)}/100` : 'Momentum unavailable'}
          </span>
          ${momentum ? `
            <span class="heatmap-score-factors">
              Technical ${Math.round(momentum.technical)} · Fundamental ${Math.round(momentum.fundamental)}
            </span>
          ` : ''}
        </button>
      `;
    }).join('');
    const scoredCount = liveRows.filter((row) => row.momentum).length;
    $('#heatmapNotice').textContent = liveRows.length
      ? scoredCount
        ? `${liveRows.length} live Finnhub quotes available; ${scoredCount} have enough live fundamentals for scoring. Sectors without live quotes show illustrative daily changes.`
        : `${liveRows.length} live Finnhub quotes available, but no complete fundamentals for scoring. Sectors without live quotes show illustrative daily changes.`
      : 'No live quotes are available; daily changes use illustrative sample data and momentum scores are unavailable.';

    $('#heatmapGrid').querySelectorAll('[data-sector]').forEach((tile) => {
      tile.addEventListener('click', () => {
        $('#sectorFilter').value = tile.dataset.sector;

        renderMarket(
          marketData.filter((row) => row.sector === tile.dataset.sector)
        );

        navigate('market');
      });
    });
  }

  function renderSupplyDemand(payload) {
    const timeframe = $('#supplyDemandTimeframe').value;
    const timeframeLabel = supplyDemandTimeframeLabels[timeframe] || '5-minute';
    $('#supplyDemandNotice').textContent =
      `Calculated from ${payload.source}. ${payload.warning}`;
    $('#supplyDemandPrice').textContent =
      Number(payload.current_price).toLocaleString(undefined, {
        style: payload.currency ? 'currency' : 'decimal',
        currency: payload.currency || 'USD',
        maximumFractionDigits: 2,
      });
    $('#supplyDemandPriceLabel').textContent = `Latest ${timeframeLabel} close`;
    $('#supplyDemandAsOf').textContent =
      `${timeframeLabel} candle as of ${new Date(payload.last_updated).toLocaleString()}`;
    const outlook = payload.outlook;
    const outlookPanel = $('#sdOutlook');
    outlookPanel.classList.remove('bullish', 'bearish', 'neutral');
    outlookPanel.classList.add(outlook?.bias || 'neutral');
    $('#sdOutlookLabel').textContent = outlook?.label || 'Neutral · unavailable';
    $('#sdOutlookReason').textContent =
      outlook?.reason || 'A directional zone outlook could not be calculated.';
    $('#sdOutlookConfirmation').textContent = outlook?.confirmation || '—';
    $('#sdOutlookZone').textContent = outlook?.zone
      ? `${outlook.zone.type} · ${Number(outlook.zone.low).toLocaleString()}–${Number(outlook.zone.high).toLocaleString()}${outlook.zone.distance_percent == null ? '' : ` · ${outlook.zone.distance_percent}% from current price`}`
      : 'No single active zone to watch.';
    $('#sdOutlookInvalidationRow').hidden = !outlook?.invalidation;
    $('#sdOutlookInvalidation').textContent = outlook?.invalidation || '';

    const renderZones = (zones, type) => {
      if (!zones.length) {
        return `<p class="sd-empty-state">No active candidate zone was found in the available ${escapeHtml(timeframeLabel)} history. Try another instrument, timeframe, or check again later.</p>`;
      }
      return zones.map((zone, index) => {
        const confirmingTimeframes = ['15m', '1h'].filter(
          (interval) => payload.multi_timeframe?.[interval]?.[type]?.[index]
        );
        const comparisonUnavailable = Object.keys(
          payload.multi_timeframe_errors || {}
        ).length > 0;
        const confirmation = timeframe === '5m'
          ? confirmingTimeframes.length
            ? `<span class="sd-zone-confirmed">Overlaps ${confirmingTimeframes.map((interval) => escapeHtml(interval)).join(' · ')}</span>`
            : comparisonUnavailable
              ? '<span class="sd-zone-unconfirmed">Confirmation unavailable</span>'
              : '<span class="sd-zone-unconfirmed">No 15m / 1h overlap</span>'
          : '';
        return `
        <article class="sd-zone-card ${type}">
          <div class="sd-zone-card-heading">
            <strong>${type === 'demand' ? 'Buying interest' : 'Selling pressure'}</strong>
            <span>${escapeHtml(zone.relation === 'inside'
              ? 'Price is inside'
              : `Zone ${zone.relation} current price`)}</span>
          </div>
          <p class="sd-zone-price">
            ${Number(zone.low).toLocaleString(undefined, { maximumFractionDigits: 2 })}
            <span>–</span>
            ${Number(zone.high).toLocaleString(undefined, { maximumFractionDigits: 2 })}
          </p>
          <div class="sd-zone-meta">
            <span>Formed ${escapeHtml(zone.formed_at)}</span>
            <span>${zone.touches} later candle${zone.touches === 1 ? '' : 's'} overlapped</span>
            <span>${zone.distance_percent}% from current close</span>
            ${confirmation}
          </div>
          <button type="button" class="sd-zone-alert-button"
                  data-zone-alert
                  data-zone-type="${type}"
                  data-zone-low="${Number(zone.low)}"
                  data-zone-high="${Number(zone.high)}">
            Alert me when price enters
          </button>
        </article>
      `;
      }).join('');
    };

    $('#demandZones').innerHTML = renderZones(payload.zones.demand, 'demand');
    $('#supplyZones').innerHTML = renderZones(payload.zones.supply, 'supply');
    const demandConfirmed = (payload.multi_timeframe?.['15m']?.demand || [])
      .filter(Boolean).length + (payload.multi_timeframe?.['1h']?.demand || [])
      .filter(Boolean).length;
    const supplyConfirmed = (payload.multi_timeframe?.['15m']?.supply || [])
      .filter(Boolean).length + (payload.multi_timeframe?.['1h']?.supply || [])
      .filter(Boolean).length;
    const comparisonErrors = Object.values(payload.multi_timeframe_errors || {});
    $('#sdMultiTimeframeSummary').textContent = timeframe !== '5m'
      ? 'Select 5 minutes to compare its zones with 15-minute and hourly zones.'
      : `${demandConfirmed} demand-zone overlaps and ${supplyConfirmed} supply-zone overlaps found across available 15-minute and hourly data. An overlap means the price bands intersect; it is not a trade signal.${comparisonErrors.length ? ` ${comparisonErrors.join(' ')}` : ''}`;
  }

  function showSupplyDemandError(error) {
    const message = error.message || 'Supply and demand zones could not be loaded.';
    $('#supplyDemandNotice').textContent = message;
    $('#supplyDemandPrice').textContent = '—';
    $('#supplyDemandAsOf').textContent = '';
    $('#demandZones').innerHTML =
      `<p class="sd-empty-state">${escapeHtml(message)}</p>`;
    $('#supplyZones').innerHTML =
      `<p class="sd-empty-state">${escapeHtml(message)}</p>`;
    $('#sdMultiTimeframeSummary').textContent = message;
    $('#sdOutlook').classList.remove('bullish', 'bearish');
    $('#sdOutlook').classList.add('neutral');
    $('#sdOutlookLabel').textContent = 'Neutral · unavailable';
    $('#sdOutlookReason').textContent = message;
    $('#sdOutlookConfirmation').textContent = 'Retry analysis when candle data is available.';
    $('#sdOutlookZone').textContent = 'No zone data available.';
    $('#sdOutlookInvalidationRow').hidden = true;
  }

  function featureRequest(url, method = 'GET', payload) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
    const options = {
      method,
      headers: {
        'X-CSRF-Token': csrfToken,
        'Content-Type': 'application/json',
      },
    };
    if (payload !== undefined) options.body = JSON.stringify(payload);
    return getJson(url, options);
  }

  function formatUsd(value) {
    return Number(value).toLocaleString(undefined, {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 2,
    });
  }

  function renderPortfolio(payload) {
    latestPortfolioPayload = payload;
    $('#portfolioCost').textContent = formatUsd(payload.total_cost);
    $('#portfolioValue').textContent = payload.quotes_complete
      ? formatUsd(payload.total_value)
      : 'Incomplete quotes';
    $('#portfolioGainLoss').textContent = payload.quotes_complete
      ? formatUsd(payload.gain_loss)
      : 'Unavailable';
    $('#portfolioGainLoss').classList.toggle(
      'is-positive',
      payload.quotes_complete && Number(payload.gain_loss) >= 0
    );
    $('#portfolioGainLoss').classList.toggle(
      'is-negative',
      payload.quotes_complete && Number(payload.gain_loss) < 0
    );
    $('#portfolioReturn').textContent = payload.quotes_complete
      ? payload.total_cost ? `${payload.gain_loss_percent}%` : '—'
      : 'Unavailable';
    $('#portfolioNotice').textContent = payload.positions.length
      ? payload.quotes_complete
        ? 'Latest available Yahoo Finance prices loaded; market data may be delayed.'
        : 'One or more Yahoo Finance quotes are unavailable; totals are incomplete.'
      : 'No holdings yet. Add a tracked stock to get started.';
    const rankedPositions = [...payload.positions].sort((first, second) =>
      Number(second.market_value || 0) - Number(first.market_value || 0)
    );
    $('#portfolioPositions').innerHTML = rankedPositions.length
      ? rankedPositions.map((position) => `
        <article class="personal-feature-item portfolio-position">
          <div>
            <strong>${escapeHtml(position.symbol)}</strong>
            <span>${Number(position.quantity).toLocaleString()} shares · avg cost ${formatUsd(position.average_cost)}</span>
            <span>${position.quote_error
              ? escapeHtml(position.quote_error)
              : `Last ${formatUsd(position.current_price)} · value ${formatUsd(position.market_value)} · P/L ${formatUsd(position.gain_loss)} (${position.gain_loss_percent}%) · ${position.allocation_percent ?? '—'}% allocation`}</span>
            ${position.quote_error ? '' : `
              <span class="allocation-track" aria-label="${position.allocation_percent}% portfolio allocation">
                <span style="width:${Math.max(0, Math.min(100, Number(position.allocation_percent) || 0))}%"></span>
              </span>
            `}
          </div>
          <button type="button" data-remove-position="${position.id}">Remove</button>
        </article>
      `).join('')
      : '';
    renderPortfolioAllocation(payload, rankedPositions);
    renderPortfolioInsights(payload, rankedPositions);
    renderPortfolioScenario(payload);
  }

  function renderPortfolioScenario(payload = latestPortfolioPayload) {
    const result = $('#portfolioScenarioResult');
    const positionsContainer = $('#portfolioScenarioPositions');
    if (!payload) return;
    if (!payload.positions.length) {
      result.textContent = 'Add holdings to preview a hypothetical portfolio move.';
      positionsContainer.replaceChildren();
      return;
    }
    if (!payload.quotes_complete) {
      result.textContent = 'Scenario preview unavailable until quotes for every holding load.';
      positionsContainer.replaceChildren();
      return;
    }
    const shock = Number($('#portfolioShock').value);
    const scenarioValue = payload.total_value * (1 + shock / 100);
    const scenarioPnl = scenarioValue - payload.total_cost;
    const sign = shock > 0 ? '+' : '';
    result.textContent =
      `If every holding moved ${sign}${shock}% from its latest available price, estimated value would be ${formatUsd(scenarioValue)} (${formatUsd(scenarioValue - payload.total_value)} from now), with an unrealized P/L of ${formatUsd(scenarioPnl)}.`;
    const positions = payload.positions
      .filter((position) => !position.quote_error)
      .map((position) => ({
        ...position,
        scenarioImpact: position.market_value * shock / 100,
      }))
      .sort((first, second) =>
        Math.abs(second.scenarioImpact) - Math.abs(first.scenarioImpact)
      );
    positionsContainer.innerHTML = positions.map((position) => `
      <div class="scenario-position">
        <span>${escapeHtml(position.symbol)}</span>
        <strong class="${position.scenarioImpact < 0 ? 'is-negative' : 'is-positive'}">
          ${position.scenarioImpact > 0 ? '+' : ''}${formatUsd(position.scenarioImpact)}
        </strong>
      </div>
    `).join('');
  }

  function renderPortfolioAllocation(payload, positions) {
    const completePositions = payload.quotes_complete
      ? positions.filter(
        (position) => Number(position.market_value) > 0
      )
      : [];
    const labels = completePositions.map((position) => position.symbol);
    const values = completePositions.map((position) => position.market_value);
    const colors = [
      '#38d9c4', '#7798ff', '#f5c76b', '#e95768', '#9c78e8',
      '#4eb4dc', '#f28c5b', '#75c977', '#df78b2', '#8cabc8',
    ];
    const canvas = $('#portfolioAllocationChart');
    if (typeof Chart === 'undefined') {
      $('#portfolioAllocationLegend').textContent =
        'Allocation chart unavailable. Review the holding percentages below.';
      return;
    }
    if (portfolioAllocationChart) {
      portfolioAllocationChart.data.labels = labels;
      portfolioAllocationChart.data.datasets[0].data = values;
      portfolioAllocationChart.data.datasets[0].backgroundColor =
        labels.map((_, index) => colors[index % colors.length]);
      portfolioAllocationChart.update();
    } else {
      portfolioAllocationChart = new Chart(canvas, {
        type: 'doughnut',
        data: {
          labels,
          datasets: [{
            data: values,
            backgroundColor: labels.map((_, index) => colors[index % colors.length]),
            borderColor: getThemeColor('--surface'),
            borderWidth: 3,
            hoverOffset: 8,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '68%',
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label(context) {
                  const position = completePositions[context.dataIndex];
                  const share = position?.allocation_percent ?? 0;
                  return ` ${context.label}: ${formatUsd(context.raw)} (${share}%)`;
                },
              },
            },
          },
        },
      });
    }
    if (!completePositions.length) {
      $('#portfolioAllocationLegend').textContent = positions.length
        ? 'Allocation chart unavailable until all holding quotes load.'
        : 'Add holdings to view your allocation.';
      return;
    }
    $('#portfolioAllocationLegend').innerHTML = completePositions.map((position, index) => `
      <span class="portfolio-legend-item">
        <i style="--legend-color:${colors[index % colors.length]}"></i>
        <strong>${escapeHtml(position.symbol)}</strong>
        <span>${position.allocation_percent ?? 0}%</span>
      </span>
    `).join('');
  }

  function renderPortfolioInsights(payload, positions) {
    if (!payload.quotes_complete) {
      $('#portfolioInsights').innerHTML = `
        <h3>Portfolio insights</h3>
        <p>Concentration and performance insights require quotes for every holding. Refresh prices when data is available.</p>
        <small>Partial quotes are not used to estimate portfolio allocation.</small>
      `;
      return;
    }
    const available = positions.filter((position) => !position.quote_error);
    if (!available.length) {
      $('#portfolioInsights').innerHTML = `
        <h3>Portfolio insights</h3>
        <p>${positions.length
          ? 'Insights appear once current quotes are available.'
          : 'Add positions to see concentration and performance insights.'}</p>
      `;
      return;
    }
    const largest = available[0];
    const topShare = Number(largest.allocation_percent) || 0;
    const best = [...available].sort(
      (first, second) => second.gain_loss_percent - first.gain_loss_percent
    )[0];
    const worst = [...available].sort(
      (first, second) => first.gain_loss_percent - second.gain_loss_percent
    )[0];
    const sectorTotals = new Map();
    available.forEach((position) => {
      const sector = marketData.find((row) => row.symbol === position.symbol)?.sector
        || 'Other';
      sectorTotals.set(
        sector,
        (sectorTotals.get(sector) || 0) + Number(position.market_value || 0)
      );
    });
    const largestSector = [...sectorTotals.entries()].sort(
      (first, second) => second[1] - first[1]
    )[0];
    const sectorShare = payload.total_value
      ? largestSector[1] / payload.total_value * 100
      : 0;
    const concentration = topShare >= 40
      ? `${escapeHtml(largest.symbol)} is ${topShare}% of portfolio value. This is a high single-stock concentration.`
      : 'No single holding currently exceeds 40% of portfolio value.';
    const sectorWarning = sectorShare >= 60
      ? `${escapeHtml(largestSector[0])} represents ${sectorShare.toFixed(1)}% of tracked value.`
      : '';
    $('#portfolioInsights').innerHTML = `
      <h3>Portfolio insights</h3>
      <p class="${topShare >= 40 ? 'insight-warning' : 'insight-positive'}">
        ${concentration}
      </p>
      ${sectorWarning ? `<p class="insight-warning">${sectorWarning}</p>` : ''}
      ${available.length > 1 ? `
        <div class="insight-performers">
          <span>Top return <strong>${escapeHtml(best.symbol)} · ${best.gain_loss_percent}%</strong></span>
          <span>Lowest return <strong>${escapeHtml(worst.symbol)} · ${worst.gain_loss_percent}%</strong></span>
        </div>
      ` : ''}
      <small>Based on available quotes; informational only, not investment advice.</small>
    `;
  }

  async function loadPortfolio() {
    const payload = await getJson('/api/portfolio');
    renderPortfolio(payload);
  }

  function renderPriceAlerts(alerts) {
    const activeCount = alerts.filter((alert) => !alert.fired_at).length;
    $('#priceAlertCount').textContent =
      `${activeCount} active · ${alerts.length - activeCount} triggered`;
    $('#priceAlertList').innerHTML = alerts.length
      ? alerts.map((alert) => {
        const threshold = alert.alert_type === 'zone'
          ? `${alert.zone_type} zone ${Number(alert.baseline_price).toLocaleString()}–${Number(alert.threshold).toLocaleString()} · ${alert.zone_timeframe}`
          : alert.alert_type === 'price'
          ? `price ${alert.direction} ${Number(alert.threshold).toLocaleString()}`
          : `${alert.direction === 'above' ? '+' : '-'}${alert.threshold}% from ${Number(alert.baseline_price).toLocaleString()}`;
        const live = priceAlertLiveState[alert.id];
        return `
          <article class="personal-feature-item alert-position ${alert.fired_at ? 'is-complete' : ''}">
            <div>
              <strong>${escapeHtml(alert.symbol)} · ${alert.fired_at ? 'Triggered' : 'Active'}</strong>
              <span>Alert when ${escapeHtml(threshold)}</span>
              ${live && !alert.fired_at ? `
                <span>Latest ${Number(live.current_price).toLocaleString()} · ${alert.alert_type === 'zone'
                  ? live.inside_zone
                    ? 'inside zone'
                    : `${Number(live.distance_to_zone_percent).toFixed(2)}% from zone`
                  : alert.alert_type === 'percent'
                    ? `${live.current_move_percent > 0 ? '+' : ''}${live.current_move_percent}% from baseline`
                    : `target ${Number(alert.threshold).toLocaleString()}`}</span>
                <span class="alert-progress-track" role="progressbar"
                      aria-label="Alert progress" aria-valuemin="0"
                      aria-valuemax="100" aria-valuenow="${live.progress_percent}">
                  <span style="width:${Math.max(0, Math.min(100, Number(live.progress_percent) || 0))}%"></span>
                </span>
              ` : ''}
              ${alert.fired_at ? `<span>Triggered ${escapeHtml(new Date(alert.fired_at).toLocaleString())}</span>` : ''}
            </div>
            <button type="button" data-remove-alert="${alert.id}">Remove</button>
          </article>
        `;
      }).join('')
      : '<p class="muted">No price alerts yet.</p>';
  }

  async function loadPriceAlerts() {
    const payload = await getJson('/api/price-alerts');
    renderPriceAlerts(payload.alerts);
  }

  async function checkPriceAlerts() {
    const payload = await featureRequest('/api/price-alerts/check', 'POST');
    if (payload.errors.length) {
      $('#priceAlertStatus').textContent =
        `Some prices could not be checked: ${payload.errors.map((item) => item.symbol).join(', ')}.`;
    }
    if (payload.live_alerts) {
      priceAlertLiveState = Object.fromEntries(
        payload.live_alerts.map((item) => [item.id, item])
      );
      await loadPriceAlerts();
    }
    if (payload.triggered.length) {
      payload.triggered.forEach((alert) => {
        const message = alert.alert_type === 'zone'
          ? `${alert.symbol} entered its ${alert.zone_type} zone at ${Number(alert.current_price).toLocaleString()}.`
          : `${alert.symbol} reached ${Number(alert.current_price).toLocaleString()}.`;
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification('FinPulse price alert', { body: message });
        }
      });
      $('#priceAlertStatus').textContent =
        `${payload.triggered.length} price alert${payload.triggered.length === 1 ? '' : 's'} triggered.`;
      await loadPriceAlerts();
    } else if (!payload.errors.length) {
      $('#priceAlertStatus').textContent =
        payload.checked_symbols
          ? 'Price alerts checked; none have triggered.'
          : 'No active alerts to check.';
    }
  }

  const correlationGroups = {
    all: [
      'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'JPM', 'BAC', 'C', 'GS', 'XOM',
      'CVX', 'LLY', 'UNH', 'JNJ', 'PFE', 'TSLA', 'F', 'GM', 'STLA', 'COST',
      'PEP', 'WMT', 'PG', 'CAT', 'GE', 'HON', 'UPS', 'NEE', 'DUK', 'SO',
      'T', 'VZ', 'CMCSA', 'PLD', 'AMT', 'CPT', 'DLR', 'LIN', 'APD', 'FCX',
      'NEM', 'EURUSD', 'GBPUSD', 'USDJPY', 'USDINR', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD'
    ],
    technology: ['AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'AVGO', 'CRM', 'ORCL', 'AMD', 'INTC', 'QCOM', 'CSCO', 'ADBE', 'SAP', 'SHOP', 'PLTR', 'MCHP', 'TXN', 'KLAC'],
    banking: ['JPM', 'BAC', 'GS', 'C', 'MS', 'WFC', 'USB', 'PNC', 'AXP', 'COF', 'SCHW', 'BLK', 'CME', 'TFC', 'NTRS', 'RF', 'STT', 'MCO', 'SPGI', 'ICE'],
    healthcare: ['LLY', 'UNH', 'JNJ', 'PFE', 'ABT', 'TMO', 'DHR', 'MRK', 'CVS', 'CI', 'MDT', 'ISRG', 'BSX', 'AZN', 'GILD', 'REGN', 'VRTX', 'DXCM', 'IDXX', 'ALGN'],
    energy: ['XOM', 'CVX', 'COP', 'SLB', 'EOG', 'HAL', 'OXY', 'MPC', 'DVN', 'EQT', 'PXD', 'WMB', 'CHK', 'NEM', 'GLC', 'HES', 'MRO', 'APA', 'CXO', 'RIG'],
    consumer: ['COST', 'PEP', 'WMT', 'PG', 'KO', 'PM', 'NKE', 'HD', 'MCD', 'SBUX', 'TGT', 'LOW', 'CVS', 'KHC', 'KMB', 'CL', 'EL', 'CAG', 'GIS', 'MNST'],
    industrials: ['CAT', 'GE', 'HON', 'UPS', 'RTX', 'BA', 'DE', 'EMR', 'ITW', 'NOC', 'LMT', 'MMM', 'UNP', 'CSX', 'FDX', 'DAL', 'CARR', 'CP', 'JCI', 'PWR'],
    utilities: ['NEE', 'DUK', 'SO', 'AEP', 'EXC', 'NGG', 'D', 'ED', 'PPL', 'EIX', 'SRE', 'AES', 'CMS', 'FE', 'EVRG', 'NWE', 'CNP', 'ETR', 'XEL', 'LNT'],
    telecom: ['T', 'VZ', 'TMUS', 'CMCSA', 'CHTR', 'DIS', 'NFLX', 'EA', 'ATVI', 'PARA', 'ROKU', 'SONY', 'SPOT', 'NTES', 'BAND', 'SID', 'VOD'],
    'real-estate': ['PLD', 'AMT', 'CPT', 'DLR', 'EQIX', 'PSA', 'O', 'WELL', 'SPG', 'UDR', 'REG', 'AVB', 'EQR', 'MAA', 'BXP', 'VTR', 'EXR', 'INVH', 'ESS', 'KIM'],
    materials: ['LIN', 'APD', 'FCX', 'NEM', 'AA', 'NUE', 'CSTM', 'PPG', 'ECL', 'SHW', 'MOS', 'DOW', 'BHP', 'RIO', 'VALE', 'NTR', 'MLM', 'CF', 'ALB', 'ATI'],
    semiconductors: ['NVDA', 'AMD', 'INTC', 'QCOM', 'AVGO', 'MU', 'MCHP', 'TXN', 'ADI', 'KLAC', 'NXPI', 'MRVL', 'ON', 'LRCX', 'SMCI', 'CREE', 'BRKS', 'MPWR', 'SWKS', 'SNPS'],
    forex: ['EURUSD', 'GBPUSD', 'USDJPY', 'USDINR', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD', 'USDMXN', 'NZDJPY', 'EURAUD', 'AUDJPY'],
  };

  function getCorrelationLabel(value) {
    if (value > 0.5) return { label: 'Positive', tone: 'positive' };
    if (value < -0.5) return { label: 'Negative', tone: 'negative' };
    return { label: 'Neutral', tone: 'neutral' };
  }

  function buildCorrelationSeries(symbol) {
    const row = marketData.find((item) => item.symbol === symbol) || { change: 0 };
    const base = Number(row.change) || 0;
    const drift = Math.max(0.35, Math.abs(base) / 4 + 0.5);
    const prefix = symbol.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0);

    return Array.from({ length: 6 }, (_, index) => {
      const steps = index - 2.5;
      const offset = steps * drift;
      const noise = ((prefix % 11) - 5) * 0.18;
      return Number((base + offset + noise).toFixed(3));
    });
  }

  function pearsonCorrelation(left, right) {
    if (left.length !== right.length || left.length < 2) return 0;

    const meanLeft = left.reduce((sum, value) => sum + value, 0) / left.length;
    const meanRight = right.reduce((sum, value) => sum + value, 0) / right.length;
    let numerator = 0;
    let leftVariance = 0;
    let rightVariance = 0;

    for (let index = 0; index < left.length; index += 1) {
      const leftDelta = left[index] - meanLeft;
      const rightDelta = right[index] - meanRight;
      numerator += leftDelta * rightDelta;
      leftVariance += leftDelta * leftDelta;
      rightVariance += rightDelta * rightDelta;
    }

    const denominator = Math.sqrt(leftVariance * rightVariance);
    if (!denominator) return 0;
    return Math.max(-1, Math.min(1, numerator / denominator));
  }

  function getCorrelationLabelText(symbol) {
    const company = marketData.find((row) => row.symbol === symbol);
    return company ? `${company.company} (${symbol})` : (supplyDemandForexPairs[symbol] || symbol);
  }

  function renderCorrelationAnalysis() {
    const select = $('#correlationCompanies');
    const selectedSymbols = Array.from(select.selectedOptions).map((option) => option.value);

    if (selectedSymbols.length < 2) {
      $('#correlationNotice').textContent = 'Choose at least two instruments to compare their relative movement.';
      $('#correlationPairs').innerHTML = '';
      $('#correlationMatrix').innerHTML = '';
      return;
    }

    const pairs = [];
    for (let leftIndex = 0; leftIndex < selectedSymbols.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < selectedSymbols.length; rightIndex += 1) {
        const left = selectedSymbols[leftIndex];
        const right = selectedSymbols[rightIndex];
        const value = pearsonCorrelation(buildCorrelationSeries(left), buildCorrelationSeries(right));
        const reading = getCorrelationLabel(value);
        pairs.push({ left, right, value, reading });
      }
    }

    pairs.sort((a, b) => Math.abs(b.value) - Math.abs(a.value));

    $('#correlationNotice').textContent =
      `${selectedSymbols.length} instruments selected; ${pairs.length} pair readings are ready.`;

    $('#correlationPairs').innerHTML = pairs.length
      ? pairs.map(({ left, right, value, reading }) => `
        <article class="correlation-pair-card">
          <div class="correlation-pair-companies">
            <span>
              <strong>${escapeHtml(getCorrelationLabelText(left))}</strong>
              <small>vs ${escapeHtml(getCorrelationLabelText(right))}</small>
            </span>
            <a class="correlation-pair-link" href="https://www.tradingview.com/chart/" target="_blank" rel="noopener noreferrer">Chart ↗</a>
          </div>
          <div class="correlation-pair-reading ${reading.tone}">
            ${reading.label} relationship
          </div>
          <div class="correlation-scale" aria-label="Correlation strength ${value.toFixed(2)}">
            <span class="correlation-scale-marker" style="left:${((value + 1) / 2) * 100}%"></span>
          </div>
          <div class="correlation-scale-labels">
            <span>Negative</span>
            <span>Neutral</span>
            <span>Positive</span>
          </div>
          <p class="correlation-pair-value">
            <strong>${value.toFixed(2)}</strong>
            <span> relative movement score</span>
          </p>
        </article>
      `).join('')
      : '<p class="muted">No pair comparisons are available for this selection.</p>';

    const matrixCells = selectedSymbols.map((leftSymbol) => {
      const row = [`<th>${escapeHtml(getCorrelationLabelText(leftSymbol))}</th>`];
      for (const rightSymbol of selectedSymbols) {
        const value = pearsonCorrelation(
          buildCorrelationSeries(leftSymbol),
          buildCorrelationSeries(rightSymbol)
        );
        const reading = getCorrelationLabel(value);
        const cellValue = leftSymbol === rightSymbol ? '1.00' : value.toFixed(2);
        row.push(`
          <td class="correlation-cell">
            <span class="${reading.tone}">${cellValue}</span>
            <small>${leftSymbol === rightSymbol ? 'Self' : reading.label}</small>
          </td>
        `);
      }
      return `<tr>${row.join('')}</tr>`;
    }).join('');

    $('#correlationMatrix').innerHTML = `
      <table>
        <thead>
          <tr>
            <th></th>
            ${selectedSymbols.map((symbol) => `<th>${escapeHtml(symbol)}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${matrixCells}
        </tbody>
      </table>
    `;
  }

  function populateCorrelationCompanies(group = 'all') {
    const select = $('#correlationCompanies');
    const chosenGroup = correlationGroups[group] || correlationGroups.all;
    const groupOptions = chosenGroup.map((symbol) => {
      const option = document.createElement('option');
      option.value = symbol;
      option.textContent = getCorrelationLabelText(symbol);
      return option;
    });

    select.replaceChildren(...groupOptions);
    Array.from(select.options).forEach((option, index) => {
      option.selected = index < Math.min(6, select.options.length);
    });
    renderCorrelationAnalysis();
  }

  function populatePersonalFeatureSymbols() {
    const stockOptions = marketData.map(({ symbol, company }) => {
      const option = document.createElement('option');
      option.value = symbol;
      option.textContent = `${company} (${symbol})`;
      return option;
    });
    $('#portfolioSymbol').replaceChildren(...stockOptions.map((option) => option.cloneNode(true)));
    const alertOptions = stockOptions.map((option) => option.cloneNode(true));
    const otherInstruments = document.createElement('optgroup');
    otherInstruments.label = 'Forex and commodities';
    [
      ...Object.entries(supplyDemandForexPairs).map(([symbol, pair]) => [symbol, pair]),
      ['GOLD', 'Gold futures (GC=F)'],
    ].forEach(([symbol, label]) => {
      const option = document.createElement('option');
      option.value = symbol;
      option.textContent = label;
      otherInstruments.append(option);
    });
    alertOptions.push(otherInstruments);
    $('#priceAlertSymbol').replaceChildren(...alertOptions);
  }

  async function loadSupplyDemand(symbol = $('#supplyDemandSymbol').value) {
    const timeframe = $('#supplyDemandTimeframe').value;
    const timeframeLabel = supplyDemandTimeframeLabels[timeframe] || '5-minute';
    const status = $('#supplyDemandNotice');
    status.textContent = `Loading ${timeframeLabel} candles for ${symbol}...`;
    $('#supplyDemandPrice').textContent = '—';
    $('#supplyDemandAsOf').textContent = '';
    $('#demandZones').replaceChildren();
    $('#supplyZones').replaceChildren();
    const query = new URLSearchParams({
      symbol,
      timeframe,
      compare: timeframe === '5m' ? '1' : '0',
    });
    const payload = await getJson(`/api/supply-demand?${query}`);
    if (
      symbol !== $('#supplyDemandSymbol').value ||
      timeframe !== $('#supplyDemandTimeframe').value
    ) {
      return;
    }
    renderSupplyDemand(payload);
  }

  function populateSupplyDemandCompanies() {
    const select = $('#supplyDemandSymbol');
    const stocks = document.createElement('optgroup');
    stocks.label = 'Stocks';
    marketData.forEach((company) => {
      const option = document.createElement('option');
      option.value = company.symbol;
      option.textContent = `${company.company} (${company.symbol})`;
      stocks.append(option);
    });

    const usedSymbols = new Set(marketData.map((company) => company.symbol));
    const indianCompanies = document.createElement('optgroup');
    indianCompanies.label = 'Indian stocks';
    Object.entries(supplyDemandIndianCompanies).forEach(([symbol, company]) => {
      if (usedSymbols.has(symbol)) return;
      const option = document.createElement('option');
      option.value = symbol;
      option.textContent = company;
      indianCompanies.append(option);
    });
    const forexPairs = document.createElement('optgroup');
    forexPairs.label = 'Forex pairs';
    Object.entries(supplyDemandForexPairs).forEach(([symbol, pair]) => {
      const option = document.createElement('option');
      option.value = symbol;
      option.textContent = `${pair} · Forex`;
      forexPairs.append(option);
    });
    const commodities = document.createElement('optgroup');
    commodities.label = 'Commodities';
    const gold = document.createElement('option');
    gold.value = 'GOLD';
    gold.textContent = 'Gold futures · GC=F';
    commodities.append(gold);

    select.replaceChildren(
      stocks,
      indianCompanies,
      forexPairs,
      commodities
    );
    select.value = marketData.some(
      (company) => company.symbol === defaultSupplyDemandSymbol
    ) ? defaultSupplyDemandSymbol : select.options[0]?.value || '';
  }

  function renderSupplyDemandTradingViewChart() {
    const symbol = $('#supplyDemandSymbol').value;
    const timeframe = $('#supplyDemandTimeframe').value;
    const timeframeLabel = supplyDemandTimeframeLabels[timeframe] || '5-minute';
    if (!symbol || typeof window.showTradingViewChart !== 'function') return;

    window.showTradingViewChart(
      symbol,
      '1',
      'supply-demand-tradingview-chart',
      tradingViewIntervals[timeframe] || '5'
    );
    $('#sdLiveChartHeading').textContent = `${timeframeLabel} candle chart`;
    $('#sdLiveChartDescription').textContent =
      `TradingView chart for the selected instrument · ${timeframeLabel} timeframe. Zone calculations use recent Yahoo Finance ${timeframeLabel} candles.`;
    $('#supply-demand-tradingview-chart').setAttribute(
      'aria-label',
      `TradingView ${timeframeLabel} candle chart`
    );
    const link = $('#supplyDemandTradingViewLink');
    const tradingViewSymbol = {
      AAPL: 'NASDAQ:AAPL',
      MSFT: 'NASDAQ:MSFT',
      NVDA: 'NASDAQ:NVDA',
      JPM: 'NYSE:JPM',
      BAC: 'NYSE:BAC',
      GS: 'NYSE:GS',
      XOM: 'NYSE:XOM',
      TSLA: 'NASDAQ:TSLA',
      RELIANCE: 'NSE:RELIANCE',
      TCS: 'NSE:TCS',
      INFY: 'NSE:INFY',
      HDFCBANK: 'NSE:HDFCBANK',
      ICICIBANK: 'NSE:ICICIBANK',
      SBIN: 'NSE:SBIN',
      EURUSD: 'FX:EURUSD',
      GBPUSD: 'FX:GBPUSD',
      USDJPY: 'FX:USDJPY',
      USDINR: 'FX:USDINR',
      AUDUSD: 'FX:AUDUSD',
      USDCAD: 'FX:USDCAD',
      USDCHF: 'FX:USDCHF',
      NZDUSD: 'FX:NZDUSD',
      GOLD: 'COMEX:GC1!',
    }[symbol] || symbol;
    link.href =
      `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tradingViewSymbol)}` +
      `&interval=${encodeURIComponent(tradingViewIntervals[timeframe] || '5')}`;
  }

  async function loadCareers() {
    const status = $('#careerStatus');
    status.textContent = 'Searching current openings...';

    const keyword = $('#careerKeyword').value.trim();
    const location = $('#careerLocation').value.trim();
    const company = $('#careerCompany').value;
    updateCareerPortalLinks(keyword, location, company);
    const query = new URLSearchParams({ q: keyword, location, company, page: String(careerPage) });
    const payload = await getJson(`/api/careers?${query}`);
    const jobs = Array.isArray(payload.jobs) ? payload.jobs : [];

    $('#careerResults').innerHTML = jobs.length
      ? jobs.map((job) => {
          const salary = job.salary_min != null || job.salary_max != null
            ? `<p>Salary: ${job.salary_min != null ? `₹${Number(job.salary_min).toLocaleString('en-IN')}` : ''}${job.salary_min != null && job.salary_max != null ? ' – ' : ''}${job.salary_max != null ? `₹${Number(job.salary_max).toLocaleString('en-IN')}` : ''}</p>`
            : '';
          const posted = job.created && !Number.isNaN(Date.parse(job.created))
            ? `<p class="muted">Posted ${escapeHtml(new Date(job.created).toLocaleDateString())}</p>`
            : '';
          const skills = Array.isArray(job.skills) && job.skills.length
            ? `<p>${job.skills.map(escapeHtml).join(' · ')}</p>`
            : '';
          const description = job.description
            ? `<p>${escapeHtml(job.description.trim().slice(0, 280))}${job.description.trim().length > 280 ? '…' : ''}</p>`
            : '';
          const applyLink = job.url
            ? `<a href="${escapeHtml(job.url)}" target="_blank" rel="noopener noreferrer">View opening / Apply ↗</a>`
            : job.company_url
              ? `<a href="${escapeHtml(job.company_url)}" target="_blank" rel="noopener noreferrer">Visit careers page ↗</a>`
              : '';
          return `
          <article class="career-card">
            <h4>${escapeHtml(job.title)}</h4>
            <p class="muted">${escapeHtml(job.company)}</p>
            <p>${escapeHtml(job.location)}</p>
            <p>${escapeHtml(job.type || 'Job')}</p>
            ${description}${skills}${salary}${posted}
            ${applyLink}
          </article>
        `;
        }).join('')
      : payload.live
        ? '<p class="muted">No openings matched those filters. Try a broader role or location.</p>'
        : '<p class="muted">No live feed is connected for in-app listings. Open a live company search above.</p>';

    const sourceLabel = payload.live
      ? `Live openings via ${payload.source}`
      : `${payload.source || 'No live feed connected'}. Use the live search links below.`;
    if (payload.live) {
      status.textContent = `${sourceLabel}. ${Number(payload.count || 0).toLocaleString()} matching opening${payload.count === 1 ? '' : 's'}${company ? ` at ${company}` : ''}${keyword ? ` for “${keyword}”` : ''}${location ? ` in ${location}` : ''}.`;
    } else {
      status.textContent = sourceLabel;
    }
    const pagination = $('#careerPagination');
    const totalPages = Math.max(1, Number(payload.pages) || 1);
    pagination.classList.toggle('hidden', totalPages <= 1);
    $('#careerPrevious').disabled = careerPage <= 1;
    $('#careerNext').disabled = careerPage >= totalPages;
    $('#careerPageLabel').textContent = `Page ${payload.page || careerPage} of ${totalPages}`;
  }

  function updateCareerPortalLinks(keyword, location, company = $('#careerCompany').value) {
    const wordsToSlug = (value) => value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
    const term = keyword.trim();
    const place = location.trim();
    const employer = company.trim();
    const searchPhrase = [term, employer ? `at ${employer}` : '', place].filter(Boolean).join(' ');
    const locationSlug = wordsToSlug(place);
    const searchSlug = wordsToSlug([term, employer].filter(Boolean).join(' '));
    const naukriPath = searchSlug
      ? `${searchSlug}-jobs${locationSlug ? `-in-${locationSlug}` : ''}`
      : locationSlug
        ? `jobs-in-${locationSlug}`
        : 'jobs';
    const workIndiaPath = locationSlug
      ? `jobs-in-${locationSlug}/`
      : 'jobs/';
    const workIndiaQuery = new URLSearchParams();
    if (term) workIndiaQuery.set('search', [term, employer].filter(Boolean).join(' '));
    const linkedInQuery = new URLSearchParams();
    if (term || employer) linkedInQuery.set('keywords', [term, employer].filter(Boolean).join(' '));
    if (place) linkedInQuery.set('location', place);
    const workIndiaQueryString = workIndiaQuery.toString();
    const linkedInQueryString = linkedInQuery.toString();
    const urls = {
      naukri: `https://www.naukri.com/${naukriPath}`,
      workindia: `https://www.workindia.in/${workIndiaPath}${workIndiaQueryString ? `?${workIndiaQueryString}` : ''}`,
      linkedin: `https://www.linkedin.com/jobs/search/${linkedInQueryString ? `?${linkedInQueryString}` : ''}`,
      google: `https://www.google.com/search?q=${encodeURIComponent(`${searchPhrase || 'jobs'} jobs`)}`,
    };

    document.querySelectorAll('[data-career-portal]').forEach((link) => {
      link.href = urls[link.dataset.careerPortal];
    });
  }

  async function loadNews() {
    const status = $('#newsStatus');
    const results = $('#newsResults');

    const symbol = $('#newsSymbol').value;
    updateNewsPortalLinks(symbol);
    results.replaceChildren();

    if (
      symbol === 'FOREX' ||
      symbol === 'INDIA' ||
      symbol.startsWith('FX:') ||
      Object.prototype.hasOwnProperty.call(indianCompanies, symbol)
    ) {
      status.textContent =
        'Use the source links above for current headlines. These sites open externally; no live feed is connected for this category.';
      return;
    }

    status.textContent = 'Loading news...';
    try {
      const query = new URLSearchParams({ symbol, limit: '40' });
      const articles = await getJson(`/api/news?${query}`);

      if (!articles.length) {
        status.textContent =
          'No news articles were returned for this selection.';
        return;
      }

      results.innerHTML = renderNewsCards(articles);

      status.textContent =
        `${articles.length} news article${articles.length === 1 ? '' : 's'} loaded.`;
    } catch (error) {
      status.textContent = error.message;
    }
  }

  function renderNewsCards(articles) {
    return articles.map((article) => {
      const timestamp = Number(article.datetime);
      const published = Number.isFinite(timestamp) && timestamp > 0
        ? new Date(timestamp * 1000).toLocaleString()
        : 'Publication time unavailable';
      let safeUrl = '';

      try {
        const parsedUrl = new URL(article.url);
        if (parsedUrl.protocol === 'https:' || parsedUrl.protocol === 'http:') {
          safeUrl = parsedUrl.href;
        }
      } catch {
        safeUrl = '';
      }

      return `
        <article class="card">
          <h4>${escapeHtml(article.headline || 'Untitled article')}</h4>
          <p class="muted">
            ${escapeHtml(article.source || 'News source unavailable')}
            · ${escapeHtml(published)}
          </p>
          <p>${escapeHtml(article.summary || '')}</p>
          ${safeUrl
            ? `<a href="${escapeHtml(safeUrl)}"
                  target="_blank"
                  rel="noopener noreferrer">Read article</a>`
            : ''}
        </article>
      `;
    }).join('');
  }

  async function loadOverviewNewsFeed(symbol, resultsSelector, statusSelector) {
    const status = $(statusSelector);
    const results = $(resultsSelector);
    status.textContent = 'Loading headlines...';
    results.replaceChildren();

    try {
      const query = new URLSearchParams({ symbol, limit: '6' });
      const articles = await getJson(`/api/news?${query}`);
      if (!articles.length) {
        status.textContent = 'No headlines were returned for this feed.';
        return;
      }
      results.innerHTML = renderNewsCards(articles);
      status.textContent =
        `${articles.length} ${symbol === 'GENERAL' ? 'market' : 'company'} headlines loaded.`;
    } catch (error) {
      status.textContent = error.message;
    }
  }

  function loadOverviewNews() {
    const symbol = $('#overviewCompanyNewsSymbol').value;
    return Promise.all([
      loadOverviewNewsFeed(
        'GENERAL',
        '#overviewMarketNewsResults',
        '#overviewMarketNewsStatus'
      ),
      loadOverviewNewsFeed(
        symbol,
        '#overviewCompanyNewsResults',
        '#overviewCompanyNewsStatus'
      ),
    ]);
  }

  function updateNewsPortalLinks(selection) {
    const company = marketData.find((item) => item.symbol === selection);
    const searchLink = (label, url) => ({ label, url });
    let sources;
    let description;

    if (selection === 'FOREX' || selection.startsWith('FX:')) {
      const pair = selection.startsWith('FX:')
        ? selection.slice(3).replace(/(.{3})(.{3})/, '$1/$2')
        : '';
      const query = pair || 'forex major currencies exchange rates';
      const encodedQuery = encodeURIComponent(query);
      sources = [
        searchLink('FXStreet · Forex news', `https://www.fxstreet.com/news?query=${encodedQuery}`),
        searchLink('ForexLive · Currency news', `https://www.forexlive.com/?s=${encodedQuery}`),
        searchLink('Forex Factory · Calendar', 'https://www.forexfactory.com/calendar'),
        searchLink('Investing.com · Forex news', `https://www.investing.com/news/forex-news?search=${encodedQuery}`),
        searchLink('Reuters · Currency markets', `https://www.reuters.com/markets/currencies/`),
        searchLink('Federal Reserve · News', 'https://www.federalreserve.gov/newsevents.htm'),
        searchLink('ECB · Press releases', 'https://www.ecb.europa.eu/press/pr/html/index.en.html'),
        searchLink('RBI · Press releases', 'https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx'),
        searchLink('Google News · Search this topic', `https://news.google.com/search?q=${encodeURIComponent(`${query} forex currency news`)}`),
      ];
      description = pair
        ? `Major currency news and headlines for ${pair}. Sources open externally.`
        : 'Major forex and currency-market news sources. Sources open externally.';
    } else if (selection === 'INDIA') {
      sources = [
        searchLink('RBI · Press releases', 'https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx'),
        searchLink('NSE · Corporate announcements', 'https://www.nseindia.com/companies-listing/corporate-filings-announcements'),
        searchLink('BSE · Corporate announcements', 'https://www.bseindia.com/corporates/ann.html'),
        searchLink('Moneycontrol · Markets', 'https://www.moneycontrol.com/news/business/markets/'),
        searchLink('Economic Times · Markets', 'https://economictimes.indiatimes.com/markets'),
        searchLink('Google News · Indian markets', 'https://news.google.com/search?q=Indian+stock+market+news'),
      ];
      description = 'Indian market headlines, exchange announcements, and official RBI releases.';
    } else if (company || indianCompanies[selection]) {
      const companyName = company?.company || indianCompanies[selection];
      const companyQuery = `${companyName} ${selection} company news`;
      sources = [
        ...(company
          ? [searchLink('Yahoo Finance · Company news', `https://finance.yahoo.com/quote/${encodeURIComponent(company.symbol)}/news/`)]
          : []),
        searchLink('Google News · Company coverage', `https://news.google.com/search?q=${encodeURIComponent(companyQuery)}`),
        searchLink('Find official company newsroom', `https://www.google.com/search?q=${encodeURIComponent(`${companyName} official newsroom investor relations news`)}`),
        searchLink('Reuters · Company coverage', `https://www.reuters.com/site-search/?query=${encodeURIComponent(selection)}`),
        ...(indianCompanies[selection]
          ? [
            searchLink('NSE · Company announcements', `https://www.nseindia.com/get-quotes/equity?symbol=${encodeURIComponent(selection)}`),
            searchLink('BSE · Corporate announcements', 'https://www.bseindia.com/corporates/ann.html'),
            searchLink('Moneycontrol · Company coverage', `https://www.moneycontrol.com/news/tags/${encodeURIComponent(selection.toLowerCase())}.html`),
          ]
          : []),
      ];
      description = `News and announcements for ${companyName} (${selection}). Use official company, NSE, or BSE links for company-published updates.`;
    } else {
      sources = [
        searchLink('Reuters · Markets', 'https://www.reuters.com/markets/'),
        searchLink('CNBC · Markets', 'https://www.cnbc.com/markets/'),
        searchLink('Bloomberg · Markets', 'https://www.bloomberg.com/markets'),
        searchLink('Moneycontrol · Markets', 'https://www.moneycontrol.com/news/business/markets/'),
        searchLink('Economic Times · Markets', 'https://economictimes.indiatimes.com/markets'),
        searchLink('Google News · Global markets', 'https://news.google.com/search?q=global+financial+markets+news'),
      ];
      description = 'Global markets and business news from major publishers.';
    }

    $('#newsPortalDescription').textContent = description;
    $('#newsPortalLinks').replaceChildren(...sources.map(({ label, url }) => {
      const link = document.createElement('a');
      link.className = 'news-portal-link';
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = `${label} ↗`;
      return link;
    }));
  }

  async function loadDashboard() {
    const [market, sectors] = await Promise.all([
      getJson('/api/market'),
      getJson('/api/sectors'),
    ]);

    marketData = market.data;
    const careerCompanySelect = $('#careerCompany');
    careerCompanySelect.replaceChildren(new Option('Any tracked company', ''));
    marketData
      .filter((row) => !/\b(?:Group|Holdings)\s+\d+$/i.test(row.company))
      .sort((left, right) => left.company.localeCompare(right.company))
      .forEach((row) => {
        careerCompanySelect.add(new Option(`${row.company} (${row.symbol})`, row.company));
      });
    const liveRows = marketData.filter((row) => row.price_source === 'Finnhub');
    const summaryRows = liveRows.length ? liveRows : [];
    const averageChange = summaryRows.length
      ? summaryRows.reduce((sum, row) => sum + Number(row.change), 0) / summaryRows.length
      : null;
    const highestPerformer = summaryRows.reduce(
      (best, row) => !best || Number(row.change) > Number(best.change) ? row : best,
      null
    );
    const lowestPerformer = summaryRows.reduce(
      (worst, row) => !worst || Number(row.change) < Number(worst.change) ? row : worst,
      null
    );
    const notice = liveRows.length
      ? `${liveRows.length} live Finnhub quotes loaded. Rows marked “Illustrative data” are sample values, not live prices.`
      : 'Live quotes are unavailable. Prices marked “Illustrative data” are sample values, not live prices.';
    $('#marketDataNotice').textContent = notice;
    $('#marketExplorerNotice').textContent = notice;

    const stockOptions = $('#tradingviewStockOptions');
    stockOptions.replaceChildren(...marketData.map((row) => {
      const option = document.createElement('option');
      option.value = row.symbol;
      option.textContent = `${row.company} (${row.symbol})`;
      return option;
    }));

    $('#companyCount').textContent = marketData.length;
    $('#averageChange').textContent = averageChange === null
      ? 'Unavailable'
      : formatChange(averageChange);
    $('#bestPerformer').textContent = highestPerformer?.company || 'Unavailable';
    $('#bestPerformerDetail').textContent = highestPerformer
      ? `${highestPerformer.symbol} · ${formatChange(highestPerformer.change)}`
      : 'No market data available';
    $('#worstPerformer').textContent = lowestPerformer?.company || 'Unavailable';
    $('#worstPerformerDetail').textContent = lowestPerformer
      ? `${lowestPerformer.symbol} · ${formatChange(lowestPerformer.change)}`
      : 'No market data available';
    renderOverviewCompanies();

    $('#sectorFilter').innerHTML =
      '<option value="All">All sectors</option>' +
      sectors.map((sector) =>
        `<option value="${escapeHtml(sector)}">${escapeHtml(sector)}</option>`
      ).join('');

    renderMarket();
    renderHeatmap();

    if (window.Chart) {
      const chartRows = liveRows.length ? liveRows : marketData;
      const movers = [...chartRows]
        .sort((a, b) => Math.abs(b.change) - Math.abs(a.change))
        .slice(0, 20);
      renderMarketMoverLinks(movers.slice(0, 8));
      $('#marketMoversNotice').textContent = liveRows.length
        ? `Daily changes from ${liveRows.length} live Finnhub quotes.`
        : 'No live quotes are available; these daily changes are illustrative sample data.';

      const overviewSelector = $('#overviewTradingViewSymbol');
      overviewSelector.replaceChildren(...movers.map((row) => {
        const option = document.createElement('option');
        option.value = row.symbol;
        option.textContent = `${row.symbol} · ${Number(row.change) > 0 ? '+' : ''}${Number(row.change).toFixed(2)}%`;
        return option;
      }));
      if (movers.length && typeof window.showTradingViewChart === 'function') {
        window.showTradingViewChart(
          overviewSelector.value,
          '1',
          'overview-tradingview-chart'
        );
      }

      if (marketChart) marketChart.destroy();
      const chartTextColor = getThemeColor('--muted');
      const chartGridColor = getThemeColor('--table-rule');
      marketChart = new Chart($('#marketChart'), {
        type: 'bar',
        data: {
          labels: movers.map((row) => row.symbol),
          datasets: [{
            label: liveRows.length
              ? 'Live daily change (%) · Finnhub'
              : 'Illustrative daily change (%)',
            data: movers.map((row) => row.change),
            backgroundColor: movers.map((row) =>
              row.change >= 0
                ? getThemeColor('--accent')
                : getThemeColor('--danger')
            ),
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              ticks: { color: chartTextColor },
              grid: { color: chartGridColor },
            },
            y: {
              ticks: { color: chartTextColor },
              grid: { color: chartGridColor },
            },
          },
          plugins: {
            legend: {
              labels: { color: chartTextColor },
            },
          },
        },
      });
    }
  }

  document.querySelectorAll('.nav-button[data-section]').forEach((button) => {
    button.addEventListener('click', () => {
      navigate(button.dataset.section);

      if (button.dataset.section === 'news') {
        loadNews();
      }
    });
  });

  document.querySelectorAll('[data-profile-form]').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const status = document.getElementById(form.dataset.status);
      const button = form.querySelector('button[type="submit"]');
      button.disabled = true;
      status.textContent = 'Saving...';
      try {
        const payload = await getJson(form.dataset.url, {
          method: 'POST',
          body: new FormData(form),
        });
        status.textContent = payload.message;
        if (form.dataset.action === 'start-phone-verification') {
          $('#profilePhoneVerifyForm').classList.remove('hidden');
          $('#profilePhoneCode').focus();
        } else if (form.dataset.action === 'verify-phone') {
          $('#profilePhoneStatus').textContent = `Verified: ${payload.phone}`;
          form.reset();
          form.classList.add('hidden');
        } else if (form.dataset.url.endsWith('/password')) {
          form.reset();
        }
      } catch (error) {
        status.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  });

  $('#themeToggle').addEventListener('click', () => {
    const nextTheme = document.documentElement.dataset.theme === 'light'
      ? 'dark'
      : 'light';
    setTheme(nextTheme);
  });
  setTheme(document.documentElement.dataset.theme);

  $('#newsRefreshButton').addEventListener('click', loadNews);
  $('#newsSymbol').addEventListener('change', () => {
    updateNewsPortalLinks($('#newsSymbol').value);
    loadNews();
  });
  $('#overviewNewsButton').addEventListener('click', loadOverviewNews);
  $('#overviewCompanyNewsSymbol').addEventListener('change', () => {
    loadOverviewNewsFeed(
      $('#overviewCompanyNewsSymbol').value,
      '#overviewCompanyNewsResults',
      '#overviewCompanyNewsStatus'
    );
  });
  document.querySelectorAll('[data-open-news]').forEach((button) => {
    button.addEventListener('click', () => {
      $('#newsSymbol').value = button.dataset.openNews;
      navigate('news');
      loadNews();
    });
  });
  document.querySelector('[data-open-company-news]').addEventListener('click', () => {
    $('#newsSymbol').value = $('#overviewCompanyNewsSymbol').value;
    updateNewsPortalLinks($('#newsSymbol').value);
    navigate('news');
    loadNews();
  });

  $('#reportButton').addEventListener('click', () => {
    const menu = $('#reportMenu');
    const open = menu.classList.toggle('hidden');

    $('#reportButton').setAttribute('aria-expanded', String(!open));
  });

  $('#reportMenu').addEventListener('click', (event) => {
    const option = event.target.closest('[data-report-format]');
    if (!option) return;

    const paths = {
      pdf: '/api/report',
      csv: '/api/report/csv',
      xlsx: '/api/report/xlsx',
    };

    window.location.assign(paths[option.dataset.reportFormat]);
  });

  document.addEventListener('click', (event) => {
    if (!event.target.closest('.report-download')) {
      $('#reportMenu').classList.add('hidden');
      $('#reportButton').setAttribute('aria-expanded', 'false');
    }
  });

  $('#sectorFilter').addEventListener('change', () => {
    const selected = $('#sectorFilter').value;

    renderMarket(
      selected === 'All'
        ? marketData
        : marketData.filter((row) => row.sector === selected)
    );
  });

  $('#analyzeSupplyDemand').addEventListener('click', () => {
    loadSupplyDemand().catch((error) => {
      showSupplyDemandError(error);
    });
  });

  document.querySelectorAll('.correlation-group-button').forEach((button) => {
    button.addEventListener('click', () => {
      const group = button.dataset.correlationGroup;
      document.querySelectorAll('.correlation-group-button').forEach((groupButton) => {
        groupButton.setAttribute('aria-pressed', String(groupButton === button));
      });
      populateCorrelationCompanies(group);
    });
  });

  $('#correlationApply').addEventListener('click', () => {
    renderCorrelationAnalysis();
  });

  $('#correlationReset').addEventListener('click', () => {
    populateCorrelationCompanies('all');
  });

  $('#supplyDemandSymbol').addEventListener('change', () => {
    renderSupplyDemandTradingViewChart();
    loadSupplyDemand().catch((error) => {
      showSupplyDemandError(error);
    });
  });

  $('#supplyDemandTimeframe').addEventListener('change', () => {
    renderSupplyDemandTradingViewChart();
    loadSupplyDemand().catch((error) => {
      showSupplyDemandError(error);
    });
  });

  ['#demandZones', '#supplyZones'].forEach((selector) => {
    $(selector).addEventListener('click', async (event) => {
      const button = event.target.closest('[data-zone-alert]');
      if (!button) return;
      const status = $('#priceAlertStatus');
      const symbol = $('#supplyDemandSymbol').value;
      const timeframe = $('#supplyDemandTimeframe').value;
      status.textContent = `Creating an alert for ${symbol} entering this ${button.dataset.zoneType} zone...`;
      try {
        await featureRequest('/api/price-alerts/zone', 'POST', {
          symbol,
          timeframe,
          zone_type: button.dataset.zoneType,
          zone_low: button.dataset.zoneLow,
          zone_high: button.dataset.zoneHigh,
        });
        status.textContent = `Alert created for ${symbol} entering the ${button.dataset.zoneType} zone.`;
        await checkPriceAlerts();
      } catch (error) {
        status.textContent = error.message;
      }
    });
  });

  $('#portfolioShock').addEventListener('input', () => {
    const shock = Number($('#portfolioShock').value);
    $('#portfolioShockLabel').textContent = `${shock > 0 ? '+' : ''}${shock}%`;
    renderPortfolioScenario();
  });

  $('#priceAlertType').addEventListener('change', () => {
    const isPercent = $('#priceAlertType').value === 'percent';
    $('#priceAlertThresholdLabel span').textContent =
      isPercent ? 'Movement (%)' : 'Target price';
    $('#priceAlertThreshold').max = isPercent ? '1000' : '';
  });

  $('#priceAlertForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    const status = $('#priceAlertStatus');
    status.textContent = 'Saving price alert...';
    try {
      await featureRequest('/api/price-alerts', 'POST', {
        symbol: $('#priceAlertSymbol').value,
        alert_type: $('#priceAlertType').value,
        direction: $('#priceAlertDirection').value,
        threshold: $('#priceAlertThreshold').value,
      });
      $('#priceAlertForm').reset();
      $('#priceAlertType').dispatchEvent(new Event('change'));
      status.textContent = 'Price alert saved. It will be checked while this dashboard is open.';
      await loadPriceAlerts();
      await checkPriceAlerts();
    } catch (error) {
      status.textContent = error.message;
    }
  });

  $('#priceAlertPresets').addEventListener('click', async (event) => {
    const button = event.target.closest('[data-alert-preset]');
    if (!button) return;
    const [direction, threshold] = button.dataset.alertPreset.split(':');
    $('#priceAlertSymbol').value = $('#supplyDemandSymbol').value
      || $('#priceAlertSymbol').value;
    $('#priceAlertStatus').textContent =
      `Creating ${direction} ${threshold}% alert for ${$('#priceAlertSymbol').value}...`;
    try {
      await featureRequest('/api/price-alerts', 'POST', {
        symbol: $('#priceAlertSymbol').value,
        alert_type: 'percent',
        direction,
        threshold,
      });
      $('#priceAlertType').value = 'percent';
      $('#priceAlertType').dispatchEvent(new Event('change'));
      $('#priceAlertStatus').textContent =
        `${direction === 'above' ? '+' : '-'}${threshold}% alert created from the latest available price.`;
      await checkPriceAlerts();
    } catch (error) {
      $('#priceAlertStatus').textContent = error.message;
    }
  });

  $('#enablePriceNotifications').addEventListener('click', async () => {
    if (!('Notification' in window)) {
      $('#priceAlertStatus').textContent =
        'This browser does not support desktop notifications. Alerts will still appear here.';
      return;
    }
    const permission = await Notification.requestPermission();
    $('#priceAlertStatus').textContent = permission === 'granted'
      ? 'Browser notifications enabled.'
      : 'Notifications were not enabled. Alerts will still appear here while the dashboard is open.';
  });

  $('#priceAlertList').addEventListener('click', async (event) => {
    const button = event.target.closest('[data-remove-alert]');
    if (!button) return;
    try {
      await featureRequest(`/api/price-alerts/${button.dataset.removeAlert}`, 'DELETE');
      await loadPriceAlerts();
    } catch (error) {
      $('#priceAlertStatus').textContent = error.message;
    }
  });

  $('#portfolioForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    $('#portfolioNotice').textContent = 'Saving holding...';
    try {
      await featureRequest('/api/portfolio', 'POST', {
        symbol: $('#portfolioSymbol').value,
        quantity: $('#portfolioQuantity').value,
        average_cost: $('#portfolioAverageCost').value,
      });
      $('#portfolioForm').reset();
      await loadPortfolio();
    } catch (error) {
      $('#portfolioNotice').textContent = error.message;
    }
  });

  $('#portfolioPositions').addEventListener('click', async (event) => {
    const button = event.target.closest('[data-remove-position]');
    if (!button) return;
    try {
      await featureRequest(`/api/portfolio/${button.dataset.removePosition}`, 'DELETE');
      await loadPortfolio();
    } catch (error) {
      $('#portfolioNotice').textContent = error.message;
    }
  });

  $('#refreshPortfolio').addEventListener('click', () => {
    $('#portfolioNotice').textContent = 'Refreshing Yahoo Finance prices...';
    loadPortfolio().catch((error) => {
      $('#portfolioNotice').textContent = error.message;
    });
  });

  $('#marketTable').addEventListener('click', (event) => {
    const button = event.target.closest('[data-chart-symbol]');
    if (!button) return;

    const symbol = button.dataset.chartSymbol;
    const selector = $('#tradingviewSymbolSelector');
    const chartSymbol = [...selector.options].find(
      (option) => option.value === symbol
    );

    if (!chartSymbol) return;

    selector.value = symbol;
    navigate('market');
    $('#tradingview-chart').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  $('#compareForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const symbols = encodeURIComponent(
        $('#compareInput').value.trim()
      );

      const payload = await getJson(`/api/compare?symbols=${symbols}`);

      $('#compareResults').innerHTML = payload.data.length
        ? payload.data.map((row) => `
            <article class="card">
              <strong>${escapeHtml(row.symbol)}</strong>
              <p>${escapeHtml(row.company)}</p>
              <p>${escapeHtml(row.sector)}</p>
              <p>
                $${Number(row.price).toFixed(2)} ·
                ${Number(row.change) > 0 ? '+' : ''}${Number(row.change).toFixed(2)}%
              </p>
              <p class="muted">
                ${escapeHtml(row.price_source || 'Illustrative data')}
              </p>
            </article>
          `).join('')
        : '<p class="muted">No matching symbols found.</p>';
    } catch (error) {
      $('#compareResults').textContent = error.message;
    }
  });

  $('#careerSearchForm').addEventListener('submit', (event) => {
    event.preventDefault();
    careerPage = 1;

    loadCareers().catch((error) => {
      $('#careerStatus').textContent = error.message;
      $('#careerResults').replaceChildren();
    });
  });
  $('#careerPrevious').addEventListener('click', () => {
    if (careerPage <= 1) return;
    careerPage -= 1;
    loadCareers().catch((error) => {
      $('#careerStatus').textContent = error.message;
      $('#careerResults').replaceChildren();
    });
  });
  $('#careerNext').addEventListener('click', () => {
    careerPage += 1;
    loadCareers().catch((error) => {
      $('#careerStatus').textContent = error.message;
      $('#careerResults').replaceChildren();
    });
  });
  $('#propMatchForm').addEventListener('submit', renderPropFirmMatches);

  const refreshCareerPortalLinks = () => {
      updateCareerPortalLinks(
        $('#careerKeyword').value,
        $('#careerLocation').value
      );
  };
  $('#overviewCompanySearch').addEventListener('input', renderOverviewCompanies);
  ['input', 'change'].forEach((eventName) => {
    $('#careerKeyword').addEventListener(eventName, refreshCareerPortalLinks);
    $('#careerLocation').addEventListener(eventName, refreshCareerPortalLinks);
    $('#careerCompany').addEventListener(eventName, refreshCareerPortalLinks);
  });

  updateCareerPortalLinks(
    $('#careerKeyword').value,
    $('#careerLocation').value
  );

  document.querySelectorAll('.career-quick-search').forEach((button) => {
    button.addEventListener('click', () => {
      $('#careerKeyword').value = button.dataset.keyword;
      careerPage = 1;
      updateCareerPortalLinks(
        $('#careerKeyword').value,
        $('#careerLocation').value
      );

      loadCareers().catch((error) => {
        $('#careerStatus').textContent = error.message;
        $('#careerResults').replaceChildren();
      });
    });
  });

  async function executeAssistantAction(action) {
    if (!action || typeof action !== 'object') return;

    if (action.type === 'navigate') {
      navigate(action.page);
      if (action.page === 'news') await loadNews();
      if (action.page === 'supplyDemand') {
        try {
          await loadSupplyDemand();
        } catch (error) {
          showSupplyDemandError(error);
        }
      }
      return;
    }

    if (action.type === 'market') {
      if (action.sector) {
        const sectorExists = [...$('#sectorFilter').options]
          .some((option) => option.value === action.sector);
        if (!sectorExists) {
          throw new Error(`The ${action.sector} sector is not available.`);
        }
        $('#sectorFilter').value = action.sector;
        renderMarket(marketData.filter((row) => row.sector === action.sector));
      }

      navigate('market');
      if (action.symbol) {
        const selector = $('#tradingviewSymbolSelector');
        const option = [...selector.options]
          .find((item) => item.value === action.symbol);
        if (!option) {
          throw new Error(`The ${action.symbol} chart is not available.`);
        }
        selector.value = action.symbol;
        selector.dispatchEvent(new Event('change'));
        $('#tradingview-chart').scrollIntoView({
          behavior: 'smooth',
          block: 'start',
        });
      }
      return;
    }

    if (action.type === 'search_careers') {
      $('#careerKeyword').value = action.keyword;
      $('#careerLocation').value = action.location;
      careerPage = 1;
      updateCareerPortalLinks(action.keyword, action.location);
      navigate('careers');
      await loadCareers();
      return;
    }

    if (action.type === 'show_news' || action.type === 'refresh_news') {
      const selector = $('#newsSymbol');
      const option = [...selector.options]
        .find((item) => item.value === action.symbol);
      if (!option) {
        throw new Error(`News for ${action.symbol} is not available.`);
      }
      selector.value = action.symbol;
      updateNewsPortalLinks(action.symbol);
      navigate('news');
      await loadNews();
      return;
    }

    if (action.type === 'supply_demand') {
      const symbol = Array.isArray(action.symbols) ? action.symbols[0] : '';
      if (symbol && [...$('#supplyDemandSymbol').options]
        .some((option) => option.value === symbol)) {
        $('#supplyDemandSymbol').value = symbol;
      }
      navigate('supplyDemand');
      try {
        await loadSupplyDemand();
      } catch (error) {
        showSupplyDemandError(error);
      }
      return;
    }

    if (action.type === 'compare') {
      if (!Array.isArray(action.symbols) || action.symbols.length < 2) return;
      $('#compareInput').value = action.symbols.join(', ');
      navigate('market');
      $('#compareForm').requestSubmit();
      $('#compareForm').scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    if (action.type === 'report') {
      const reportPaths = {
        pdf: '/api/report',
        csv: '/api/report/csv',
        xlsx: '/api/report/xlsx',
      };
      const path = reportPaths[action.format];
      if (!path) throw new Error('That report format is not supported.');
      window.location.assign(path);
      return;
    }

    if (action.type === 'refresh_dashboard') {
      await loadDashboard();
      await loadOverviewNews();
      navigate('overview');
    }
  }

  $('#assistantToggle').addEventListener('click', () => {
    const isOpen = $('#assistantPanel').classList.toggle('hidden') === false;
    $('#assistantToggle').setAttribute('aria-expanded', String(isOpen));
    if (!isOpen && voiceRecognition) voiceRecognition.stop();
  });

  $('#closeAssistant').addEventListener('click', () => {
    $('#assistantPanel').classList.add('hidden');
    $('#assistantToggle').setAttribute('aria-expanded', 'false');
    if (voiceRecognition) voiceRecognition.stop();
  });

  $('#newAssistantChat').addEventListener('click', () => {
    if (voiceRecognition) voiceRecognition.stop();
    assistantHistory.length = 0;
    $('#assistantMessages').replaceChildren();
    addAssistantMessage(assistantWelcome, 'bot');
    $('#voiceStatus').textContent = '';
    $('#assistantInput').focus();
  });

  $('#assistantForm').addEventListener('submit', async (event) => {
    event.preventDefault();

    const input = $('#assistantInput');
    const message = input.value.trim();

    if (!message) return;

    const sendButton = $('#assistantForm button[type="submit"]');
    const newChatButton = $('#newAssistantChat');
    sendButton.disabled = true;
    newChatButton.disabled = true;
    $('#assistantMessages').setAttribute('aria-busy', 'true');
    addAssistantMessage(message, 'user');
    input.value = '';

    try {
      const response = await getJson('/api/assistant', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, history: assistantHistory }),
      });

      assistantHistory.push(
        { role: 'user', content: message },
        {
          role: 'assistant',
          content: response.message,
          context: response.context,
        }
      );
      if (assistantHistory.length > 20) {
        assistantHistory.splice(0, assistantHistory.length - 20);
      }

      addAssistantMessage(response.message, 'bot');
      await executeAssistantAction(response.action);
    } catch (error) {
      addAssistantMessage(
        `Jarvis couldn't complete that action: ${error.message}`,
        'bot'
      );
    } finally {
      sendButton.disabled = false;
      newChatButton.disabled = false;
      $('#assistantMessages').setAttribute('aria-busy', 'false');
      input.focus();
    }
  });

  $('#voiceButton').addEventListener('click', () => {
    if (voiceRecognition) {
      voiceRecognition.stop();
      return;
    }

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      $('#voiceStatus').textContent =
        'Voice input is not supported by this browser. You can type a command instead.';
      return;
    }

    voiceRecognition = new SpeechRecognition();
    voiceRecognition.lang = 'en-IN';
    voiceRecognition.interimResults = false;
    voiceRecognition.maxAlternatives = 1;
    $('#voiceButton').textContent = 'Listening… Click to stop';
    $('#voiceButton').setAttribute('aria-pressed', 'true');
    $('#voiceStatus').textContent = 'Listening for a command…';

    voiceRecognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript.trim();
      $('#assistantInput').value = transcript;
      $('#voiceStatus').textContent = transcript
        ? `Heard: “${transcript}”`
        : 'No command was recognized.';
      if (transcript) $('#assistantForm').requestSubmit();
    };

    voiceRecognition.onerror = (event) => {
      const errorMessages = {
        'not-allowed': 'Microphone access was denied. Allow access or type a command.',
        'no-speech': 'No speech was detected. Please try again.',
      };
      $('#voiceStatus').textContent =
        errorMessages[event.error] || `Voice input failed: ${event.error}.`;
    };

    voiceRecognition.onend = () => {
      voiceRecognition = null;
      $('#voiceButton').textContent = '🎙 Start voice command';
      $('#voiceButton').setAttribute('aria-pressed', 'false');
    };

    try {
      voiceRecognition.start();
    } catch (error) {
      $('#voiceStatus').textContent =
        `Voice input could not start: ${error.message}`;
      voiceRecognition = null;
      $('#voiceButton').textContent = '🎙 Start voice command';
      $('#voiceButton').setAttribute('aria-pressed', 'false');
    }
  });

  loadDashboard()
    .catch((error) => {
      console.error('Could not load FinPulse dashboard:', error);
      $('#averageChange').textContent = 'Market data unavailable';
    })
    .then(() => {
      populateSupplyDemandCompanies();
      populateCorrelationCompanies('all');
      populatePersonalFeatureSymbols();
      marketData.forEach(({ symbol, company }) => {
        const option = document.createElement('option');
        option.value = symbol;
        option.textContent = `${company} (${symbol})`;
        $('#newsSymbol').append(option);
      });
      const overviewCompanySelector = $('#overviewCompanyNewsSymbol');
      overviewCompanySelector.replaceChildren(...marketData.map(({ symbol, company }) => {
        const option = document.createElement('option');
        option.value = symbol;
        option.textContent = `${company} (${symbol})`;
        return option;
      }));
      overviewCompanySelector.value = marketData.some(({ symbol }) => symbol === 'AAPL')
        ? 'AAPL'
        : marketData[0]?.symbol || '';
      loadOverviewNews();
      const currencies = document.createElement('optgroup');
      currencies.label = 'Major currency pairs';
      [
        ['FX:EURUSD', 'EUR/USD'],
        ['FX:GBPUSD', 'GBP/USD'],
        ['FX:USDJPY', 'USD/JPY'],
        ['FX:USDINR', 'USD/INR'],
        ['FX:AUDUSD', 'AUD/USD'],
        ['FX:USDCAD', 'USD/CAD'],
        ['FX:USDCHF', 'USD/CHF'],
        ['FX:NZDUSD', 'NZD/USD'],
      ].forEach(([value, label]) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        currencies.append(option);
      });
      $('#newsSymbol').append(currencies);
      updateNewsPortalLinks('GENERAL');
      if (marketData.length) {
        loadSupplyDemand().catch((error) => {
          showSupplyDemandError(error);
        });
      } else {
        $('#supplyDemandNotice').textContent =
          'Company data is unavailable, so zones cannot be loaded.';
      }
    });

  window.setInterval(() => {
    checkPriceAlerts().catch((error) => {
      $('#priceAlertStatus').textContent = error.message;
    });
  }, 60000);
})();
