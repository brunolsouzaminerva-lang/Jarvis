import { test, expect } from '@playwright/test';

const destinations = {
  agentes: 'Agentes',
  automacao: 'Automação',
  indicadores: 'Indicadores',
  relatorios: 'Relatórios',
  agenda: 'Agenda',
  configuracoes: 'Configurações',
};
const states = ['idle', 'listening', 'processing', 'responding', 'error', 'disconnected'];

async function openAreasMenu(page) {
  const menu = page.locator('#areas-menu');
  if (!(await menu.evaluate((details) => details.open))) {
    await menu.locator('summary').click();
  }
  await expect(menu).toHaveJSProperty('open', true);
  return menu;
}

async function selectArea(page, route) {
  const menu = await openAreasMenu(page);
  await menu.locator(`a[href="#${route}"]`).click();
}

test.beforeEach(async ({ page }) => {
  page.jarvisErrors = [];
  page.jarvisExternalRequests = [];
  page.on('pageerror', (error) => page.jarvisErrors.push(error.message));
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) {
      page.jarvisExternalRequests.push(request.url());
    }
  });
});

test.afterEach(async ({ page }) => {
  expect(page.jarvisErrors, 'Erros JavaScript na interface').toEqual([]);
  expect(page.jarvisExternalRequests, 'A interface isolada não deve chamar serviços externos').toEqual([]);
});

test('home apresenta JARVIS, o reator central e os seis destinos no menu de áreas', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'home');
  await expect(page.getByRole('heading', { level: 1, name: 'JARVIS', exact: true })).toHaveText('JARVIS');
  await expect(page.locator('.brand-wordmark')).toBeVisible();
  await expect(page.locator('.brand-wordmark')).toHaveText('JARVIS');
  await expect(page.locator('#reactor')).toHaveAttribute('data-state', 'idle');
  const menu = await openAreasMenu(page);
  for (const route of Object.keys(destinations)) {
    await expect(menu.locator(`a[href="#${route}"]`)).toBeVisible();
  }
  await expect(page.getByRole('link', { name: 'Configurar microfone', exact: true })).toBeVisible();
});

test('todos os destinos do menu de áreas abrem uma tela real com o título correto', async ({ page }) => {
  for (const [route, title] of Object.entries(destinations)) {
    await page.goto('/');
    await selectArea(page, route);
    await expect(page.locator('#app')).toHaveAttribute('data-route', route);
    await expect(page.getByRole('heading', { level: 1, name: title, exact: true })).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`#${route}$`));
  }
});

test('hash direto, voltar e avançar preservam a navegação entre telas', async ({ page }) => {
  await page.goto('/#ggo');
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'ggo');
  await selectArea(page, 'configuracoes');
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'configuracoes');
  await page.goBack();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'ggo');
  await page.goForward();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'configuracoes');
});

test('uma rota desconhecida apresenta a home de forma segura', async ({ page }) => {
  await page.goto('/#rota-inexistente');
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'home');
  await expect(page.getByRole('heading', { level: 1, name: 'JARVIS', exact: true })).toHaveText('JARVIS');
  await expect(page.locator('.brand-wordmark')).toBeVisible();
});

test('teclado aciona a navegação e recebe foco no conteúdo de destino', async ({ page }) => {
  await page.goto('/');
  const summary = page.locator('#areas-menu summary');
  await summary.focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#areas-menu')).toHaveJSProperty('open', true);
  const agents = page.locator('#areas-menu a[href="#agentes"]');
  await agents.focus();
  await page.keyboard.press('Enter');
  const heading = page.getByRole('heading', { level: 1, name: 'Agentes', exact: true });
  await expect(heading).toBeVisible();
  await expect(heading).toBeFocused();
});

test('Jarvis abre o catálogo de agentes e GGO permanece dentro dele', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle('JARVIS');
  const primary = page.locator('.primary-agents');
  await expect(primary).toHaveAttribute('href', '#agentes');
  await expect(primary).toHaveText('Agentes');
  await expect(page.locator('#areas-menu a[href="#ggo"]')).toHaveCount(0);
  await primary.click();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'agentes');
  await expect(page.getByRole('heading', { level: 1, name: 'Agentes', exact: true })).toBeFocused();
  await expect(page.locator('.agent-card')).toHaveCount(1);
  await expect(page.locator('.agent-card')).toContainText('Integração não configurada');
  await page.locator('.agent-card a[href="#ggo"]').click();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'ggo');
  await expect(page.getByRole('heading', { level: 1, name: 'GGO', exact: true })).toBeVisible();
  await expect(page).toHaveTitle('JARVIS');
  await expect(page.locator('.ggo-sidebar .sidebar-note')).toContainText('Nenhum serviço conectado');
});

test('Escape fecha o menu de áreas e devolve o foco ao acionador', async ({ page }) => {
  await page.goto('/');
  const menu = await openAreasMenu(page);
  const summary = menu.locator('summary');
  await menu.locator('a[href="#agenda"]').focus();
  await page.keyboard.press('Escape');
  await expect(menu).toHaveJSProperty('open', false);
  await expect(summary).toBeFocused();
});

test('status de conexão fecha o menu e informa que não há integração configurada', async ({ page }) => {
  await page.goto('/');
  const menu = await openAreasMenu(page);
  const status = page.getByRole('button', { name: 'Status de conexão: não configurado', exact: true });
  await status.click();
  await expect(menu).toHaveJSProperty('open', false);
  await expect(page.locator('#feature-dialog')).toBeVisible();
  await expect(page.locator('#feature-dialog')).toContainText('Não configurado');
  await page.keyboard.press('Escape');
  await expect(page.locator('#feature-dialog')).not.toBeVisible();
  await expect(status).toBeFocused();
});

test('atalho de conteúdo preserva a seção atual e move o foco para o conteúdo', async ({ page }) => {
  await page.goto('/#relatorios');
  await page.locator('.skip-link').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'relatorios');
  await expect(page).toHaveURL(/#relatorios$/);
  await expect(page.locator('#main')).toBeFocused();
});

test('os seis estados são prévias visuais explícitas, não estado operacional presumido', async ({ page }) => {
  await page.goto('/#configuracoes');
  await expect(page.getByText(/prévia/i).first()).toBeVisible();
  for (const state of states) {
    await page.locator(`[data-state-choice="${state}"]`).click();
    await expect(page.locator('#reactor')).toHaveAttribute('data-state', state);
    await expect(page.locator('#reactor-status')).toHaveAttribute('role', 'status');
    await expect(page.locator('#reactor-status')).not.toBeEmpty();
  }
});

test('microfone abre a configuração sem solicitar áudio nem iniciar reconhecimento', async ({ page }) => {
  await page.addInitScript(() => {
    window.jarvisAudioCalls = 0;
    const rejectAudio = () => {
      window.jarvisAudioCalls += 1;
      return Promise.reject(new Error('Áudio não deve ser iniciado no protótipo'));
    };
    if (navigator.mediaDevices) navigator.mediaDevices.getUserMedia = rejectAudio;
    else Object.defineProperty(navigator, 'mediaDevices', { value: { getUserMedia: rejectAudio } });
    const rejectRecognition = function () {
      window.jarvisAudioCalls += 1;
      throw new Error('Reconhecimento não deve ser iniciado no protótipo');
    };
    window.SpeechRecognition = rejectRecognition;
    window.webkitSpeechRecognition = rejectRecognition;
  });
  await page.goto('/');
  const microphone = page.getByRole('link', { name: 'Configurar microfone', exact: true });
  await expect(microphone).toHaveCount(1);
  await microphone.click();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'configuracoes');
  await expect(page.getByText(/não configurado/i).first()).toBeVisible();
  expect(await page.evaluate(() => window.jarvisAudioCalls)).toBe(0);
});

test('ações operacionais ausentes mostram Não configurado e o diálogo devolve o foco', async ({ page }) => {
  await page.goto('/#ggo');
  const action = page.locator('.ggo-layout [data-unconfigured]:visible').first();
  await action.click();
  const dialog = page.locator('#feature-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText(/não configurado/i);
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(action).toBeFocused();
});

test('todas as telas cabem em viewport móvel sem transbordamento da página', async ({ page }) => {
  for (const width of [320, 360, 390, 768]) {
    await page.setViewportSize({ width, height: 844 });
    for (const route of ['home', 'ggo', ...Object.keys(destinations)]) {
      await page.goto(`/#${route}`);
      await expect(page.locator('#app')).toHaveAttribute('data-route', route);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
        `${route} em ${width}px`).toBe(true);
    }
  }
});

test('preferência por movimento reduzido interrompe as animações do reator', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.locator('#reactor')).toBeVisible();
  await expect.poll(() => page.locator('#reactor').evaluate((reactor) => (
    reactor.getAnimations({ subtree: true }).filter((animation) => animation.playState === 'running').length
  ))).toBe(0);
});

test('navegação e prévias permanecem funcionais sem rede após carregar a interface', async ({ page, context }) => {
  await page.goto('/');
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'home');
  await context.setOffline(true);
  await page.locator('.primary-agents').click();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'agentes');
  await page.locator('.agent-card a[href="#ggo"]').click();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'ggo');
  await selectArea(page, 'configuracoes');
  await page.locator('[data-state-choice="processing"]').click();
  await expect(page.locator('#reactor')).toHaveAttribute('data-state', 'processing');
});
