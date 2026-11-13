const REGION_MAP = {
  Todas: 'Todas',
  'América do Norte': 'América do Norte',
  Europa: 'Europa',
  Ásia: 'Ásia',
  'América do Sul': 'América do Sul',
  Oceania: 'Oceania',
  África: 'África',
};

const fmtInt = (n) => new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 }).format(Number(n) || 0);
const fmt = (n) => new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 }).format(Number(n) || 0);
const pct = (n) => `${fmt(n)}%`;
const money = (n) => {
  const num = Number(n) || 0;
  const prefix = num < 0 ? '-US$ ' : 'US$ ';
  return prefix + fmtInt(Math.abs(num));
};

const capFirst = (s) => {
  const str = String(s ?? '').trim();
  return str ? str.charAt(0).toUpperCase() + str.slice(1) : '';
};

const escapeHtml = (s) =>
  String(s ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[c]));

async function json(url, opts) {
  const r = await fetch(url, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const msg = data?.error?.message || data?.detail?.[0]?.msg || data?.detail || `Erro HTTP ${r.status}`;
    throw Error(String(msg));
  }
  return data;
}

function showError(err) {
  const banner = document.querySelector('#global-error');
  const text = document.querySelector('#global-error-text');
  if (!banner || !text) return;
  const msg = err?.message || String(err) || 'Erro inesperado ao consultar o servidor.';
  text.textContent = `Não Foi Possível Atualizar os Dados: ${msg}`;
  banner.hidden = false;
}

function clearError() {
  const banner = document.querySelector('#global-error');
  if (banner) banner.hidden = true;
}

function setPageLoading(pageId, loading) {
  const el = document.getElementById(pageId);
  if (!el) return;
  el.classList.toggle('is-loading', loading);
  el.setAttribute('aria-busy', loading ? 'true' : 'false');
}

document.querySelector('#global-error-close')?.addEventListener('click', clearError);

/* Navigation */
function page(id) {
  document.querySelectorAll('.page').forEach((x) => x.classList.toggle('active', x.id === id));
  document.querySelectorAll('.nav-btn, .bottom-item').forEach((x) => {
    const isActive = x.dataset.page === id;
    x.classList.toggle('active', isActive);
    if (isActive) {
      x.setAttribute('aria-current', 'page');
    } else {
      x.removeAttribute('aria-current');
    }
  });
  window.scrollTo(0, 0);
  if (id === 'overview') loadOverview(document.querySelector('#region-filter')?.value || 'Todas').catch(showError);
  if (id === 'bi') loadBI().catch(showError);
  if (id === 'routes') loadRoutes().catch(showError);
  if (id === 'predict') initPredictOptions().catch(showError);
}

document.querySelectorAll('[data-page]').forEach((b) => {
  b.addEventListener('click', () => page(b.dataset.page));
});

document.querySelectorAll('[data-goto]').forEach((b) => {
  b.addEventListener('click', () => page(b.dataset.goto));
});

/* Tab 1: Overview */
async function loadOverview(region = 'Todas') {
  setPageLoading('overview', true);
  try {
    const mapped = REGION_MAP[region] || region;
    const d = await json(`/api/overview?region=${encodeURIComponent(mapped)}`);
    clearError();

    document.querySelector('#ov-rows').textContent = fmtInt(d.rows);
    document.querySelector('#ov-unique-orders').textContent = `${fmtInt(d.unique_orders)} Pedidos Únicos no Recorte`;
    document.querySelector('#ov-risk').textContent = pct(d.late_risk_pct);
    document.querySelector('#ov-delay-note').textContent = `${fmtInt(d.late_rows)} Linhas · Atraso Médio: ${fmt(d.avg_delay_days)} Dias`;

    const list = document.querySelector('#overview-regions-list');
    if (!d.regions || d.regions.length === 0) {
      list.innerHTML = '<div class="route-empty">Nenhum Registro Encontrado para a Região Selecionada.</div>';
      return;
    }

    const max = Math.max(...d.regions.map((x) => Number(x.orders) || 0), 1);
    list.innerHTML = d.regions
      .slice(0, 6)
      .map(
        (r) => `
          <div class="region-row">
            <span>${escapeHtml(r['order region'])}</span>
            <div class="bar"><i style="width:${Math.max(3, (Number(r.orders) / max) * 100)}%"></i></div>
            <b>${fmtInt(r.orders)} Linhas · ${pct(r.risk_pct)} Risco</b>
          </div>`
      )
      .join('');
  } finally {
    setPageLoading('overview', false);
  }
}

document.querySelector('#region-filter')?.addEventListener('change', (e) => {
  loadOverview(e.target.value).catch(showError);
});

/* Tab 2: BI Executive */
let biData = null;

function barRows(rows, labelKey, valueKey, detailFn) {
  const max = Math.max(...rows.map((r) => Number(r[valueKey]) || 0), 1);
  return rows
    .map(
      (r) => `
        <div class="chart-row">
          <div class="chart-label">
            <b>${escapeHtml(r[labelKey])}</b>
            <small>${escapeHtml(detailFn(r))}</small>
          </div>
          <div class="chart-track"><i style="width:${Math.max(2, ((Number(r[valueKey]) || 0) / max) * 100)}%"></i></div>
          <strong>${money(r[valueKey])}</strong>
        </div>`
    )
    .join('');
}

function renderBIScenario() {
  const slider = document.querySelector('#bi-reduction');
  if (!slider) return;
  const percent = Number(slider.value) || 0;
  const e = biData?.observed?.europe || {
    risk_pct: Number(slider.dataset.europeRisk) || 0,
    risk_lines: Number(slider.dataset.europeRiskLines) || 0,
  };
  document.querySelector('#bi-reduction-value').textContent = `${percent}%`;
  const current = Number(e.risk_pct) || 0;
  const scenario = current * (1 - percent / 100);
  const max = Math.max(current, 1);

  document.querySelector('#bi-scenario-chart').innerHTML = `
    <div class="scenario-bar-row">
      <span>Risco Atual na Europa</span>
      <div class="chart-track"><i style="width:${(current / max) * 100}%"></i></div>
      <b>${pct(current)}</b>
    </div>
    <div class="scenario-bar-row">
      <span>Risco no Cenário</span>
      <div class="chart-track"><i class="scenario-fill" style="width:${(scenario / max) * 100}%"></i></div>
      <b>${pct(scenario)}</b>
    </div>`;
  document.querySelector('#bi-scenario-lines').textContent = fmtInt(Math.round((Number(e.risk_lines) || 0) * (percent / 100)));
}

function recommendationTagClass(kind) {
  const k = String(kind || '').toLowerCase();
  if (k.includes('observado')) return 'observed';
  if (k.includes('faltante')) return 'missing';
  return 'hypothesis';
}

async function loadBI() {
  setPageLoading('bi', true);
  try {
    const d = await json('/api/bi');
    clearError();
    biData = d;
    const o = d.observed;

    document.querySelector('#bi-scope-tag').textContent = `Observado no CSV · ${fmtInt(o.lines)} Linhas`;
    document.querySelector('#bi-lines').textContent = fmtInt(o.lines);
    document.querySelector('#bi-lines-note').textContent = `${fmtInt(o.orders)} Pedidos Únicos`;
    document.querySelector('#bi-risk').textContent = pct(o.risk_pct);
    document.querySelector('#bi-risk-note').textContent = `${fmtInt(o.risk_lines)} Linhas · ${fmtInt(o.risk_orders)} Pedidos`;
    document.querySelector('#bi-delay').textContent = `${fmt(o.avg_delay_days_late)} Dias`;
    document.querySelector('#bi-sales').textContent = money(o.sales_usd);
    document.querySelector('#bi-loss').textContent = money(o.negative_profit_loss_usd);
    document.querySelector('#bi-late-loss').textContent = money(o.delayed_negative_profit_usd);
    document.querySelector('#bi-loss-share').textContent = `${pct(o.delayed_negative_profit_share_pct)} do Total · ${fmtInt(o.late_negative_lines)} Linhas`;
    document.querySelector('#bi-top8').textContent = pct(o.top8_negative_loss_share_pct);

    document.querySelector('#bi-modes').innerHTML = barRows(
      o.modes,
      'shipping mode',
      'delayed_negative_profit_usd',
      (r) => `${pct(r.risk_pct)} Risco · ${fmtInt(r.lines)} Linhas`
    );

    const regions = [...o.regions]
      .sort((a, b) => b.delayed_negative_profit_usd - a.delayed_negative_profit_usd)
      .slice(0, 8);
    document.querySelector('#bi-regions').innerHTML = barRows(
      regions,
      'order region',
      'delayed_negative_profit_usd',
      (r) => `${fmtInt(r.lines)} Linhas · ${pct(r.risk_pct)} Risco`
    );

    document.querySelector('#bi-products').innerHTML = barRows(
      o.top_products,
      'product_name',
      'negative_profit_loss_usd',
      (r) =>
        `Em Linhas com Risco: ${money(r.delayed_negative_profit_usd)} · ${pct(r.risk_pct)} Risco · ${
          r.package_gross_weight_kg == null
            ? 'Dimensões Não Disponíveis'
            : `${fmt(r.package_gross_weight_kg)} kg / ${fmtInt(r.package_volume_cm3)} cm³`
        }`
    );

    document.querySelector('#bi-recommendations').innerHTML = d.recommendations
      .map(
        (r) => `
          <article class="recommendation">
            <div class="recommendation-head">
              <h3>${escapeHtml(capFirst(r.title))}</h3>
              <span class="tag ${recommendationTagClass(r.kind)}">${escapeHtml(capFirst(r.kind || 'Hipótese'))}</span>
            </div>
            <p>${escapeHtml(capFirst(r.evidence))}</p>
          </article>`
      )
      .join('');

    const src = d.data_sources;
    if (src) {
      document.querySelector('#bi-sources').innerHTML = `
        <article class="card">
          <span class="tag observed">Base Principal</span>
          <h3>${escapeHtml(src.transactions.file)}</h3>
          <strong>${fmtInt(src.transactions.rows)} Linhas · ${fmtInt(src.transactions.orders)} Pedidos</strong>
          <p>${fmtInt(src.transactions.late_negative_lines)} Linhas com Margem Negativa e Risco de Atraso.</p>
        </article>
        <article class="card">
          <span class="tag missing">Tabela Auxiliar</span>
          <h3>${escapeHtml(src.product_dimensions.file)}</h3>
          <strong>${fmtInt(src.product_dimensions.products)} Produtos</strong>
          <p>${escapeHtml(capFirst(src.product_dimensions.note))}</p>
        </article>
        <article class="card">
          <span class="tag missing">Logs de Navegação</span>
          <h3>${escapeHtml(src.web_logs.file)}</h3>
          <strong>${fmtInt(src.web_logs.events)} Eventos</strong>
          <p>${escapeHtml(capFirst(src.web_logs.note))}</p>
        </article>`;
    }

    document.querySelector('#bi-warning').textContent = capFirst(d.warning || '');
    renderBIScenario();
  } finally {
    setPageLoading('bi', false);
  }
}

document.querySelector('#bi-reduction')?.addEventListener('input', renderBIScenario);
renderBIScenario();

/* Tab 3: Routes & Delays */
const routeRegionSelect = document.querySelector('#routes-region-filter');
const routeModeSelect = document.querySelector('#routes-mode-filter');
const routeSortSelect = document.querySelector('#routes-sort-filter');

function syncSelectOptions(selectEl, items, allLabel) {
  if (!selectEl || !Array.isArray(items) || items.length === 0) return;
  const current = selectEl.value;
  const options = [
    `<option value="Todas">${escapeHtml(allLabel)}</option>`,
    ...items.map((item) => `<option value="${escapeHtml(item)}">${escapeHtml(item)}</option>`),
  ];
  selectEl.innerHTML = options.join('');
  if ([...selectEl.options].some((o) => o.value === current)) {
    selectEl.value = current;
  } else {
    selectEl.value = 'Todas';
  }
}

function riskBadgeClass(riskPct) {
  const v = Number(riskPct) || 0;
  if (v >= 65) return 'risk-high';
  if (v >= 45) return 'risk-mid';
  return 'risk-low';
}

async function loadRoutes() {
  setPageLoading('routes', true);
  try {
    const rg = routeRegionSelect?.value || 'Todas';
    const mode = routeModeSelect?.value || 'Todas';
    const sortBy = routeSortSelect?.value || 'impact';
    const url = `/api/routes?region=${encodeURIComponent(REGION_MAP[rg] || rg)}&mode=${encodeURIComponent(mode)}&sort_by=${encodeURIComponent(sortBy)}`;
    const d = await json(url);
    clearError();

    syncSelectOptions(routeModeSelect, d.shipping_modes, 'Todas as Modalidades');

    const s = d.summary || {};
    document.querySelector('#rt-lines').textContent = fmtInt(s.lines);
    document.querySelector('#rt-orders').textContent = `${fmtInt(s.orders)} Pedidos Únicos`;
    document.querySelector('#rt-risk').textContent = pct(s.risk_pct);
    document.querySelector('#rt-risk-lines').textContent = `${fmtInt(s.risk_lines)} Linhas com Risco`;
    document.querySelector('#rt-delay').textContent = `${fmt(s.avg_delay_days)} Dias`;
    document.querySelector('#rt-sales').textContent = money(s.sales_usd);
    document.querySelector('#rt-profit').textContent = `Lucro: ${money(s.profit_usd)} · Negativo Bruto: ${money(s.negative_profit_loss_usd)}`;

    const list = document.querySelector('#routes-list');
    if (!d.routes || d.routes.length === 0) {
      list.innerHTML = '<div class="route-empty">Nenhuma Rota Encontrada para os Filtros Selecionados.</div>';
    } else {
      list.innerHTML = d.routes
        .map((r) => {
          const profitNum = Number(r.profit) || 0;
          const profitCls = profitNum < 0 ? 'profit-neg' : 'profit-pos';
          return `
            <div class="route">
              <div class="route-icon" aria-hidden="true">↗</div>
              <div class="route-main">
                <b>${escapeHtml(r['order region'])} → ${escapeHtml(r['order country'])}</b>
                <div class="route-meta">
                  <span>${fmtInt(r.orders)} Linhas (${fmtInt(r.unique_orders)} Pedidos)</span>
                  <span>Atraso Médio: ${fmt(r.avg_delay)} Dias</span>
                  <span>Vendas: ${money(r.sales)}</span>
                  <span class="${profitCls}">Lucro: ${money(r.profit)}</span>
                </div>
              </div>
              <span class="risk ${riskBadgeClass(r.risk_pct)}">${pct(r.risk_pct)} Risco</span>
            </div>`;
        })
        .join('');
    }

    const noteEl = document.querySelector('#routes-note');
    if (d.applied_min_orders > 0) {
      noteEl.textContent = `Exibindo até 15 Destinos com Piso Mínimo de ${fmtInt(d.applied_min_orders)} Linhas (${fmtInt(d.total_routes)} Rotas no Recorte). O CSV Não Informa a Localização dos CDs de Origem.`;
    } else {
      noteEl.textContent = `Exibindo ${Math.min(15, d.routes?.length || 0)} de ${fmtInt(d.total_routes)} Destinos Encontrados no Recorte. O CSV Não Informa a Localização dos CDs de Origem.`;
    }
  } finally {
    setPageLoading('routes', false);
  }
}

[routeRegionSelect, routeModeSelect, routeSortSelect].forEach((el) => {
  el?.addEventListener('change', () => loadRoutes().catch(showError));
});

/* Tab 4: Scenarios & CD Simulation */
function renderScenarioNetwork(proposal) {
  const network = document.querySelector('#scenario-network');
  const label = document.querySelector('#scenario-label');
  const title = document.querySelector('#scenario-title');
  const tag = document.querySelector('#scenario-tag');
  const copy = document.querySelector('#scenario-copy');

  document.querySelectorAll('.scenario-tab').forEach((btn) => {
    const active = (btn.dataset.scenario === 'proposal') === proposal;
    btn.classList.toggle('active', active);
    btn.setAttribute('aria-selected', active ? 'true' : 'false');
  });

  if (proposal) {
    label.textContent = 'CENÁRIO PROPOSTO';
    title.textContent = 'CD Europeu + Operadores Logísticos (3PL)';
    tag.textContent = 'Hipótese';
    tag.className = 'tag hypothesis';
    copy.textContent =
      'Configuração conceitual para avaliação executiva: CD próprio na Europa e parceiros terceirizados nos EUA e na China. Os ganhos reais dependem de custos, acordos de prazo (SLA) e estoque.';
    network.innerHTML = `
      <div class="network-lane">
        <div class="node node-proposal"><span>CD PRÓPRIO</span><b>Europa</b><small>Estoque Local Proposto</small></div>
        <div class="connector"><i></i><small>Atendimento Regional</small></div>
        <div class="node node-proposal"><span>DESTINO</span><b>Europa</b><small>Redução Hipotética no Tempo de Entrega</small></div>
      </div>
      <div class="network-lane">
        <div class="node node-proposal"><span>OPERADOR LOGÍSTICO (3PL)</span><b>EUA</b><small>Operação Terceirizada</small></div>
        <div class="connector"><i></i><small>Acordo de Prazo (SLA)</small></div>
        <div class="node node-proposal"><span>DESTINO</span><b>América do Norte</b><small>Cobertura e Custo a Validar</small></div>
      </div>
      <div class="network-lane">
        <div class="node node-proposal"><span>OPERADOR LOGÍSTICO (3PL)</span><b>China</b><small>Operação Terceirizada</small></div>
        <div class="connector"><i></i><small>Acordo de Prazo (SLA)</small></div>
        <div class="node node-proposal"><span>DESTINO</span><b>Ásia / Pacífico</b><small>Demanda e Tarifas a Validar</small></div>
      </div>`;
  } else {
    label.textContent = 'CENÁRIO OBSERVADO';
    title.textContent = 'Operação Histórica Registrada';
    tag.textContent = 'Base CSV';
    tag.className = 'tag observed';
    copy.textContent =
      'Referência histórica calculada no CSV. O arquivo registra destinos, prazos, atrasos e margens, mas não informa a localização nem os custos dos centros de distribuição.';
    network.innerHTML = `
      <div class="network-lane">
        <div class="node"><span>ORIGEM NO CSV</span><b>Não Informada</b><small>Arquivo Não Identifica CDs</small></div>
        <div class="connector"><i></i><small>Fluxo Histórico Observado</small></div>
        <div class="node"><span>DESTINOS</span><b>Mercados Globais</b><small>180.519 Linhas Registradas</small></div>
      </div>`;
  }
}

document.querySelectorAll('.scenario-tab').forEach((btn) => {
  btn.addEventListener('click', () => renderScenarioNetwork(btn.dataset.scenario === 'proposal'));
});
renderScenarioNetwork(false);

const shareSlider = document.querySelector('#share');
shareSlider?.addEventListener('input', (e) => {
  document.querySelector('#shareVal').textContent = `${e.target.value}%`;
});

document.querySelector('#simulate')?.addEventListener('click', async () => {
  const btn = document.querySelector('#simulate');
  const out = document.querySelector('#simulationResult');
  const share = Number(document.querySelector('#share').value) / 100;
  const reduction = Number(document.querySelector('#reduction').value);
  const cost = Number(document.querySelector('#cost').value);

  btn.disabled = true;
  out.innerHTML = '<p class="note">Calculando Simulação…</p>';
  try {
    const d = await json('/api/scenario', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        eu_demand_share: share,
        delay_reduction_days: reduction,
        cost_per_order: cost,
      }),
    });
    clearError();
    const cappedNote =
      d.delay_reduction_assumption_days > d.applied_delay_reduction_days
        ? `Limitado ao Atraso Médio Observado (${fmt(d.observed_europe_avg_delay_days)} Dias)`
        : `Atraso Médio Observado na Europa: ${fmt(d.observed_europe_avg_delay_days)} Dias`;

    out.innerHTML = `
      <div class="sim-kpis">
        <div class="sim-kpi">
          <span>Linhas Europeias no CSV</span>
          <strong>${fmtInt(d.europe_orders_in_csv)}</strong>
          <small>${fmtInt(d.risk_orders_historical)} Linhas com Risco Histórico</small>
        </div>
        <div class="sim-kpi">
          <span>Dias de Atraso Evitados</span>
          <strong>${fmt(d.estimated_delay_days_avoided)}</strong>
          <small>Estimativa na Parcela Simulada</small>
        </div>
        <div class="sim-kpi">
          <span>Redução Aplicada</span>
          <strong>${fmt(d.applied_delay_reduction_days)} Dias</strong>
          <small>${escapeHtml(cappedNote)}</small>
        </div>
        <div class="sim-kpi">
          <span>Custo Adicional Estimado</span>
          <strong>${money(d.assumed_cost)}</strong>
          <small>Retorno Não Calculado (Sem Custos Reais)</small>
        </div>
      </div>`;
  } catch (e) {
    out.innerHTML = `<p class="note">${escapeHtml(capFirst(e.message || 'Não Foi Possível Executar a Simulação.'))}</p>`;
  } finally {
    btn.disabled = false;
  }
});

/* Tab 5: Predictive Model Simulator */
let predictOptions = null;

function setSelectValues(selectEl, values, selectedValue) {
  if (!selectEl) return;
  selectEl.innerHTML = (values || [])
    .map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`)
    .join('');
  if (selectedValue && [...selectEl.options].some((o) => o.value === selectedValue)) {
    selectEl.value = selectedValue;
  }
}

function updateCountryOptions(preferredCountry) {
  if (!predictOptions) return;
  const region = document.querySelector('#pred-region').value;
  const countries = predictOptions.regions_countries?.[region] || predictOptions.countries || [];
  setSelectValues(document.querySelector('#pred-country'), countries, preferredCountry);
}

function updateProductOptions(preferredProduct, updatePrice = true) {
  if (!predictOptions) return;
  const cat = document.querySelector('#pred-category').value;
  const items = predictOptions.categories_products?.[cat] || predictOptions.products || [];
  const productSelect = document.querySelector('#pred-product');
  productSelect.innerHTML = items
    .map(
      (p) =>
        `<option value="${escapeHtml(p.product_name)}" data-price="${Number(p.product_price) || 0}">${escapeHtml(
          p.product_name
        )} (${money(p.product_price)})</option>`
    )
    .join('');
  if (preferredProduct && [...productSelect.options].some((o) => o.value === preferredProduct)) {
    productSelect.value = preferredProduct;
  }
  if (updatePrice) {
    const opt = productSelect.selectedOptions[0];
    if (opt && opt.dataset.price !== undefined) {
      document.querySelector('#pred-price').value = Number(opt.dataset.price).toFixed(2);
    }
  }
}

function applyPredictPayload(payload) {
  if (!payload || !predictOptions) return;
  const modeEl = document.querySelector('#pred-mode');
  if ([...modeEl.options].some((o) => o.value === payload.shipping_mode)) {
    modeEl.value = payload.shipping_mode;
  }
  const regionEl = document.querySelector('#pred-region');
  if ([...regionEl.options].some((o) => o.value === payload.order_region)) {
    regionEl.value = payload.order_region;
  }
  updateCountryOptions(payload.order_country);

  const catEl = document.querySelector('#pred-category');
  if ([...catEl.options].some((o) => o.value === payload.category_name)) {
    catEl.value = payload.category_name;
  }
  updateProductOptions(payload.product_name, false);

  document.querySelector('#pred-scheduled').value = payload.scheduled_days ?? 1;
  document.querySelector('#pred-quantity').value = payload.quantity ?? 1;
  document.querySelector('#pred-price').value = payload.product_price ?? 0;
  document.querySelector('#pred-month').value = String(payload.order_month ?? 11);
  document.querySelector('#pred-weekday').value = String(payload.order_weekday ?? 2);
}

function updateModelStatusPill(available, message) {
  const pill = document.querySelector('#model-status-pill');
  if (!pill) return;
  pill.classList.remove('is-ready', 'is-warn');
  if (available) {
    pill.textContent = 'Base CSV · Modelo IA Ativo';
    pill.classList.add('is-ready');
  } else {
    pill.textContent = 'Base CSV Ativa · Modelo IA Indisponível';
    pill.classList.add('is-warn');
    if (message) pill.title = message;
  }
}

function buildRecommendedDecision(level, payload) {
  const mode = String(payload.shipping_mode || '');
  const isExpress =
    mode === 'Primeira Classe' ||
    mode === 'Segunda Classe' ||
    mode === 'First Class' ||
    mode === 'Second Class';
  if (level === 'alto') {
    if (isExpress) {
      return 'Não prometer entrega expressa de 1–2 dias nesta rota; alterar para Classe Padrão (4+ dias) ou priorizar expedição a partir de CD regional próximo ao destino.';
    }
    return 'Sinalizar risco elevado antes do faturamento: revisar o prazo prometido ao cliente, confirmar estoque local na região de destino e priorizar expedição.';
  }
  if (level === 'moderado') {
    if (isExpress) {
      return 'Risco moderado em modalidade expressa: confirmar disponibilidade imediata em estoque antes de prometer prazo curto ou avaliar migração para Classe Padrão.';
    }
    return 'Monitorar expedição: confirmar janela de coleta da transportadora e estoque disponível para evitar atraso na entrega.';
  }
  return 'Manter fluxo padrão de expedição: o perfil histórico deste pedido indica menor risco de atraso dentro do prazo programado.';
}

async function runPrediction() {
  const submitBtn = document.querySelector('#predict-submit');
  const resultBody = document.querySelector('#predict-result-body');

  const scheduled = Number(document.querySelector('#pred-scheduled').value);
  const quantity = Number(document.querySelector('#pred-quantity').value);
  const price = Number(document.querySelector('#pred-price').value);
  if (Number.isNaN(scheduled) || scheduled < 0 || scheduled > 30) {
    showError(new Error('Prazo Programado Deve Estar Entre 0 e 30 Dias.'));
    return;
  }
  if (Number.isNaN(quantity) || quantity < 1 || quantity > 1000) {
    showError(new Error('Quantidade Deve Ser de Pelo Menos 1 Unidade.'));
    return;
  }
  if (Number.isNaN(price) || price < 0) {
    showError(new Error('Preço Unitário Deve Ser Maior ou Igual a Zero.'));
    return;
  }

  const payload = {
    shipping_mode: document.querySelector('#pred-mode').value,
    order_region: document.querySelector('#pred-region').value,
    order_country: document.querySelector('#pred-country').value,
    category_name: document.querySelector('#pred-category').value,
    product_name: document.querySelector('#pred-product').value,
    scheduled_days: scheduled,
    quantity,
    product_price: price,
    order_month: Number(document.querySelector('#pred-month').value),
    order_weekday: Number(document.querySelector('#pred-weekday').value),
  };

  submitBtn.disabled = true;
  resultBody.innerHTML = '<div class="predict-empty">Calculando Probabilidade com o Modelo Preditivo…</div>';
  try {
    const d = await json('/api/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    clearError();
    const rawLevel = String(d.risk_level || '').trim().toLowerCase();
    const level = ['alto', 'moderado', 'baixo'].includes(rawLevel) ? rawLevel : 'moderado';
    const badgeCls = level === 'alto' ? 'risk-high' : level === 'baixo' ? 'risk-low' : 'risk-mid';
    const statusText = d.late_delivery_risk === 1 ? 'Alerta: Provável Atraso' : 'Dentro do Prazo Previsto';
    const decisionText = buildRecommendedDecision(level, payload);

    resultBody.innerHTML = `
      <div class="predict-output">
        <div class="predict-hero">
          <div class="predict-hero-top">
            <span class="predict-prob-value ${level}">${pct(d.probability_pct)}</span>
            <span class="risk ${badgeCls}">${escapeHtml(capFirst(d.risk_label))}</span>
          </div>
          <div class="predict-gauge" aria-hidden="true">
            <i class="${level}" style="width:${Math.max(4, Math.min(100, Number(d.probability_pct) || 0))}%"></i>
          </div>
          <strong>${escapeHtml(statusText)}</strong>
        </div>
        <div class="predict-decision ${level}">
          <strong>Decisão Recomendada ao Gestor</strong>
          <p>${escapeHtml(decisionText)}</p>
        </div>
        <div class="predict-summary">
          <div><span>Modalidade / Prazo</span><b>${escapeHtml(payload.shipping_mode)} · ${fmtInt(payload.scheduled_days)} Dias</b></div>
          <div><span>Destino</span><b>${escapeHtml(payload.order_region)} → ${escapeHtml(payload.order_country)}</b></div>
          <div><span>Produto</span><b>${escapeHtml(payload.product_name)} (×${fmtInt(payload.quantity)})</b></div>
        </div>
        <p class="note">${escapeHtml(capFirst(d.interpretation))}</p>
      </div>`;
  } catch (e) {
    resultBody.innerHTML = `<div class="predict-empty">${escapeHtml(capFirst(e.message || 'Não Foi Possível Executar a Previsão.'))}</div>`;
  } finally {
    submitBtn.disabled = predictOptions ? !predictOptions.model_available : false;
  }
}

async function initPredictOptions() {
  if (predictOptions) return predictOptions;
  const d = await json('/api/predict-options');
  predictOptions = d;

  updateModelStatusPill(Boolean(d.model_available), d.model_message);

  const warnEl = document.querySelector('#predict-unavailable');
  const submitBtn = document.querySelector('#predict-submit');
  if (!d.model_available) {
    warnEl.textContent = capFirst(d.model_message || 'Modelo Preditivo Indisponível Neste Ambiente no Momento.');
    warnEl.hidden = false;
    submitBtn.disabled = true;
  } else {
    warnEl.hidden = true;
    submitBtn.disabled = false;
  }

  setSelectValues(document.querySelector('#pred-mode'), d.shipping_modes);
  setSelectValues(document.querySelector('#pred-region'), d.regions);
  setSelectValues(document.querySelector('#pred-category'), d.categories);

  const presetsBox = document.querySelector('#predict-presets');
  presetsBox.innerHTML = (d.presets || [])
    .map(
      (p) => `
        <button type="button" class="preset-btn" data-preset-id="${escapeHtml(p.id)}">
          <strong>${escapeHtml(capFirst(p.label))}</strong>
          <span>${escapeHtml(capFirst(p.description))}</span>
        </button>`
    )
    .join('');

  presetsBox.querySelectorAll('.preset-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      presetsBox.querySelectorAll('.preset-btn').forEach((b) => b.classList.toggle('is-active', b === btn));
      const preset = (d.presets || []).find((p) => p.id === btn.dataset.presetId);
      if (!preset) return;
      applyPredictPayload(preset.payload);
      if (d.model_available) {
        runPrediction();
      }
    });
  });

  if (d.presets?.length) {
    applyPredictPayload(d.presets[0].payload);
  } else {
    updateCountryOptions();
    updateProductOptions(null, true);
  }

  return d;
}

document.querySelector('#pred-region')?.addEventListener('change', () => updateCountryOptions());
document.querySelector('#pred-category')?.addEventListener('change', () => updateProductOptions(null, true));
document.querySelector('#pred-product')?.addEventListener('change', (e) => {
  const opt = e.target.selectedOptions[0];
  if (opt && opt.dataset.price !== undefined) {
    document.querySelector('#pred-price').value = Number(opt.dataset.price).toFixed(2);
  }
});

document.querySelector('#predict-form')?.addEventListener('submit', (e) => {
  e.preventDefault();
  runPrediction();
});

/* Initial Bootstrap */
loadOverview().catch(showError);
initPredictOptions().catch(() => {
  updateModelStatusPill(false, 'Falha ao Verificar Modelo Preditivo.');
});
