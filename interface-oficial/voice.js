// Loaded only by the local BrowserAudioBridge. The static preview never imports it.
const PCM_RATE = 48000;
const READY_TIMEOUT_MS = 10000;
const CLEANUP_TIMEOUT_MS = 5000;
const MAX_BUFFERED_BYTES = PCM_RATE * Float32Array.BYTES_PER_ELEMENT * 2;
const AudioContextClass = window.AudioContext || window.webkitAudioContext;
const available = Boolean(AudioContextClass && navigator.mediaDevices?.getUserMedia && window.WebSocket);
let session = null;
let cleanup = null;
let disposed = false;
let status = {
  state: available ? 'idle' : 'error',
  label: available ? 'Microfone desligado' : 'Microfone indisponível',
  caption: available
    ? 'Ative o microfone para falar com o Jarvis neste computador. O provedor configurado no aplicativo pode processar o áudio online.'
    : 'Este navegador não oferece os recursos de áudio necessários. Nenhuma captura foi iniciada.',
  active: false,
  available,
};

export function getVoiceState() { return { ...status }; }

function setStatus(state, label, caption) {
  status = { state, label, caption, active: Boolean(session), available };
  renderControls();
  window.dispatchEvent(new CustomEvent('jarvis:voice', { detail: getVoiceState() }));
}

function makeButton(label, action, className = 'button button-secondary') {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = className;
  button.dataset[action] = '';
  button.textContent = label;
  return button;
}

function renderControls() {
  const app = document.getElementById('app');
  if (!app || disposed) return;
  app.dataset.voice = 'local';
  let liveStatus = document.getElementById('voice-status');
  if (!liveStatus) {
    liveStatus = document.createElement('p');
    liveStatus.id = 'voice-status';
    liveStatus.className = 'visually-hidden';
    liveStatus.setAttribute('role', 'status');
    liveStatus.setAttribute('aria-live', 'polite');
    app.append(liveStatus);
  }
  liveStatus.dataset.state = status.state;
  liveStatus.textContent = `${status.label}. ${status.caption}`;
  const badge = document.querySelector('.service-badge');
  if (badge) {
    const led = document.createElement('i');
    led.setAttribute('aria-hidden', 'true');
    badge.replaceChildren(led, document.createTextNode('Ponte de voz local'));
    badge.title = 'Somente voz local. DUX, Excel e GGO não estão conectados.';
  }
  const connection = document.querySelector('.connection-control');
  if (connection) {
    connection.setAttribute('aria-label', `Ponte de voz local: ${status.label}`);
    connection.title = 'Status da ponte de voz local';
  }
  const headerVoice = document.querySelector('.voice-control');
  if (headerVoice) headerVoice.title = status.label;
  const footerStatus = document.querySelector('.app-footer > span:last-child');
  if (footerStatus) {
    const led = footerStatus.querySelector('.footer-led') || document.createElement('span');
    led.className = 'footer-led';
    led.setAttribute('aria-hidden', 'true');
    footerStatus.replaceChildren(document.createTextNode(`VOZ LOCAL · ${status.label.toLocaleUpperCase('pt-BR')} `), led);
  }
  const headerTools = document.querySelector('.header-tools');
  let headerStop = document.getElementById('voice-stop-header');
  if (session && headerTools && !headerStop) {
    headerStop = makeButton('Parar microfone', 'voiceStop', 'chrome-control voice-stop-header');
    headerStop.id = 'voice-stop-header';
    headerStop.setAttribute('aria-label', 'Parar microfone');
    headerStop.textContent = '■';
    headerStop.title = 'Encerrar captura de áudio';
    headerTools.prepend(headerStop);
  } else if (!session && headerStop) headerStop.remove();

  const oldMic = document.querySelector('.microphone-zone .mic-button');
  if (oldMic) {
    const mic = oldMic.tagName === 'BUTTON' ? oldMic : document.createElement('button');
    if (mic !== oldMic) {
      mic.type = 'button';
      mic.className = oldMic.className;
      mic.replaceChildren(...Array.from(oldMic.childNodes));
      oldMic.replaceWith(mic);
    }
    delete mic.dataset.voiceStart;
    delete mic.dataset.voiceStop;
    mic.dataset[session ? 'voiceStop' : 'voiceStart'] = '';
    mic.disabled = !available || Boolean(cleanup);
    mic.setAttribute('aria-label', session ? 'Parar microfone' : 'Ativar microfone');
    mic.setAttribute('aria-describedby', 'voice-status');
    const actionLabel = mic.querySelector('.mic-action');
    if (actionLabel) actionLabel.textContent = session ? 'Parar microfone' : 'Ativar microfone';
  }
  const micStatus = document.querySelector('.mic-status');
  if (micStatus) micStatus.textContent = status.label;

  for (const row of document.querySelectorAll('.settings-panel .setting-row')) {
    if (row.querySelector('strong')?.textContent !== 'Microfone') continue;
    row.querySelector('p').textContent = `${status.label}. ${status.caption}`;
    let actions = row.querySelector('.voice-actions');
    if (!actions) {
      actions = document.createElement('div');
      actions.className = 'voice-actions';
      actions.append(makeButton('Ativar microfone', 'voiceStart'), makeButton('Parar microfone', 'voiceStop'));
      row.append(actions);
    }
    const start = actions.querySelector('[data-voice-start]');
    start.disabled = !available || Boolean(session) || Boolean(cleanup);
    const stop = actions.querySelector('[data-voice-stop]');
    stop.disabled = !session;
  }
  const preview = document.querySelector('.state-preview');
  if (preview) {
    preview.querySelector('.eyebrow').textContent = 'VOZ LOCAL';
    preview.querySelector('h2').textContent = 'Estado da captura';
    preview.querySelector('.card-description').textContent = 'O círculo acompanha a conexão e o microfone reais. Os estados simulados estão desativados neste modo.';
    preview.querySelectorAll('[data-state-choice]').forEach((button) => {
      button.disabled = true;
      button.title = 'No modo de voz, o estado reflete a captura real.';
    });
  }
}

function isCurrent(target) { return session === target && !target.cancelled; }

function release(target) {
  if (!target) return Promise.resolve();
  if (target.cancelled) return target.released || Promise.resolve();
  target.cancelled = true;
  const pending = [];
  clearTimeout(target.readyTimer);
  if (target.processor) target.processor.onaudioprocess = null;
  for (const [track, handler] of target.trackHandlers || []) track.removeEventListener('ended', handler);
  target.stream?.getTracks().forEach((track) => track.stop());
  for (const node of [target.source, target.processor, target.gain]) {
    try { node?.disconnect(); } catch { /* Already disconnected. */ }
  }
  if (target.context) {
    target.context.onstatechange = null;
    if (target.context.state !== 'closed') {
      try { pending.push(Promise.resolve(target.context.close())); }
      catch (error) { pending.push(Promise.reject(error)); }
    }
  }
  if (target.socket) {
    target.socket.onopen = null;
    target.socket.onmessage = null;
    target.socket.onerror = null;
    target.socket.onclose = null;
    if (target.socket.readyState !== WebSocket.CLOSED) {
      pending.push(new Promise((resolve, reject) => {
        const closed = () => resolve();
        target.socket.addEventListener('close', closed, { once: true });
        try { target.socket.close(); }
        catch (error) {
          target.socket.removeEventListener('close', closed);
          reject(error);
        }
      }));
    }
  }
  target.released = Promise.all(pending);
  return target.released;
}

function endSession(target, state, label, caption) {
  if (!isCurrent(target)) return;
  session = null;
  const closing = { failed: false };
  cleanup = closing;
  setStatus('idle', 'Encerrando microfone', 'Aguarde a liberação do dispositivo e da conexão local.');
  const failed = () => {
    if (cleanup !== closing || disposed) return;
    closing.failed = true;
    setStatus('error', 'Falha ao encerrar microfone', 'Atualize esta página antes de ativar o microfone novamente.');
  };
  const timeout = setTimeout(failed, CLEANUP_TIMEOUT_MS);
  release(target).then(() => {
    clearTimeout(timeout);
    if (cleanup !== closing || closing.failed || disposed) return;
    cleanup = null;
    setStatus(state, label, caption);
  }, () => {
    clearTimeout(timeout);
    failed();
  });
}

function reflectCapture(target) {
  if (!isCurrent(target) || !target.ready) return;
  if (target.muted) {
    setStatus('idle', 'Microfone pausado', 'A ponte local está silenciada. Nenhum áudio é enviado enquanto o silêncio estiver ativo.');
  } else if (target.context.state !== 'running') {
    setStatus('idle', 'Captura suspensa', 'O navegador suspendeu o áudio. Pare o microfone e ative novamente para retomar.');
  } else {
    setStatus('listening', 'Ouvindo', 'Áudio entregue ao Jarvis neste computador. O provedor configurado no aplicativo pode processá-lo online.');
  }
}

export async function startVoice() {
  if (disposed || session || cleanup || !available) return;
  const target = { cancelled: false, ready: false, muted: true, trackHandlers: [] };
  session = target;
  setStatus('idle', 'Preparando microfone', 'Aguardando sua permissão e a conexão com a ponte local.');
  try {
    target.context = new AudioContextClass({ sampleRate: PCM_RATE });
    if (target.context.sampleRate !== PCM_RATE) throw new Error('sample-rate');
    const resume = Promise.resolve(target.context.resume()).then(() => null, (error) => error);
    // Called directly from the explicit button activation, never on page load.
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, sampleRate: PCM_RATE, echoCancellation: true, noiseSuppression: true, autoGainControl: true }, video: false,
    });
    if (!isCurrent(target)) { stream.getTracks().forEach((track) => track.stop()); return; }
    target.stream = stream;
    const resumeError = await resume;
    if (!isCurrent(target)) return;
    if (resumeError) throw resumeError;
    if (target.context.state !== 'running') throw new Error('audio-suspended');
    for (const track of stream.getTracks()) {
      const handler = () => endSession(target, 'error', 'Microfone interrompido', 'O dispositivo de áudio foi encerrado. Nenhum áudio está sendo enviado.');
      track.addEventListener('ended', handler);
      target.trackHandlers.push([track, handler]);
    }
    target.source = target.context.createMediaStreamSource(stream);
    target.processor = target.context.createScriptProcessor(4096, 1, 1);
    target.gain = target.context.createGain();
    target.gain.gain.value = 0;
    target.source.connect(target.processor);
    target.processor.connect(target.gain);
    target.gain.connect(target.context.destination);
    const endpoint = new URL('/jarvis-audio', window.location.href);
    endpoint.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    target.socket = new WebSocket(endpoint.href);
    target.socket.binaryType = 'arraybuffer';
    target.processor.onaudioprocess = (event) => {
      if (!isCurrent(target) || !target.ready || target.muted || target.context.state !== 'running'
        || target.socket.readyState !== WebSocket.OPEN) return;
      if (target.socket.bufferedAmount > MAX_BUFFERED_BYTES) {
        endSession(target, 'error', 'Ponte de voz lenta', 'A captura foi encerrada para evitar acumular áudio. Ative novamente quando a ponte estiver disponível.');
        return;
      }
      const channel = event.inputBuffer.getChannelData(0);
      target.socket.send(new Float32Array(channel).buffer);
    };
    target.context.onstatechange = () => reflectCapture(target);
    target.socket.onmessage = (event) => {
      if (!isCurrent(target) || typeof event.data !== 'string') return;
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      if (message?.type === 'ready' && typeof message.muted === 'boolean' && !target.ready) {
        clearTimeout(target.readyTimer);
        target.ready = true;
        target.muted = message.muted;
        reflectCapture(target);
      } else if (message?.type === 'muted' && typeof message.value === 'boolean' && target.ready) {
        target.muted = message.value;
        reflectCapture(target);
      } else if (message?.type === 'error') {
        endSession(target, 'error', 'Falha na ponte de voz', 'A ponte local interrompeu a captura. Nenhum áudio está sendo enviado.');
      }
    };
    target.socket.onerror = () => endSession(target, 'error', 'Ponte de voz indisponível', 'Não foi possível conectar à ponte local. O microfone foi desligado.');
    target.socket.onclose = () => endSession(target, 'disconnected', 'Ponte desconectada', 'A conexão local foi encerrada. O microfone foi desligado; não há reconexão automática.');
    target.readyTimer = setTimeout(() => endSession(target, 'error', 'Ponte sem resposta', 'A ponte local não confirmou a captura. O microfone foi desligado.'), READY_TIMEOUT_MS);
    setStatus('idle', 'Conectando ponte local', 'O microfone está aberto, mas nenhum áudio será enviado antes da confirmação da ponte.');
  } catch (error) {
    if (!isCurrent(target)) return;
    const denied = error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError';
    const sampleRate = error?.message === 'sample-rate';
    endSession(target, 'error', denied ? 'Permissão do microfone negada' : sampleRate ? 'Áudio incompatível' : 'Falha ao ativar microfone',
      denied ? 'Autorize o microfone no navegador e clique em Ativar microfone para tentar novamente.'
        : sampleRate ? 'A ponte exige áudio mono a 48 kHz. Este navegador abriu outra frequência; nenhuma captura foi enviada.'
          : 'A captura foi encerrada. Confira o dispositivo e a ponte local antes de tentar novamente.');
  }
}

export function stopVoice() {
  const target = session;
  if (target) {
    endSession(target, 'idle', 'Microfone desligado', 'Captura encerrada. O botão Mudo da janela de voz mantém sua configuração.');
  } else if (!cleanup && !disposed) {
    setStatus('idle', 'Microfone desligado', 'Captura encerrada. O botão Mudo da janela de voz mantém sua configuração.');
  }
}

function onClick(event) {
  if (event.target.closest('[data-voice-start]')) { event.preventDefault(); void startVoice(); }
  else if (event.target.closest('[data-voice-stop]')) { event.preventDefault(); stopVoice(); }
  else if (event.target.closest('.connection-control')) {
    event.preventDefault();
    event.stopImmediatePropagation();
    window.location.hash = 'configuracoes';
  }
}
function onRender() {
  renderControls();
  window.dispatchEvent(new CustomEvent('jarvis:voice', { detail: getVoiceState() }));
}
function onPageHide() { stopVoice(); }

export function disposeVoice() {
  stopVoice();
  disposed = true;
  document.removeEventListener('click', onClick, true);
  window.removeEventListener('jarvis:render', onRender);
  window.removeEventListener('pagehide', onPageHide);
}

document.addEventListener('click', onClick, true);
window.addEventListener('jarvis:render', onRender);
window.addEventListener('pagehide', onPageHide);
onRender();
