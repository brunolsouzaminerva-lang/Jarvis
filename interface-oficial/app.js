import { STATES, STATE_DETAILS, routeFromHash, stateFromValue, getScreenTitle } from './core.js';

// Camada de interface isolada: sem serviços, microfone, arquivos ou persistência.
const app = document.getElementById('app');
const root = document.getElementById('view-root');
const dialog = document.getElementById('feature-dialog');
const paths = {
  ggo: ['M4 3v17h17', 'M9 15v-4m5 4V6m5 9v-6'],
  automacao: ['m13 2-9 12h7l-1 8 10-13h-8Z'],
  indicadores: ['M3 17 9 11l4 4 8-10', 'M15 5h6v6'],
  relatorios: ['M6 3h8l4 4v14H6Z', 'M14 3v5h4M9 12h6m-6 4h6'],
  agenda: ['M8 3v4m8-4v4M3 10h18', 'M5 5h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2'],
  configuracoes: ['m9 3-1 3-3 1 1 4-1 4 3 1 1 3h6l1-3 3-1-1-4 1-4-3-1-1-3Z', 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6'],
  microphone: ['M9 5a3 3 0 0 1 6 0v6a3 3 0 0 1-6 0Z', 'M6 10v1a6 6 0 0 0 12 0v-1m-6 7v5m-4 0h8'],
  home: ['m3 11 9-8 9 8', 'M5 10v11h14V10M9 21v-7h6v7'],
  arrow: ['M5 12h14m-6-6 6 6-6 6'],
  shield: ['m12 2 8 3v6c0 5-8 11-8 11S4 16 4 11V5Z', 'm8 11 3 3 5-6'],
  check: ['m5 12 4 4L19 6'],
};
let visualState = 'idle';

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function icon(name, className = 'icon') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('class', className);
  svg.setAttribute('aria-hidden', 'true');
  for (const value of paths[name] || paths.arrow) {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', value);
    svg.append(path);
  }
  return svg;
}

function navButton(label, route, name = route) {
  const link = element('a', 'tile-button');
  link.href = `#${route}`;
  link.dataset.routeLink = route;
  const symbol = element('span', 'tile-icon');
  symbol.append(icon(name));
  link.append(symbol, element('span', 'tile-label', label), icon('arrow', 'icon tile-arrow'));
  return link;
}

function featureButton(label, feature = label) {
  const button = element('button', 'button button-secondary', label);
  button.type = 'button';
  button.dataset.unconfigured = feature;
  button.append(icon('arrow'));
  return button;
}

function heading(title, kicker, description) {
  const wrap = element('div', 'module-heading');
  if (kicker) wrap.append(element('p', 'eyebrow', kicker));
  const titleNode = element('h1', '', title);
  titleNode.tabIndex = -1;
  wrap.append(titleNode);
  if (description) wrap.append(element('p', 'module-description', description));
  return wrap;
}

function reactor() {
  const stage = element('div', 'reactor-stage');
  const top = element('div', 'reactor-topline');
  top.append(element('span', '', 'JARVIS CORE'), element('span', '', 'INTERFACE / 01'));
  const sphere = element('div', 'reactor');
  sphere.id = 'reactor';
  sphere.dataset.state = visualState;
  sphere.setAttribute('role', 'img');
  sphere.setAttribute('aria-label', `Reator JARVIS — ${STATE_DETAILS[visualState].label}`);
  for (const className of ['reactor-aura', 'reactor-orbit orbit-outer', 'reactor-orbit orbit-inner']) {
    sphere.append(element('div', className));
  }
  const shell = element('div', 'reactor-shell');
  sphere.append(shell, element('div', 'reactor-rim'), element('div', 'reactor-orb'),
    element('span', 'reactor-glint'), element('span', 'reactor-core'), element('span', 'reactor-mark'));
  const readout = element('div', 'reactor-readout');
  const label = element('p', 'reactor-status', STATE_DETAILS[visualState].label);
  label.id = 'reactor-status';
  label.setAttribute('role', 'status');
  label.setAttribute('aria-live', 'polite');
  const caption = element('p', 'state-caption', STATE_DETAILS[visualState].caption);
  caption.id = 'state-caption';
  readout.append(label, caption);
  stage.append(top, sphere, readout);
  return stage;
}

function microphone() {
  const wrap = element('div', 'microphone-zone');
  const link = element('a', 'mic-button');
  link.href = '#configuracoes';
  link.setAttribute('aria-label', 'Configurar microfone');
  link.append(icon('microphone'));
  wrap.append(link, element('strong', 'mic-label', 'Seu comando começa aqui.'),
    element('span', 'mic-status', 'Microfone não configurado'));
  return wrap;
}

function homeScreen() {
  const screen = element('section', 'home-screen');
  const title = element('div', 'home-heading');
  title.append(element('p', 'home-kicker', 'SEU ASSISTENTE PESSOAL'));
  const mainTitle = element('h1', '', 'JARVIS');
  mainTitle.tabIndex = -1;
  title.append(mainTitle, element('p', 'home-description', 'Uma nova forma de estar no controle.'));
  const actions = element('nav', 'home-actions');
  actions.setAttribute('aria-label', 'Áreas do Jarvis');
  for (const [label, route] of [['GGO', 'ggo'], ['Automação', 'automacao'], ['Indicadores', 'indicadores'],
    ['Relatórios', 'relatorios'], ['Agenda', 'agenda'], ['Configurações', 'configuracoes']]) {
    actions.append(navButton(label, route));
  }
  screen.append(title, reactor(), actions, microphone());
  return screen;
}

function sidebar() {
  const side = element('aside', 'ggo-sidebar');
  side.setAttribute('aria-label', 'Menu do painel GGO');
  side.append(element('p', 'eyebrow', 'ÁREA DE TRABALHO'), element('strong', 'ggo-sidebar-title', 'GGO'));
  const nav = element('nav', 'ggo-navigation');
  for (const [label, route, symbol] of [['Início', 'home', 'home'], ['Painel GGO', 'ggo', 'ggo'],
    ['Relatórios', 'relatorios', 'relatorios'], ['Configurações', 'configuracoes', 'configuracoes']]) {
    const link = element('a', 'ggo-nav');
    link.href = `#${route}`;
    link.append(icon(symbol), element('span', '', label));
    if (route === 'ggo') link.setAttribute('aria-current', 'page');
    nav.append(link);
  }
  const note = element('div', 'sidebar-note');
  note.append(icon('shield'), element('strong', '', 'Ambiente isolado'),
    element('p', '', 'Automação corporativa preservada. Nenhum serviço conectado.'));
  side.append(nav, note);
  return side;
}

function statusCard(label, value, description) {
  const card = element('article', 'status-card');
  card.append(element('p', 'status-label', label), element('strong', 'status-value', value),
    element('span', 'status-description', description));
  return card;
}

function ggoScreen() {
  const screen = element('section', 'ggo-layout');
  const main = element('div', 'ggo-main');
  const intro = heading('GGO', 'CENTRAL DE OPERAÇÕES', 'Engenharia e Controladoria em um mesmo espaço.');
  intro.classList.add('ggo-titlebar');
  const overview = element('div', 'ggo-overview');
  const copy = element('div', 'ggo-copy');
  copy.append(element('p', 'eyebrow', 'PRÓXIMO CICLO'), element('h2', '', 'Tudo começa com uma visão clara.'),
    element('p', '', 'Prepare o fluxo, confira as informações e acompanhe cada etapa. A integração operacional ainda não está configurada.'));
  overview.append(copy, reactor());
  const cards = element('div', 'ggo-grid');
  cards.append(statusCard('DUX', 'Não configurado', 'Sem conexão com o aplicativo.'),
    statusCard('Excel', 'Não configurado', 'Nenhuma planilha aberta.'),
    statusCard('Etapa 201', 'Pendente', 'Validação operacional necessária.'));
  const operations = element('div', 'ggo-bottom-grid');
  const quick = element('article', 'quick-actions');
  quick.append(element('p', 'eyebrow', 'SEU FLUXO'), element('h2', '', 'Execução rápida'),
    element('p', 'card-description', 'As ações dependem de uma integração autorizada.'));
  const actionRow = element('div', 'quick-buttons');
  actionRow.append(featureButton('Engenharia'), featureButton('Controladoria'));
  quick.append(actionRow);
  const reports = element('article', 'report-card');
  reports.append(element('p', 'eyebrow', 'ACOMPANHAMENTO'), element('h2', '', 'Relatórios'),
    element('p', 'card-description', 'Não configurado. Nenhum relatório corporativo está disponível.'),
    featureButton('Atualizar relatórios', 'Relatórios GGO'));
  operations.append(quick, reports);
  main.append(intro, overview, cards, operations);
  screen.append(sidebar(), main);
  return screen;
}

function settingsScreen() {
  const screen = element('section', 'module-screen settings-screen');
  screen.append(heading('Configurações', 'SEU JARVIS', 'Uma interface preparada para evoluir com você.'));
  const layout = element('div', 'settings-layout');
  const panel = element('article', 'settings-panel');
  panel.append(icon('configuracoes', 'icon feature-symbol'), element('h2', '', 'Serviços e preferências'));
  for (const [label, description] of [['Microfone', 'Não configurado. Este protótipo não solicita acesso ao microfone.'],
    ['Automação', 'Não configurado. Nenhum fluxo operacional está conectado.'],
    ['DUX e Excel', 'Não configurado. A integração exige o ambiente corporativo autorizado.']]) {
    const row = element('div', 'setting-row');
    row.append(element('strong', '', label), element('p', '', description));
    panel.append(row);
  }
  const note = element('p', 'settings-note', 'A preferência de movimento reduzido do sistema é respeitada automaticamente.');
  panel.append(note);
  const preview = element('article', 'state-preview');
  preview.append(element('p', 'eyebrow', 'SOMENTE VISUAL'), element('h2', '', 'Prévia dos estados'),
    element('p', 'card-description', 'Explore as animações. Nenhuma escuta, resposta de voz ou operação real será iniciada.'), reactor());
  const buttons = element('div', 'state-buttons');
  buttons.setAttribute('role', 'group');
  buttons.setAttribute('aria-label', 'Escolher estado visual');
  for (const state of STATES) {
    const button = element('button', 'state-button', STATE_DETAILS[state].label);
    button.type = 'button';
    button.dataset.stateChoice = state;
    button.setAttribute('aria-pressed', String(state === visualState));
    buttons.append(button);
  }
  preview.append(buttons);
  layout.append(panel, preview);
  screen.append(layout);
  return screen;
}

function moduleScreen(route) {
  const name = getScreenTitle(route);
  const descriptions = {
    automacao: 'Seus próximos fluxos, em um só lugar.',
    indicadores: 'Uma visão clara dos números que importam.',
    relatorios: 'Informações organizadas para cada decisão.',
    agenda: 'Espaço para os seus próximos compromissos.',
  };
  const screen = element('section', 'module-screen');
  screen.append(heading(name, 'ÁREA DE TRABALHO', descriptions[route]));
  const card = element('article', 'empty-card');
  const symbol = element('span', 'empty-icon');
  symbol.append(icon(route));
  card.append(symbol, element('span', 'outline-label', 'NÃO CONFIGURADO'),
    element('h2', '', 'Seu próximo espaço de trabalho.'),
    element('p', '', `${name} ainda não tem um serviço conectado. Nenhum dado corporativo é acessado por esta interface.`),
    featureButton('Ver configuração necessária', name));
  const back = element('a', 'back-link', 'Voltar ao início');
  back.href = '#home';
  screen.append(card, back);
  return screen;
}

function updateState(value) {
  visualState = stateFromValue(value);
  const sphere = document.getElementById('reactor');
  if (!sphere) return;
  sphere.dataset.state = visualState;
  sphere.setAttribute('aria-label', `Reator JARVIS — ${STATE_DETAILS[visualState].label}`);
  document.getElementById('reactor-status').textContent = STATE_DETAILS[visualState].label;
  document.getElementById('state-caption').textContent = STATE_DETAILS[visualState].caption;
  document.querySelectorAll('[data-state-choice]').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.stateChoice === visualState));
  });
}

function render(focus = true) {
  const route = routeFromHash(window.location.hash);
  if (dialog.open) dialog.close();
  visualState = 'idle';
  app.dataset.route = route;
  document.getElementById('nav-current').textContent = getScreenTitle(route);
  document.title = route === 'home' ? 'JARVIS' : `${getScreenTitle(route)} · JARVIS`;
  const screen = route === 'home' ? homeScreen() : route === 'ggo' ? ggoScreen()
    : route === 'configuracoes' ? settingsScreen() : moduleScreen(route);
  root.replaceChildren(screen);
  if (focus) {
    screen.querySelector('h1').focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
}

root.addEventListener('click', (event) => {
  const choice = event.target.closest('[data-state-choice]');
  if (choice) { updateState(choice.dataset.stateChoice); return; }
  const unavailable = event.target.closest('[data-unconfigured]');
  if (!unavailable) return;
  document.getElementById('feature-title').textContent = 'Não configurado';
  document.getElementById('feature-message').textContent = `${unavailable.dataset.unconfigured} depende de uma integração autorizada. Esta interface não executa ações no DUX, Excel, GGO ou em outros serviços.`;
  dialog.showModal();
});
document.querySelector('.skip-link').addEventListener('click', (event) => {
  event.preventDefault();
  document.getElementById('main').focus();
});
document.getElementById('feature-close').addEventListener('click', () => dialog.close());
window.addEventListener('hashchange', () => render());

const clockFormat = new Intl.DateTimeFormat('pt-BR', {
  timeZone: 'America/Sao_Paulo', hour: '2-digit', minute: '2-digit', hour12: false,
});
let clockTimer;
function updateClock() {
  const now = new Date();
  const clock = document.getElementById('clock-label');
  clock.textContent = `${clockFormat.format(now)} · Brasília`;
  clock.setAttribute('datetime', now.toISOString());
}
function updateVisibility() {
  clearInterval(clockTimer);
  app.classList.toggle('is-paused', document.hidden);
  if (!document.hidden) {
    updateClock();
    clockTimer = setInterval(updateClock, 60000);
  }
}
document.addEventListener('visibilitychange', updateVisibility);
updateVisibility();
render(false);
