export const ROUTES = Object.freeze([
  'home', 'ggo', 'automacao', 'indicadores', 'relatorios', 'agenda', 'configuracoes',
]);

export const STATES = Object.freeze([
  'idle', 'listening', 'processing', 'responding', 'error', 'disconnected',
]);

export const SCREEN_TITLES = Object.freeze({
  home: 'JARVIS',
  ggo: 'GGO',
  automacao: 'Automação',
  indicadores: 'Indicadores',
  relatorios: 'Relatórios',
  agenda: 'Agenda',
  configuracoes: 'Configurações',
});

export const STATE_DETAILS = Object.freeze({
  idle: Object.freeze({ label: 'Em espera', caption: 'Nenhum serviço conectado.' }),
  listening: Object.freeze({ label: 'Ouvindo', caption: 'Prévia visual de escuta. O microfone permanece desligado.' }),
  processing: Object.freeze({ label: 'Processando', caption: 'Prévia visual. Nenhuma operação está sendo executada.' }),
  responding: Object.freeze({ label: 'Respondendo', caption: 'Prévia visual. Nenhuma resposta de voz está sendo reproduzida.' }),
  error: Object.freeze({ label: 'Erro', caption: 'Prévia visual do estado de erro. Nenhum sistema foi acionado.' }),
  disconnected: Object.freeze({ label: 'Desconectado', caption: 'Prévia visual. As integrações permanecem não configuradas.' }),
});

export function routeFromHash(hash) {
  if (typeof hash !== 'string') return 'home';
  const route = hash.replace(/^#\/?/, '');
  return ROUTES.includes(route) ? route : 'home';
}

export function stateFromValue(value) {
  return STATES.includes(value) ? value : 'idle';
}

export function getScreenTitle(route) {
  return SCREEN_TITLES[ROUTES.includes(route) ? route : 'home'];
}
