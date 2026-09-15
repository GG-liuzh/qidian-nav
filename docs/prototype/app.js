"use strict";

// This is an in-memory design prototype. All seeded addresses and credentials are fictional.
const paths = {
  layout: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 9v12"/>',
  star: '<path d="m12 3 2.8 5.7 6.3.9-4.6 4.5 1.1 6.3-5.6-3-5.6 3 1.1-6.3L3 9.6l6.2-.9Z"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  "folder-lock": '<path d="M9 20H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v3"/><rect x="12" y="14" width="9" height="7" rx="1"/><path d="M14 14v-2a2.5 2.5 0 0 1 5 0v2"/>',
  sliders: '<path d="M4 7h7m4 0h5M4 17h3m4 0h9"/><circle cx="13" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="m16 8-2.5 5.5L8 16l2.5-5.5Z"/>',
  "arrow-right": '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  settings: '<path d="m9 3-1 3-3 1-2 3 2 2v3l2 3 3-1 2 2 3-1 1-3 3-1 1-3-2-2V7l-3-2-3 1Z"/><circle cx="11" cy="11" r="3"/>',
  chevrons: '<path d="m9 8 3-3 3 3m-6 8 3 3 3-3"/>',
  home: '<path d="m3 10 9-7 9 7v10H3Zm6 10v-7h6v7"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  moon: '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 2-2.5 2-2.5 4m0 3h.01"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  x: '<path d="m6 6 12 12M6 18 18 6"/>',
  pin: '<path d="m9 3 12 12-4 1-3 3-3-6-6-3 3-3Zm2 10-7 7"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  list: '<path d="M9 5h12M9 12h12M9 19h12M3 5h1M3 12h1M3 19h1"/>',
  sort: '<path d="M8 4v16m-4-4 4 4 4-4M14 5h7m-7 5h5m-5 5h3"/>',
  package: '<path d="m12 3 9 5-9 5-9-5Zm-9 5v10l9 5 9-5V8M12 13v10M7 5.8l9 5"/>',
  wallet: '<rect x="3" y="6" width="18" height="14" rx="2"/><path d="M3 8V5a2 2 0 0 1 2-2h12v3m4 5h-6v5h6m-3-2.5h.01"/>',
  boxes: '<path d="m8 3 5 3-5 3-5-3Zm-5 3v6l5 3 5-3V6M8 9v6m8-5 5 3-5 3-5-3Zm-5 3v6l5 3 5-3v-6M16 16v6"/>',
  users: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 4v3"/>',
  shield: '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
  terminal: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3m6 0h4"/>',
  code: '<path d="m8 7-5 5 5 5m8-10 5 5-5 5M14 4l-4 16"/>',
  book: '<path d="M12 6C9 3 5 3 2 5v15c3-2 7-2 10 1 3-3 7-3 10-1V5c-3-2-7-2-10 1Zm0 0v15"/>',
  key: '<circle cx="8" cy="9" r="5"/><path d="m12 12 8 8m-3-3 3-3m-6 0 3-3"/>',
  edit: '<path d="m15 5 4 4M4 20l4-1L20 7a2.8 2.8 0 0 0-4-4L4 15Z"/>',
  external: '<path d="M14 3h7v7m0-7L10 14M10 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"/>',
  "arrow-up-right": '<path d="M6 18 18 6M6 6h12v12"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H3V3h12v2"/>',
  eye: '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/>',
  "eye-off": '<path d="m3 3 18 18M10 5.2A13 13 0 0 1 22 12a16 16 0 0 1-4 4M6 6a17 17 0 0 0-4 6s3.5 7 10 7a12 12 0 0 0 5-1m-8-8 5 5"/>',
  "check-circle": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10h.01"/>',
  upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5"/>',
  history: '<path d="M3 11a9 9 0 1 1 3 8M3 4v7h7m2-4v6l4 2"/>',
  globe: '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[character]);
const icon = (name) => `<svg class="icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.globe}</svg>`;
function hydrateIcons(root = document) { $$('[data-icon]', root).forEach(node => { node.innerHTML = icon(node.dataset.icon); }); }
const environments = { dev: { label: "开发", code: "DEV" }, test: { label: "测试", code: "TEST" }, prod: { label: "生产", code: "PROD" }, link: { label: "通用", code: "LINK" } };
const categories = { trade: "交易平台", growth: "用户增长", infra: "基础设施", common: "公共工具", learning: "学习资料", tools: "效率工具" };
const endpoints = (prefix, keys = ["dev", "test", "prod"]) => Object.fromEntries(keys.map(env => [env, `https://${prefix}${env === "prod" ? "" : `-${env}`}.example/`]));
const resources = [
  { id: "orders", scope: "team", type: "system", name: "订单中心", alias: "OMS", aliases: "dingdan dd 订单管理", description: "订单查询、履约管理与售后处理。", category: "trade", tags: ["订单", "履约", "售后"], icon: "package", color: "green", owner: "林知夏", endpoints: endpoints("oms"), updated: "2026-09-14" },
  { id: "payment", scope: "team", type: "system", name: "支付网关", alias: "PAYMENT", aliases: "zhifu zf 支付 对账", description: "支付路由、渠道配置与交易对账。", category: "trade", tags: ["支付", "财务"], icon: "wallet", color: "blue", owner: "陈以安", endpoints: endpoints("payment"), updated: "2026-09-12" },
  { id: "products", scope: "team", type: "system", name: "商品管理", alias: "PIM", aliases: "shangpin sp 商品 库存", description: "商品资料、库存同步与上下架管理。", category: "trade", tags: ["商品", "库存"], icon: "boxes", color: "amber", owner: "林知夏", endpoints: endpoints("products"), updated: "2026-09-13" },
  { id: "growth", scope: "team", type: "system", name: "用户增长平台", alias: "GROWTH", aliases: "yonghu yh yingxiao 营销", description: "用户分群、活动配置与触达管理。", category: "growth", tags: ["营销", "活动", "运营"], icon: "users", color: "amber", owner: "许清和", endpoints: endpoints("growth"), updated: "2026-09-11" },
  { id: "access", scope: "team", type: "system", name: "统一权限中心", alias: "IAM", aliases: "quanxian qx 认证 单点登录", description: "角色授权、组织成员与权限策略。", category: "infra", tags: ["权限", "组织"], icon: "shield", color: "green", owner: "周亦舟", endpoints: endpoints("iam", ["test", "prod"]), updated: "2026-09-10" },
  { id: "logs", scope: "team", type: "system", name: "日志检索平台", alias: "OBSERVABILITY", aliases: "rizhi rz log kibana 监控", description: "应用日志、链路追踪与问题定位。", category: "infra", tags: ["日志", "排障", "监控"], icon: "terminal", color: "blue", owner: "沈南星", endpoints: endpoints("logs", ["test", "prod"]), updated: "2026-09-14" },
  { id: "api-docs", scope: "team", type: "bookmark", name: "接口文档", alias: "API DOCS", aliases: "jiekou jk swagger apifox", description: "接口定义与联调说明", category: "common", tags: ["文档", "API"], icon: "code", color: "blue", owner: "林知夏", endpoints: { link: "https://api-docs.example/" }, updated: "2026-09-13" },
  { id: "wiki", scope: "team", type: "bookmark", name: "团队知识库", alias: "WIKI", aliases: "zhishi zs 文档 wiki", description: "规范、经验与新人入门", category: "common", tags: ["知识库", "文档"], icon: "book", color: "green", owner: "许清和", endpoints: { link: "https://wiki.example/" }, updated: "2026-09-12" },
  { id: "python", scope: "personal", type: "bookmark", name: "Python 学习手册", alias: "PYTHON", aliases: "xuexi xx python", description: "自己的学习资料与常用参考", category: "learning", tags: ["Python", "学习"], icon: "code", color: "blue", owner: "林知夏", endpoints: { link: "https://python-notes.example/" }, updated: "2026-09-14" },
  { id: "colors", scope: "personal", type: "bookmark", name: "配色灵感收藏", alias: "COLORS", aliases: "peise ps 设计 color", description: "喜欢的颜色与界面参考", category: "tools", tags: ["设计", "灵感"], icon: "compass", color: "amber", owner: "林知夏", endpoints: { link: "https://color-notes.example/" }, updated: "2026-09-13" },
];
const state = { view: "team", category: "all", env: "all", search: "", layout: "grid", sort: "default", favorites: new Set(["orders", "logs", "api-docs"]), recent: [], drawer: null, dirty: false, nextId: 1 };
const shortcuts = [{ id: "orders", env: "test" }, { id: "logs", env: "prod" }, { id: "api-docs", env: "link" }];
const demoAccounts = {};
for (const resource of resources.filter(resource => resource.type === "system")) {
  demoAccounts[resource.id] = {};
  for (const env of Object.keys(resource.endpoints)) {
    demoAccounts[resource.id][env] = [{ name: env === "prod" ? "只读查询账号" : "团队联调账号", username: `demo_${resource.id}_${env}`, password: `DEMO-only_${env.toUpperCase()}_2026!`, note: env === "prod" ? "演示：仅用于查询，不具有写入权限。" : "演示：供日常联调使用，测试数据可能定期重置。" }];
  }
}
demoAccounts.orders.test.push({ name: "订单只读账号", username: "demo_orders_reader", password: "DEMO-only_READER_2026!", note: "演示：适合排查订单状态，不支持修改订单。" });
const revealTimers = new Map();
let manualTimer;
let toastTimer;
let returnFocus;
let pendingDrawerAction;
let drawerEpoch = 0;

const findResource = (id) => resources.find(resource => resource.id === id);
const getAccounts = (id, env) => (demoAccounts[id]?.[env] || []).filter(account => !account.pending);
const accountsCount = (id) => Object.values(demoAccounts[id] || {}).reduce((sum, accounts) => sum + accounts.filter(account => !account.pending).length, 0);
function checkedUrl(value) {
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) throw new Error("地址需要使用 HTTP/HTTPS，且不能在地址中嵌入账号密码。");
  return url;
}
function parsedQuery() {
  const envWords = { "开发": "dev", dev: "dev", "测试": "test", test: "test", "生产": "prod", prod: "prod" };
  const words = state.search.normalize("NFKC").toLowerCase().trim().split(/\s+/).filter(Boolean);
  return { terms: words.filter(word => !envWords[word]), envs: words.filter(word => envWords[word]).map(word => envWords[word]) };
}
function baseResources() {
  if (state.view === "favorites") return resources.filter(resource => state.favorites.has(resource.id));
  if (state.view === "recent") return [...new Set(state.recent.map(visit => visit.id))].map(findResource).filter(Boolean);
  return resources.filter(resource => resource.scope === (state.view === "personal" ? "personal" : "team"));
}
function visibleEnvironments(resource) {
  let keys = Object.keys(resource.endpoints);
  if (resource.type === "bookmark") return keys;
  if (state.view === "recent") keys = keys.filter(env => state.recent.some(visit => visit.id === resource.id && visit.env === env));
  if (state.env !== "all") keys = keys.filter(env => env === state.env);
  const query = parsedQuery();
  if (query.envs.length) keys = keys.filter(env => query.envs.includes(env));
  return keys;
}
function filteredResources() {
  const query = parsedQuery();
  let list = baseResources().filter(resource => {
    if (state.category !== "all" && resource.category !== state.category) return false;
    if (resource.type === "system" && !visibleEnvironments(resource).length) return false;
    if (resource.type === "bookmark" && query.envs.length) return false;
    const haystack = [resource.name, resource.alias, resource.aliases, resource.description, categories[resource.category], ...resource.tags, ...Object.values(resource.endpoints)].join(" ").normalize("NFKC").toLowerCase();
    return query.terms.every(term => haystack.includes(term));
  });
  if (state.sort === "name") list.sort((a, b) => a.name.localeCompare(b.name, "zh-CN"));
  else if (state.sort === "updated") list.sort((a, b) => b.updated.localeCompare(a.updated));
  else if (query.terms.length) {
    const relevance = resource => query.terms.reduce((score, term) => score + (resource.name.toLowerCase() === term ? 100 : resource.name.toLowerCase().startsWith(term) ? 60 : resource.alias.toLowerCase().includes(term) ? 40 : 0), 0) + (state.favorites.has(resource.id) ? 1 : 0);
    list.sort((a, b) => relevance(b) - relevance(a));
  }
  return list;
}
function environmentLink(resource, env) {
  const { label, code } = environments[env];
  return `<a class="environment-link ${env}" href="${escapeHTML(resource.endpoints[env])}" target="_blank" rel="noopener noreferrer" data-action="open" data-id="${escapeHTML(resource.id)}" data-env="${env}" aria-label="打开${escapeHTML(resource.name)} · ${label}"><i class="env-dot ${env}"></i>${label}<span class="env-code">${code}</span>${icon("arrow-up-right")}</a>`;
}
function favoriteButton(resource) {
  const saved = state.favorites.has(resource.id);
  return `<button class="icon-button favorite-button ${saved ? "is-favorite" : ""}" data-action="favorite" data-id="${escapeHTML(resource.id)}" aria-label="${saved ? "取消收藏" : "收藏"}${escapeHTML(resource.name)}" aria-pressed="${saved}">${icon("star")}</button>`;
}
function systemCard(resource) {
  const count = accountsCount(resource.id);
  return `<article class="resource-card" data-resource-id="${escapeHTML(resource.id)}">
    <div class="card-top"><span class="app-icon ${resource.color}">${icon(resource.icon)}</span><div class="card-title-group"><button class="card-title" data-action="details" data-id="${escapeHTML(resource.id)}">${escapeHTML(resource.name)}</button><div class="card-subtitle">${escapeHTML(categories[resource.category])} <span>·</span> ${escapeHTML(resource.alias)}</div></div>${favoriteButton(resource)}</div>
    <p class="card-description">${escapeHTML(resource.description || "还没有添加描述。")}</p>
    <div class="environment-links">${visibleEnvironments(resource).map(env => environmentLink(resource, env)).join("")}</div>
    <div class="card-footer"><button class="credential-button" data-action="details" data-id="${escapeHTML(resource.id)}">${icon(count ? "key" : "info")}${count ? `共享账号 <span class="credential-count">${count}</span>` : "使用说明"}</button><span class="owner"><span class="owner-dot">${escapeHTML(resource.owner[0])}</span>${escapeHTML(resource.owner)}<button class="icon-button" data-action="edit" data-id="${escapeHTML(resource.id)}" aria-label="编辑${escapeHTML(resource.name)}">${icon("edit")}</button></span></div>
  </article>`;
}
function bookmarkCard(resource) {
  const url = resource.endpoints.link;
  return `<article class="bookmark-card" data-resource-id="${escapeHTML(resource.id)}"><span class="app-icon ${resource.color}">${icon(resource.icon)}</span><div class="bookmark-main"><a class="bookmark-link" href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer" data-action="open" data-id="${escapeHTML(resource.id)}" data-env="link">${escapeHTML(resource.name)}</a><div class="bookmark-domain">${escapeHTML(checkedUrl(url).host)} · ${resource.scope === "personal" ? "仅自己可见" : escapeHTML(resource.description)}</div></div>${accountsCount(resource.id) ? `<button class="icon-button" data-action="details" data-id="${escapeHTML(resource.id)}" aria-label="查看${escapeHTML(resource.name)}的演示账号">${icon("key")}</button>` : ""}${favoriteButton(resource)}<button class="icon-button" data-action="edit" data-id="${escapeHTML(resource.id)}" aria-label="编辑${escapeHTML(resource.name)}">${icon("edit")}</button></article>`;
}
function renderCategories() {
  const base = baseResources();
  const categoryKeys = state.view === "personal" ? ["learning", "tools"] : ["trade", "growth", "infra", "common", ...((state.view === "favorites" || state.view === "recent") ? ["learning", "tools"] : [])];
  $("#category-label").textContent = state.view === "personal" ? "个人分组" : "业务线";
  $("#category-nav").innerHTML = categoryKeys.filter(key => ["team", "personal"].includes(state.view) || base.some(resource => resource.category === key)).map(key => `<button class="nav-item ${state.category === key ? "active" : ""}" data-category="${key}" aria-pressed="${state.category === key}"><span class="category-icon ${key}"><i></i></span>${categories[key]}<span class="nav-count">${base.filter(resource => resource.category === key).length}</span></button>`).join("");
}
function renderShortcuts() {
  $("#shortcuts").innerHTML = shortcuts.map(shortcut => {
    const resource = findResource(shortcut.id);
    if (!resource?.endpoints[shortcut.env]) return "";
    return `<a class="shortcut" href="${escapeHTML(resource.endpoints[shortcut.env])}" target="_blank" rel="noopener noreferrer" data-action="open" data-id="${shortcut.id}" data-env="${shortcut.env}" aria-label="快捷打开${escapeHTML(resource.name)} · ${environments[shortcut.env].label}"><span class="mini-icon">${icon(resource.icon)}</span><span class="shortcut-name">${escapeHTML(resource.name)}</span><span class="env-badge ${shortcut.env}">${environments[shortcut.env].label}</span><span>${icon("arrow-up-right")}</span></a>`;
  }).join("");
}
function render() {
  const headings = {
    team: ["团队导航", "每个入口，都井然有序。", "业务后台、共享账号、常用书签。你的工作，从这里开始。", "A LITTLE LESS SEARCHING."],
    favorites: ["我的收藏", "顺手的入口，留在身边。", "收藏团队系统与自己的书签，下一次更快到达。", "KEEP THE GOOD ONES CLOSE."],
    recent: ["最近访问", "熟悉的路径，随时回去。", "这里记录本次演示访问过的具体入口，仅自己可见。", "PICK UP WHERE YOU LEFT OFF."],
    personal: ["个人空间", "留一处，给自己的收藏。", "你的学习资料、灵感与常用工具。这里仅自己可见。", "A SMALL SPACE, ALL YOURS."],
  };
  const [title, heading, description, eyebrow] = headings[state.view];
  $("#breadcrumb-current").textContent = title;
  $("#page-title").textContent = heading;
  $("#page-description").textContent = description;
  $("#eyebrow").textContent = eyebrow;
  $("#resources-title").textContent = state.category === "all" ? ({ team: "全部资源", favorites: "收藏的入口", recent: "最近打开", personal: "我的书签" })[state.view] : categories[state.category];
  $("#favorite-count").textContent = state.favorites.size;
  $("#team-count").textContent = resources.filter(resource => resource.scope === "team").length;
  $$("[data-view]").forEach(button => { button.classList.toggle("active", button.dataset.view === state.view); button.toggleAttribute("aria-current", button.dataset.view === state.view); if (button.hasAttribute("aria-current")) button.setAttribute("aria-current", "page"); });
  $$("[data-env]", $("#environment-filter")).forEach(button => { const selected = button.dataset.env === state.env; button.classList.toggle("selected", selected); button.setAttribute("aria-pressed", selected); });
  $$("[data-layout]").forEach(button => { const selected = button.dataset.layout === state.layout; button.classList.toggle("selected", selected); button.setAttribute("aria-pressed", selected); });
  $("#shortcuts-section").hidden = state.view !== "team" || !!state.search.trim();
  $("#reset-filters").hidden = state.category === "all" && state.env === "all" && !state.search;
  $("#clear-search").hidden = !state.search;
  renderCategories();
  renderShortcuts();
  const visible = filteredResources();
  const systems = visible.filter(resource => resource.type === "system");
  const bookmarks = visible.filter(resource => resource.type === "bookmark");
  $("#result-count").textContent = visible.length;
  $("#result-count").setAttribute("aria-label", `显示 ${visible.length} 个资源`);
  const filters = [state.search ? `搜索“${state.search}”` : "", state.env !== "all" ? `仅显示${environments[state.env].label}入口，通用书签单列` : ""].filter(Boolean);
  $("#filter-description").textContent = filters.length ? filters.join(" · ") : state.view === "personal" ? "私人收藏，按自己的方式整理" : state.view === "recent" ? "按最近访问排列；刷新页面后清空演示记录" : "为日常工作整理的每一个入口";
  $("#resource-grid").classList.toggle("list-view", state.layout === "list");
  $("#resource-grid").innerHTML = systems.map(systemCard).join("");
  $("#bookmark-grid").innerHTML = bookmarks.map(bookmarkCard).join("");
  $("#bookmarks-section").hidden = bookmarks.length === 0;
  $("#resource-grid").hidden = systems.length === 0;
  $("#empty-state").hidden = visible.length !== 0;
  const isFiltered = !!state.search || state.env !== "all" || state.category !== "all";
  $("#empty-title").textContent = isFiltered ? "暂时没有找到匹配的入口" : state.view === "favorites" ? "把常用的入口，先收藏起来" : state.view === "recent" ? "从打开第一个入口开始" : "这里还没有链接";
  $("#empty-description").textContent = isFiltered ? "试试系统名称、标签，或换一个环境。" : state.view === "recent" ? "你从导航中打开的入口，会出现在这里。" : "在团队导航中发现常用系统，也可以添加自己的书签。";
  $("#empty-action").textContent = isFiltered ? "清除筛选" : "去团队导航";
}
function toast(message, isError = false) {
  clearTimeout(toastTimer);
  const node = $("#toast");
  ($( "#drawer").open ? $("#drawer") : document.body).append(node);
  node.classList.toggle("error", isError);
  $("#toast-message").textContent = message;
  node.hidden = false;
  toastTimer = setTimeout(() => { node.hidden = true; }, isError ? 5500 : 2600);
}
function resetFilters() { state.category = "all"; state.env = "all"; state.search = ""; $("#search").value = ""; render(); }
function changeView(view) { state.view = view; state.sort = view === "recent" ? "default" : state.sort; $("#sort").value = state.sort; resetFilters(); closeMobileNav(); }

function hidePassword(index) {
  clearTimeout(revealTimers.get(index));
  revealTimers.delete(index);
  const value = $(`#password-${index}`);
  const button = $(`[data-action="reveal"][data-index="${index}"]`);
  if (value) { value.textContent = "••••••••••••"; value.classList.add("masked"); value.dataset.revealed = "false"; }
  if (button) { button.innerHTML = icon("eye"); button.setAttribute("aria-label", "显示演示密码 20 秒"); button.setAttribute("aria-pressed", "false"); }
}
function clearSecrets() {
  for (const index of [...revealTimers.keys()]) hidePassword(index);
  $$("[data-secret]").forEach(node => { node.textContent = "••••••••••••"; node.classList.add("masked"); node.dataset.revealed = "false"; });
  clearTimeout(manualTimer);
  $("#manual-copy")?.remove();
}
function forceCloseDrawer() {
  clearSecrets();
  state.dirty = false;
  state.drawer = null;
  drawerEpoch++;
  $("#toast").hidden = true;
  document.body.append($("#toast"));
  $("#drawer-content").replaceChildren();
  $("#drawer").close();
  document.body.style.overflow = "";
  if (returnFocus?.isConnected) returnFocus.focus();
  else $("#add-resource").focus();
}
function requestCloseDrawer() {
  if (state.dirty) { pendingDrawerAction = forceCloseDrawer; $("#confirm-dialog").showModal(); }
  else forceCloseDrawer();
}
function presentDrawer(title, eyebrow, content, drawerState) {
  if (state.dirty) {
    pendingDrawerAction = () => presentDrawer(title, eyebrow, content, drawerState);
    $("#confirm-dialog").showModal();
    return false;
  }
  clearSecrets();
  clearTimeout(toastTimer);
  $("#toast").hidden = true;
  closeMobileNav();
  const dialog = $("#drawer");
  if (!dialog.open) returnFocus = document.activeElement;
  $("#drawer-title").textContent = title;
  $("#drawer-eyebrow").textContent = eyebrow;
  $("#drawer-content").innerHTML = content;
  state.drawer = { ...drawerState, epoch: ++drawerEpoch };
  state.dirty = false;
  if (!dialog.open) dialog.showModal();
  document.body.style.overflow = "hidden";
  $("#close-drawer").focus();
  return true;
}
function detailContent(resource, env) {
  const accounts = getAccounts(resource.id, env);
  const envLabel = environments[env].label;
  const chips = Object.keys(resource.endpoints).map(key => `<button class="${key} ${key === env ? "selected" : ""}" data-action="switch-env" data-env="${key}" data-id="${escapeHTML(resource.id)}" aria-pressed="${key === env}">${environments[key].label} ${environments[key].code}</button>`).join("");
  return `<p class="drawer-intro">${escapeHTML(resource.description)}</p>
    <div class="drawer-environments" role="group" aria-label="选择账号所属环境">${chips}</div>
    <div class="endpoint-preview"><div class="endpoint-preview-header"><strong>${env === "link" ? "通用链接" : `${envLabel}环境入口`}</strong><a class="text-button" href="${escapeHTML(resource.endpoints[env])}" target="_blank" rel="noopener noreferrer" data-action="open" data-id="${escapeHTML(resource.id)}" data-env="${env}">打开链接 ${icon("external")}</a></div><span class="endpoint-address">${escapeHTML(resource.endpoints[env])}</span></div>
    <div class="account-section-title">${env === "link" ? "共享账号" : `${envLabel}环境的共享账号`}<span>${accounts.length} 个演示账号</span></div>
    ${accounts.length ? accounts.map((account, index) => `<section class="account-card" aria-label="${escapeHTML(account.name)}"><div class="account-heading"><strong>${escapeHTML(account.name)}</strong><span class="account-status">演示可用</span></div>
      <span class="secret-label">用户名</span><div class="secret-field"><span class="secret-value">${escapeHTML(account.username)}</span><button class="text-button" data-action="copy" data-field="username" data-index="${index}" aria-label="复制${escapeHTML(account.name)}的用户名">${icon("copy")}复制用户名</button></div>
      <span class="secret-label">密码</span><div class="secret-field"><span class="secret-value masked" id="password-${index}" data-secret data-revealed="false">••••••••••••</span><button class="icon-button" data-action="reveal" data-index="${index}" aria-label="显示演示密码 20 秒" aria-pressed="false">${icon("eye")}</button><button class="text-button" data-action="copy" data-field="password" data-index="${index}" aria-label="复制${escapeHTML(account.name)}的密码">${icon("copy")}复制密码</button></div>
      <p class="account-note">${escapeHTML(account.note)}</p><div class="account-meta"><span>${escapeHTML(resource.owner)}维护 · ${escapeHTML(resource.updated)}</span><button class="text-button" data-action="feedback">账号不可用</button></div>
    </section>`).join("") : `<div class="info-note">${icon("key")}<span>这个环境还没有演示账号。可以在编辑链接时添加一份虚构账号，体验完整流程。</span></div>`}
    <div class="info-note">${icon("info")}<span>当前均为虚构演示账号。显示的密码将在 20 秒后隐藏，切换环境或关闭面板时立即隐藏。</span></div>
    <div class="drawer-detail"><div class="detail-row"><span>业务归属</span><span>${escapeHTML(categories[resource.category])}</span></div><div class="detail-row"><span>维护人</span><span>${escapeHTML(resource.owner)}</span></div><div class="detail-row"><span>标签</span><span class="tags">${resource.tags.map(tag => `<span class="tag">${escapeHTML(tag)}</span>`).join("") || "未设置"}</span></div><div class="detail-row"><span>可见范围</span><span>${resource.scope === "personal" ? "个人空间 · 仅自己可见" : "产品研发部 · 团队共享"}</span></div><button class="button secondary" data-action="edit" data-id="${escapeHTML(resource.id)}">${icon("edit")}编辑链接</button></div>`;
}
function openDetails(resource, requestedEnv) {
  const preferredEnv = requestedEnv || (state.env !== "all" ? state.env : parsedQuery().envs[0]);
  const env = resource.endpoints[preferredEnv] ? preferredEnv : resource.endpoints.test ? "test" : Object.keys(resource.endpoints)[0];
  presentDrawer(resource.name, `${categories[resource.category]} / 共享账号与使用说明`, detailContent(resource, env), { kind: "details", id: resource.id, env });
}
function revealPassword(index) {
  if (state.drawer?.kind !== "details") return;
  const account = getAccounts(state.drawer.id, state.drawer.env)[index];
  const node = $(`#password-${index}`);
  if (!account || !node) return;
  if (node.dataset.revealed === "true") { hidePassword(index); return; }
  node.textContent = account.password;
  node.classList.remove("masked");
  node.dataset.revealed = "true";
  const button = $(`[data-action="reveal"][data-index="${index}"]`);
  button.innerHTML = icon("eye-off");
  button.setAttribute("aria-label", "隐藏演示密码");
  button.setAttribute("aria-pressed", "true");
  revealTimers.set(index, setTimeout(() => hidePassword(index), 20000));
}
async function copyCredential(index, field) {
  if (state.drawer?.kind !== "details" || !["username", "password"].includes(field)) return;
  const account = getAccounts(state.drawer.id, state.drawer.env)[index];
  if (!account) return;
  const epoch = state.drawer.epoch;
  const value = account[field];
  try {
    if (!navigator.clipboard?.writeText) throw new Error("Clipboard unavailable");
    await navigator.clipboard.writeText(value);
    if (state.drawer?.epoch === epoch) toast(`${environments[state.drawer.env].label}环境的${field === "username" ? "用户名" : "密码"}已复制`);
  } catch {
    if (state.drawer?.epoch !== epoch) return;
    $("#manual-copy")?.remove();
    const manual = document.createElement("section");
    manual.id = "manual-copy";
    manual.className = "manual-copy";
    manual.innerHTML = '<p role="alert">浏览器未允许自动复制。请手动复制下方选中的演示内容；20 秒后自动隐藏。</p><textarea rows="2" readonly aria-label="手动复制演示内容"></textarea>';
    $("#drawer-content").prepend(manual);
    $("textarea", manual).value = value;
    $("textarea", manual).focus();
    $("textarea", manual).select();
    clearTimeout(manualTimer);
    manualTimer = setTimeout(() => { manual.remove(); if ($("#drawer").open) $("#close-drawer").focus(); }, 20000);
  }
}
function openDestination(resource, env) {
  presentDrawer("准备前往这个入口", "环境跳转预览", `<div class="demo-destination"><span>${icon(resource.icon)}</span><h3>${escapeHTML(resource.name)}</h3><span class="env-badge ${env}">${environments[env].label} ${environments[env].code}</span><span class="endpoint-address">${escapeHTML(resource.endpoints[env])}</span></div><div class="info-note">${icon("info")}<span>这是保留的 .example 演示地址，不连接真实业务系统。正式版本会直接打开你配置的地址，环境关系保持一致。</span></div>${resource.type === "system" ? `<button class="button primary" data-action="details" data-id="${escapeHTML(resource.id)}" data-env="${env}">${icon("key")}查看这个环境的账号</button>` : ""}`, { kind: "destination", id: resource.id, env });
}
function recordVisit(resource, env) {
  state.recent = [{ id: resource.id, env, at: Date.now() }, ...state.recent.filter(visit => visit.id !== resource.id || visit.env !== env)].slice(0, 30);
  if (state.view === "recent") render();
}

function editorMarkup(resource) {
  const type = resource?.type || (state.view === "personal" ? "bookmark" : "system");
  const scope = resource?.scope || (state.view === "personal" ? "personal" : "team");
  const disabled = resource ? "disabled" : "";
  return `<form id="resource-form"><p class="drawer-intro">${resource ? "保持系统信息和环境入口清晰，大家就能更快找到。" : "给常用的系统或书签，安排一个固定的位置。"}</p>
    <div class="form-error" id="form-error" role="alert" hidden></div>
    <fieldset class="type-fieldset"><legend class="sr-only">链接类型</legend><div class="type-selector"><label><input type="radio" name="type" value="system" ${type === "system" ? "checked" : ""} ${disabled}>${icon("layout")}业务系统</label><label><input type="radio" name="type" value="bookmark" ${type === "bookmark" ? "checked" : ""} ${disabled}>${icon("book")}普通书签</label></div></fieldset>
    <div class="form-row"><div class="form-group"><label class="form-label" for="resource-scope">保存到</label><select class="form-field" id="resource-scope" name="scope" ${disabled}><option value="team" ${scope === "team" ? "selected" : ""}>团队空间 · 部门共享</option><option value="personal" ${scope === "personal" ? "selected" : ""}>个人空间 · 仅自己可见</option></select></div><div class="form-group"><label class="form-label" for="resource-category">业务线 / 分组</label><select class="form-field" id="resource-category" name="category"></select></div></div>
    <div class="form-group"><label class="form-label" for="resource-name">名称<span class="required">*</span></label><input class="form-field" id="resource-name" name="name" placeholder="例如：订单中心" maxlength="80" value="${escapeHTML(resource?.name || "")}" required></div>
    <div class="form-row"><div class="form-group"><label class="form-label" for="resource-alias">英文简称</label><input class="form-field" id="resource-alias" name="alias" maxlength="32" placeholder="例如：OMS" value="${escapeHTML(resource?.alias || "")}"></div><div class="form-group"><label class="form-label" for="resource-owner">维护人</label><input class="form-field" id="resource-owner" name="owner" maxlength="24" value="${escapeHTML(resource?.owner || "林知夏")}"></div></div>
    <div class="form-group"><label class="form-label" for="resource-description">简短描述</label><textarea class="form-field" id="resource-description" name="description" maxlength="160" placeholder="这个入口可以用来做什么？">${escapeHTML(resource?.description || "")}</textarea></div>
    <section id="system-fields" ${type === "system" ? "" : "hidden"}><div class="form-section-heading"><h3>环境与地址</h3><span>至少配置一个环境</span></div>${["dev", "test", "prod"].map(env => `<div class="endpoint-form-row"><label for="endpoint-${env}"><i class="env-dot ${env}"></i>${environments[env].label}</label><input class="form-field" id="endpoint-${env}" name="endpoint_${env}" placeholder="https://system${env === "prod" ? "" : `-${env}`}.example" value="${escapeHTML(resource?.endpoints[env] || "")}" inputmode="url" maxlength="2048"></div>`).join("")}<p class="form-help">不同环境分别填写。没有的环境留空，入口不会自动替换。</p></section>
    <section id="bookmark-fields" ${type === "bookmark" ? "" : "hidden"}><div class="form-group"><label class="form-label" for="bookmark-url">链接地址<span class="required">*</span></label><input class="form-field" id="bookmark-url" name="bookmark_url" placeholder="https://docs.example/" value="${escapeHTML(resource?.endpoints.link || "")}" inputmode="url" maxlength="2048"></div></section>
    <div class="form-group" style="margin-top:22px"><label class="form-label" for="resource-tags">标签</label><input class="form-field" id="resource-tags" name="tags" maxlength="120" placeholder="例如：订单, 联调, 常用" value="${escapeHTML(resource?.tags.join(", ") || "")}"><p class="form-help">多个标签用逗号分隔。</p></div>
    <details class="account-config"><summary>${icon("key")}新增演示账号<span>可选</span></summary><p class="form-help">仅填写虚构信息。原型在页面内存中保存演示账号，刷新后清除。</p><div class="form-row"><div class="form-group"><label class="form-label" for="credential-env">所属环境</label><select class="form-field" id="credential-env" name="credential_env"></select></div><div class="form-group"><label class="form-label" for="credential-name">账号用途</label><input class="form-field" id="credential-name" name="credential_name" placeholder="例如：只读查询" maxlength="40"></div></div><div class="form-group"><label class="form-label" for="credential-username">演示用户名</label><input class="form-field" id="credential-username" name="credential_username" autocomplete="off" maxlength="128" placeholder="demo_reader"></div><div class="form-group"><label class="form-label" for="credential-password">演示密码</label><input class="form-field" type="password" id="credential-password" name="credential_password" autocomplete="new-password" maxlength="256" placeholder="请使用虚构密码"></div></details>
    <div class="form-actions"><span class="form-help">当前页面内保存</span><button class="button secondary" type="button" data-action="close-drawer">取消</button><button class="button primary" type="submit">${icon("check-circle")}${resource ? "保存修改" : "保存链接"}</button></div>
  </form>`;
}
function updateEditorFields(preferredCategory) {
  const form = $("#resource-form");
  if (!form) return;
  const type = $('input[name="type"]:checked', form).value;
  const scope = $("#resource-scope").value;
  $("#system-fields").hidden = type !== "system";
  $("#bookmark-fields").hidden = type !== "bookmark";
  const keys = scope === "team" ? ["trade", "growth", "infra", "common"] : ["learning", "tools"];
  const currentCategory = preferredCategory || $("#resource-category").value || state.category;
  $("#resource-category").innerHTML = keys.map(key => `<option value="${key}" ${key === currentCategory ? "selected" : ""}>${categories[key]}</option>`).join("");
  const selectedEnv = $("#credential-env").value || "test";
  $("#credential-env").innerHTML = (type === "system" ? ["dev", "test", "prod"] : ["link"]).map(env => `<option value="${env}" ${env === selectedEnv ? "selected" : ""}>${environments[env].label}</option>`).join("");
}
function openEditor(resource) {
  const opened = presentDrawer(resource ? `编辑${resource.name}` : "添加一个新入口", resource ? "链接配置 / 编辑" : "链接配置 / 新增", editorMarkup(resource), { kind: "editor", id: resource?.id || null });
  if (!opened) { pendingDrawerAction = () => openEditor(resource); return; }
  updateEditorFields(resource?.category);
  const form = $("#resource-form");
  form.addEventListener("input", () => { state.dirty = true; });
  form.addEventListener("change", event => { state.dirty = true; if (["type", "scope"].includes(event.target.name)) updateEditorFields(); });
  form.addEventListener("submit", saveResource);
  $("#resource-name").focus();
}
function saveResource(event) {
  event.preventDefault();
  const form = event.currentTarget;
  if (!form.reportValidity()) return;
  const values = new FormData(form);
  const read = key => String(values.get(key) || "").trim();
  const existing = state.drawer?.id ? findResource(state.drawer.id) : null;
  const type = existing?.type || read("type");
  const scope = existing?.scope || read("scope");
  let newEndpoints;
  let pendingBindings = false;
  try {
    if (!read("name")) throw new Error("请填写链接名称。");
    newEndpoints = type === "bookmark" ? { link: read("bookmark_url") } : Object.fromEntries(["dev", "test", "prod"].map(env => [env, read(`endpoint_${env}`)]).filter(([, url]) => url));
    if (!Object.keys(newEndpoints).length || Object.values(newEndpoints).some(url => !url)) throw new Error("请至少填写一个完整链接地址。");
    for (const url of Object.values(newEndpoints)) {
      try { checkedUrl(url); } catch { throw new Error("请输入完整的 HTTP/HTTPS 地址，地址中不能包含账号密码。"); }
    }
    const hasCredential = read("credential_username") || read("credential_password") || read("credential_name");
    if (hasCredential && (!read("credential_username") || !read("credential_password"))) throw new Error("添加演示账号时，请同时填写用户名与密码。");
    if (hasCredential && !newEndpoints[read("credential_env")]) throw new Error("演示账号所属环境还没有链接，请先配置该环境地址。");
    const id = existing?.id || `custom-${state.nextId++}`;
    const next = { id, scope, type, name: read("name"), alias: read("alias") || (type === "system" ? "SYSTEM" : "BOOKMARK"), aliases: existing?.aliases || "", description: read("description"), category: read("category"), tags: read("tags").split(/[,，]/).map(tag => tag.trim()).filter(Boolean), icon: existing?.icon || (type === "system" ? "globe" : "book"), color: existing?.color || "green", owner: read("owner") || "林知夏", endpoints: newEndpoints, updated: new Date().toLocaleDateString("en-CA") };
    if (existing) {
      for (const [env, accounts] of Object.entries(demoAccounts[id] || {})) {
        if (!newEndpoints[env] || !existing.endpoints[env] || checkedUrl(existing.endpoints[env]).origin !== checkedUrl(newEndpoints[env]).origin) { accounts.forEach(account => { account.pending = true; }); pendingBindings ||= accounts.length > 0; }
      }
      Object.assign(existing, next);
    } else resources.push(next);
    if (hasCredential) {
      demoAccounts[id] ||= {};
      demoAccounts[id][read("credential_env")] ||= [];
      demoAccounts[id][read("credential_env")].push({ name: read("credential_name") || "演示共享账号", username: read("credential_username"), password: String(values.get("credential_password") || ""), note: "刚刚在界面稿中添加的演示账号，仅在当前页面有效。" });
    }
    state.dirty = false;
    state.view = scope === "personal" ? "personal" : "team";
    resetFilters();
    forceCloseDrawer();
    const card = $(`[data-resource-id="${id}"]`);
    $("button, a", card)?.focus();
    toast(pendingBindings ? "链接已更新；原域名的演示账号已暂停显示，需重新确认" : `${existing ? "修改" : "链接"}已保存到${scope === "personal" ? "个人空间" : "团队空间"}（本页演示）`);
  } catch (error) {
    $("#form-error").textContent = error.message;
    $("#form-error").hidden = false;
    $("#form-error").scrollIntoView({ block: "nearest", behavior: "auto" });
  }
}

function featureItem(name, description, iconName) {
  return `<div class="feature-item"><span>${icon(iconName)}</span><div><strong>${escapeHTML(name)}</strong><p>${escapeHTML(description)}</p></div></div>`;
}
function openInfo(kind) {
  const panels = {
    settings: { title: "空间设置", subtitle: "设计方案 / 后续实现", intro: "管理功能已纳入设计，当前界面稿展示其组织方式。下面的设置尚未连接正式服务。", items: [
      ["业务线与环境", "维护交易平台、用户增长等分类；环境可以增加、改名和排序。已有引用不能被直接删除。", "sliders"],
      ["成员与账号授权", "邀请部门成员，为业务维护人分配管理范围。链接编辑与账号读取分别授权。", "users"],
      ["导入与导出", "导入浏览器书签、CSV 或 JSON，先预览重复项和环境建议。普通导出不包含凭据。", "upload"],
      ["链接与账号维护", "汇总失效反馈、账号到期和负责人待办。自动检测区分超时、需登录与无法判断。", "key"],
      ["修改记录与回收站", "查看非敏感字段的变更，恢复 30 天内删除的资源；密码不进入普通修改历史。", "history"],
    ] },
    categories: { title: "业务线与环境", subtitle: "设计方案 / 分类配置", intro: "业务线组织系统，环境组织入口。两者各有自己的稳定标识，重命名不改变已有收藏。", items: [
      ["业务线", "默认示例：交易平台、用户增长、基础设施、公共工具。正式版支持页面内增删改与调整顺序。", "layout"],
      ["环境", "默认开发 DEV、测试 TEST、生产 PROD；正式版可以配置预发、灰度等自定义环境。", "globe"],
      ["归属与授权", "每个系统具有负责人和归属。删除分类前需要迁移其资源，环境停用不自动替换成其他入口。", "shield"],
    ] },
    guide: { title: "少一点寻找，多一点专注", subtitle: "栖点 / 设计说明", intro: "这份界面稿用虚构数据呈现团队与个人导航的工作方式。核心是把系统、环境与账号的关系说清楚。", items: [
      ["一个系统，多个明确入口", "开发、测试和生产聚合在一张卡片里，直接点击目标环境。普通书签单独整理。", "layout"],
      ["账号始终属于具体环境", "每份账号标明用途，用户名和密码分别复制。切换环境、关闭或离开页面都会隐藏已显示密码。", "key"],
      ["团队共享，个人独立", "共享资源可以收藏，个人空间与最近访问归本人。正式版本通过服务端权限实现隔离。", "folder-lock"],
      ["把配置留在页面上", "右上角添加链接，可以一次填写三套环境，也可以只添加一个普通书签。所有演示修改刷新后重置。", "edit"],
    ] },
    help: { title: "从这里顺手出发", subtitle: "使用说明 / 快捷键", intro: "界面稿支持搜索、筛选、收藏、账号复制和链接配置。全部操作使用当前页面内的演示数据。", items: [
      ["Ctrl / Cmd + K，或 /", "聚焦搜索框。试试“订单 测试”“OMS”“日志”或“dingdan”。密码不参与搜索。", "search"],
      ["Esc", "关闭当前面板；表单有未保存修改时，先选择继续编辑或放弃。", "layout"],
      ["星标与个人空间", "星标把资源加入我的收藏；个人空间里的书签在设计上仅本人可见。", "star"],
      ["示例链接与复制", ".example 地址展示目标预览。你新添的正常 HTTP/HTTPS 地址会在新标签页打开。复制失败可手动选择演示内容。", "external"],
    ] },
    feedback: { title: "账号不可用时，让维护人知道", subtitle: "设计方案 / 账号反馈", intro: "正式版会把反馈定位到当前系统、环境和账号，并通知对应维护人。原型尚不提交反馈。", items: [
      ["反馈问题", "选择登录失败、账号过期或权限不足，填写现象即可，无需在反馈中重复密码。", "info"],
      ["维护人处理", "负责人核实后更新账号或使用说明，并把处理结果通知反馈者。", "users"],
    ] },
  };
  const panel = panels[kind] || panels.guide;
  presentDrawer(panel.title, panel.subtitle, `<p class="drawer-intro">${escapeHTML(panel.intro)}</p><div class="feature-list">${panel.items.map(item => featureItem(...item)).join("")}</div>`, { kind: "info" });
}
function openMobileNav() {
  $("#sidebar").classList.add("mobile-open");
  $("#sidebar").setAttribute("role", "dialog");
  $("#sidebar").setAttribute("aria-modal", "true");
  $("#sidebar-scrim").hidden = false;
  $("#menu-toggle").setAttribute("aria-expanded", "true");
  $(".main-shell").inert = true;
  document.body.style.overflow = "hidden";
  $("#close-mobile-nav").focus();
}
function closeMobileNav() {
  const wasOpen = $("#sidebar").classList.contains("mobile-open");
  $("#sidebar").classList.remove("mobile-open");
  $("#sidebar").removeAttribute("role");
  $("#sidebar").removeAttribute("aria-modal");
  $("#sidebar-scrim").hidden = true;
  $("#menu-toggle").setAttribute("aria-expanded", "false");
  $(".main-shell").inert = false;
  if (wasOpen) { document.body.style.overflow = ""; $("#menu-toggle").focus(); }
}

document.addEventListener("click", event => {
  const action = event.target.closest("[data-action]");
  if (action) {
    const resource = action.dataset.id ? findResource(action.dataset.id) : null;
    switch (action.dataset.action) {
      case "favorite": {
        if (!resource) return;
        const wasSaved = state.favorites.has(resource.id);
        wasSaved ? state.favorites.delete(resource.id) : state.favorites.add(resource.id);
        render();
        $(`[data-action="favorite"][data-id="${resource.id}"]`)?.focus();
        toast(wasSaved ? "已从我的收藏移除" : "已添加到我的收藏");
        break;
      }
      case "open": {
        if (!resource?.endpoints[action.dataset.env]) { event.preventDefault(); return; }
        const env = action.dataset.env;
        const url = checkedUrl(resource.endpoints[env]);
        recordVisit(resource, env);
        if (url.hostname === "example" || url.hostname.endsWith(".example")) { event.preventDefault(); openDestination(resource, env); }
        break;
      }
      case "details": if (resource) openDetails(resource, action.dataset.env); break;
      case "edit": if (resource) openEditor(resource); break;
      case "switch-env": if (resource) { openDetails(resource, action.dataset.env); $(`[data-action="switch-env"][data-env="${action.dataset.env}"]`)?.focus(); } break;
      case "reveal": revealPassword(Number(action.dataset.index)); break;
      case "copy": void copyCredential(Number(action.dataset.index), action.dataset.field); break;
      case "feedback": openInfo("feedback"); break;
      case "close-drawer": requestCloseDrawer(); break;
    }
    return;
  }
  const nav = event.target.closest("[data-view]");
  if (nav) { changeView(nav.dataset.view); return; }
  const category = event.target.closest("[data-category]");
  if (category) { state.category = state.category === category.dataset.category ? "all" : category.dataset.category; render(); closeMobileNav(); $(`[data-category="${category.dataset.category}"]`)?.focus(); return; }
  const env = event.target.closest("#environment-filter [data-env]");
  if (env) { state.env = env.dataset.env; render(); return; }
  const layout = event.target.closest("[data-layout]");
  if (layout) { state.layout = layout.dataset.layout; render(); }
});
$("#search-form").addEventListener("submit", event => event.preventDefault());
$("#search").addEventListener("input", event => { state.search = event.target.value; render(); });
$("#clear-search").addEventListener("click", () => { state.search = ""; $("#search").value = ""; render(); $("#search").focus(); });
$("#reset-filters").addEventListener("click", resetFilters);
$("#sort").addEventListener("change", event => { state.sort = event.target.value; render(); });
$("#empty-action").addEventListener("click", () => { if (state.category !== "all" || state.env !== "all" || state.search) resetFilters(); else changeView("team"); });
$("#add-resource").addEventListener("click", () => openEditor());
$("#close-drawer").addEventListener("click", requestCloseDrawer);
$("#drawer").addEventListener("cancel", event => { event.preventDefault(); requestCloseDrawer(); });
$("#drawer").addEventListener("click", event => { if (event.target !== $("#drawer")) return; const bounds = $("#drawer").getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) requestCloseDrawer(); });
$("#keep-editing").addEventListener("click", () => { $("#confirm-dialog").close(); pendingDrawerAction = null; });
$("#discard-changes").addEventListener("click", () => { $("#confirm-dialog").close(); state.dirty = false; const action = pendingDrawerAction; pendingDrawerAction = null; action?.(); });
$("#confirm-dialog").addEventListener("cancel", () => { pendingDrawerAction = null; });
$("#settings-button").addEventListener("click", () => openInfo("settings"));
$("#manage-categories").addEventListener("click", () => openInfo("categories"));
$("#guide-button").addEventListener("click", () => openInfo("guide"));
$("#help-button").addEventListener("click", () => openInfo("help"));
$("#menu-toggle").addEventListener("click", openMobileNav);
$("#close-mobile-nav").addEventListener("click", closeMobileNav);
$("#sidebar-scrim").addEventListener("click", closeMobileNav);
$(".brand").addEventListener("click", event => { event.preventDefault(); changeView("team"); });
$("#theme-toggle").addEventListener("click", () => {
  const dark = document.documentElement.dataset.theme !== "dark";
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  $("#theme-toggle").innerHTML = icon(dark ? "sun" : "moon");
  $("#theme-toggle").setAttribute("aria-label", dark ? "切换浅色主题" : "切换深色主题");
});
document.addEventListener("keydown", event => {
  const drawerOpen = $("#drawer").open || $("#confirm-dialog").open;
  const navOpen = $("#sidebar").classList.contains("mobile-open");
  if (navOpen && event.key === "Escape") { event.preventDefault(); closeMobileNav(); return; }
  if (navOpen && event.key === "Tab") {
    const focusable = $$('a[href], button:not(:disabled)', $("#sidebar")).filter(node => node.getClientRects().length);
    const first = focusable[0], last = focusable.at(-1);
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    return;
  }
  if (drawerOpen || navOpen) return;
  const editing = /INPUT|TEXTAREA|SELECT/.test(event.target.tagName) || event.target.isContentEditable;
  if (((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") || (event.key === "/" && !editing)) { event.preventDefault(); $("#search").focus(); }
  if (event.key === "Escape" && document.activeElement === $("#search")) { state.search = ""; $("#search").value = ""; render(); }
});
window.addEventListener("blur", clearSecrets);
document.addEventListener("visibilitychange", () => { if (document.hidden) clearSecrets(); });
window.addEventListener("resize", () => { if (window.innerWidth > 960 && $("#sidebar").classList.contains("mobile-open")) closeMobileNav(); });
if (/Mac|iPhone|iPad/.test(navigator.platform)) $("#search-key").textContent = "⌘ K";
hydrateIcons();
render();
