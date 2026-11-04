import test from 'node:test';
import assert from 'node:assert/strict';
import {
  ROUTES,
  STATES,
  routeFromHash,
  stateFromValue,
  getScreenTitle,
} from '../interface-oficial/core.js';

const destinations = {
  home: 'JARVIS',
  ggo: 'GGO',
  automacao: 'Automação',
  indicadores: 'Indicadores',
  relatorios: 'Relatórios',
  agenda: 'Agenda',
  configuracoes: 'Configurações',
};

test('a navegação oferece a home e os seis destinos da interface aprovada', () => {
  assert.deepEqual(new Set(ROUTES), new Set(Object.keys(destinations)));
  for (const [route, title] of Object.entries(destinations)) {
    assert.equal(routeFromHash(`#${route}`), route);
    assert.equal(getScreenTitle(route), title);
  }
});

test('hashes desconhecidos ou vazios voltam à home sem aceitar uma rota arbitrária', () => {
  for (const hash of ['', '#', '#inexistente', '#__proto__', '#constructor', '#<script>', null, undefined]) {
    assert.equal(routeFromHash(hash), 'home', `hash: ${String(hash)}`);
  }
});

test('os seis estados visuais podem ser selecionados explicitamente', () => {
  const expected = ['idle', 'listening', 'processing', 'responding', 'error', 'disconnected'];
  assert.deepEqual(new Set(STATES), new Set(expected));
  for (const state of expected) assert.equal(stateFromValue(state), state);
});

test('um estado desconhecido não simula conexão, áudio ou processamento', () => {
  for (const state of ['', 'connected', 'running-ggo', '__proto__', null, undefined]) {
    assert.equal(stateFromValue(state), 'idle', `estado: ${String(state)}`);
  }
});

test('títulos desconhecidos usam JARVIS como fallback', () => {
  assert.equal(getScreenTitle('inexistente'), 'JARVIS');
});
