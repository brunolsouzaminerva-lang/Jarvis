import { test, expect } from '@playwright/test';

// These doubles never open a microphone, audio device or network connection.
async function installVoiceDoubles(page, options = {}) {
  await page.addInitScript(({ permission = 'granted', sampleRate = 48000 }) => {
    const state = {
      permissionCalls: 0,
      constraints: [],
      trackStops: 0,
      contexts: [],
      processors: [],
      sockets: [],
    };
    const track = Object.assign(new EventTarget(), {
      kind: 'audio',
      readyState: 'live',
      stop() {
        if (this.readyState !== 'ended') state.trackStops += 1;
        this.readyState = 'ended';
      },
    });
    const stream = { getTracks: () => [track], getAudioTracks: () => [track] };
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        async getUserMedia(constraints) {
          state.permissionCalls += 1;
          state.constraints.push(constraints);
          if (permission === 'denied') throw new DOMException('Permissão sintética recusada', 'NotAllowedError');
          return stream;
        },
      },
    });

    function audioNode(extra = {}) {
      return {
        connectCalls: 0,
        disconnectCalls: 0,
        connect() { this.connectCalls += 1; return this; },
        disconnect() { this.disconnectCalls += 1; },
        ...extra,
      };
    }

    class FakeAudioContext {
      constructor() {
        this.sampleRate = sampleRate;
        this.state = 'suspended';
        this.closeCalls = 0;
        this.destination = audioNode();
        state.contexts.push(this);
      }
      async resume() { this.state = 'running'; }
      async close() { this.closeCalls += 1; this.state = 'closed'; }
      createMediaStreamSource() { this.source = audioNode(); return this.source; }
      createGain() { return audioNode({ gain: { value: 1 } }); }
      createScriptProcessor() {
        const processor = audioNode({ onaudioprocess: null });
        state.processors.push(processor);
        return processor;
      }
    }
    window.AudioContext = FakeAudioContext;
    window.webkitAudioContext = FakeAudioContext;

    class FakeWebSocket extends EventTarget {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSING = 2;
      static CLOSED = 3;
      constructor(url) {
        super();
        this.url = String(url);
        this.readyState = FakeWebSocket.CONNECTING;
        this.bufferedAmount = 0;
        this.sent = [];
        this.closeCalls = 0;
        state.sockets.push(this);
      }
      emit(type, event) {
        this.dispatchEvent(event);
        this[`on${type}`]?.(event);
      }
      send(value) {
        if (this.readyState !== FakeWebSocket.OPEN) throw new DOMException('Socket sintético fechado', 'InvalidStateError');
        if (typeof value === 'string') this.sent.push({ kind: 'text', value });
        else {
          const bytes = value instanceof ArrayBuffer
            ? value.slice(0)
            : value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength);
          this.sent.push({ kind: 'binary', values: [...new Float32Array(bytes)], byteLength: bytes.byteLength });
        }
      }
      close() {
        this.closeCalls += 1;
        if (this.readyState === FakeWebSocket.CLOSED) return;
        this.readyState = FakeWebSocket.CLOSED;
        this.emit('close', new CloseEvent('close', { code: 1000 }));
      }
    }
    Object.assign(FakeWebSocket.prototype, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
    window.WebSocket = FakeWebSocket;

    window.voiceHarness = {
      snapshot() {
        return {
          permissionCalls: state.permissionCalls,
          constraints: state.constraints,
          trackStops: state.trackStops,
          contexts: state.contexts.map((context) => ({ state: context.state, closeCalls: context.closeCalls })),
          sockets: state.sockets.map((socket) => ({
            url: socket.url, readyState: socket.readyState, closeCalls: socket.closeCalls, sent: socket.sent,
          })),
        };
      },
      open() {
        const socket = state.sockets.at(-1);
        if (!socket) throw new Error('Nenhum WebSocket criado');
        socket.readyState = FakeWebSocket.OPEN;
        socket.emit('open', new Event('open'));
      },
      message(value) {
        state.sockets.at(-1).emit('message', new MessageEvent('message', { data: JSON.stringify(value) }));
      },
      serverClose() {
        const socket = state.sockets.at(-1);
        socket.readyState = FakeWebSocket.CLOSED;
        socket.emit('close', new CloseEvent('close', { code: 1006 }));
      },
      frame(values = [0.25, -0.5, 0, 1]) {
        const data = Float32Array.from(values);
        for (const processor of state.processors) {
          processor.onaudioprocess?.({ inputBuffer: { getChannelData: () => data } });
        }
      },
    };
  }, options);
}

async function loadVoice(page, options) {
  await installVoiceDoubles(page, options);
  await page.goto('/');
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'home');
  await page.evaluate(() => import('/voice.js'));
  await expect(page.locator('[data-voice-start]').first()).toBeVisible();
}

const snapshot = (page) => page.evaluate(() => window.voiceHarness.snapshot());

async function openSocket(page) {
  await expect.poll(async () => (await snapshot(page)).sockets.length).toBe(1);
  await page.evaluate(() => window.voiceHarness.open());
}

async function ready(page) {
  await openSocket(page);
  await page.evaluate(() => window.voiceHarness.message({ type: 'ready', muted: false }));
}

test.beforeEach(async ({ page }) => {
  page.voiceErrors = [];
  page.voiceExternalRequests = [];
  page.on('pageerror', (error) => page.voiceErrors.push(error.message));
  page.on('request', (request) => {
    if (!['127.0.0.1', 'localhost'].includes(new URL(request.url()).hostname)) {
      page.voiceExternalRequests.push(request.url());
    }
  });
});

test.afterEach(async ({ page }) => {
  expect(page.voiceErrors, 'A integração de voz não deve produzir erros JavaScript').toEqual([]);
  expect(page.voiceExternalRequests, 'Os testes sintéticos não devem chamar serviços externos').toEqual([]);
});

test('carregar a ponte opcional não solicita permissão nem inicia captura automaticamente', async ({ page }) => {
  await loadVoice(page);
  await expect(page.locator('#voice-status')).toHaveAttribute('role', 'status');
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'idle');
  await expect(page.locator('#voice-status')).toContainText('Microfone desligado');
  await expect(page.locator('.service-badge')).toContainText('Ponte de voz local');
  expect(await snapshot(page)).toMatchObject({ permissionCalls: 0, trackStops: 0, contexts: [], sockets: [] });
});

test('clique explícito aguarda ready antes de indicar escuta e transmitir Float32', async ({ page }) => {
  await loadVoice(page);
  await page.locator('[data-voice-start]').first().click();
  await openSocket(page);
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'idle');
  await expect(page.locator('#voice-status')).not.toContainText('Ouvindo');
  await page.evaluate(() => window.voiceHarness.frame());
  const pending = await snapshot(page);
  expect(pending.permissionCalls).toBe(1);
  expect(pending.sockets[0].url).toBe('ws://127.0.0.1:8790/jarvis-audio');
  expect(pending.sockets[0].sent).toEqual([]);

  await page.evaluate(() => window.voiceHarness.message({ type: 'ready', muted: false }));
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'listening');
  await expect(page.locator('#voice-status')).toContainText('Ouvindo');
  await expect(page.locator('#reactor')).toHaveAttribute('data-state', 'listening');
  await page.evaluate(() => window.voiceHarness.frame([0.25, -0.5, 0, 1]));
  expect((await snapshot(page)).sockets[0].sent).toEqual([
    { kind: 'binary', values: [0.25, -0.5, 0, 1], byteLength: 16 },
  ]);
});

test('estado muted descarta áudio até a ponte autorizar a escuta', async ({ page }) => {
  await loadVoice(page);
  await page.locator('[data-voice-start]').first().click();
  await openSocket(page);
  await page.evaluate(() => {
    window.voiceHarness.message({ type: 'ready', muted: true });
    window.voiceHarness.frame();
  });
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'idle');
  await expect(page.locator('#voice-status')).toContainText('Microfone pausado');
  expect((await snapshot(page)).sockets[0].sent).toEqual([]);

  await page.evaluate(() => window.voiceHarness.message({ type: 'muted', value: false }));
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'listening');
  await page.evaluate(() => {
    window.voiceHarness.frame();
    window.voiceHarness.message({ type: 'muted', value: true });
    window.voiceHarness.frame();
  });
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'idle');
  expect((await snapshot(page)).sockets[0].sent).toHaveLength(1);
});

test('permissão recusada apresenta erro sem fingir escuta nem deixar recursos ativos', async ({ page }) => {
  await loadVoice(page, { permission: 'denied' });
  await page.locator('[data-voice-start]').first().click();
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'error');
  await expect(page.locator('#voice-status')).not.toContainText('Ouvindo');
  await expect(page.locator('#reactor')).toHaveAttribute('data-state', 'error');
  const result = await snapshot(page);
  expect(result.permissionCalls).toBe(1);
  expect(result.trackStops).toBe(0);
  expect(result.contexts.every((context) => context.state === 'closed')).toBe(true);
  expect(result.sockets.every((socket) => socket.readyState === 3)).toBe(true);
  await expect(page.locator('[data-voice-start]').first()).toBeEnabled();
});

test('parar libera a trilha, o WebSocket e o AudioContext e impede novos envios', async ({ page }) => {
  await loadVoice(page);
  await page.locator('[data-voice-start]').first().click();
  await ready(page);
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'listening');
  await page.evaluate(() => window.voiceHarness.frame());
  await page.locator('[data-voice-stop]').first().click();
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'idle');
  await expect(page.locator('#voice-status')).toContainText('Microfone desligado');
  await page.evaluate(() => window.voiceHarness.frame());
  const result = await snapshot(page);
  expect(result.trackStops).toBe(1);
  expect(result.contexts).toEqual([{ state: 'closed', closeCalls: 1 }]);
  expect(result.sockets[0]).toMatchObject({ readyState: 3, closeCalls: 1 });
  expect(result.sockets[0].sent).toHaveLength(1);
  await expect(page.locator('[data-voice-start]').first()).toBeEnabled();
});

test('navegação conserva a sessão e o controle de parada sem confundir prévia com escuta', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await loadVoice(page);
  await page.locator('[data-voice-start]').first().click();
  await ready(page);
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'listening');
  await page.locator('.primary-ggo').click();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'ggo');
  await expect(page.locator('#reactor')).toHaveAttribute('data-state', 'listening');
  await page.locator('.ggo-navigation a[href="#configuracoes"]').click();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'configuracoes');
  await expect(page.locator('[data-state-choice]')).toHaveCount(6);
  for (const button of await page.locator('[data-state-choice]').all()) await expect(button).toBeDisabled();
  // Even a stale dispatched preview event must not replace the live status.
  await page.locator('[data-state-choice="error"]').dispatchEvent('click');
  await expect(page.locator('#reactor')).toHaveAttribute('data-state', 'listening');
  await expect(page.locator('#reactor-status')).toContainText('Ouvindo');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const result = await snapshot(page);
  expect(result.permissionCalls).toBe(1);
  expect(result.sockets).toHaveLength(1);

  await page.locator('#areas-menu summary').click();
  await page.locator('#areas-menu a[href="#agenda"]').click();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'agenda');
  await expect(page.locator('[data-voice-stop]').first()).toBeVisible();
  await page.locator('[data-voice-stop]').first().click();
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'idle');
  expect((await snapshot(page)).trackStops).toBe(1);
});

test('queda do WebSocket informa desconexão e encerra a captura', async ({ page }) => {
  await loadVoice(page);
  await page.locator('[data-voice-start]').first().click();
  await ready(page);
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'listening');
  await page.evaluate(() => window.voiceHarness.serverClose());
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'disconnected');
  await expect(page.locator('#voice-status')).toContainText('Ponte desconectada');
  await expect(page.locator('#reactor')).toHaveAttribute('data-state', 'disconnected');
  await page.evaluate(() => window.voiceHarness.frame());
  const result = await snapshot(page);
  expect(result.trackStops).toBe(1);
  expect(result.contexts).toEqual([{ state: 'closed', closeCalls: 1 }]);
  expect(result.sockets[0].sent).toEqual([]);
  await expect(page.locator('[data-voice-start]').first()).toBeEnabled();
});

test('taxa de amostragem incompatível falha de forma explícita e libera a captura', async ({ page }) => {
  await loadVoice(page, { sampleRate: 44100 });
  await page.locator('[data-voice-start]').first().click();
  await expect(page.locator('#voice-status')).toHaveAttribute('data-state', 'error');
  await expect(page.locator('#voice-status')).not.toContainText('Ouvindo');
  await expect(page.locator('#reactor')).toHaveAttribute('data-state', 'error');
  const result = await snapshot(page);
  expect(result.permissionCalls).toBe(0);
  expect(result.trackStops).toBe(0);
  expect(result.contexts).toEqual([{ state: 'closed', closeCalls: 1 }]);
  expect(result.sockets.every((socket) => socket.readyState === 3 && socket.sent.length === 0)).toBe(true);
});
