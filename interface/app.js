(() => {
  'use strict';

  // Demonstração local: nenhuma integração, persistência ou acesso à rede.
  const byId = (id) => document.getElementById(id);
  const viewTitles = {
    overview: 'Visão geral',
    engineering: 'Engenharia',
    controllership: 'Controladoria',
    history: 'Histórico',
  };
  const navigation = [...document.querySelectorAll('.nav-item[data-view]')];
  const panels = [...document.querySelectorAll('section[data-panel]')];
  const simulationButtons = [
    byId('simulate-button'),
    byId('engineering-simulate'),
    byId('controllership-simulate'),
  ];
  const periodButtons = [byId('period-open'), byId('period-open-secondary')];
  const dialog = byId('period-dialog');
  const startInput = byId('start-date');
  const endInput = byId('end-date');
  const periodError = byId('period-error');
  const reactor = byId('reactor');
  const cancelButton = byId('simulation-cancel');
  const toast = byId('toast');
  const timeFormatter = new Intl.DateTimeFormat('pt-BR', {
    timeZone: 'America/Sao_Paulo',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });

  let period = { start: '2026-10-01', end: '2026-10-31' };
  let events = [];
  let running = false;
  let simulationTimer = null;
  let toastTimer = null;
  let runId = 0;

  function parseDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!match) return null;
    const [, yearText, monthText, dayText] = match;
    const year = Number(yearText);
    const month = Number(monthText);
    const day = Number(dayText);
    const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    const monthDays = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    if (year < 1 || month < 1 || month > 12 || day < 1 || day > monthDays[month - 1]) {
      return null;
    }
    return { iso: value, label: `${dayText}/${monthText}/${yearText}` };
  }

  function periodLabel() {
    return `${parseDate(period.start).label} – ${parseDate(period.end).label}`;
  }

  function updatePeriodLabels() {
    const label = periodLabel();
    byId('period-display').textContent = label;
    document.querySelectorAll('[data-period-label]').forEach((element) => {
      element.textContent = label;
    });
  }

  function notify(message) {
    window.clearTimeout(toastTimer);
    toast.textContent = message;
    toast.classList.add('visible');
    toastTimer = window.setTimeout(() => toast.classList.remove('visible'), 4000);
  }

  function navigate(view, focus = true) {
    if (!Object.hasOwn(viewTitles, view)) return;
    panels.forEach((panel) => { panel.hidden = panel.dataset.panel !== view; });
    navigation.forEach((button) => {
      const active = button.dataset.view === view;
      button.classList.toggle('is-active', active);
      button.classList.toggle('active', active);
      if (active) button.setAttribute('aria-current', 'page');
      else button.removeAttribute('aria-current');
    });
    byId('page-title').textContent = viewTitles[view];
    if (focus) {
      const heading = panels.find((panel) => panel.dataset.panel === view).querySelector('h1');
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
      window.scrollTo(0, 0);
    }
  }

  function renderEvents() {
    const activity = byId('activity-list');
    const history = byId('history-body');
    activity.replaceChildren();
    history.replaceChildren();
    byId('history-empty').hidden = events.length > 0;

    if (events.length === 0) {
      const empty = document.createElement('li');
      empty.className = 'activity-empty';
      empty.textContent = 'Nenhum evento nesta sessão de demonstração.';
      activity.append(empty);
      return;
    }

    events.slice(0, 5).forEach((event) => {
      const item = document.createElement('li');
      item.className = 'activity-item';
      const dot = document.createElement('span');
      dot.className = 'activity-dot';
      dot.setAttribute('aria-hidden', 'true');
      const copy = document.createElement('div');
      copy.className = 'activity-copy';
      const message = document.createElement('p');
      message.textContent = event.message;
      const time = document.createElement('span');
      time.className = 'activity-time';
      time.textContent = `${event.time} · Simulação`;
      copy.append(message, time);
      item.append(dot, copy);
      activity.append(item);
    });

    events.forEach((event) => {
      const row = document.createElement('tr');
      [event.time, event.message, event.period].forEach((value) => {
        const cell = document.createElement('td');
        cell.textContent = value;
        row.append(cell);
      });
      const statusCell = document.createElement('td');
      const status = document.createElement('span');
      status.className = 'history-status';
      status.textContent = 'Simulado';
      statusCell.append(status);
      row.append(statusCell);
      history.append(row);
    });
  }

  function record(message) {
    events.unshift({ time: timeFormatter.format(new Date()), message, period: periodLabel() });
    events = events.slice(0, 100);
    renderEvents();
  }

  function setProgress(value) {
    byId('progress-bar').style.width = `${value}%`;
    const progress = byId('cycle-progress');
    progress.setAttribute('aria-valuenow', String(value));
    progress.setAttribute('aria-valuetext', `Simulação: ${value}%`);
  }

  function setRunning(value) {
    running = value;
    reactor.classList.toggle('is-running', value);
    simulationButtons.forEach((button) => { button.disabled = value; });
    periodButtons.forEach((button) => { button.disabled = value; });
    cancelButton.hidden = !value;
  }

  function simulate() {
    if (running) return;
    navigate('overview');
    const currentRun = ++runId;
    setRunning(true);
    setProgress(0);
    byId('reactor-status').textContent = 'Simulação em andamento';
    byId('execution-status').textContent = 'Iniciando demonstração com dados fictícios…';
    record('Simulação iniciada com dados de exemplo.');

    const steps = [
      'Simulação: período conferido.',
      'Simulação: Engenharia conferida.',
      'Simulação: Controladoria conferida.',
    ];
    let step = 0;
    const advance = () => {
      if (!running || currentRun !== runId) return;
      const message = steps[step];
      step += 1;
      setProgress(Math.round((step / steps.length) * 100));
      byId('execution-status').textContent = message;
      record(message);
      if (step < steps.length) {
        simulationTimer = window.setTimeout(advance, 800);
        return;
      }
      simulationTimer = null;
      setRunning(false);
      byId('reactor-status').textContent = 'Simulação concluída';
      byId('execution-status').textContent = 'Demonstração concluída';
      record('Simulação concluída. Nenhum arquivo alterado.');
      notify('Simulação concluída. Nenhum sistema real foi alterado.');
    };
    simulationTimer = window.setTimeout(advance, 800);
  }

  function clearPeriodError() {
    periodError.textContent = '';
    startInput.removeAttribute('aria-invalid');
    endInput.removeAttribute('aria-invalid');
  }

  function openPeriodDialog() {
    if (running || dialog.open) return;
    startInput.value = period.start;
    endInput.value = period.end;
    clearPeriodError();
    dialog.showModal();
    startInput.focus();
  }

  navigation.forEach((button) => {
    button.addEventListener('click', () => navigate(button.dataset.view));
  });
  document.querySelectorAll('[data-go-view]').forEach((button) => {
    button.addEventListener('click', () => navigate(button.dataset.goView));
  });
  simulationButtons.forEach((button) => button.addEventListener('click', simulate));
  periodButtons.forEach((button) => button.addEventListener('click', openPeriodDialog));

  cancelButton.addEventListener('click', () => {
    if (!running) return;
    window.clearTimeout(simulationTimer);
    simulationTimer = null;
    runId += 1;
    setRunning(false);
    setProgress(0);
    byId('reactor-status').textContent = 'Simulação cancelada';
    byId('execution-status').textContent = 'Demonstração cancelada';
    record('Simulação cancelada. Nenhum arquivo alterado.');
    notify('Simulação cancelada. Nenhum sistema real foi alterado.');
    byId('simulate-button').focus({ preventScroll: true });
  });

  byId('period-cancel').addEventListener('click', (event) => {
    event.preventDefault();
    clearPeriodError();
    dialog.close();
  });
  dialog.addEventListener('cancel', clearPeriodError);
  startInput.addEventListener('input', clearPeriodError);
  endInput.addEventListener('input', clearPeriodError);

  byId('period-form').addEventListener('submit', (event) => {
    event.preventDefault();
    clearPeriodError();
    const start = parseDate(startInput.value);
    const end = parseDate(endInput.value);
    if (!start || !end) {
      periodError.textContent = 'Informe uma data inicial e uma data final válidas.';
      const invalid = !start ? startInput : endInput;
      invalid.setAttribute('aria-invalid', 'true');
      invalid.focus();
      return;
    }
    if (start.iso > end.iso) {
      periodError.textContent = 'A data final deve ser igual ou posterior à data inicial.';
      endInput.setAttribute('aria-invalid', 'true');
      endInput.focus();
      return;
    }
    if (running) {
      periodError.textContent = 'Aguarde ou cancele a simulação antes de alterar o período.';
      return;
    }
    period = { start: start.iso, end: end.iso };
    updatePeriodLabels();
    dialog.close();
    record(`Período de demonstração atualizado: ${periodLabel()}.`);
    notify('Período da demonstração atualizado. Nenhuma data foi alterada no DUX.');
  });

  byId('clear-history').addEventListener('click', () => {
    events = [];
    renderEvents();
    notify('Histórico desta sessão de demonstração limpo.');
  });

  function updateClock() {
    const now = new Date();
    byId('clock-label').textContent = `${timeFormatter.format(now)} · Brasília`;
    byId('clock-label').dateTime = now.toISOString();
  }

  updateClock();
  window.setInterval(updateClock, 1000);
  navigate('overview', false);
  updatePeriodLabels();
  setProgress(0);
  setRunning(false);
  byId('reactor-status').textContent = 'Em espera';
  byId('execution-status').textContent = 'Aguardando simulação';
  record('Demonstração iniciada. Pronto para explorar.');
})();
