(function () {
  "use strict";

  const STORAGE_KEY = "cargoOpsState.v1";
  const USD_API_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL";
  const REFRESH_MS = 5 * 60 * 1000;

  const app = document.getElementById("app");
  const toastHost = document.getElementById("toast");

  const roleLabels = {
    coordenador: "Coordenador",
    supervisao: "Supervisão",
    comprador: "Comprador",
    financeiro: "Financeiro",
    admin: "Administração"
  };

  const roleAccess = {
    coordenador: ["dashboard", "compras", "importacao", "estoque", "financeiro", "agenda", "chamados", "relatorios", "administracao"],
    supervisao: ["dashboard", "compras", "importacao", "estoque", "agenda", "chamados", "relatorios"],
    comprador: ["dashboard", "compras", "estoque", "agenda", "chamados", "relatorios"],
    financeiro: ["dashboard", "financeiro", "agenda", "chamados", "relatorios"],
    admin: ["dashboard", "compras", "importacao", "estoque", "financeiro", "agenda", "chamados", "relatorios", "administracao"]
  };

  const navigation = [
    { id: "dashboard", label: "Dashboard", icon: "DB" },
    {
      id: "compras",
      label: "Compras",
      icon: "CO",
      children: [
        { id: "pedidos", label: "Pedidos" },
        { id: "sugestao", label: "Sugestão de Compra" },
        { id: "aprovacoes", label: "Aprovações" }
      ]
    },
    {
      id: "importacao",
      label: "Importação",
      icon: "IM",
      children: [
        { id: "processos", label: "Processos" },
        { id: "containers", label: "Containers" },
        { id: "portos", label: "Portos" },
        { id: "navios", label: "Navios" },
        { id: "proformas", label: "Proformas" }
      ]
    },
    {
      id: "estoque",
      label: "Estoque",
      icon: "ES",
      children: [
        { id: "produtos", label: "Produtos" },
        { id: "depositos", label: "Depósitos" },
        { id: "movimentacoes", label: "Movimentações" }
      ]
    },
    {
      id: "financeiro",
      label: "Financeiro",
      icon: "FI",
      children: [
        { id: "adiantamentos", label: "Adiantamentos" },
        { id: "saldo", label: "Saldo" },
        { id: "numerario", label: "Numerário" },
        { id: "cambio", label: "Câmbio" }
      ]
    },
    { id: "agenda", label: "Agenda", icon: "AG" },
    { id: "chamados", label: "Chamados", icon: "CH" },
    { id: "relatorios", label: "Relatórios", icon: "RE" },
    { id: "administracao", label: "Administração", icon: "AD" }
  ];

  function uid(prefix) {
    return `${prefix}-${Math.random().toString(36).slice(2, 8)}-${Date.now().toString(36).slice(-4)}`;
  }

  function today(offset = 0) {
    const date = new Date();
    date.setDate(date.getDate() + offset);
    return date.toISOString().slice(0, 10);
  }

  function formatDate(value) {
    if (!value) return "-";
    const date = new Date(`${String(value).slice(0, 10)}T12:00:00`);
    return new Intl.DateTimeFormat("pt-BR").format(date);
  }

  function formatDateTime(value) {
    if (!value) return "-";
    return new Intl.DateTimeFormat("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    }).format(new Date(value));
  }

  function moneyBRL(value) {
    return Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
  }

  function moneyUSD(value) {
    return Number(value || 0).toLocaleString("pt-BR", { style: "currency", currency: "USD" });
  }

  function numberBR(value, digits = 0) {
    return Number(value || 0).toLocaleString("pt-BR", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits
    });
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function toCsvValue(value) {
    const text = String(value ?? "");
    if (/[",\n;]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
    return text;
  }

  function parseNumber(value) {
    if (typeof value === "number") return value;
    const normalized = String(value ?? "0")
      .trim()
      .replace(/[R$\s]/g, "")
      .replace(/\.(?=\d{3}(\D|$))/g, "")
      .replace(",", ".");
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function getSeedState() {
    const products = [
      {
        id: "prod-cabo-cobre",
        sku: "ELT-1040",
        nome: "Cabo de cobre 16 mm",
        categoria: "Elétrica",
        ncm: "8544.49.00",
        estoque: 180,
        minimo: 260,
        custoUSD: 2.78,
        deposito: "São Paulo",
        fornecedores: ["sup-global-metals", "sup-delta-eletrica"]
      },
      {
        id: "prod-parafuso-inox",
        sku: "MNT-2211",
        nome: "Parafuso inox M8",
        categoria: "Manutenção",
        ncm: "7318.15.00",
        estoque: 1450,
        minimo: 800,
        custoUSD: 0.08,
        deposito: "Curitiba",
        fornecedores: ["sup-norte-fixadores"]
      },
      {
        id: "prod-sensor-nivel",
        sku: "AUT-5098",
        nome: "Sensor de nível IP67",
        categoria: "Automação",
        ncm: "9032.89.29",
        estoque: 22,
        minimo: 60,
        custoUSD: 41.9,
        deposito: "Itajaí",
        fornecedores: ["sup-asiatech", "sup-delta-eletrica"]
      },
      {
        id: "prod-bomba-hidraulica",
        sku: "MEC-3300",
        nome: "Bomba hidráulica 3CV",
        categoria: "Mecânica",
        ncm: "8413.70.90",
        estoque: 8,
        minimo: 18,
        custoUSD: 280,
        deposito: "Santos",
        fornecedores: ["sup-harbor-machines"]
      },
      {
        id: "prod-filme-stretch",
        sku: "LOG-7780",
        nome: "Filme stretch 500 mm",
        categoria: "Embalagem",
        ncm: "3920.10.99",
        estoque: 390,
        minimo: 500,
        custoUSD: 5.45,
        deposito: "São Paulo",
        fornecedores: ["sup-packline"]
      }
    ];

    const suppliers = [
      {
        id: "sup-global-metals",
        nome: "Global Metals Trading",
        contato: "Marina Alves",
        email: "cotacoes@globalmetals.example",
        categorias: ["Elétrica", "Mecânica"],
        prazo: "12 dias",
        status: "Homologado",
        cnpj: "12.345.678/0001-10"
      },
      {
        id: "sup-delta-eletrica",
        nome: "Delta Elétrica Industrial",
        contato: "Rafael Lima",
        email: "vendas@deltaeletrica.example",
        categorias: ["Elétrica", "Automação"],
        prazo: "7 dias",
        status: "Homologado",
        cnpj: "33.987.654/0001-44"
      },
      {
        id: "sup-asiatech",
        nome: "AsiaTech Components",
        contato: "Li Wei",
        email: "rfq@asiatech.example",
        categorias: ["Automação"],
        prazo: "28 dias",
        status: "Internacional",
        cnpj: "EX-88420"
      },
      {
        id: "sup-harbor-machines",
        nome: "Harbor Machines Co.",
        contato: "Carla Rocha",
        email: "sales@harbormachines.example",
        categorias: ["Mecânica"],
        prazo: "35 dias",
        status: "Internacional",
        cnpj: "EX-33012"
      },
      {
        id: "sup-norte-fixadores",
        nome: "Norte Fixadores",
        contato: "Diego Martins",
        email: "compras@nortefixadores.example",
        categorias: ["Manutenção"],
        prazo: "5 dias",
        status: "Homologado",
        cnpj: "10.111.222/0001-90"
      },
      {
        id: "sup-packline",
        nome: "Packline Embalagens",
        contato: "Bruna Torres",
        email: "atendimento@packline.example",
        categorias: ["Embalagem"],
        prazo: "4 dias",
        status: "Homologado",
        cnpj: "45.222.333/0001-11"
      }
    ];

    const users = [
      { id: "usr-coordenador", nome: "Ana Coordenadora", email: "coordenador@cargo.ops", password: "cargo123", role: "coordenador" },
      { id: "usr-supervisao", nome: "Bruno Supervisão", email: "supervisor@cargo.ops", password: "cargo123", role: "supervisao" },
      { id: "usr-comprador", nome: "Clara Compradora", email: "comprador@cargo.ops", password: "cargo123", role: "comprador" },
      { id: "usr-financeiro", nome: "Felipe Financeiro", email: "financeiro@cargo.ops", password: "cargo123", role: "financeiro" },
      { id: "usr-admin", nome: "Admin Cargo.Ops", email: "admin@erp.com", password: "admin123", role: "admin" }
    ];

    const orders = [
      {
        id: "ped-2026-001",
        produtoId: "prod-cabo-cobre",
        fornecedorId: "sup-delta-eletrica",
        quantidade: 120,
        precoUSD: 2.71,
        status: "Em aprovação",
        solicitante: "Clara Compradora",
        criadoEm: today(-2),
        prazo: today(8)
      },
      {
        id: "ped-2026-002",
        produtoId: "prod-sensor-nivel",
        fornecedorId: "sup-asiatech",
        quantidade: 50,
        precoUSD: 39.2,
        status: "Aprovado",
        solicitante: "Ana Coordenadora",
        criadoEm: today(-6),
        prazo: today(24)
      },
      {
        id: "ped-2026-003",
        produtoId: "prod-filme-stretch",
        fornecedorId: "sup-packline",
        quantidade: 220,
        precoUSD: 5.28,
        status: "Pedido emitido",
        solicitante: "Bruno Supervisão",
        criadoEm: today(-4),
        prazo: today(5)
      }
    ];

    return {
      version: 1,
      currentUserId: null,
      view: { module: "dashboard", sub: null },
      ui: { selectedQuoteProductIds: ["prod-cabo-cobre", "prod-sensor-nivel"] },
      users,
      products,
      suppliers,
      orders,
      approvals: [
        { id: "apr-ped-001", orderId: "ped-2026-001", nivel: "Supervisão", status: "Pendente", responsavel: "Bruno Supervisão", atualizadoEm: today(-1) },
        { id: "apr-ped-002", orderId: "ped-2026-002", nivel: "Coordenador", status: "Aprovado", responsavel: "Ana Coordenadora", atualizadoEm: today(-5) }
      ],
      rfqs: [
        {
          id: "rfq-2026-014",
          produtoIds: ["prod-cabo-cobre", "prod-sensor-nivel"],
          fornecedorIds: ["sup-delta-eletrica", "sup-asiatech"],
          status: "Enviado",
          criadoEm: today(-1),
          prazoResposta: today(2)
        }
      ],
      importacao: {
        processos: [
          { id: "IMP-2026-044", origem: "Shanghai", destino: "Santos", status: "Em trânsito", eta: today(11), agente: "Maersk" },
          { id: "IMP-2026-039", origem: "Rotterdam", destino: "Itajaí", status: "Desembaraço", eta: today(-1), agente: "Kuehne+Nagel" }
        ],
        containers: [
          { id: "MSKU-882341-7", processo: "IMP-2026-044", navio: "Ever Prime", porto: "Santos", status: "Mar aberto", eta: today(11) },
          { id: "TCLU-443298-0", processo: "IMP-2026-039", navio: "Atlas Norte", porto: "Itajaí", status: "Porto", eta: today(-1) }
        ],
        portos: [
          { id: "porto-santos", nome: "Porto de Santos", uf: "SP", leadTime: "2 dias", status: "Operando" },
          { id: "porto-itajai", nome: "Porto de Itajaí", uf: "SC", leadTime: "3 dias", status: "Fila moderada" }
        ],
        navios: [
          { id: "nav-ever-prime", nome: "Ever Prime", armador: "Evergreen", viagem: "EVP-622", eta: today(11) },
          { id: "nav-atlas-norte", nome: "Atlas Norte", armador: "MSC", viagem: "ATN-158", eta: today(-1) }
        ],
        proformas: [
          { id: "PF-8831", fornecedorId: "sup-asiatech", valorUSD: 1960, status: "Aguardando pagamento", vencimento: today(3) },
          { id: "PF-7712", fornecedorId: "sup-harbor-machines", valorUSD: 5600, status: "Em conferência", vencimento: today(7) }
        ]
      },
      estoque: {
        depositos: [
          { id: "dep-sp", nome: "São Paulo", endereco: "CD Anhanguera", ocupacao: 78, status: "Operando" },
          { id: "dep-itj", nome: "Itajaí", endereco: "Zona Portuária", ocupacao: 62, status: "Operando" },
          { id: "dep-ctb", nome: "Curitiba", endereco: "CIC", ocupacao: 84, status: "Atenção" }
        ],
        movimentacoes: [
          { id: "mov-0104", produtoId: "prod-cabo-cobre", tipo: "Saída", quantidade: 80, deposito: "São Paulo", data: today(-1) },
          { id: "mov-0105", produtoId: "prod-parafuso-inox", tipo: "Entrada", quantidade: 500, deposito: "Curitiba", data: today(-3) },
          { id: "mov-0106", produtoId: "prod-sensor-nivel", tipo: "Reserva", quantidade: 18, deposito: "Itajaí", data: today(-2) }
        ]
      },
      financeiro: {
        adiantamentos: [
          { id: "ADT-901", fornecedorId: "sup-asiatech", valorUSD: 980, status: "Solicitado", vencimento: today(3) },
          { id: "ADT-877", fornecedorId: "sup-harbor-machines", valorUSD: 2800, status: "Aprovado", vencimento: today(7) }
        ],
        saldos: [
          { conta: "Conta Operacional", moeda: "BRL", valor: 438500 },
          { conta: "Conta Importação", moeda: "USD", valor: 72400 }
        ],
        numerario: [
          { id: "NUM-331", processo: "IMP-2026-044", valorBRL: 18800, status: "Previsto", vencimento: today(9) },
          { id: "NUM-298", processo: "IMP-2026-039", valorBRL: 12640, status: "Pago", vencimento: today(-2) }
        ],
        cambio: [
          { data: today(-4), taxa: 5.41, operacao: "Remessa", valorUSD: 2200 },
          { data: today(-2), taxa: 5.44, operacao: "PTAX referência", valorUSD: 0 },
          { data: today(-1), taxa: 5.47, operacao: "Fechamento", valorUSD: 980 }
        ],
        notas: []
      },
      agenda: [
        { id: "ag-001", data: today(1), titulo: "Follow-up RFQ cabos e sensores", responsavel: "Compras", status: "Aberto" },
        { id: "ag-002", data: today(3), titulo: "Vencimento proforma PF-8831", responsavel: "Financeiro", status: "Crítico" },
        { id: "ag-003", data: today(11), titulo: "ETA container MSKU-882341-7", responsavel: "Importação", status: "Aberto" }
      ],
      chamados: [
        {
          id: "CH-2026-001",
          tipo: "Chamado entre setores",
          origem: "Compras",
          destino: "Financeiro",
          prioridade: "Alta",
          titulo: "Validar dados bancários AsiaTech",
          descricao: "Fornecedor internacional precisa confirmar banco intermediário antes do adiantamento.",
          status: "Em andamento",
          responsavel: "Felipe Financeiro",
          criadoEm: today(-2),
          prazo: today(1)
        },
        {
          id: "CH-2026-002",
          tipo: "Melhoria",
          origem: "Supervisão",
          destino: "Projeto",
          prioridade: "Média",
          titulo: "Comparativo automático de propostas",
          descricao: "Criar ranking por preço, prazo e condição de pagamento após resposta da RFQ.",
          status: "Em análise",
          responsavel: "Ana Coordenadora",
          criadoEm: today(-4),
          prazo: today(6)
        },
        {
          id: "CH-2026-003",
          tipo: "Correção",
          origem: "Estoque",
          destino: "Projeto",
          prioridade: "Baixa",
          titulo: "Ajustar máscara do campo NCM",
          descricao: "Permitir colagem com ou sem pontos no cadastro de produto.",
          status: "Resolvido",
          responsavel: "Admin Cargo.Ops",
          criadoEm: today(-8),
          prazo: today(-1)
        }
      ],
      usd: {
        bid: 5.45,
        pctChange: 0,
        updatedAt: new Date().toISOString(),
        source: "fallback",
        stale: true
      }
    };
  }

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return getSeedState();
      const loaded = JSON.parse(raw);
      const seed = getSeedState();
      return {
        ...seed,
        ...loaded,
        view: { ...seed.view, ...(loaded.view || {}) },
        ui: { ...seed.ui, ...(loaded.ui || {}) },
        importacao: { ...seed.importacao, ...(loaded.importacao || {}) },
        estoque: { ...seed.estoque, ...(loaded.estoque || {}) },
        financeiro: { ...seed.financeiro, ...(loaded.financeiro || {}) }
      };
    } catch (error) {
      console.warn("Falha ao carregar estado local", error);
      return getSeedState();
    }
  }

  let state = loadState();

  function saveState() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function currentUser() {
    return state.users.find((user) => user.id === state.currentUserId) || null;
  }

  function canAccess(moduleId) {
    const user = currentUser();
    if (!user) return false;
    return (roleAccess[user.role] || []).includes(moduleId);
  }

  function ensureAccessibleView() {
    if (!currentUser()) return;
    if (!canAccess(state.view.module)) {
      state.view = { module: "dashboard", sub: null };
    }
  }

  function productById(id) {
    return state.products.find((item) => item.id === id);
  }

  function supplierById(id) {
    return state.suppliers.find((item) => item.id === id);
  }

  function orderById(id) {
    return state.orders.find((item) => item.id === id);
  }

  function selectedQuoteProducts() {
    return state.ui.selectedQuoteProductIds
      .map(productById)
      .filter(Boolean);
  }

  function suppliersForProducts(productIds) {
    const categories = new Set(
      productIds
        .map(productById)
        .filter(Boolean)
        .map((product) => product.categoria)
    );
    if (!categories.size) return [];
    return state.suppliers.filter((supplier) => supplier.categorias.some((category) => categories.has(category)));
  }

  function statusClass(status) {
    const text = String(status || "").toLowerCase();
    if (["aprovado", "operando", "pago", "homologado", "pedido emitido", "resolvido", "baixa"].some((key) => text.includes(key))) return "ok";
    if (["pendente", "solicitado", "atenção", "moderada", "aguardando", "em aprovação", "em análise", "média", "media"].some((key) => text.includes(key))) return "warn";
    if (["crítico", "rejeitado", "baixo", "vencido", "alta"].some((key) => text.includes(key))) return "danger";
    if (["internacional", "em trânsito", "porto", "desembaraço", "em andamento"].some((key) => text.includes(key))) return "cyan";
    return "info";
  }

  function statusBadge(status) {
    return `<span class="status ${statusClass(status)}">${escapeHtml(status)}</span>`;
  }

  function viewLabel(moduleId, subId) {
    const module = navigation.find((item) => item.id === moduleId);
    const child = module?.children?.find((item) => item.id === subId);
    if (moduleId === "dashboard") return "Dashboard";
    return child ? `${module.label} / ${child.label}` : module?.label || "Dashboard";
  }

  function metricCard(label, value, foot, tone = "") {
    return `
      <article class="metric-card ${tone}">
        <div>
          <div class="metric-label">${escapeHtml(label)}</div>
          <div class="metric-value">${value}</div>
        </div>
        <div class="metric-foot">${escapeHtml(foot)}</div>
      </article>
    `;
  }

  function clampPercent(value) {
    const numeric = Number(value || 0);
    if (!Number.isFinite(numeric)) return 0;
    return Math.max(0, Math.min(100, Math.round(numeric)));
  }

  function ringCard(label, value, percent, foot, tone = "orange") {
    const pct = clampPercent(percent);
    return `
      <article class="ring-card tone-${escapeHtml(tone)}" style="--pct:${pct}%">
        <div class="ring-chart" aria-label="${escapeHtml(label)} ${pct}%">
          <div class="ring-center">
            <strong class="font-mono">${pct}%</strong>
            <span>${escapeHtml(label)}</span>
          </div>
        </div>
        <div class="ring-copy">
          <div class="ring-value">${value}</div>
          <div class="metric-foot">${escapeHtml(foot)}</div>
        </div>
      </article>
    `;
  }

  function chamadoSummary() {
    const chamados = state.chamados || [];
    const open = chamados.filter((item) => !["Resolvido", "Cancelado"].includes(item.status));
    const late = open.filter((item) => item.prazo && item.prazo < today());
    const resolved = chamados.filter((item) => item.status === "Resolvido");
    return { total: chamados.length, open: open.length, late: late.length, resolved: resolved.length };
  }

  function table(headers, rows, emptyText = "Nenhum registro encontrado.") {
    if (!rows.length) {
      return `<div class="empty">${escapeHtml(emptyText)}</div>`;
    }
    return `
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>${headers.map((header) => `<th class="${header.numeric ? "numeric" : ""}">${escapeHtml(header.label)}</th>`).join("")}</tr>
          </thead>
          <tbody>${rows.map((cells) => `<tr>${cells.join("")}</tr>`).join("")}</tbody>
        </table>
      </div>
    `;
  }

  function cell(value, className = "") {
    return `<td class="${className}">${value}</td>`;
  }

  function toast(message, type = "") {
    const node = document.createElement("div");
    node.className = `toast-message ${type}`;
    node.textContent = message;
    toastHost.appendChild(node);
    window.setTimeout(() => node.remove(), 4200);
  }

  async function fetchDollar() {
    try {
      const response = await fetch(USD_API_URL, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const quote = data.USDBRL;
      state.usd = {
        bid: Number(quote.bid),
        pctChange: Number(quote.pctChange || 0),
        updatedAt: quote.create_date ? new Date(quote.create_date.replace(" ", "T")).toISOString() : new Date().toISOString(),
        source: "AwesomeAPI",
        stale: false
      };
      state.financeiro.cambio = [
        ...state.financeiro.cambio.filter((item) => item.operacao !== "Cotação online"),
        { data: today(), taxa: state.usd.bid, operacao: "Cotação online", valorUSD: 0 }
      ].slice(-8);
      saveState();
      updateDollarBox();
    } catch (error) {
      state.usd = {
        ...state.usd,
        updatedAt: state.usd.updatedAt || new Date().toISOString(),
        stale: true
      };
      saveState();
      updateDollarBox();
    }
  }

  function dollarBoxHtml() {
    const changeClass = state.usd.pctChange >= 0 ? "up" : "down";
    const changePrefix = state.usd.pctChange >= 0 ? "+" : "";
    return `
      <div class="dollar-box ${state.usd.stale ? "is-stale" : ""}" role="status" aria-live="polite">
        <span class="ticker-dot" aria-hidden="true"></span>
        <div>
          <div class="dollar-label">USD/BRL · ${escapeHtml(state.usd.source)}</div>
          <div class="dollar-value font-mono">${numberBR(state.usd.bid, 4)}</div>
        </div>
        <div class="dollar-change ${changeClass} font-mono">${changePrefix}${numberBR(state.usd.pctChange, 2)}%</div>
      </div>
    `;
  }

  function updateDollarBox() {
    const host = document.querySelector("[data-dollar-host]");
    if (host) host.innerHTML = dollarBoxHtml();
  }

  function renderLogin() {
    app.innerHTML = `
      <main class="auth-shell">
        <section class="auth-panel">
          <div class="brand-mark">
            <div class="brand-symbol">CO</div>
            <div>
              <div class="brand-title">Cargo.Ops</div>
              <div class="brand-subtitle">Supply Chain Procurement OS</div>
            </div>
          </div>
          <h1>Compras, importação, estoque e financeiro no mesmo painel.</h1>
          <p>Entre com um perfil operacional para acessar pedidos, cotações, aprovações, dólar, Excel, importação e financeiro.</p>
          <form class="form-grid" data-form="login">
            <div class="field">
              <label for="login-email">E-mail</label>
              <input class="input" id="login-email" name="email" type="email" autocomplete="username" value="coordenador@cargo.ops" data-testid="login-email" required />
            </div>
            <div class="field">
              <label for="login-password">Senha</label>
              <input class="input" id="login-password" name="password" type="password" autocomplete="current-password" value="cargo123" data-testid="login-password" required />
            </div>
            <button class="btn btn-primary" type="submit" data-testid="login-submit">Entrar</button>
          </form>
          <div class="demo-users" aria-label="Perfis de teste">
            ${state.users
              .slice(0, 4)
              .map(
                (user) => `
                  <button class="btn btn-secondary demo-btn" type="button" data-action="demo-login" data-email="${escapeHtml(user.email)}" data-password="${escapeHtml(user.password)}" data-testid="demo-${escapeHtml(user.role)}">
                    <span class="menu-ico">${escapeHtml(user.role.slice(0, 2).toUpperCase())}</span>
                    ${escapeHtml(roleLabels[user.role])}
                  </button>
                `
              )
              .join("")}
          </div>
        </section>
        <section class="auth-image" aria-label="Operação logística portuária"></section>
      </main>
    `;
  }

  function renderShell() {
    ensureAccessibleView();
    const user = currentUser();
    app.innerHTML = `
      <div class="shell">
        ${renderSidebar()}
        <main class="workspace">
          <header class="topbar">
            <div class="crumb">
              <div class="crumb-label">Cargo.Ops</div>
              <h2>${escapeHtml(viewLabel(state.view.module, state.view.sub))}</h2>
            </div>
            <div data-dollar-host>${dollarBoxHtml()}</div>
            <div class="user-box">
              <div class="avatar">${escapeHtml(user.nome.slice(0, 1))}</div>
              <div>
                <div class="user-name">${escapeHtml(user.nome)}</div>
                <div class="user-role">${escapeHtml(roleLabels[user.role])}</div>
              </div>
              <button class="btn btn-secondary btn-small" type="button" data-action="logout" data-testid="logout">Sair</button>
            </div>
          </header>
          <section class="content">
            ${renderContent()}
          </section>
        </main>
      </div>
    `;
  }

  function renderSidebar() {
    const items = navigation
      .filter((item) => canAccess(item.id))
      .map((item) => {
        const isActive = state.view.module === item.id;
        const childHtml = item.children && isActive
          ? `<div class="submenu">${item.children
              .map(
                (child) => `
                  <button class="menu-btn ${state.view.sub === child.id ? "active" : ""}" type="button" data-action="nav" data-module="${escapeHtml(item.id)}" data-sub="${escapeHtml(child.id)}" data-testid="nav-${escapeHtml(item.id)}-${escapeHtml(child.id)}">
                    ${escapeHtml(child.label)}
                  </button>
                `
              )
              .join("")}</div>`
          : "";
        return `
          <div class="nav-group">
            <button class="menu-btn ${isActive && !state.view.sub ? "active" : ""}" type="button" data-action="nav" data-module="${escapeHtml(item.id)}" data-testid="nav-${escapeHtml(item.id)}">
              <span class="menu-title"><span class="menu-ico">${escapeHtml(item.icon)}</span>${escapeHtml(item.label)}</span>
              ${item.children ? `<span class="font-mono">${isActive ? "-" : "+"}</span>` : ""}
            </button>
            ${childHtml}
          </div>
        `;
      })
      .join("");

    return `
      <aside class="sidebar">
        <div class="sidebar-top">
          <div class="brand-symbol">CO</div>
          <div>
            <div class="sidebar-title">Cargo.Ops</div>
            <div class="sidebar-caption">Compras · Supply Chain</div>
          </div>
        </div>
        <nav aria-label="Navegação principal">${items}</nav>
      </aside>
    `;
  }

  function renderContent() {
    switch (state.view.module) {
      case "compras":
        return renderCompras(state.view.sub || "pedidos");
      case "importacao":
        return renderImportacao(state.view.sub || "processos");
      case "estoque":
        return renderEstoque(state.view.sub || "produtos");
      case "financeiro":
        return renderFinanceiro(state.view.sub || "adiantamentos");
      case "agenda":
        return renderAgenda();
      case "chamados":
        return renderChamados();
      case "relatorios":
        return renderRelatorios();
      case "administracao":
        return renderAdministracao();
      default:
        return renderDashboard();
    }
  }

  function renderDashboard() {
    const totalStock = state.products.reduce((sum, item) => sum + Number(item.estoque || 0), 0);
    const lowStock = state.products.filter((item) => Number(item.estoque) < Number(item.minimo));
    const pendingApprovals = state.approvals.filter((item) => item.status === "Pendente");
    const approvedApprovals = state.approvals.filter((item) => item.status === "Aprovado");
    const ordersUsd = state.orders.reduce((sum, order) => sum + Number(order.quantidade) * Number(order.precoUSD), 0);
    const processInTransit = state.importacao.processos.filter((item) => item.status !== "Concluído").length;
    const healthyProducts = state.products.length - lowStock.length;
    const stockHealth = state.products.length ? (healthyProducts / state.products.length) * 100 : 100;
    const approvalHealth = state.approvals.length ? (approvedApprovals.length / state.approvals.length) * 100 : 100;
    const rfqDone = state.rfqs.filter((item) => ["Respondido", "Comparado", "Fechado"].includes(item.status)).length;
    const rfqHealth = state.rfqs.length ? (rfqDone / state.rfqs.length) * 100 : 0;
    const chamados = chamadoSummary();
    const chamadosHealth = chamados.total ? (chamados.resolved / chamados.total) * 100 : 100;
    const dashboardLeftPanel = canAccess("compras") ? renderQuotePanel() : renderFinanceDashboardPanel();
    const dashboardRightPanel = canAccess("financeiro") ? renderFinanceEmailsPanel() : renderAgendaPanel();
    const dashboardActions = [
      canAccess("compras")
        ? `<button class="btn btn-primary" type="button" data-action="nav" data-module="compras" data-sub="pedidos" data-testid="dash-new-order">Novo pedido</button>`
        : "",
      canAccess("financeiro")
        ? `<button class="btn btn-secondary" type="button" data-action="nav" data-module="financeiro" data-sub="cambio" data-testid="dash-cambio">Câmbio</button>`
        : ""
    ].join("");

    return `
      <section class="dashboard-hero">
        <div class="dashboard-hero-copy">
          <div class="crumb-label">Painel executivo</div>
          <h1 class="page-title">Central de compras e supply chain</h1>
          <p class="page-desc">Sinais de estoque, aprovação, cotação, câmbio e chamados em uma visão mais rápida para tomada de decisão.</p>
        </div>
        <div class="panel-actions">
          ${dashboardActions}
          <button class="btn btn-secondary" type="button" data-action="nav" data-module="chamados" data-testid="dash-open-tickets">Abrir chamados</button>
        </div>
      </section>
      <section class="kpi-grid">
        ${metricCard("Dólar atualizado", `<span class="money">R$ ${numberBR(state.usd.bid, 4)}</span>`, `Fonte: ${state.usd.source} · ${formatDateTime(state.usd.updatedAt)}`)}
        ${metricCard("Estoque total", `<span class="font-mono">${numberBR(totalStock)}</span>`, `${lowStock.length} item(ns) abaixo do mínimo`)}
        ${metricCard("Aprovações", `<span class="font-mono">${pendingApprovals.length}</span>`, "Pedidos aguardando decisão")}
        ${metricCard("Carteira USD", `<span class="money">${moneyUSD(ordersUsd)}</span>`, `${processInTransit} processo(s) de importação ativos`)}
      </section>
      <section class="ring-grid">
        ${ringCard("Estoque", `<span class="font-mono">${healthyProducts}/${state.products.length}</span>`, stockHealth, "Produtos dentro do nível mínimo", "green")}
        ${ringCard("Aprovações", `<span class="font-mono">${approvedApprovals.length}/${state.approvals.length}</span>`, approvalHealth, "Aprovações concluídas", "orange")}
        ${ringCard("RFQs", `<span class="font-mono">${rfqDone}/${state.rfqs.length}</span>`, rfqHealth, "Cotações respondidas ou fechadas", "cyan")}
        ${ringCard("Chamados", `<span class="font-mono">${chamados.resolved}/${chamados.total}</span>`, chamadosHealth, `${chamados.open} aberto(s), ${chamados.late} atrasado(s)`, "violet")}
      </section>
      <div class="layout-2" style="margin-top:14px">
        <section class="panel">
          <div class="panel-head">
            <h3 class="panel-title">Sinais de compra</h3>
            <div class="panel-actions">
              <button class="btn btn-secondary btn-small" type="button" data-action="nav" data-module="compras" data-sub="sugestao" data-testid="dash-suggestions">Abrir sugestões</button>
            </div>
          </div>
          <div class="panel-body">
            ${renderSuggestionTable(lowStock)}
          </div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h3 class="panel-title">Operações em andamento</h3>
          </div>
          <div class="panel-body">
            <div class="timeline">
              ${state.importacao.processos
                .map(
                  (processo, index) => `
                    <div class="timeline-row">
                      <span class="timeline-dot ${index === 0 ? "active" : "done"}"></span>
                      <div>
                        <strong>${escapeHtml(processo.id)}</strong><br />
                        <small>${escapeHtml(processo.origem)} → ${escapeHtml(processo.destino)}</small>
                      </div>
                      ${statusBadge(processo.status)}
                    </div>
                  `
                )
                .join("")}
            </div>
          </div>
        </section>
      </div>
      <div class="layout-2" style="margin-top:14px">
        ${renderChamadosPanel()}
        <section class="panel">
          <div class="panel-head">
            <h3 class="panel-title">Resumo por setor</h3>
          </div>
          <div class="panel-body">
            ${renderSectorPulse()}
          </div>
        </section>
      </div>
      <div class="layout-2" style="margin-top:14px">
        ${dashboardLeftPanel}
        ${dashboardRightPanel}
      </div>
    `;
  }

  function renderCompras(sub) {
    const tabs = renderTabs("compras", [
      ["pedidos", "Pedidos"],
      ["sugestao", "Sugestão de Compra"],
      ["aprovacoes", "Aprovações"]
    ], sub);

    if (sub === "sugestao") {
      const lowStock = state.products.filter((item) => Number(item.estoque) < Number(item.minimo));
      return `
        ${pageHeader("Compras", "Sugestão de Compra", "Produtos abaixo do estoque mínimo entram na fila de negociação e podem virar RFQ em um clique.")}
        ${tabs}
        <div class="layout-2">
          <section class="panel">
            <div class="panel-head"><h3 class="panel-title">Itens recomendados</h3></div>
            <div class="panel-body">${renderSuggestionTable(lowStock)}</div>
          </section>
          ${renderQuotePanel()}
        </div>
      `;
    }

    if (sub === "aprovacoes") {
      return `
        ${pageHeader("Compras", "Aprovações", "Fila de decisão para supervisão e coordenação, com vínculo direto aos pedidos.")}
        ${tabs}
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">Workflow de aprovação</h3></div>
          <div class="panel-body">${renderApprovalsTable()}</div>
        </section>
      `;
    }

    return `
      ${pageHeader("Compras", "Pedidos", "Criação de pedidos, cotação automática por fornecedor e preparação para aprovação.")}
      ${tabs}
      <div class="layout-2">
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">Novo pedido de compra</h3></div>
          <div class="panel-body">${renderOrderForm()}</div>
        </section>
        ${renderQuotePanel()}
      </div>
      <section class="panel" style="margin-top:14px">
        <div class="panel-head">
          <h3 class="panel-title">Pedidos</h3>
          <div class="panel-actions">
            <button class="btn btn-secondary btn-small" type="button" data-action="export-orders" data-testid="export-orders">Exportar Excel</button>
          </div>
        </div>
        <div class="panel-body">${renderOrdersTable()}</div>
      </section>
    `;
  }

  function pageHeader(area, title, desc) {
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">${escapeHtml(title)}</h1>
          <p class="page-desc">${escapeHtml(area)} · ${escapeHtml(desc)}</p>
        </div>
      </div>
    `;
  }

  function renderTabs(module, tabs, active) {
    return `
      <div class="tabs">
        ${tabs
          .map(
            ([id, label]) => `
              <button class="tab-btn ${active === id ? "active" : ""}" type="button" data-action="nav" data-module="${escapeHtml(module)}" data-sub="${escapeHtml(id)}" data-testid="tab-${escapeHtml(module)}-${escapeHtml(id)}">${escapeHtml(label)}</button>
            `
          )
          .join("")}
      </div>
    `;
  }

  function renderOrderForm() {
    return `
      <form class="compact-form" data-form="order">
        <div class="field">
          <label for="order-product">Produto</label>
          <select class="select" id="order-product" name="produtoId" data-testid="order-product" required>
            ${state.products.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.sku)} · ${escapeHtml(item.nome)}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label for="order-supplier">Fornecedor</label>
          <select class="select" id="order-supplier" name="fornecedorId" data-testid="order-supplier" required>
            ${state.suppliers.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.nome)}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label for="order-qty">Quantidade</label>
          <input class="input" id="order-qty" name="quantidade" type="number" min="1" value="100" data-testid="order-qty" required />
        </div>
        <div class="field">
          <label for="order-price">Preço USD</label>
          <input class="input" id="order-price" name="precoUSD" type="number" min="0" step="0.01" value="1.00" data-testid="order-price" required />
        </div>
        <div class="field">
          <label for="order-deadline">Prazo previsto</label>
          <input class="input" id="order-deadline" name="prazo" type="date" value="${today(10)}" data-testid="order-deadline" required />
        </div>
        <div class="field">
          <label for="order-requester">Solicitante</label>
          <input class="input" id="order-requester" name="solicitante" value="${escapeHtml(currentUser()?.nome || "")}" data-testid="order-requester" required />
        </div>
        <div class="wide">
          <button class="btn btn-primary" type="submit" data-testid="create-order">Criar pedido e enviar para aprovação</button>
        </div>
      </form>
    `;
  }

  function renderOrdersTable() {
    const rows = state.orders.map((order) => {
      const product = productById(order.produtoId);
      const supplier = supplierById(order.fornecedorId);
      const totalUsd = Number(order.quantidade) * Number(order.precoUSD);
      const totalBrl = totalUsd * Number(state.usd.bid);
      return [
        cell(`<span class="font-mono">${escapeHtml(order.id)}</span>`),
        cell(`${escapeHtml(product?.sku || "-")}<br><small>${escapeHtml(product?.nome || "-")}</small>`),
        cell(escapeHtml(supplier?.nome || "-")),
        cell(`<span class="font-mono">${numberBR(order.quantidade)}</span>`, "numeric"),
        cell(`<span class="money">${moneyUSD(totalUsd)}</span>`, "numeric"),
        cell(`<span class="money">${moneyBRL(totalBrl)}</span>`, "numeric"),
        cell(statusBadge(order.status)),
        cell(formatDate(order.prazo))
      ];
    });
    return table(
      [
        { label: "Pedido" },
        { label: "Produto" },
        { label: "Fornecedor" },
        { label: "Qtd.", numeric: true },
        { label: "Total USD", numeric: true },
        { label: "Total BRL", numeric: true },
        { label: "Status" },
        { label: "Prazo" }
      ],
      rows
    );
  }

  function renderSuggestionTable(items) {
    const rows = items.map((product) => {
      const suggested = Math.max(Number(product.minimo) - Number(product.estoque), Math.ceil(Number(product.minimo) * 0.3));
      return [
        cell(`<span class="font-mono">${escapeHtml(product.sku)}</span>`),
        cell(escapeHtml(product.nome)),
        cell(escapeHtml(product.categoria)),
        cell(`<span class="font-mono">${numberBR(product.estoque)}</span>`, "numeric"),
        cell(`<span class="font-mono">${numberBR(product.minimo)}</span>`, "numeric"),
        cell(`<span class="font-mono">${numberBR(suggested)}</span>`, "numeric"),
        cell(`<button class="btn btn-secondary btn-small" type="button" data-action="quote-add-one" data-id="${escapeHtml(product.id)}" data-testid="quote-add-${escapeHtml(product.id)}">Cotação</button>`)
      ];
    });
    return table(
      [
        { label: "SKU" },
        { label: "Produto" },
        { label: "Categoria" },
        { label: "Estoque", numeric: true },
        { label: "Mínimo", numeric: true },
        { label: "Sugerido", numeric: true },
        { label: "Ação" }
      ],
      rows,
      "Sem itens críticos no momento."
    );
  }

  function renderApprovalsTable() {
    const rows = state.approvals.map((approval) => {
      const order = orderById(approval.orderId);
      const product = productById(order?.produtoId);
      const canDecide = ["coordenador", "supervisao", "admin"].includes(currentUser()?.role);
      const actions = approval.status === "Pendente"
        ? `
          <div class="panel-actions">
            <button class="btn btn-success btn-small" type="button" data-action="approval" data-result="Aprovado" data-id="${escapeHtml(approval.id)}" data-testid="approve-${escapeHtml(approval.id)}" ${canDecide ? "" : "disabled"}>Aprovar</button>
            <button class="btn btn-danger btn-small" type="button" data-action="approval" data-result="Rejeitado" data-id="${escapeHtml(approval.id)}" data-testid="reject-${escapeHtml(approval.id)}" ${canDecide ? "" : "disabled"}>Rejeitar</button>
          </div>
        `
        : statusBadge(approval.status);
      return [
        cell(`<span class="font-mono">${escapeHtml(approval.id)}</span>`),
        cell(`<span class="font-mono">${escapeHtml(order?.id || "-")}</span>`),
        cell(escapeHtml(product?.nome || "-")),
        cell(escapeHtml(approval.nivel)),
        cell(statusBadge(approval.status)),
        cell(formatDate(approval.atualizadoEm)),
        cell(actions)
      ];
    });
    return table(
      [
        { label: "Aprovação" },
        { label: "Pedido" },
        { label: "Produto" },
        { label: "Nível" },
        { label: "Status" },
        { label: "Atualização" },
        { label: "Ação" }
      ],
      rows
    );
  }

  function renderQuotePanel() {
    const selected = selectedQuoteProducts();
    const suppliers = suppliersForProducts(state.ui.selectedQuoteProductIds);
    return `
      <section class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Central de cotação</h3>
          <div class="panel-actions">
            <button class="btn btn-primary btn-small" type="button" data-action="create-rfq" data-testid="create-rfq">Enviar RFQ</button>
          </div>
        </div>
        <div class="panel-body quote-grid">
          <div class="quote-grid">
            ${state.products
              .map((product) => {
                const checked = state.ui.selectedQuoteProductIds.includes(product.id);
                return `
                  <label class="quote-product" for="quote-${escapeHtml(product.id)}">
                    <input id="quote-${escapeHtml(product.id)}" type="checkbox" data-action="quote-toggle" data-id="${escapeHtml(product.id)}" data-testid="quote-toggle-${escapeHtml(product.id)}" ${checked ? "checked" : ""} />
                    <span><strong>${escapeHtml(product.sku)}</strong> · ${escapeHtml(product.nome)}<br><small>${escapeHtml(product.categoria)} · estoque ${numberBR(product.estoque)} / mínimo ${numberBR(product.minimo)}</small></span>
                    ${Number(product.estoque) < Number(product.minimo) ? statusBadge("Baixo") : statusBadge("OK")}
                  </label>
                `;
              })
              .join("")}
          </div>
          <div class="supplier-list">
            ${suppliers.length
              ? suppliers
                  .map(
                    (supplier) => `
                      <div class="supplier-row">
                        <div><strong>${escapeHtml(supplier.nome)}</strong><br><small>${escapeHtml(supplier.email)} · ${escapeHtml(supplier.categorias.join(", "))}</small></div>
                        ${statusBadge(supplier.status)}
                      </div>
                    `
                  )
                  .join("")
              : `<div class="empty">Selecione produtos para filtrar fornecedores homologados.</div>`}
          </div>
          <div class="metric-foot">
            ${selected.length} produto(s) selecionado(s) · ${suppliers.length} fornecedor(es) filtrado(s)
          </div>
          <div class="table-wrap">
            ${renderRfqHistory()}
          </div>
        </div>
      </section>
    `;
  }

  function renderRfqHistory() {
    const rows = state.rfqs.slice().reverse().map((rfq) => {
      const products = rfq.produtoIds.map(productById).filter(Boolean).map((item) => item.sku).join(", ");
      const suppliers = rfq.fornecedorIds.map(supplierById).filter(Boolean).map((item) => item.nome).join(", ");
      return [
        cell(`<span class="font-mono">${escapeHtml(rfq.id)}</span>`),
        cell(escapeHtml(products)),
        cell(escapeHtml(suppliers)),
        cell(statusBadge(rfq.status)),
        cell(formatDate(rfq.prazoResposta))
      ];
    });
    return table(
      [
        { label: "RFQ" },
        { label: "Produtos" },
        { label: "Fornecedores" },
        { label: "Status" },
        { label: "Resposta" }
      ],
      rows,
      "Nenhuma cotação enviada."
    );
  }

  function renderImportacao(sub) {
    const tabs = renderTabs("importacao", [
      ["processos", "Processos"],
      ["containers", "Containers"],
      ["portos", "Portos"],
      ["navios", "Navios"],
      ["proformas", "Proformas"]
    ], sub);

    const title = {
      processos: "Processos",
      containers: "Containers",
      portos: "Portos",
      navios: "Navios",
      proformas: "Proformas"
    }[sub] || "Processos";

    return `
      ${pageHeader("Importação", title, "Acompanhamento de embarques, proformas, portos e previsões de chegada.")}
      ${tabs}
      <div class="layout-2">
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">${escapeHtml(title)}</h3></div>
          <div class="panel-body">${renderImportTable(sub)}</div>
        </section>
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">Tracking do container</h3></div>
          <div class="panel-body">
            <div class="timeline">
              ${["Proforma", "Produção", "Embarque", "Mar aberto", "Porto", "Desembaraço", "Entrega"]
                .map((step, index) => `
                  <div class="timeline-row">
                    <span class="timeline-dot ${index < 3 ? "done" : index === 3 ? "active" : ""}"></span>
                    <div><strong>${escapeHtml(step)}</strong><br><small>${index < 4 ? "Concluído ou em andamento" : "Previsto"}</small></div>
                    <span class="font-mono">${formatDate(today(index * 3 - 8))}</span>
                  </div>
                `)
                .join("")}
            </div>
          </div>
        </section>
      </div>
    `;
  }

  function renderImportTable(sub) {
    if (sub === "containers") {
      const rows = state.importacao.containers.map((item) => [
        cell(`<span class="font-mono">${escapeHtml(item.id)}</span>`),
        cell(escapeHtml(item.processo)),
        cell(escapeHtml(item.navio)),
        cell(escapeHtml(item.porto)),
        cell(statusBadge(item.status)),
        cell(formatDate(item.eta))
      ]);
      return table([{ label: "Container" }, { label: "Processo" }, { label: "Navio" }, { label: "Porto" }, { label: "Status" }, { label: "ETA" }], rows);
    }

    if (sub === "portos") {
      const rows = state.importacao.portos.map((item) => [
        cell(escapeHtml(item.nome)),
        cell(escapeHtml(item.uf)),
        cell(escapeHtml(item.leadTime)),
        cell(statusBadge(item.status))
      ]);
      return table([{ label: "Porto" }, { label: "UF" }, { label: "Lead time" }, { label: "Status" }], rows);
    }

    if (sub === "navios") {
      const rows = state.importacao.navios.map((item) => [
        cell(escapeHtml(item.nome)),
        cell(escapeHtml(item.armador)),
        cell(`<span class="font-mono">${escapeHtml(item.viagem)}</span>`),
        cell(formatDate(item.eta))
      ]);
      return table([{ label: "Navio" }, { label: "Armador" }, { label: "Viagem" }, { label: "ETA" }], rows);
    }

    if (sub === "proformas") {
      const rows = state.importacao.proformas.map((item) => {
        const supplier = supplierById(item.fornecedorId);
        return [
          cell(`<span class="font-mono">${escapeHtml(item.id)}</span>`),
          cell(escapeHtml(supplier?.nome || "-")),
          cell(`<span class="money">${moneyUSD(item.valorUSD)}</span>`, "numeric"),
          cell(`<span class="money">${moneyBRL(Number(item.valorUSD) * Number(state.usd.bid))}</span>`, "numeric"),
          cell(statusBadge(item.status)),
          cell(formatDate(item.vencimento))
        ];
      });
      return table(
        [{ label: "Proforma" }, { label: "Fornecedor" }, { label: "USD", numeric: true }, { label: "BRL", numeric: true }, { label: "Status" }, { label: "Vencimento" }],
        rows
      );
    }

    const rows = state.importacao.processos.map((item) => [
      cell(`<span class="font-mono">${escapeHtml(item.id)}</span>`),
      cell(escapeHtml(item.origem)),
      cell(escapeHtml(item.destino)),
      cell(escapeHtml(item.agente)),
      cell(statusBadge(item.status)),
      cell(formatDate(item.eta))
    ]);
    return table([{ label: "Processo" }, { label: "Origem" }, { label: "Destino" }, { label: "Agente" }, { label: "Status" }, { label: "ETA" }], rows);
  }

  function renderEstoque(sub) {
    const tabs = renderTabs("estoque", [
      ["produtos", "Produtos"],
      ["depositos", "Depósitos"],
      ["movimentacoes", "Movimentações"]
    ], sub);

    if (sub === "depositos") {
      const rows = state.estoque.depositos.map((item) => [
        cell(escapeHtml(item.nome)),
        cell(escapeHtml(item.endereco)),
        cell(`<span class="font-mono">${numberBR(item.ocupacao)}%</span>`, "numeric"),
        cell(statusBadge(item.status))
      ]);
      return `
        ${pageHeader("Estoque", "Depósitos", "Capacidade, ocupação e status das posições de armazenagem.")}
        ${tabs}
        <section class="panel"><div class="panel-body">${table([{ label: "Depósito" }, { label: "Endereço" }, { label: "Ocupação", numeric: true }, { label: "Status" }], rows)}</div></section>
      `;
    }

    if (sub === "movimentacoes") {
      const rows = state.estoque.movimentacoes.map((item) => {
        const product = productById(item.produtoId);
        return [
          cell(`<span class="font-mono">${escapeHtml(item.id)}</span>`),
          cell(`${escapeHtml(product?.sku || "-")}<br><small>${escapeHtml(product?.nome || "-")}</small>`),
          cell(statusBadge(item.tipo)),
          cell(`<span class="font-mono">${numberBR(item.quantidade)}</span>`, "numeric"),
          cell(escapeHtml(item.deposito)),
          cell(formatDate(item.data))
        ];
      });
      return `
        ${pageHeader("Estoque", "Movimentações", "Entradas, saídas, reservas e transferências por depósito.")}
        ${tabs}
        <section class="panel"><div class="panel-body">${table([{ label: "Mov." }, { label: "Produto" }, { label: "Tipo" }, { label: "Qtd.", numeric: true }, { label: "Depósito" }, { label: "Data" }], rows)}</div></section>
      `;
    }

    return `
      ${pageHeader("Estoque", "Produtos", "Cadastro de itens, NCM, níveis mínimos e integração Excel.")}
      ${tabs}
      <div class="layout-2">
        <section class="panel">
          <div class="panel-head">
            <h3 class="panel-title">Produtos</h3>
            <div class="panel-actions">
              <button class="btn btn-secondary btn-small" type="button" data-action="export-products" data-testid="export-products">Exportar Excel</button>
              <button class="btn btn-secondary btn-small" type="button" data-action="trigger-import" data-testid="trigger-import">Importar Excel</button>
              <input class="hidden-input" type="file" accept=".csv,.xlsx,.xls" data-action="import-products" data-testid="import-products" />
            </div>
          </div>
          <div class="panel-body">${renderProductsTable()}</div>
        </section>
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">Novo produto</h3></div>
          <div class="panel-body">${renderProductForm()}</div>
        </section>
      </div>
    `;
  }

  function renderProductsTable() {
    const rows = state.products.map((product) => [
      cell(`<span class="font-mono">${escapeHtml(product.sku)}</span>`),
      cell(`${escapeHtml(product.nome)}<br><small>NCM ${escapeHtml(product.ncm)}</small>`),
      cell(escapeHtml(product.categoria)),
      cell(`<span class="font-mono">${numberBR(product.estoque)}</span>`, "numeric"),
      cell(`<span class="font-mono">${numberBR(product.minimo)}</span>`, "numeric"),
      cell(`<span class="money">${moneyUSD(product.custoUSD)}</span>`, "numeric"),
      cell(Number(product.estoque) < Number(product.minimo) ? statusBadge("Baixo") : statusBadge("OK"))
    ]);
    return table(
      [{ label: "SKU" }, { label: "Produto" }, { label: "Categoria" }, { label: "Estoque", numeric: true }, { label: "Mínimo", numeric: true }, { label: "Custo USD", numeric: true }, { label: "Status" }],
      rows
    );
  }

  function renderProductForm() {
    return `
      <form class="compact-form" data-form="product">
        <div class="field">
          <label for="product-sku">SKU</label>
          <input class="input" id="product-sku" name="sku" value="NOV-1001" data-testid="product-sku" required />
        </div>
        <div class="field">
          <label for="product-name">Produto</label>
          <input class="input" id="product-name" name="nome" value="Novo item industrial" data-testid="product-name" required />
        </div>
        <div class="field">
          <label for="product-category">Categoria</label>
          <input class="input" id="product-category" name="categoria" value="Manutenção" data-testid="product-category" required />
        </div>
        <div class="field">
          <label for="product-ncm">NCM</label>
          <input class="input" id="product-ncm" name="ncm" value="0000.00.00" data-testid="product-ncm" required />
        </div>
        <div class="field">
          <label for="product-stock">Estoque</label>
          <input class="input" id="product-stock" name="estoque" type="number" value="0" data-testid="product-stock" required />
        </div>
        <div class="field">
          <label for="product-min">Mínimo</label>
          <input class="input" id="product-min" name="minimo" type="number" value="10" data-testid="product-min" required />
        </div>
        <div class="field wide">
          <label for="product-cost">Custo USD</label>
          <input class="input" id="product-cost" name="custoUSD" type="number" step="0.01" value="1.00" data-testid="product-cost" required />
        </div>
        <div class="wide">
          <button class="btn btn-primary" type="submit" data-testid="create-product">Adicionar produto</button>
        </div>
      </form>
    `;
  }

  function renderFinanceiro(sub) {
    const tabs = renderTabs("financeiro", [
      ["adiantamentos", "Adiantamentos"],
      ["saldo", "Saldo"],
      ["numerario", "Numerário"],
      ["cambio", "Câmbio"]
    ], sub);

    return `
      ${pageHeader("Financeiro", subLabel("financeiro", sub), "Adiantamentos, saldos, numerário, câmbio e pré-notas vinculadas às compras.")}
      ${tabs}
      <div class="layout-2">
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">${escapeHtml(subLabel("financeiro", sub))}</h3></div>
          <div class="panel-body">${renderFinanceTable(sub)}</div>
        </section>
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">Pré-nota fiscal</h3></div>
          <div class="panel-body">${renderFiscalNotePanel()}</div>
        </section>
      </div>
      <div class="layout-2" style="margin-top:14px">
        ${renderFinanceEmailsPanel()}
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">Notas geradas</h3></div>
          <div class="panel-body">${renderNotesTable()}</div>
        </section>
      </div>
    `;
  }

  function subLabel(module, sub) {
    const nav = navigation.find((item) => item.id === module);
    return nav?.children?.find((item) => item.id === sub)?.label || nav?.label || "";
  }

  function renderFinanceTable(sub) {
    if (sub === "saldo") {
      return `
        <section class="kpi-grid">
          ${state.financeiro.saldos
            .map((saldo) => metricCard(saldo.conta, `<span class="money">${saldo.moeda === "USD" ? moneyUSD(saldo.valor) : moneyBRL(saldo.valor)}</span>`, `Moeda ${saldo.moeda}`))
            .join("")}
          ${metricCard("Exposição em pedidos", `<span class="money">${moneyUSD(state.orders.reduce((sum, order) => sum + Number(order.precoUSD) * Number(order.quantidade), 0))}</span>`, "Carteira de compras")}
          ${metricCard("Taxa atual", `<span class="money">R$ ${numberBR(state.usd.bid, 4)}</span>`, "Atualização a cada 5 minutos")}
        </section>
      `;
    }

    if (sub === "numerario") {
      const rows = state.financeiro.numerario.map((item) => [
        cell(`<span class="font-mono">${escapeHtml(item.id)}</span>`),
        cell(escapeHtml(item.processo)),
        cell(`<span class="money">${moneyBRL(item.valorBRL)}</span>`, "numeric"),
        cell(statusBadge(item.status)),
        cell(formatDate(item.vencimento))
      ]);
      return table([{ label: "Numerário" }, { label: "Processo" }, { label: "Valor", numeric: true }, { label: "Status" }, { label: "Vencimento" }], rows);
    }

    if (sub === "cambio") {
      const rows = state.financeiro.cambio.slice().reverse().map((item) => [
        cell(formatDate(item.data)),
        cell(`<span class="font-mono">${numberBR(item.taxa, 4)}</span>`, "numeric"),
        cell(escapeHtml(item.operacao)),
        cell(`<span class="money">${moneyUSD(item.valorUSD)}</span>`, "numeric")
      ]);
      return table([{ label: "Data" }, { label: "Taxa", numeric: true }, { label: "Operação" }, { label: "Valor USD", numeric: true }], rows);
    }

    const rows = state.financeiro.adiantamentos.map((item) => {
      const supplier = supplierById(item.fornecedorId);
      return [
        cell(`<span class="font-mono">${escapeHtml(item.id)}</span>`),
        cell(escapeHtml(supplier?.nome || "-")),
        cell(`<span class="money">${moneyUSD(item.valorUSD)}</span>`, "numeric"),
        cell(`<span class="money">${moneyBRL(Number(item.valorUSD) * Number(state.usd.bid))}</span>`, "numeric"),
        cell(statusBadge(item.status)),
        cell(formatDate(item.vencimento))
      ];
    });
    return table([{ label: "Adiantamento" }, { label: "Fornecedor" }, { label: "USD", numeric: true }, { label: "BRL", numeric: true }, { label: "Status" }, { label: "Vencimento" }], rows);
  }

  function renderFiscalNotePanel() {
    const eligibleOrders = state.orders.filter((order) => ["Aprovado", "Pedido emitido"].includes(order.status));
    return `
      <form class="compact-form" data-form="fiscal-note">
        <div class="field wide">
          <label for="note-order">Pedido aprovado</label>
          <select class="select" id="note-order" name="orderId" data-testid="note-order" required>
            ${eligibleOrders.map((order) => `<option value="${escapeHtml(order.id)}">${escapeHtml(order.id)} · ${escapeHtml(productById(order.produtoId)?.nome || "-")}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label for="note-type">Tipo</label>
          <select class="select" id="note-type" name="tipo" data-testid="note-type">
            <option>Pré-nota de entrada</option>
            <option>Espelho financeiro</option>
            <option>Conferência fiscal</option>
          </select>
        </div>
        <div class="field">
          <label for="note-due">Vencimento financeiro</label>
          <input class="input" id="note-due" name="vencimento" type="date" value="${today(7)}" data-testid="note-due" required />
        </div>
        <div class="wide">
          <button class="btn btn-primary" type="submit" data-testid="generate-note">Gerar nota</button>
        </div>
      </form>
    `;
  }

  function renderNotesTable() {
    const rows = state.financeiro.notas.slice().reverse().map((note) => [
      cell(`<span class="font-mono">${escapeHtml(note.id)}</span>`),
      cell(`<span class="font-mono">${escapeHtml(note.orderId)}</span>`),
      cell(escapeHtml(note.fornecedor)),
      cell(`<span class="money">${moneyBRL(note.valorBRL)}</span>`, "numeric"),
      cell(statusBadge(note.status)),
      cell(`<button class="btn btn-secondary btn-small" type="button" data-action="download-note" data-id="${escapeHtml(note.id)}" data-testid="download-note-${escapeHtml(note.id)}">Baixar</button>`)
    ]);
    return table([{ label: "Nota" }, { label: "Pedido" }, { label: "Fornecedor" }, { label: "Valor", numeric: true }, { label: "Status" }, { label: "Arquivo" }], rows, "Nenhuma nota gerada.");
  }

  function renderFinanceEmailsPanel() {
    return `
      <section class="panel">
        <div class="panel-head"><h3 class="panel-title">Tratativas com fornecedores</h3></div>
        <div class="panel-body">
          ${table(
            [{ label: "Fornecedor" }, { label: "Contato" }, { label: "Categorias" }, { label: "E-mail" }],
            state.suppliers.map((supplier) => [
              cell(`${escapeHtml(supplier.nome)}<br><small>${escapeHtml(supplier.cnpj)}</small>`),
              cell(escapeHtml(supplier.contato)),
              cell(escapeHtml(supplier.categorias.join(", "))),
              cell(`
                <div class="panel-actions">
                  <button class="btn btn-secondary btn-small" type="button" data-action="finance-email" data-kind="dados" data-id="${escapeHtml(supplier.id)}" data-testid="finance-email-dados-${escapeHtml(supplier.id)}">Dados</button>
                  <button class="btn btn-secondary btn-small" type="button" data-action="finance-email" data-kind="tratativa" data-id="${escapeHtml(supplier.id)}" data-testid="finance-email-tratativa-${escapeHtml(supplier.id)}">Trativa</button>
                </div>
              `)
            ])
          )}
        </div>
      </section>
    `;
  }

  function renderFinanceDashboardPanel() {
    return `
      <section class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Financeiro imediato</h3>
          <button class="btn btn-secondary btn-small" type="button" data-action="nav" data-module="financeiro" data-sub="adiantamentos" data-testid="dash-financeiro">Abrir financeiro</button>
        </div>
        <div class="panel-body">
          ${renderFinanceTable("adiantamentos")}
        </div>
      </section>
    `;
  }

  function renderAgendaPanel() {
    return `
      <section class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Agenda operacional</h3>
          <button class="btn btn-secondary btn-small" type="button" data-action="nav" data-module="agenda" data-testid="dash-agenda">Abrir agenda</button>
        </div>
        <div class="panel-body">
          ${table(
            [{ label: "Data" }, { label: "Evento" }, { label: "Status" }],
            state.agenda.slice(0, 4).map((item) => [
              cell(formatDate(item.data)),
              cell(escapeHtml(item.titulo)),
              cell(statusBadge(item.status))
            ])
          )}
        </div>
      </section>
    `;
  }

  function renderChamadosPanel(limit = 5) {
    const chamados = (state.chamados || []).slice().sort((a, b) => String(b.criadoEm).localeCompare(String(a.criadoEm)));
    const rows = chamados.slice(0, limit).map((item) => [
      cell(`<span class="font-mono">${escapeHtml(item.id)}</span>`),
      cell(`${escapeHtml(item.titulo)}<br><small>${escapeHtml(item.origem)} → ${escapeHtml(item.destino)}</small>`),
      cell(statusBadge(item.tipo)),
      cell(statusBadge(item.prioridade)),
      cell(statusBadge(item.status)),
      cell(formatDate(item.prazo))
    ]);
    return `
      <section class="panel">
        <div class="panel-head">
          <h3 class="panel-title">Chamados e melhorias</h3>
          <button class="btn btn-secondary btn-small" type="button" data-action="nav" data-module="chamados" data-testid="dash-chamados">Abrir central</button>
        </div>
        <div class="panel-body">
          ${table(
            [{ label: "ID" }, { label: "Solicitação" }, { label: "Tipo" }, { label: "Prioridade" }, { label: "Status" }, { label: "Prazo" }],
            rows,
            "Nenhum chamado aberto."
          )}
        </div>
      </section>
    `;
  }

  function renderSectorPulse() {
    const sectors = ["Compras", "Financeiro", "Estoque", "Importação", "Projeto", "Administração"];
    const openTickets = (state.chamados || []).filter((item) => item.status !== "Resolvido");
    const max = Math.max(...sectors.map((sector) => openTickets.filter((item) => item.destino === sector).length), 1);
    return `
      <div class="sector-pulse">
        ${sectors
          .map((sector) => {
            const count = openTickets.filter((item) => item.destino === sector).length;
            return `
              <div class="sector-row">
                <strong>${escapeHtml(sector)}</strong>
                <div class="bar-track"><div class="bar-fill" style="width:${Math.max(4, (count / max) * 100)}%"></div></div>
                <span class="font-mono">${count}</span>
              </div>
            `;
          })
          .join("")}
      </div>
    `;
  }

  function renderChamados() {
    const summary = chamadoSummary();
    const resolvedPct = summary.total ? (summary.resolved / summary.total) * 100 : 100;
    const onTimeOpen = summary.open ? ((summary.open - summary.late) / summary.open) * 100 : 100;
    return `
      ${pageHeader("Chamados", "Central de chamados", "Solicitações entre setores, melhorias e correções do projeto em uma fila compartilhada.")}
      <section class="ring-grid">
        ${ringCard("Resolvidos", `<span class="font-mono">${summary.resolved}/${summary.total}</span>`, resolvedPct, "Taxa de conclusão", "green")}
        ${ringCard("No prazo", `<span class="font-mono">${Math.max(summary.open - summary.late, 0)}/${summary.open}</span>`, onTimeOpen, "Chamados abertos dentro do prazo", "cyan")}
        ${ringCard("Abertos", `<span class="font-mono">${summary.open}</span>`, summary.total ? (summary.open / summary.total) * 100 : 0, "Pendências entre setores", "orange")}
        ${ringCard("Atrasados", `<span class="font-mono">${summary.late}</span>`, summary.open ? (summary.late / summary.open) * 100 : 0, "Precisam de atenção", "violet")}
      </section>
      <div class="layout-2" style="margin-top:14px">
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">Abrir chamado</h3></div>
          <div class="panel-body">${renderChamadoForm()}</div>
        </section>
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">Pulso por setor</h3></div>
          <div class="panel-body">${renderSectorPulse()}</div>
        </section>
      </div>
      <section class="panel" style="margin-top:14px">
        <div class="panel-head"><h3 class="panel-title">Fila de chamados</h3></div>
        <div class="panel-body">${renderChamadosTable()}</div>
      </section>
    `;
  }

  function renderChamadoForm() {
    return `
      <form class="compact-form" data-form="ticket">
        <div class="field">
          <label for="ticket-type">Tipo</label>
          <select class="select" id="ticket-type" name="tipo" data-testid="ticket-type" required>
            <option>Chamado entre setores</option>
            <option>Melhoria</option>
            <option>Correção</option>
          </select>
        </div>
        <div class="field">
          <label for="ticket-priority">Prioridade</label>
          <select class="select" id="ticket-priority" name="prioridade" data-testid="ticket-priority" required>
            <option>Média</option>
            <option>Alta</option>
            <option>Baixa</option>
          </select>
        </div>
        <div class="field">
          <label for="ticket-origin">Origem</label>
          <select class="select" id="ticket-origin" name="origem" data-testid="ticket-origin" required>
            <option>Compras</option>
            <option>Financeiro</option>
            <option>Estoque</option>
            <option>Importação</option>
            <option>Administração</option>
          </select>
        </div>
        <div class="field">
          <label for="ticket-destination">Destino</label>
          <select class="select" id="ticket-destination" name="destino" data-testid="ticket-destination" required>
            <option>Financeiro</option>
            <option>Compras</option>
            <option>Estoque</option>
            <option>Importação</option>
            <option>Projeto</option>
            <option>Administração</option>
          </select>
        </div>
        <div class="field wide">
          <label for="ticket-title">Título</label>
          <input class="input" id="ticket-title" name="titulo" value="Nova solicitação operacional" data-testid="ticket-title" required />
        </div>
        <div class="field">
          <label for="ticket-owner">Responsável</label>
          <input class="input" id="ticket-owner" name="responsavel" value="${escapeHtml(currentUser()?.nome || "")}" data-testid="ticket-owner" required />
        </div>
        <div class="field">
          <label for="ticket-due">Prazo</label>
          <input class="input" id="ticket-due" name="prazo" type="date" value="${today(3)}" data-testid="ticket-due" required />
        </div>
        <div class="field wide">
          <label for="ticket-desc">Descrição</label>
          <textarea class="textarea" id="ticket-desc" name="descricao" data-testid="ticket-desc" required>Descreva o contexto, impacto e o que precisa ser feito.</textarea>
        </div>
        <div class="wide">
          <button class="btn btn-primary" type="submit" data-testid="create-ticket">Abrir chamado</button>
        </div>
      </form>
    `;
  }

  function renderChamadosTable() {
    const rows = (state.chamados || []).slice().reverse().map((item) => {
      const actions = item.status === "Resolvido"
        ? statusBadge("Resolvido")
        : `
          <div class="panel-actions">
            <button class="btn btn-secondary btn-small" type="button" data-action="ticket-status" data-id="${escapeHtml(item.id)}" data-status="Em andamento" data-testid="ticket-progress-${escapeHtml(item.id)}">Andamento</button>
            <button class="btn btn-success btn-small" type="button" data-action="ticket-status" data-id="${escapeHtml(item.id)}" data-status="Resolvido" data-testid="ticket-resolve-${escapeHtml(item.id)}">Resolver</button>
          </div>
        `;
      return [
        cell(`<span class="font-mono">${escapeHtml(item.id)}</span>`),
        cell(`${escapeHtml(item.titulo)}<br><small>${escapeHtml(item.descricao)}</small>`),
        cell(`${escapeHtml(item.origem)}<br><small>para ${escapeHtml(item.destino)}</small>`),
        cell(statusBadge(item.tipo)),
        cell(statusBadge(item.prioridade)),
        cell(statusBadge(item.status)),
        cell(formatDate(item.prazo)),
        cell(actions)
      ];
    });
    return table(
      [
        { label: "ID" },
        { label: "Chamado" },
        { label: "Setores" },
        { label: "Tipo" },
        { label: "Prioridade" },
        { label: "Status" },
        { label: "Prazo" },
        { label: "Ação" }
      ],
      rows,
      "Nenhum chamado criado."
    );
  }

  function renderAgenda() {
    const rows = state.agenda.map((item) => [
      cell(formatDate(item.data)),
      cell(escapeHtml(item.titulo)),
      cell(escapeHtml(item.responsavel)),
      cell(statusBadge(item.status))
    ]);

    return `
      ${pageHeader("Agenda", "Agenda", "Compromissos de compras, financeiro e importação em um único calendário operacional.")}
      <section class="panel">
        <div class="panel-head"><h3 class="panel-title">Próximos eventos</h3></div>
        <div class="panel-body">${table([{ label: "Data" }, { label: "Evento" }, { label: "Responsável" }, { label: "Status" }], rows)}</div>
      </section>
    `;
  }

  function renderRelatorios() {
    const categoryTotals = state.products.reduce((acc, product) => {
      acc[product.categoria] = (acc[product.categoria] || 0) + Number(product.estoque || 0);
      return acc;
    }, {});
    const maxValue = Math.max(...Object.values(categoryTotals), 1);
    const orderTotals = state.orders.reduce((sum, order) => sum + Number(order.precoUSD) * Number(order.quantidade), 0);
    const pendingValue = state.orders
      .filter((order) => order.status === "Em aprovação")
      .reduce((sum, order) => sum + Number(order.precoUSD) * Number(order.quantidade), 0);
    const lowStock = state.products.filter((item) => Number(item.estoque) < Number(item.minimo));
    const stockHealth = state.products.length ? ((state.products.length - lowStock.length) / state.products.length) * 100 : 100;
    const approvedApprovals = state.approvals.filter((item) => item.status === "Aprovado").length;
    const approvalHealth = state.approvals.length ? (approvedApprovals / state.approvals.length) * 100 : 100;
    const rfqDone = state.rfqs.filter((item) => ["Respondido", "Comparado", "Fechado"].includes(item.status)).length;
    const rfqHealth = state.rfqs.length ? (rfqDone / state.rfqs.length) * 100 : 0;
    const chamados = chamadoSummary();

    return `
      ${pageHeader("Relatórios", "Relatórios", "Indicadores de estoque, pedidos, câmbio e exposição financeira.")}
      <section class="kpi-grid">
        ${metricCard("Pedidos USD", `<span class="money">${moneyUSD(orderTotals)}</span>`, "Total na carteira")}
        ${metricCard("Pedidos BRL", `<span class="money">${moneyBRL(orderTotals * state.usd.bid)}</span>`, "Convertido pelo câmbio atual")}
        ${metricCard("Pendente aprovação", `<span class="money">${moneyUSD(pendingValue)}</span>`, "Risco de atraso")}
        ${metricCard("Fornecedores", `<span class="font-mono">${state.suppliers.length}</span>`, "Base homologada")}
      </section>
      <section class="ring-grid">
        ${ringCard("Estoque", `<span class="font-mono">${state.products.length - lowStock.length}/${state.products.length}</span>`, stockHealth, "Produtos saudáveis", "green")}
        ${ringCard("Aprovações", `<span class="font-mono">${approvedApprovals}/${state.approvals.length}</span>`, approvalHealth, "Fluxo aprovado", "orange")}
        ${ringCard("RFQs", `<span class="font-mono">${rfqDone}/${state.rfqs.length}</span>`, rfqHealth, "Cotações fechadas", "cyan")}
        ${ringCard("Chamados", `<span class="font-mono">${chamados.resolved}/${chamados.total}</span>`, chamados.total ? (chamados.resolved / chamados.total) * 100 : 100, "Conclusão de chamados", "violet")}
      </section>
      <div class="layout-2" style="margin-top:14px">
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">Estoque por categoria</h3></div>
          <div class="panel-body">
            <div class="bar-chart">
              ${Object.entries(categoryTotals)
                .map(([category, value]) => `
                  <div class="bar-row">
                    <strong>${escapeHtml(category)}</strong>
                    <div class="bar-track"><div class="bar-fill" style="width:${Math.max(6, (value / maxValue) * 100)}%"></div></div>
                    <span class="font-mono">${numberBR(value)}</span>
                  </div>
                `)
                .join("")}
            </div>
          </div>
        </section>
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">Saúde operacional</h3></div>
          <div class="panel-body">
            ${renderApprovalsTable()}
          </div>
        </section>
      </div>
    `;
  }

  function renderAdministracao() {
    const rows = state.users.map((user) => [
      cell(escapeHtml(user.nome)),
      cell(escapeHtml(user.email)),
      cell(statusBadge(roleLabels[user.role] || user.role)),
      cell(`<span class="font-mono">${escapeHtml(user.id)}</span>`)
    ]);
    return `
      ${pageHeader("Administração", "Usuários e perfis", "Gestão de perfis por área: Coordenador, Supervisão, Comprador e Financeiro.")}
      <div class="layout-2">
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">Usuários</h3></div>
          <div class="panel-body">${table([{ label: "Nome" }, { label: "E-mail" }, { label: "Perfil" }, { label: "ID" }], rows)}</div>
        </section>
        <section class="panel">
          <div class="panel-head"><h3 class="panel-title">Novo usuário</h3></div>
          <div class="panel-body">${renderUserForm()}</div>
        </section>
      </div>
      <section class="panel" style="margin-top:14px">
        <div class="panel-head">
          <h3 class="panel-title">Ambiente demo</h3>
          <button class="btn btn-danger btn-small" type="button" data-action="reset-demo" data-testid="reset-demo">Resetar dados</button>
        </div>
      </section>
    `;
  }

  function renderUserForm() {
    return `
      <form class="compact-form" data-form="user">
        <div class="field">
          <label for="user-name">Nome</label>
          <input class="input" id="user-name" name="nome" value="Novo usuário" data-testid="user-name" required />
        </div>
        <div class="field">
          <label for="user-email">E-mail</label>
          <input class="input" id="user-email" name="email" type="email" value="usuario@cargo.ops" data-testid="user-email" required />
        </div>
        <div class="field">
          <label for="user-role">Perfil</label>
          <select class="select" id="user-role" name="role" data-testid="user-role" required>
            <option value="coordenador">Coordenador</option>
            <option value="supervisao">Supervisão</option>
            <option value="comprador">Comprador</option>
            <option value="financeiro">Financeiro</option>
          </select>
        </div>
        <div class="field">
          <label for="user-password">Senha</label>
          <input class="input" id="user-password" name="password" value="cargo123" data-testid="user-password" required />
        </div>
        <div class="wide">
          <button class="btn btn-primary" type="submit" data-testid="create-user">Criar usuário</button>
        </div>
      </form>
    `;
  }

  function login(email, password) {
    const user = state.users.find((item) => item.email.toLowerCase() === email.toLowerCase() && item.password === password);
    if (!user) {
      toast("E-mail ou senha inválidos.", "danger");
      return;
    }
    state.currentUserId = user.id;
    state.view = { module: "dashboard", sub: null };
    saveState();
    render();
    fetchDollar();
  }

  function createOrder(form) {
    if (!canAccess("compras")) {
      toast("Seu perfil não possui acesso a Compras.", "warning");
      return;
    }
    const data = Object.fromEntries(new FormData(form).entries());
    const id = `ped-${new Date().getFullYear()}-${String(state.orders.length + 1).padStart(3, "0")}`;
    const order = {
      id,
      produtoId: data.produtoId,
      fornecedorId: data.fornecedorId,
      quantidade: parseNumber(data.quantidade),
      precoUSD: parseNumber(data.precoUSD),
      status: "Em aprovação",
      solicitante: data.solicitante,
      criadoEm: today(),
      prazo: data.prazo
    };
    state.orders.unshift(order);
    state.approvals.unshift({
      id: uid("apr"),
      orderId: order.id,
      nivel: "Supervisão",
      status: "Pendente",
      responsavel: "Supervisão",
      atualizadoEm: today()
    });
    saveState();
    toast("Pedido criado e enviado para aprovação.", "success");
    render();
  }

  function createProduct(form) {
    const data = Object.fromEntries(new FormData(form).entries());
    const existing = state.products.find((item) => item.sku.toLowerCase() === String(data.sku).toLowerCase());
    const product = {
      id: existing?.id || uid("prod"),
      sku: data.sku,
      nome: data.nome,
      categoria: data.categoria,
      ncm: data.ncm,
      estoque: parseNumber(data.estoque),
      minimo: parseNumber(data.minimo),
      custoUSD: parseNumber(data.custoUSD),
      deposito: "São Paulo",
      fornecedores: state.suppliers
        .filter((supplier) => supplier.categorias.includes(data.categoria))
        .map((supplier) => supplier.id)
    };
    if (existing) {
      Object.assign(existing, product);
      toast("Produto atualizado.", "success");
    } else {
      state.products.unshift(product);
      toast("Produto adicionado.", "success");
    }
    saveState();
    render();
  }

  function createUser(form) {
    const data = Object.fromEntries(new FormData(form).entries());
    if (state.users.some((user) => user.email.toLowerCase() === data.email.toLowerCase())) {
      toast("Já existe usuário com este e-mail.", "warning");
      return;
    }
    state.users.push({
      id: uid("usr"),
      nome: data.nome,
      email: data.email,
      password: data.password,
      role: data.role
    });
    saveState();
    toast("Usuário criado.", "success");
    render();
  }

  function createChamado(form) {
    const data = Object.fromEntries(new FormData(form).entries());
    const chamados = state.chamados || [];
    const chamado = {
      id: `CH-${new Date().getFullYear()}-${String(chamados.length + 1).padStart(3, "0")}`,
      tipo: data.tipo,
      origem: data.origem,
      destino: data.destino,
      prioridade: data.prioridade,
      titulo: data.titulo,
      descricao: data.descricao,
      status: data.tipo === "Chamado entre setores" ? "Aberto" : "Em análise",
      responsavel: data.responsavel,
      criadoEm: today(),
      prazo: data.prazo
    };
    state.chamados = [chamado, ...chamados];
    saveState();
    toast("Chamado aberto e indicadores atualizados.", "success");
    render();
  }

  function updateChamadoStatus(id, status) {
    const chamado = (state.chamados || []).find((item) => item.id === id);
    if (!chamado) return;
    chamado.status = status;
    chamado.responsavel = currentUser()?.nome || chamado.responsavel;
    chamado.atualizadoEm = today();
    saveState();
    toast(`Chamado ${id} atualizado para ${status.toLowerCase()}.`, "success");
    render();
  }

  function approve(id, result) {
    const approval = state.approvals.find((item) => item.id === id);
    if (!approval) return;
    if (!["coordenador", "supervisao", "admin"].includes(currentUser()?.role)) {
      toast("Seu perfil não possui permissão para aprovar.", "warning");
      return;
    }
    approval.status = result;
    approval.responsavel = currentUser().nome;
    approval.atualizadoEm = today();
    const order = orderById(approval.orderId);
    if (order) order.status = result === "Aprovado" ? "Aprovado" : "Rejeitado";
    saveState();
    toast(`Aprovação marcada como ${result.toLowerCase()}.`, result === "Aprovado" ? "success" : "warning");
    render();
  }

  function createRfq() {
    if (!canAccess("compras")) {
      toast("Seu perfil não possui acesso a Compras.", "warning");
      return;
    }
    const productIds = state.ui.selectedQuoteProductIds;
    if (!productIds.length) {
      toast("Selecione ao menos um produto para cotação.", "warning");
      return;
    }
    const suppliers = suppliersForProducts(productIds);
    if (!suppliers.length) {
      toast("Nenhum fornecedor compatível encontrado.", "warning");
      return;
    }
    const products = productIds.map(productById).filter(Boolean);
    const rfqId = `rfq-${new Date().getFullYear()}-${String(state.rfqs.length + 1).padStart(3, "0")}`;
    const prazoResposta = today(3);
    state.rfqs.unshift({
      id: rfqId,
      produtoIds: productIds.slice(),
      fornecedorIds: suppliers.map((item) => item.id),
      status: "Enviado",
      criadoEm: today(),
      prazoResposta
    });
    saveState();

    const lines = products.map((product) => {
      const suggested = Math.max(Number(product.minimo) - Number(product.estoque), Math.ceil(Number(product.minimo) * 0.3));
      return `- ${product.sku} | ${product.nome} | Qtd. sugerida: ${suggested} | NCM: ${product.ncm}`;
    });
    const subject = `${rfqId} - Pedido de cotação Cargo.Ops`;
    const body = [
      "Prezados,",
      "",
      "Solicitamos cotação para os itens abaixo:",
      "",
      ...lines,
      "",
      `Favor responder até ${formatDate(prazoResposta)} com preço, prazo, impostos, condição de pagamento e validade da proposta.`,
      "",
      "Atenciosamente,",
      currentUser()?.nome || "Cargo.Ops"
    ].join("\n");
    openMailto(suppliers.map((supplier) => supplier.email), subject, body);
    toast("RFQ registrada e e-mail preparado.", "success");
    render();
  }

  function openMailto(emails, subject, body) {
    const href = `mailto:${emails.join(",")}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    window.location.href = href;
  }

  function sendFinanceEmail(supplierId, kind) {
    if (!canAccess("financeiro")) {
      toast("Seu perfil não possui acesso ao Financeiro.", "warning");
      return;
    }
    const supplier = supplierById(supplierId);
    if (!supplier) return;
    const subject = kind === "dados"
      ? "Solicitação de dados cadastrais e bancários"
      : "Tratativa financeira - Cargo.Ops";
    const body = kind === "dados"
      ? [
          `Olá, ${supplier.contato}.`,
          "",
          "Para sequência do processo financeiro, favor enviar/confirmar os dados cadastrais, bancários, condição fiscal e contato responsável.",
          "",
          "Atenciosamente,",
          currentUser()?.nome || "Financeiro Cargo.Ops"
        ].join("\n")
      : [
          `Olá, ${supplier.contato}.`,
          "",
          "Precisamos alinhar uma tratativa financeira referente aos processos em aberto. Poderia retornar com disponibilidade e documentos pertinentes?",
          "",
          "Atenciosamente,",
          currentUser()?.nome || "Financeiro Cargo.Ops"
        ].join("\n");
    openMailto([supplier.email], subject, body);
    toast("E-mail financeiro preparado.", "success");
  }

  function createFiscalNote(form) {
    if (!canAccess("financeiro")) {
      toast("Seu perfil não possui acesso ao Financeiro.", "warning");
      return;
    }
    const data = Object.fromEntries(new FormData(form).entries());
    const order = orderById(data.orderId);
    if (!order) {
      toast("Selecione um pedido aprovado.", "warning");
      return;
    }
    const product = productById(order.produtoId);
    const supplier = supplierById(order.fornecedorId);
    const totalUSD = Number(order.quantidade) * Number(order.precoUSD);
    const note = {
      id: `PNF-${new Date().getFullYear()}-${String(state.financeiro.notas.length + 1).padStart(3, "0")}`,
      orderId: order.id,
      tipo: data.tipo,
      fornecedor: supplier?.nome || "-",
      fornecedorCnpj: supplier?.cnpj || "-",
      produto: product?.nome || "-",
      sku: product?.sku || "-",
      quantidade: Number(order.quantidade),
      valorUSD: totalUSD,
      taxa: Number(state.usd.bid),
      valorBRL: totalUSD * Number(state.usd.bid),
      vencimento: data.vencimento,
      status: "Gerada",
      criadoEm: new Date().toISOString()
    };
    state.financeiro.notas.push(note);
    saveState();
    toast("Pré-nota fiscal gerada para o financeiro.", "success");
    render();
  }

  function downloadNote(noteId) {
    const note = state.financeiro.notas.find((item) => item.id === noteId);
    if (!note) return;
    const html = `
      <!doctype html>
      <html lang="pt-BR">
      <head>
        <meta charset="UTF-8" />
        <title>${escapeHtml(note.id)}</title>
        <style>
          body { font-family: Arial, sans-serif; color:#0f172a; margin:32px; }
          h1 { margin: 0 0 8px; }
          table { width:100%; border-collapse:collapse; margin-top:20px; }
          td, th { border:1px solid #94a3b8; padding:8px; text-align:left; }
          th { background:#f1f5f9; }
          .mono { font-family: Consolas, monospace; }
        </style>
      </head>
      <body>
        <h1>${escapeHtml(note.tipo)} · ${escapeHtml(note.id)}</h1>
        <p>Documento operacional gerado pelo Cargo.Ops para conferência financeira/fiscal.</p>
        <table>
          <tbody>
            <tr><th>Pedido</th><td class="mono">${escapeHtml(note.orderId)}</td></tr>
            <tr><th>Fornecedor</th><td>${escapeHtml(note.fornecedor)} · ${escapeHtml(note.fornecedorCnpj)}</td></tr>
            <tr><th>Produto</th><td>${escapeHtml(note.sku)} · ${escapeHtml(note.produto)}</td></tr>
            <tr><th>Quantidade</th><td class="mono">${numberBR(note.quantidade)}</td></tr>
            <tr><th>Valor USD</th><td class="mono">${moneyUSD(note.valorUSD)}</td></tr>
            <tr><th>Taxa USD/BRL</th><td class="mono">${numberBR(note.taxa, 4)}</td></tr>
            <tr><th>Valor BRL</th><td class="mono">${moneyBRL(note.valorBRL)}</td></tr>
            <tr><th>Vencimento</th><td>${formatDate(note.vencimento)}</td></tr>
            <tr><th>Gerado em</th><td>${formatDateTime(note.criadoEm)}</td></tr>
          </tbody>
        </table>
      </body>
      </html>
    `;
    downloadText(`${note.id}.html`, "text/html;charset=utf-8", html);
  }

  function exportProducts() {
    const rows = state.products.map((product) => ({
      SKU: product.sku,
      Produto: product.nome,
      Categoria: product.categoria,
      NCM: product.ncm,
      Estoque: product.estoque,
      Minimo: product.minimo,
      "Custo USD": product.custoUSD,
      Deposito: product.deposito
    }));
    exportRowsAsExcel("cargo-ops-produtos.xls", rows);
  }

  function exportOrders() {
    const rows = state.orders.map((order) => {
      const product = productById(order.produtoId);
      const supplier = supplierById(order.fornecedorId);
      return {
        Pedido: order.id,
        Produto: product?.nome || "",
        SKU: product?.sku || "",
        Fornecedor: supplier?.nome || "",
        Quantidade: order.quantidade,
        "Preco USD": order.precoUSD,
        "Total USD": Number(order.precoUSD) * Number(order.quantidade),
        "Total BRL": Number(order.precoUSD) * Number(order.quantidade) * Number(state.usd.bid),
        Status: order.status,
        Prazo: order.prazo
      };
    });
    exportRowsAsExcel("cargo-ops-pedidos.xls", rows);
  }

  function exportRowsAsExcel(filename, rows) {
    if (!rows.length) {
      toast("Não há dados para exportar.", "warning");
      return;
    }
    const headers = Object.keys(rows[0]);
    const html = `
      <html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel">
      <head><meta charset="UTF-8"></head>
      <body>
        <table>
          <thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join("")}</tr></thead>
          <tbody>${rows.map((row) => `<tr>${headers.map((header) => `<td>${escapeHtml(row[header])}</td>`).join("")}</tr>`).join("")}</tbody>
        </table>
      </body>
      </html>
    `;
    downloadText(filename, "application/vnd.ms-excel;charset=utf-8", html);
    toast("Arquivo Excel gerado.", "success");
  }

  function downloadText(filename, mime, content) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function importProductsFile(file) {
    if (!file) return;
    try {
      const lower = file.name.toLowerCase();
      let rows = [];
      if (lower.endsWith(".csv")) {
        const text = await file.text();
        rows = parseCsv(text);
      } else {
        rows = await parseExcel(file);
      }
      const imported = upsertProductsFromRows(rows);
      saveState();
      toast(`${imported} produto(s) importado(s).`, imported ? "success" : "warning");
      render();
    } catch (error) {
      console.error(error);
      toast(error.message || "Não foi possível importar a planilha.", "danger");
    }
  }

  function parseCsv(text) {
    const lines = text.split(/\r?\n/).filter((line) => line.trim());
    if (!lines.length) return [];
    const delimiter = lines[0].includes(";") ? ";" : ",";
    const headers = splitCsvLine(lines[0], delimiter).map((item) => item.trim());
    return lines.slice(1).map((line) => {
      const values = splitCsvLine(line, delimiter);
      return headers.reduce((row, header, index) => {
        row[header] = values[index] ?? "";
        return row;
      }, {});
    });
  }

  function splitCsvLine(line, delimiter) {
    const values = [];
    let current = "";
    let quoted = false;
    for (let index = 0; index < line.length; index += 1) {
      const char = line[index];
      const next = line[index + 1];
      if (char === '"' && quoted && next === '"') {
        current += '"';
        index += 1;
      } else if (char === '"') {
        quoted = !quoted;
      } else if (char === delimiter && !quoted) {
        values.push(current);
        current = "";
      } else {
        current += char;
      }
    }
    values.push(current);
    return values;
  }

  async function parseExcel(file) {
    await ensureSheetJs();
    const buffer = await file.arrayBuffer();
    const workbook = window.XLSX.read(buffer, { type: "array" });
    const first = workbook.SheetNames[0];
    return window.XLSX.utils.sheet_to_json(workbook.Sheets[first], { defval: "" });
  }

  function ensureSheetJs() {
    if (window.XLSX) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://cdn.sheetjs.com/xlsx-latest/package/dist/xlsx.full.min.js";
      script.onload = resolve;
      script.onerror = () => reject(new Error("Leitor .xlsx indisponível. Exporte a planilha como CSV ou conecte a biblioteca SheetJS localmente."));
      document.head.appendChild(script);
    });
  }

  function upsertProductsFromRows(rows) {
    let count = 0;
    rows.forEach((row) => {
      const normalized = normalizeRow(row);
      const sku = normalized.sku || normalized.SKU;
      const name = normalized.produto || normalized.nome || normalized.Produto || normalized.Nome;
      if (!sku || !name) return;
      const existing = state.products.find((item) => item.sku.toLowerCase() === String(sku).toLowerCase());
      const product = {
        id: existing?.id || uid("prod"),
        sku: String(sku).trim(),
        nome: String(name).trim(),
        categoria: String(normalized.categoria || normalized.Categoria || "Sem categoria").trim(),
        ncm: String(normalized.ncm || normalized.NCM || "0000.00.00").trim(),
        estoque: parseNumber(normalized.estoque || normalized.Estoque),
        minimo: parseNumber(normalized.minimo || normalized.Minimo || normalized.Mínimo),
        custoUSD: parseNumber(normalized.custoUSD || normalized["Custo USD"] || normalized.custo_usd),
        deposito: String(normalized.deposito || normalized.Deposito || normalized.Depósito || "São Paulo").trim(),
        fornecedores: []
      };
      product.fornecedores = state.suppliers
        .filter((supplier) => supplier.categorias.includes(product.categoria))
        .map((supplier) => supplier.id);
      if (existing) Object.assign(existing, product);
      else state.products.push(product);
      count += 1;
    });
    return count;
  }

  function normalizeRow(row) {
    return Object.entries(row).reduce((acc, [key, value]) => {
      const clean = String(key).trim();
      acc[clean] = value;
      acc[clean.normalize("NFD").replace(/[\u0300-\u036f]/g, "")] = value;
      acc[clean.toLowerCase()] = value;
      acc[clean.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")] = value;
      return acc;
    }, {});
  }

  function handleSubmit(event) {
    const form = event.target.closest("form[data-form]");
    if (!form) return;
    event.preventDefault();
    const name = form.dataset.form;
    if (name === "login") {
      const data = Object.fromEntries(new FormData(form).entries());
      login(data.email, data.password);
    }
    if (name === "order") createOrder(form);
    if (name === "product") createProduct(form);
    if (name === "user") createUser(form);
    if (name === "fiscal-note") createFiscalNote(form);
    if (name === "ticket") createChamado(form);
  }

  function handleClick(event) {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const action = button.dataset.action;

    if (action === "demo-login") {
      document.querySelector("[name='email']").value = button.dataset.email;
      document.querySelector("[name='password']").value = button.dataset.password;
    }

    if (action === "logout") {
      state.currentUserId = null;
      saveState();
      render();
    }

    if (action === "nav") {
      const moduleId = button.dataset.module;
      if (!canAccess(moduleId)) {
        toast("Seu perfil não possui acesso a este módulo.", "warning");
        return;
      }
      const module = navigation.find((item) => item.id === moduleId);
      state.view = { module: moduleId, sub: button.dataset.sub || module?.children?.[0]?.id || null };
      saveState();
      render();
    }

    if (action === "quote-add-one") {
      const id = button.dataset.id;
      if (!state.ui.selectedQuoteProductIds.includes(id)) state.ui.selectedQuoteProductIds.push(id);
      saveState();
      toast("Produto adicionado à cotação.", "success");
      render();
    }

    if (action === "create-rfq") createRfq();
    if (action === "approval") approve(button.dataset.id, button.dataset.result);
    if (action === "finance-email") sendFinanceEmail(button.dataset.id, button.dataset.kind);
    if (action === "ticket-status") updateChamadoStatus(button.dataset.id, button.dataset.status);
    if (action === "download-note") downloadNote(button.dataset.id);
    if (action === "export-products") exportProducts();
    if (action === "export-orders") exportOrders();
    if (action === "trigger-import") document.querySelector("[data-action='import-products']")?.click();

    if (action === "reset-demo") {
      const userId = state.currentUserId;
      state = getSeedState();
      state.currentUserId = userId;
      saveState();
      toast("Dados restaurados.", "success");
      render();
    }
  }

  function handleChange(event) {
    const target = event.target;
    if (target.dataset.action === "quote-toggle") {
      const id = target.dataset.id;
      const selected = new Set(state.ui.selectedQuoteProductIds);
      if (target.checked) selected.add(id);
      else selected.delete(id);
      state.ui.selectedQuoteProductIds = Array.from(selected);
      saveState();
      render();
    }

    if (target.dataset.action === "import-products") {
      importProductsFile(target.files?.[0]);
    }
  }

  function render() {
    if (!currentUser()) renderLogin();
    else renderShell();
  }

  document.addEventListener("submit", handleSubmit);
  document.addEventListener("click", handleClick);
  document.addEventListener("change", handleChange);

  render();
  fetchDollar();
  window.setInterval(fetchDollar, REFRESH_MS);
})();
