import { test, expect, type Page, type TestInfo } from '@playwright/test'

const origin = 'http://127.0.0.1:4179'
const password = 'qa-only-admin-password-20260915'

async function api(page: Page, path: string, method = 'GET', body?: unknown) {
  const me = await (await page.request.get('/api/v1/me')).json()
  const response = await page.request.fetch(`/api/v1${path}`, {
    method,
    headers: {
      Origin: origin,
      'X-CSRF-Token': me.csrf_token,
      ...(me.workspace ? { 'X-Workspace-ID': me.workspace.id } : {}),
    },
    data: body,
  })
  expect(response.ok(), await response.text()).toBeTruthy()
  return response.status() === 204 ? null : response.json()
}

async function evidence(info: TestInfo, data: unknown) {
  await info.attach('observed-behavior', {
    body: JSON.stringify(data, null, 2),
    contentType: 'application/json',
  })
}

test.beforeAll(async ({ request }) => {
  const status = await (await request.get('/api/v1/setup/status')).json()
  if (!status.needs_setup) return
  const result = await request.post('/api/v1/setup', {
    headers: { Origin: origin },
    data: {
      username: 'qa_admin',
      display_name: 'QA测试管理员',
      password,
      workspace_name: 'QA隔离测试空间',
      public_enabled: true,
      token: 'e2e-only-install-token-not-a-real-secret',
    },
  })
  expect(result.status(), await result.text()).toBe(201)
})

test.beforeEach(async ({ page }) => {
  await page.goto('/#/login')
  await page.getByLabel('用户名', { exact: true }).fill('qa_admin')
  await page.getByLabel('密码', { exact: true }).fill(password)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '每个入口，都井然有序。' })).toBeVisible()
})

test('opening a system title retains the selected production environment', async ({ page }, info) => {
  const catalog = await api(page, '/catalog')
  const environments = catalog.environments.filter((row: { scope: string }) => row.scope === 'team')
  const production = environments.find((row: { key: string }) => row.key === 'prod')
  await api(page, '/resources', 'POST', {
    scope: 'team',
    type: 'system',
    name: 'QA环境定位系统',
    endpoints: environments.map((row: { id: string; key: string }) => ({
      environment_id: row.id,
      url: `https://qa-${row.key}.example/`,
    })),
  })
  await page.goto(`/#/team?env=${production.id}`)
  await expect(page.getByRole('link', { name: '打开QA环境定位系统 · 生产' })).toBeVisible()
  await page.getByRole('button', { name: 'QA环境定位系统', exact: true }).click()
  const tabs = page.getByRole('group', { name: '选择账号所属环境' })
  await expect(tabs).toBeVisible()
  await evidence(info, {
    filter: 'prod',
    selectedDetail: await tabs.locator('[aria-pressed="true"]').innerText(),
  })
  await expect(tabs.getByRole('button', { name: /生产/ })).toHaveAttribute('aria-pressed', 'true')
})

test('renaming a disabled public bookmark preserves its disabled state', async ({ page }, info) => {
  const me = await api(page, '/me')
  const resource = await api(page, '/resources', 'POST', {
    scope: 'personal',
    type: 'bookmark',
    name: 'QA停用书签',
    is_public: true,
    endpoints: [{ url: 'https://qa-disabled.example/', enabled: false }],
  })
  const before = await page.request.get(`/api/v1/public/navigation?owner=${me.id}`)
  await page.goto('/#/personal')
  await page.getByRole('button', { name: '编辑QA停用书签', exact: true }).click()
  await page.getByRole('dialog').getByLabel(/^名称/).fill('QA停用书签改名')
  await page.getByRole('button', { name: '保存链接', exact: true }).click()
  await expect(
    page.getByRole('dialog').getByRole('heading', { name: 'QA停用书签改名', exact: true }),
  ).toBeVisible()
  const actual = await api(page, `/resources/${resource.id}`)
  const publicAfter = await page.request.get(`/api/v1/public/navigation?owner=${me.id}`)
  const publicBody = await publicAfter.json()
  await evidence(info, {
    beforeEnabled: resource.endpoints[0].configured_enabled,
    afterEnabled: actual.endpoints[0].configured_enabled,
    publicBeforeStatus: before.status(),
    publicAfterStatus: publicAfter.status(),
    nowPublic: publicBody.items?.some((row: { id: string }) => row.id === resource.id),
  })
  expect(actual.endpoints[0].configured_enabled).toBe(false)
})

test('editing an expired disabled credential does not silently reactivate it', async ({ page }, info) => {
  const resource = await api(page, '/resources', 'POST', {
    scope: 'personal',
    type: 'bookmark',
    name: 'QA停用账号状态',
    endpoints: [{ url: 'https://qa-credential.example/' }],
  })
  const account = await api(page, `/endpoints/${resource.endpoints[0].id}/credentials`, 'POST', {
    name: 'QA原先已停用',
    username: 'qa-only',
    password: 'qa-fixture-value',
    status: 'disabled',
    expires_at: '2020-01-01T00:00:00Z',
  })
  await page.goto(`/#/personal?resource=${resource.id}`)
  await page.getByRole('button', { name: '编辑账号', exact: true }).click()
  const defaultStatus = await page.getByRole('combobox', { name: '状态', exact: true }).inputValue()
  await page.getByLabel('账号名称', { exact: true }).fill('QA仅修改备注与日期')
  await page.getByLabel('有效期（选填）', { exact: true }).fill('2030-01-01T12:00')
  await page.getByRole('button', { name: '保存账号', exact: true }).click()
  await expect(page.getByText('QA仅修改备注与日期', { exact: true })).toBeVisible()
  const accounts = await api(page, `/endpoints/${resource.endpoints[0].id}/credentials`)
  const actual = accounts.find((row: { id: string }) => row.id === account.id)
  const me = await api(page, '/me')
  const access = await page.request.post(`/api/v1/credentials/${account.id}/access`, {
    headers: { Origin: origin, 'X-CSRF-Token': me.csrf_token },
    data: { field: 'username', purpose: 'reveal' },
  })
  await evidence(info, {
    configuredBefore: 'disabled',
    apiBefore: account.status,
    editorDefault: defaultStatus,
    afterStatus: actual.status,
    accessStatus: access.status(),
  })
  expect(actual.status).toBe('disabled')
})
