import { test, expect } from '@playwright/test';

const destinations = {
  ggo: 'GGO',
  automacao: 'Automação',
  indicadores: 'Indicadores',
  relatorios: 'Relatórios',
  agenda: 'Agenda',
  configuracoes: 'Configurações',
};
const states = ['idle', 'listening', 'processing', 'responding', 'error', 'disconnected'];

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

test('home apresenta JARVIS, o reator central e os seis botões de navegação', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'home');
  await expect(page.getByRole('heading', { level: 1, name: 'JARVIS', exact: true })).toBeVisible();
  await expect(page.locator('#reactor')).toHaveAttribute('data-state', 'idle');
  for (const route of Object.keys(destinations)) {
    await expect(page.locator(`a[href="#${route}"]:visible`).first()).toBeVisible();
  }
  await expect(page.getByRole('link', { name: 'Configurar microfone', exact: true })).toBeVisible();
});

test('todos os botões da home abrem uma tela real com o título correto', async ({ page }) => {
  for (const [route, title] of Object.entries(destinations)) {
    await page.goto('/');
    await page.locator(`a[href="#${route}"]:visible`).first().click();
    await expect(page.locator('#app')).toHaveAttribute('data-route', route);
    await expect(page.getByRole('heading', { level: 1, name: title, exact: true })).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`#${route}$`));
  }
});

test('hash direto, voltar e avançar preservam a navegação entre telas', async ({ page }) => {
  await page.goto('/#ggo');
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'ggo');
  await page.locator('a[href="#configuracoes"]:visible').first().click();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'configuracoes');
  await page.goBack();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'ggo');
  await page.goForward();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'configuracoes');
});

test('uma rota desconhecida apresenta a home de forma segura', async ({ page }) => {
  await page.goto('/#rota-inexistente');
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'home');
  await expect(page.getByRole('heading', { level: 1, name: 'JARVIS', exact: true })).toBeVisible();
});

test('teclado aciona a navegação e recebe foco no conteúdo de destino', async ({ page }) => {
  await page.goto('/');
  const ggo = page.locator('a[href="#ggo"]:visible').first();
  await ggo.focus();
  await page.keyboard.press('Enter');
  const heading = page.getByRole('heading', { level: 1, name: 'GGO', exact: true });
  await expect(heading).toBeVisible();
  await expect(heading).toBeFocused();
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
  await page.getByRole('link', { name: 'Configurar microfone', exact: true }).click();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'configuracoes');
  await expect(page.getByText(/não configurado/i).first()).toBeVisible();
  expect(await page.evaluate(() => window.jarvisAudioCalls)).toBe(0);
});

test('ações operacionais ausentes mostram Não configurado e o diálogo devolve o foco', async ({ page }) => {
  await page.goto('/#ggo');
  const action = page.locator('[data-unconfigured]:visible').first();
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
    for (const route of ['home', ...Object.keys(destinations)]) {
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
  await page.locator('a[href="#ggo"]:visible').first().click();
  await expect(page.locator('#app')).toHaveAttribute('data-route', 'ggo');
  await page.locator('a[href="#configuracoes"]:visible').first().click();
  await page.locator('[data-state-choice="processing"]').click();
  await expect(page.locator('#reactor')).toHaveAttribute('data-state', 'processing');
});
