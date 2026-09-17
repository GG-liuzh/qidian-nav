import { test, expect, type Page } from '@playwright/test'
import { mkdir, readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const adminPassword = 'browser-test-admin-password'
const screenshotDir = fileURLToPath(new URL('../../.runtime/screenshots/', import.meta.url))
let memberLink = ''
const errors: string[] = []
async function login(page: Page) {
  await page.goto('/#/login')
  await page.getByLabel('用户名', { exact: true }).fill('admin')
  await page.getByLabel('密码', { exact: true }).fill(adminPassword)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page.getByRole('heading', { name: '每个入口，都井然有序。' })).toBeVisible()
}
async function closeSheet(page: Page) {
  await page.getByRole('button', { name: '关闭面板', exact: true }).click()
  await expect(page.getByRole('dialog')).toHaveCount(0)
}
async function api(page: Page, path: string, method = 'GET', body?: unknown) {
  return page.evaluate(
    async ({ path, method, body }) => {
      const me = await fetch('/api/v1/me').then((r) => r.json())
      const response = await fetch(`/api/v1${path}`, {
        method,
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': me.csrf_token },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
      return { status: response.status, body: response.status === 204 ? null : await response.json() }
    },
    { path, method, body },
  )
}

test.describe.serial('real backend and browser flows', () => {
  test.beforeEach(async ({ page }) => {
    errors.length = 0
    page.on('pageerror', (error) => errors.push(error.message))
  })
  test.afterEach(() => {
    expect(errors).toEqual([])
  })

  test('first administrator, manual categories, persistent resources and preferences', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('无需登录即可浏览', { exact: true })).toBeVisible()
    await page.getByRole('link', { name: '初始化我的导航', exact: true }).click()
    await page.getByLabel('空间名称', { exact: true }).fill('研发协作空间')
    await page.getByLabel('你的姓名', { exact: true }).fill('测试管理员')
    await page.getByLabel('用户名', { exact: true }).fill('admin')
    await page.getByLabel('设置密码（至少 12 位）', { exact: true }).fill(adminPassword)
    await page.getByLabel('安装令牌').fill('e2e-only-install-token-not-a-real-secret')
    await page.getByRole('button', { name: '创建并进入' }).click()
    await page.getByRole('button', { name: '我已保存恢复码', exact: true }).click()
    await expect(page.getByRole('heading', { name: '每个入口，都井然有序。' })).toBeVisible()
    await page.getByRole('button', { name: '管理业务线与环境' }).click()
    await page.getByLabel('目录名称', { exact: true }).fill('交易平台')
    await page.getByRole('button', { name: '添加目录', exact: true }).click()
    await expect(page.getByRole('dialog').getByText('交易平台', { exact: true })).toBeVisible()
    await closeSheet(page)
    await expect(page.locator('.desktop-sidebar').getByRole('button', { name: /交易平台/ })).toBeVisible()
    await page.getByRole('button', { name: '添加链接', exact: true }).click()
    let sheet = page.getByRole('dialog')
    await sheet.getByLabel(/^名称/).fill('订单中心')
    await sheet.getByLabel('业务线', { exact: true }).selectOption({ label: '交易平台' })
    await sheet.getByLabel('简介', { exact: true }).fill('订单查询、履约管理与售后处理。')
    await sheet.getByLabel('别名', { exact: true }).fill('OMS')
    await sheet.getByLabel('公开此链接，允许未登录访问').check()
    await sheet.locator('input[type=url]').nth(0).fill('https://oms-dev.example/')
    await sheet.locator('input[type=url]').nth(1).fill('https://oms-test.example/')
    await sheet.locator('input[type=url]').nth(2).fill('https://oms.example/')
    await sheet.getByRole('button', { name: '保存链接', exact: true }).click()
    await expect(
      page.getByRole('dialog').getByRole('heading', { name: '订单中心', exact: true }),
    ).toBeVisible()
    await closeSheet(page)
    await page.reload()
    await expect(page.getByRole('button', { name: '订单中心', exact: true })).toBeVisible()
    const environmentLinks = page.locator('.resource-card .environment-links')
    await expect(environmentLinks.locator('.environment-name')).toHaveText(['开发', '测试', '生产'])
    const boxes = await environmentLinks.locator('.environment-link').evaluateAll((links) =>
      links.map((link) => {
        const { x, y, width } = link.getBoundingClientRect()
        return { x, y, width }
      }),
    )
    expect(boxes[0]!.y).toBe(boxes[1]!.y)
    expect(boxes[0]!.width).toBeCloseTo(boxes[1]!.width, 0)
    expect(boxes[2]!.y).toBeGreaterThan(boxes[0]!.y)
    expect(boxes[2]!.width).toBeCloseTo(boxes[1]!.x + boxes[1]!.width - boxes[0]!.x, 0)
    await page
      .getByRole('group', { name: '筛选环境' })
      .getByRole('button', { name: '测试', exact: true })
      .click()
    await expect(page.getByRole('link', { name: '打开订单中心 · 测试' })).toHaveAttribute(
      'href',
      'https://oms-test.example/',
    )
    await expect(page.getByRole('link', { name: '打开订单中心 · 生产' })).toHaveCount(0)
    const singleWidth = await environmentLinks
      .locator('.environment-link')
      .evaluate((link) => link.getBoundingClientRect().width)
    expect(singleWidth).toBeCloseTo((await environmentLinks.boundingBox())!.width, 0)
    await page.getByRole('button', { name: '重置筛选', exact: true }).click()
    await page.getByRole('button', { name: '收藏订单中心', exact: true }).click()
    await expect(page.getByRole('button', { name: '取消收藏订单中心', exact: true })).toBeVisible()
    await page.getByRole('button', { name: '订单中心', exact: true }).click()
    await expect(page.locator('.drawer-environments button > span')).toHaveText([
      '开发 · DEV',
      '测试 · TEST',
      '生产 · PROD',
    ])
    await page.getByRole('button', { name: '固定此环境到快捷入口', exact: true }).click()
    await closeSheet(page)
    await expect(page.locator('.shortcuts').getByText('订单中心', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: '切换明暗主题' }).click()
    await page.reload()
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
    await page.getByRole('button', { name: '切换明暗主题' }).click()
    await page.getByRole('button', { name: '设置与维护', exact: true }).click()
    await page.getByRole('button', { name: '空间设置', exact: true }).click()
    await page.getByRole('button', { name: '保存部门设置', exact: true }).click()
    await expect(page.locator('.toast')).toContainText('空间设置已保存')
    await page.getByRole('button', { name: '成员与邀请', exact: true }).click()
    await page.getByRole('button', { name: '创建邀请', exact: true }).click()
    memberLink = await page.getByLabel('生成的邀请链接').inputValue()
    expect(memberLink).toContain('/#/join?token=')
    await closeSheet(page)
    await mkdir(screenshotDir, { recursive: true })
    await page.screenshot({ path: resolve(screenshotDir, 'desktop.png'), fullPage: true })
  })

  test('members have private spaces and submit team changes for review', async ({ page, browser }) => {
    await page.goto(memberLink)
    await page.getByLabel('你的姓名', { exact: true }).fill('普通成员')
    await page.getByLabel('用户名', { exact: true }).fill('member')
    await page.getByLabel('设置密码（至少 12 位）', { exact: true }).fill('browser-test-member-password')
    await page.getByRole('button', { name: '加入团队', exact: true }).click()
    await page.getByRole('button', { name: '我已保存恢复码', exact: true }).click()
    await expect(
      page.locator('#main').getByRole('button', { name: '提交链接建议', exact: true }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: '编辑订单中心', exact: true })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '管理业务线与环境' })).toHaveCount(0)
    await page.locator('#main').getByRole('button', { name: '提交链接建议', exact: true }).click()
    await page.getByLabel('标题', { exact: true }).fill('接口文档')
    await page.getByLabel('推荐地址', { exact: true }).fill('https://api-docs.example/')
    await page.getByRole('button', { name: '提交给维护人' }).click()
    await expect(page.getByRole('dialog').getByText('待处理', { exact: true })).toBeVisible()
    await closeSheet(page)
    await page.getByRole('link', { name: '个人导航', exact: true }).click()
    await page.getByRole('button', { name: '管理个人分组' }).click()
    await page.getByLabel('目录名称', { exact: true }).fill('学习资料')
    await page.getByRole('button', { name: '添加目录', exact: true }).click()
    await expect(
      page.getByRole('dialog').locator('.management-list').getByText('学习资料', { exact: true }),
    ).toBeVisible()
    await closeSheet(page)
    await page.getByRole('button', { name: '添加链接', exact: true }).click()
    await page.getByRole('dialog').getByLabel(/^名称/).fill('私人学习笔记')
    await page.getByRole('dialog').getByLabel('URL', { exact: true }).fill('https://private-notes.example/')
    await page.getByRole('dialog').getByRole('button', { name: '保存链接', exact: true }).click()
    await expect(
      page.getByRole('dialog').getByRole('heading', { name: '私人学习笔记', exact: true }),
    ).toBeVisible()
    await page.getByRole('button', { name: '固定此书签到快捷入口', exact: true }).click()
    await expect(page.getByRole('button', { name: '移除快捷入口', exact: true })).toBeVisible()
    await closeSheet(page)
    await page.reload()
    await expect(page.getByRole('link', { name: '私人学习笔记', exact: true })).toBeVisible()
    await expect(page.locator('.shortcuts a').filter({ hasText: '私人学习笔记' })).toHaveAttribute(
      'href',
      'https://private-notes.example/',
    )
    const other = await browser.newContext(),
      admin = await other.newPage()
    await login(admin)
    expect((await api(admin, '/resources?view=personal')).body.total).toBe(0)
    await admin.getByRole('button', { name: '设置与维护', exact: true }).click()
    await admin.getByRole('button', { name: '建议与反馈', exact: true }).click()
    await admin.getByRole('button', { name: '处理建议', exact: true }).click()
    await admin.getByRole('button', { name: '采用并发布链接', exact: true }).click()
    await expect(admin.getByRole('dialog').getByText('已采用', { exact: true })).toBeVisible()
    await closeSheet(admin)
    await expect(admin.getByRole('link', { name: '接口文档', exact: true })).toBeVisible()
    await other.close()
  })

  test('encrypted accounts require audited access, clear on environment changes and copy honestly', async ({
    page,
  }) => {
    await login(page)
    await page.getByRole('button', { name: '订单中心', exact: true }).click()
    await page.getByRole('button', { name: '添加账号', exact: true }).click()
    await page.getByLabel('账号名称', { exact: true }).fill('联调只读账号')
    await page.getByLabel('用户名', { exact: true }).fill('demo_reader')
    await page.getByLabel('密码', { exact: true }).fill('E2E-fictional-password')
    await page.getByRole('button', { name: '保存账号', exact: true }).click()
    await expect(page.getByText('联调只读账号', { exact: true })).toBeVisible()
    await expect(page.getByText('demo_reader', { exact: true })).toBeVisible()
    await expect(page.getByText('E2E-fictional-password', { exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: '隐藏用户名', exact: true }).click()
    await expect(page.getByText('demo_reader', { exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: '显示用户名', exact: true }).click()
    await expect(page.getByText('demo_reader', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: '显示密码', exact: true }).click()
    await expect(page.getByText('E2E-fictional-password', { exact: true })).toBeVisible()
    await page.getByRole('group', { name: '选择账号所属环境' }).getByRole('button', { name: /生产/ }).click()
    await expect(page.getByText('E2E-fictional-password', { exact: true })).toHaveCount(0)
    await expect(page.getByText('demo_reader', { exact: true })).toHaveCount(0)
    await page.getByRole('group', { name: '选择账号所属环境' }).getByRole('button', { name: /测试/ }).click()
    await expect(page.getByText('demo_reader', { exact: true })).toBeVisible()
    await page.evaluate(() =>
      Object.defineProperty(navigator, 'clipboard', {
        configurable: true,
        value: {
          writeText: async () => {
            throw new Error('blocked')
          },
        },
      }),
    )
    await page.getByRole('button', { name: '复制密码', exact: true }).click()
    await expect(page.getByLabel('手动复制账号内容')).toHaveValue('E2E-fictional-password')
    await page.evaluate(() => window.dispatchEvent(new Event('blur')))
    await expect(page.getByLabel('手动复制账号内容')).toHaveCount(0)
    await page.evaluate(() =>
      Object.defineProperty(navigator, 'clipboard', {
        configurable: true,
        value: {
          writeText: async (value: string) => {
            ;(window as unknown as { copied: string }).copied = value
          },
        },
      }),
    )
    await page.getByRole('button', { name: '复制用户名', exact: true }).click()
    await expect(page.locator('.toast')).toContainText('用户名已复制')
    expect(await page.evaluate(() => (window as unknown as { copied: string }).copied)).toBe('demo_reader')
    await page.clock.install()
    await page.getByRole('button', { name: '显示密码', exact: true }).click()
    await expect(page.getByText('E2E-fictional-password', { exact: true })).toBeVisible()
    await page.clock.fastForward(21000)
    await expect(page.getByText('E2E-fictional-password', { exact: true })).toHaveCount(0)
    expect(
      await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length })),
    ).toEqual({ local: 0, session: 0 })
    await page.screenshot({ path: resolve(screenshotDir, 'accounts.png'), fullPage: true })
  })

  test('responsive navigation, keyboard focus, draft protection and trash restore', async ({ page }) => {
    await login(page)
    for (const width of [320, 390, 768, 1024, 1440, 1920, 2560]) {
      await page.setViewportSize({ width, height: 900 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
      expect(
        await page
          .locator('#main')
          .evaluate(
            (element) =>
              Math.abs(
                element.getBoundingClientRect().width -
                  Math.min(1680, element.parentElement!.getBoundingClientRect().width),
              ) < 2,
          ),
      ).toBe(true)
      if (width <= 960) {
        await page.getByRole('button', { name: '展开导航' }).click()
        await expect(page.getByRole('dialog')).toBeVisible()
        await page.keyboard.press('Escape')
        await expect(page.getByRole('dialog')).toHaveCount(0)
      }
      await page.getByRole('button', { name: '订单中心', exact: true }).click()
      expect(
        await page.getByRole('dialog').evaluate((element) => element.scrollWidth <= element.clientWidth + 1),
      ).toBe(true)
      await page.keyboard.press('Tab')
      expect(await page.evaluate(() => !!document.activeElement?.closest('[role=dialog]'))).toBe(true)
      if (width === 390) await page.screenshot({ path: resolve(screenshotDir, 'mobile.png'), fullPage: true })
      await page.keyboard.press('Escape')
      await expect(page.getByRole('dialog')).toHaveCount(0)
    }
    await page.getByRole('button', { name: '编辑订单中心', exact: true }).click()
    await page.getByRole('dialog').getByLabel(/^名称/).fill('尚未保存的名称')
    await page.getByRole('button', { name: '关闭面板', exact: true }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: '取消', exact: true }).click()
    await expect(page.getByRole('dialog').getByLabel(/^名称/)).toHaveValue('尚未保存的名称')
    await page.getByRole('button', { name: '关闭面板', exact: true }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: '确认', exact: true }).click()
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await page.getByRole('button', { name: '订单中心', exact: true }).click()
    await page.getByRole('button', { name: '移入回收站', exact: true }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: '确认', exact: true }).click()
    await expect(page.getByRole('button', { name: '订单中心', exact: true })).toHaveCount(0)
    await page.getByRole('button', { name: '设置与维护', exact: true }).click()
    await page.getByRole('button', { name: '回收站', exact: true }).click()
    await page.getByRole('button', { name: '恢复', exact: true }).click()
    await expect(page.getByText('回收站是空的。')).toBeVisible()
    await closeSheet(page)
    await expect(page.getByRole('button', { name: '订单中心', exact: true })).toBeVisible()
  })

  test('visitors browse public navigation at full width without login or credential calls', async ({
    page,
  }) => {
    const credentialRequests: string[] = []
    page.on('request', (request) => {
      if (request.url().includes('/credentials')) credentialRequests.push(request.url())
    })
    await page.goto('/#/team')
    await expect(page.getByText('无需登录即可浏览', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '订单中心', exact: true })).toBeVisible()
    await expect(page.getByLabel('用户名', { exact: true })).toHaveCount(0)
    await expect(page.getByRole('link', { name: '接口文档', exact: true })).toHaveCount(0)
    for (const width of [320, 390, 768, 1024, 1440, 1920, 2560]) {
      await page.setViewportSize({ width, height: 900 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
      expect(
        await page
          .locator('#main')
          .evaluate(
            (element) =>
              Math.abs(
                element.getBoundingClientRect().width -
                  Math.min(1680, element.parentElement!.getBoundingClientRect().width),
              ) < 2,
          ),
      ).toBe(true)
    }
    await page.getByRole('button', { name: '查看说明', exact: true }).click()
    await expect(
      page.getByRole('dialog').getByRole('heading', { name: '订单中心', exact: true }),
    ).toBeVisible()
    await expect(page.getByRole('button', { name: '复制密码', exact: true })).toHaveCount(0)
    await closeSheet(page)
    expect(credentialRequests).toEqual([])
    await page.setViewportSize({ width: 1920, height: 1080 })
    await page.screenshot({ path: resolve(screenshotDir, 'public-desktop.png'), fullPage: true })
  })

  test('personal signup needs no invitation or department and publishes only selected links', async ({
    page,
    browser,
  }) => {
    await page.goto('/#/signup')
    await expect(page.getByLabel('空间名称', { exact: true })).toHaveCount(0)
    await expect(page.getByLabel('邀请令牌', { exact: true })).toHaveCount(0)
    await page.getByLabel('你的姓名', { exact: true }).fill('独立使用者')
    await page.getByLabel('用户名', { exact: true }).fill('independent-user')
    await page.getByLabel('设置密码（至少 12 位）', { exact: true }).fill('independent-browser-password')
    await page.getByRole('button', { name: '创建个人账号', exact: true }).click()
    await page.getByRole('button', { name: '我已保存恢复码', exact: true }).click()
    await expect(page.getByRole('heading', { name: '留给自己的，好用入口。' })).toBeVisible()
    await expect(page.getByRole('link', { name: '团队导航', exact: true })).toHaveCount(0)
    for (const [name, url, publish] of [
      ['独立私人笔记', 'https://personal-private.example/', false],
      ['我的公开资料', 'https://personal-public.example/', true],
    ] as const) {
      await page.getByRole('button', { name: '添加链接', exact: true }).click()
      await page.getByRole('dialog').getByLabel(/^名称/).fill(name)
      await page.getByRole('dialog').getByLabel('URL', { exact: true }).fill(url)
      if (publish) await page.getByLabel('公开此链接，允许未登录访问').check()
      await page.getByRole('button', { name: '保存链接', exact: true }).click()
      await expect(page.getByRole('dialog').getByRole('heading', { name, exact: true })).toBeVisible()
      await closeSheet(page)
    }
    await page.reload()
    await expect(page.getByRole('link', { name: '独立私人笔记', exact: true })).toBeVisible()
    const me = (await api(page, '/me')).body
    expect(me.workspace).toBeNull()
    const guestContext = await browser.newContext(),
      guest = await guestContext.newPage()
    await guest.goto(me.public_profile_url)
    await expect(guest.getByRole('link', { name: '我的公开资料', exact: true })).toBeVisible()
    await expect(guest.getByRole('link', { name: '独立私人笔记', exact: true })).toHaveCount(0)
    await expect(guest.getByLabel('用户名', { exact: true })).toHaveCount(0)
    await guestContext.close()
  })

  test('personal migration downloads encrypted data and leaving a department preserves personal access', async ({
    page,
    browser,
  }) => {
    await page.goto('/#/login')
    await page.getByLabel('用户名', { exact: true }).fill('member')
    await page.getByLabel('密码', { exact: true }).fill('browser-test-member-password')
    await page.getByRole('button', { name: '登录', exact: true }).click()
    await expect(page.getByRole('heading', { name: '每个入口，都井然有序。' })).toBeVisible()
    const owned = (await api(page, '/resources?view=personal')).body.items[0]
    expect(
      (
        await api(page, `/endpoints/${owned.endpoints[0].id}/credentials`, 'POST', {
          name: '迁移测试账号',
          username: 'personal_reader',
          password: 'fictional-personal-password',
        })
      ).status,
    ).toBe(201)
    await page.getByRole('button', { name: '设置与维护', exact: true }).click()
    await page.getByRole('button', { name: '个人迁移', exact: true }).click()
    await page.getByLabel('包含个人资源的账号密码').check()
    await page.getByLabel('迁移口令（至少 12 位）', { exact: true }).fill('browser-migration-passphrase')
    const downloaded = page.waitForEvent('download')
    await page.getByRole('button', { name: '下载个人迁移文件', exact: true }).click()
    const file = await (await downloaded).path()
    expect(file).toBeTruthy()
    const data = await readFile(file!, 'utf8')
    expect(JSON.parse(data).format).toBe('qidian-personal-encrypted-v1')
    expect(data).not.toContain('fictional-personal-password')
    await page.getByRole('button', { name: '空间设置', exact: true }).click()
    await page.getByRole('button', { name: '离开当前部门', exact: true }).click()
    await page.getByRole('alertdialog').getByRole('button', { name: '确认', exact: true }).click()
    await expect(page.getByRole('heading', { name: '留给自己的，好用入口。' })).toBeVisible()
    await expect(page.getByRole('link', { name: '私人学习笔记', exact: true })).toBeVisible()
    await page.reload()
    expect((await api(page, '/me')).body.workspace).toBeNull()
    const destinationContext = await browser.newContext(),
      destination = await destinationContext.newPage()
    await destination.goto('/#/login')
    await destination.getByLabel('用户名', { exact: true }).fill('independent-user')
    await destination.getByLabel('密码', { exact: true }).fill('independent-browser-password')
    await destination.getByRole('button', { name: '登录', exact: true }).click()
    await expect(destination.getByRole('heading', { name: '留给自己的，好用入口。' })).toBeVisible()
    await destination.getByRole('button', { name: '设置与维护', exact: true }).click()
    await destination.getByRole('button', { name: '个人迁移', exact: true }).click()
    await destination.getByLabel('选择个人迁移文件').setInputFiles(file!)
    await destination.getByLabel('文件的迁移口令', { exact: true }).fill('browser-migration-passphrase')
    await destination.getByRole('button', { name: '预览迁移内容', exact: true }).click()
    await expect(destination.locator('.transfer-preview')).toContainText('1 个私人账号')
    await destination.getByRole('button', { name: '确认导入到我的导航', exact: true }).click()
    await expect(destination.getByRole('dialog')).toContainText('导入内容默认仅自己可见')
    await closeSheet(destination)
    await expect(destination.getByRole('link', { name: '私人学习笔记', exact: true })).toBeVisible()
    const imported = (await api(destination, '/resources?view=personal')).body.items.find(
      (item: { name: string }) => item.name === '私人学习笔记',
    )
    expect(imported.is_public).toBe(false)
    expect(imported.id).not.toBe(owned.id)
    const accounts = (await api(destination, `/endpoints/${imported.endpoints[0].id}/credentials`)).body
    expect(
      (
        await api(destination, `/credentials/${accounts[0].id}/access`, 'POST', {
          field: 'password',
          purpose: 'copy',
        })
      ).body.value,
    ).toBe('fictional-personal-password')
    await destinationContext.close()
  })

  test('existing personal accounts join as maintainers through invitations', async ({ page, browser }) => {
    await login(page)
    const token = (await api(page, '/invitations', 'POST', { role: 'maintainer' })).body.token
    const colleagueContext = await browser.newContext(),
      colleague = await colleagueContext.newPage()
    await colleague.goto(`/#/join?token=${encodeURIComponent(token)}`)
    await colleague.getByRole('link', { name: '已有账号，先登录', exact: true }).click()
    await colleague.getByLabel('用户名', { exact: true }).fill('independent-user')
    await colleague.getByLabel('密码', { exact: true }).fill('independent-browser-password')
    await colleague.getByRole('button', { name: '登录', exact: true }).click()
    await expect(colleague.getByRole('heading', { name: '加入团队', exact: true })).toBeVisible()
    await expect(colleague.getByLabel('邀请令牌', { exact: true })).toHaveValue(token)
    await colleague.getByRole('button', { name: '加入团队', exact: true }).click()
    await expect(colleague.getByRole('heading', { name: '每个入口，都井然有序。' })).toBeVisible()
    await expect(colleague.getByRole('button', { name: '添加链接', exact: true })).toBeVisible()
    await expect(colleague.getByRole('button', { name: '管理业务线与环境' })).toHaveCount(0)
    await colleague.getByRole('button', { name: '编辑订单中心', exact: true }).click()
    await colleague.getByLabel('简介', { exact: true }).fill('成员共同维护后的公开说明。')
    await expect(colleague.getByLabel('公开此链接，允许未登录访问')).toHaveCount(0)
    await colleague.getByRole('button', { name: '保存链接', exact: true }).click()
    await expect(
      colleague.getByRole('dialog').getByRole('heading', { name: '订单中心', exact: true }),
    ).toBeVisible()
    await closeSheet(colleague)
    expect((await api(colleague, '/resources?view=personal')).body.total).toBe(3)
    await colleague.getByRole('button', { name: '退出登录', exact: true }).click()
    await expect(colleague.getByRole('link', { name: '登录参与维护', exact: true })).toBeVisible()
    await colleagueContext.close()
  })

  test('large catalogs stay searchable and settings remain usable on small screens', async ({ page }) => {
    test.setTimeout(120000)
    await login(page)
    const categoryNames = [
      '商品与库存',
      '客户服务',
      '数据分析',
      '研发效能',
      '基础设施',
      '安全与合规',
      '团队协作',
      '市场营销',
      '人力与行政',
      '财务管理',
      '设计资源',
      '内容运营',
      '文档中心',
      '移动应用',
      '供应链',
      '开放平台',
      '质量保障',
      '效率工具',
      '产品研究',
      '运维值班',
      '项目归档',
    ]
    const teamCategories: string[] = []
    for (const [sort_order, name] of categoryNames.entries()) {
      const result = await api(page, '/categories', 'POST', { scope: 'team', name, sort_order })
      expect(result.status).toBe(201)
      teamCategories.push(result.body.id)
    }
    const catalog = (await api(page, '/catalog')).body
    const teamEnvs = catalog.environments.filter((row: { scope: string }) => row.scope === 'team')
    const systems = [
      ['商品管理平台', '统一维护商品信息、库存与上下架流程。', 'package'],
      ['客户工作台', '客户资料、服务工单与协作记录。', 'users'],
      ['数据分析中心', '查看核心指标与业务趋势，让决策有据可依。', 'compass'],
      ['研发流水线', '从代码提交到持续交付，跟进每一次发布。', 'code'],
      ['云资源控制台', '服务实例、监控告警与基础设施配置。', 'terminal'],
      ['统一身份管理', '团队账号、访问申请与安全策略。', 'shield'],
      ['团队知识库', '项目文档、工作规范和沉淀下来的经验。', 'book'],
      ['营销活动中心', '规划活动、维护投放入口与跟进效果。', 'boxes'],
    ]
    for (const [index, [name, description, icon]] of systems.entries()) {
      const result = await api(page, '/resources', 'POST', {
        scope: 'team',
        type: 'system',
        name,
        description,
        icon,
        category_id: teamCategories[index],
        tags: ['团队常用'],
        endpoints: teamEnvs.map((env: { id: string; key: string }) => ({
          environment_id: env.id,
          url: `https://service-${index}-${env.key}.example/`,
        })),
      })
      expect(result.status).toBe(201)
      if (index < 6)
        expect((await api(page, `/me/shortcuts/${result.body.endpoints[0].id}`, 'PUT')).status).toBe(204)
    }
    for (const [key, label] of [
      ['staging', '预发'],
      ['canary', '灰度'],
    ]) {
      expect(
        (await api(page, '/environments', 'POST', { scope: 'team', key, label, kind: 'custom' })).status,
      ).toBe(201)
    }
    await page.reload()
    await expect(page.getByRole('combobox', { name: '筛选环境' })).toBeVisible()
    await expect(page.locator('.shortcut-item')).toHaveCount(6)
    await page.getByRole('button', { name: '查看全部 7 个快捷入口' }).click()
    await expect(page.locator('.shortcut-item')).toHaveCount(7)
    await page.getByRole('button', { name: '收起快捷入口' }).click()
    await page.getByRole('button', { name: '整理', exact: true }).click()
    await expect(page.getByRole('button', { name: '快捷入口前移' })).toHaveCount(7)
    await page.getByRole('button', { name: '完成整理', exact: true }).click()
    const sidebar = page.locator('.desktop-sidebar')
    await sidebar.getByLabel('搜索目录', { exact: true }).fill('质量')
    await expect(sidebar.locator('.directory-row')).toHaveCount(1)
    await sidebar.getByLabel('搜索目录', { exact: true }).fill('')
    await page.screenshot({ path: resolve(screenshotDir, 'layout-v2-desktop.png'), fullPage: true })

    const root = (await api(page, '/categories', 'POST', { scope: 'personal', name: '工作资料' })).body
    const child = (
      await api(page, '/categories', 'POST', { scope: 'personal', name: '研发手册', parent_id: root.id })
    ).body
    const leaf = (
      await api(page, '/categories', 'POST', { scope: 'personal', name: 'API 设计规范', parent_id: child.id })
    ).body
    for (let index = 1; index <= 40; index++) {
      expect(
        (
          await api(page, '/categories', 'POST', {
            scope: 'personal',
            name: `资料归档 ${String(index).padStart(2, '0')}`,
            sort_order: index,
          })
        ).status,
      ).toBe(201)
    }
    await page.getByRole('link', { name: '个人导航', exact: true }).click()
    await page.reload()
    await page.getByRole('button', { name: '添加链接', exact: true }).click()
    await page.getByRole('dialog').getByLabel(/^名称/).fill('接口规范与实践')
    const longUrl = `https://docs.example/reference?section=${'a'.repeat(300)}`
    await page.getByRole('dialog').getByLabel('URL', { exact: true }).fill(longUrl)
    await page.getByRole('dialog').getByLabel('个人分组', { exact: true }).selectOption(leaf.id)
    await page.getByRole('button', { name: '保存链接', exact: true }).click()
    await expect(
      page.getByRole('dialog').getByRole('heading', { name: '接口规范与实践', exact: true }),
    ).toBeVisible()
    await closeSheet(page)
    await expect(sidebar.getByRole('button', { name: /^API 设计规范/ })).toHaveCount(0)
    await sidebar.getByLabel('搜索目录', { exact: true }).fill('API')
    await expect(sidebar.locator('.directory-row')).toHaveCount(3)
    await sidebar.getByRole('button', { name: /^API 设计规范/ }).click()
    await expect(page.getByRole('link', { name: '接口规范与实践', exact: true })).toHaveAttribute(
      'href',
      longUrl,
    )
    await sidebar.getByLabel('搜索目录', { exact: true }).fill('')
    await expect(sidebar.getByRole('button', { name: /^API 设计规范/ })).toBeVisible()
    await sidebar.getByRole('button', { name: '收起工作资料', exact: true }).click()
    await expect(sidebar.getByRole('button', { name: /^API 设计规范/ })).toHaveCount(0)
    await page.setViewportSize({ width: 1024, height: 640 })
    const settings = sidebar.getByRole('button', { name: '设置与维护', exact: true })
    const before = await settings.boundingBox()
    expect(before!.y + before!.height).toBeLessThan(640)
    expect(
      await sidebar
        .locator('.directory-scroll')
        .evaluate((element) => element.scrollHeight > element.clientHeight),
    ).toBe(true)
    await sidebar.locator('.directory-scroll').evaluate((element) => {
      element.scrollTop = element.scrollHeight
    })
    expect(Math.abs((await settings.boundingBox())!.y - before!.y)).toBeLessThan(1)

    await page.setViewportSize({ width: 1440, height: 1000 })
    await settings.click()
    await expect(page.getByRole('navigation', { name: '设置分类' })).toBeVisible()
    await expect(page.getByLabel('显示姓名')).toBeVisible()
    await expect(page.getByLabel('当前密码', { exact: true })).toHaveCount(0)
    await expect(page.locator('.toast')).toHaveCount(0)
    await page.screenshot({ path: resolve(screenshotDir, 'settings-v2-desktop.png') })
    await page.getByRole('button', { name: '登录与安全', exact: true }).click()
    await expect(page.getByLabel('当前密码', { exact: true })).toBeVisible()
    await expect(page.getByLabel('空间名称', { exact: true })).toHaveCount(0)
    for (const width of [320, 390, 768, 1024]) {
      await page.setViewportSize({ width, height: 640 })
      expect(
        await page.getByRole('dialog').evaluate((element) => element.scrollWidth <= element.clientWidth + 1),
      ).toBe(true)
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true)
      if (width < 700) {
        await page.getByRole('combobox', { name: '设置分类' }).selectOption('exports')
        await expect(page.getByRole('link', { name: '个人书签 JSON' })).toBeVisible()
        await page.getByRole('combobox', { name: '设置分类' }).selectOption('security')
      }
    }
    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({ path: resolve(screenshotDir, 'settings-v2-mobile.png') })
    await closeSheet(page)
    await page.setViewportSize({ width: 320, height: 568 })
    await page.getByRole('button', { name: '展开导航' }).click()
    const mobileSettings = page
      .locator('.mobile-nav-content')
      .getByRole('button', { name: '设置与维护', exact: true })
    const mobileBox = await mobileSettings.boundingBox()
    expect(mobileBox!.y + mobileBox!.height).toBeLessThan(568)
    await mobileSettings.click()
    await expect(page.getByRole('combobox', { name: '设置分类' })).toBeVisible()
    await closeSheet(page)
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.getByRole('link', { name: '团队导航', exact: true }).click()
    await page.getByRole('button', { name: '切换明暗主题' }).click()
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
    await page.screenshot({ path: resolve(screenshotDir, 'layout-v2-dark.png'), fullPage: true })
    await page.getByRole('button', { name: '切换明暗主题' }).click()
  })

  test('reusable invitations and disabling then reenabling a site user', async ({ page, browser }) => {
    await login(page)
    await page.getByRole('button', { name: '设置与维护', exact: true }).click()
    await page.getByRole('button', { name: '成员与邀请', exact: true }).click()
    await page.getByLabel('可使用次数').selectOption({ label: '5 次' })
    await page.getByLabel('有效时长').selectOption({ label: '24 小时' })
    await page.getByRole('button', { name: '创建邀请', exact: true }).click()
    const link = await page.getByLabel('生成的邀请链接').inputValue()
    await expect(page.getByText('邀请链接（最多使用 5 次）', { exact: true })).toBeVisible()
    await expect(page.getByText('已使用 0 次 · 还可使用 5 次（共 5 次）')).toBeVisible()

    const context = await browser.newContext()
    const invited = await context.newPage()
    try {
      await invited.goto(link)
      await expect(invited.locator('.invite-summary')).toContainText('还可使用 5 次')
      await invited.getByLabel('你的姓名', { exact: true }).fill('状态管理成员')
      await invited.getByLabel('用户名', { exact: true }).fill('status-invited-user')
      await invited.getByLabel('设置密码（至少 12 位）', { exact: true }).fill('invited-browser-password')
      await invited.getByRole('button', { name: '加入团队', exact: true }).click()
      await invited.getByRole('button', { name: '我已保存恢复码', exact: true }).click()
      await expect(invited.getByRole('heading', { name: '每个入口，都井然有序。' })).toBeVisible()

      await page.getByRole('button', { name: '空间设置', exact: true }).click()
      await page.getByRole('button', { name: '成员与邀请', exact: true }).click()
      await expect(page.getByText('已使用 1 次 · 还可使用 4 次（共 5 次）')).toBeVisible()
      await page.getByLabel('可使用次数').selectOption({ label: '有效期内不限次数' })
      await page.getByRole('button', { name: '创建邀请', exact: true }).click()
      await expect(page.getByText('邀请链接（有效期内不限次数）', { exact: true })).toBeVisible()
      await page.setViewportSize({ width: 390, height: 844 })
      expect(await page.getByRole('dialog').evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true)
      await page.screenshot({ path: resolve(screenshotDir, 'invitation-limits-mobile.png') })
      await page.setViewportSize({ width: 1440, height: 1000 })

      await page.getByRole('button', { name: '超级管理', exact: true }).click()
      await page.getByRole('button', { name: '站点用户', exact: true }).click()
      const card = page.locator('.member-card').filter({ hasText: 'status-invited-user' })
      await expect(card).toBeVisible()
      await expect(page.getByRole('button', { name: '删除用户', exact: true })).toHaveCount(0)
      await card.getByLabel('账号启用').uncheck()
      await card.getByRole('button', { name: '保存用户设置' }).click()
      const disableResponse = page.waitForResponse(
        (response) =>
          response.url().includes('/api/v1/admin/users/') && response.request().method() === 'PATCH',
      )
      await page.getByRole('alertdialog').getByRole('button', { name: '保存', exact: true }).click()
      expect((await disableResponse).status()).toBe(200)
      await expect(card.getByLabel('账号启用')).not.toBeChecked()
      expect((await invited.request.get(`${new URL(link).origin}/api/v1/me`)).status()).toBe(401)
      await invited.reload()
      await invited.getByRole('link', { name: '登录参与维护' }).click()
      await expect(invited.getByRole('heading', { name: '欢迎回到栖点' })).toBeVisible()
      await card.getByLabel('账号启用').check()
      await card.getByRole('button', { name: '保存用户设置' }).click()
      const enableResponse = page.waitForResponse(
        (response) =>
          response.url().includes('/api/v1/admin/users/') && response.request().method() === 'PATCH',
      )
      await page.getByRole('alertdialog').getByRole('button', { name: '保存', exact: true }).click()
      expect((await enableResponse).status()).toBe(200)
      await expect(card.getByLabel('账号启用')).toBeChecked()
      await invited.getByLabel('用户名', { exact: true }).fill('status-invited-user')
      await invited.getByLabel('密码', { exact: true }).fill('invited-browser-password')
      await invited.getByRole('button', { name: '登录', exact: true }).click()
      await expect(invited.getByRole('heading', { name: '每个入口，都井然有序。' })).toBeVisible()
    } finally {
      await context.close()
    }
  })
})
