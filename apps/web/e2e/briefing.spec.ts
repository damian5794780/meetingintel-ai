import { test, expect } from '@playwright/test';

test('real frontend → API → LangGraph demo, evidence, reload, export and print', async ({page}) => {
  const errors:string[]=[];
  page.on('pageerror',e => errors.push(e.message));
  await page.setViewportSize({width:1440,height:1100});
  await page.goto('/');
  const create=page.getByRole('button',{name:'Create demo briefing'});
  await expect(create).toBeEnabled();
  await page.getByText('Add meeting context', {exact:false}).click();
  await page.getByLabel('Your organization / role').fill('Founder of an AI integration studio');
  await page.getByLabel('What you bring to the conversation').fill('AI workflow integrations');
  await page.getByLabel('Desired outcome').fill('Agree on a small integration pilot');
  await page.getByText('Add meeting context', {exact:false}).click();
  await create.click();
  await expect(page.getByRole('heading',{name:'Northstar Labs',exact:true})).toBeVisible();
  await expect(page.getByText(/Fictional demonstration/)).toBeVisible();
  await expect(page.getByText('Agree on a small integration pilot', {exact:false}).last()).toBeVisible();
  await expect(page.getByText(/AI workflow integrations could fit/).first()).toBeVisible();
  await page.getByRole('button',{name:'Show source S1'}).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('dialog')).toContainText('Fictional fixture');
  await expect(page.getByRole('link',{name:/Open original source/})).toHaveAttribute('href',/example.com/);
  await page.getByRole('button',{name:'Close evidence'}).click();
  await expect(page.getByRole('button',{name:'Show source S1'})).toBeFocused();
  const download=page.waitForEvent('download');
  await page.getByRole('button',{name:'Markdown',exact:true}).click();
  expect((await download).suggestedFilename()).toBe('meetingintel-briefing.md');
  await page.reload();
  await expect(page.getByRole('heading',{name:'Northstar Labs',exact:true})).toBeVisible();
  await page.emulateMedia({media:'print'});
  const pdf=await page.pdf({path:'test-results/demo-briefing.pdf',format:'A4',printBackground:true,preferCSSPageSize:true});
  expect((pdf.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length).toBe(1);
  await page.emulateMedia({media:'screen'});
  await page.setViewportSize({width:390,height:844});
  await expect(page.getByRole('heading',{name:'Northstar Labs',exact:true})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole('button',{name:'Live research',exact:true}).click();
  await expect(page.getByRole('button',{name:'Create briefing',exact:true})).toBeDisabled();
  expect(errors).toEqual([]);
});

test('an unavailable saved briefing does not block a new one', async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem('meetingintel-ticket', JSON.stringify({
    id: 'expired-ticket', access_token: 'fixture-only',
  })));
  await page.route('**/backend/api/research/expired-ticket/status', route => route.fulfill({
    status: 404, json: { detail: 'Briefing not found or token invalid.' },
  }));

  await page.goto('/');
  await expect(page.getByRole('alert').filter({ hasText: 'This saved briefing is unavailable' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Create demo briefing' })).toBeEnabled();
  expect(await page.evaluate(() => sessionStorage.getItem('meetingintel-ticket'))).toBeNull();
});

test('retry after a lost submission response opens the original report', async ({ page }) => {
  const submissions: { key: string; id: string }[] = [];
  await page.route('**/backend/api/research', async route => {
    const response = await route.fetch();
    expect(response.status()).toBe(202);
    const ticket = await response.json();
    submissions.push({ key: route.request().headers()['idempotency-key'], id: ticket.id });
    if (submissions.length === 1) await route.abort();
    else await route.fulfill({ response });
  });

  await page.goto('/');
  const create = page.getByRole('button', { name: 'Create demo briefing' });
  await expect(create).toBeEnabled();
  await create.click();
  await expect(page.locator('.result-column').getByRole('alert')).toBeVisible();
  await create.click();
  await expect(page.getByRole('heading', { name: 'Northstar Labs', exact: true })).toBeVisible();
  expect(submissions).toHaveLength(2);
  expect(submissions[0].key).toMatch(/^[a-f0-9]{64}$/);
  expect(submissions[1]).toEqual(submissions[0]);
});

test('long mixed-certainty briefing fits one A4 page and labels uncertain evidence', async ({page}) => {
  const fill=(text:string,size:number) => (text+' ').repeat(size).slice(0,size);
  const sources=Array.from({length:4},(_,i)=>({id:`S${i+1}`,title:fill('Example publication announcement',250),url:`https://example.com/${i}`,
    content:'An exact source excerpt.',published_at:i<2 ? '2026-11-10T10:00:00Z' : null,provider_date:'2026-11-10T10:00:00Z',
    date_origin:i<2 ? 'explicit_page':'provider_estimate',date_precision:'instant',temporal_status:i<2 ? 'in_window':'estimated'}));
  const findings=sources.map(s=>({text:fill('Example source reported a material product and partnership development.',240),category:'product',
    relevance:fill('Discuss the integration constraints and scope of a potential partner pilot.',180),source_ids:[s.id],evidence:{[s.id]:'An exact source excerpt.'},
    evidence_status:'excerpt_matched',temporal_note:'Publication timing needs review.'}));
  const result={entity:'Example Corporation',entity_type:'company',meeting_at:'2026-11-15T12:00:00Z',timezone:'Europe/Warsaw',purpose:'partnership',mode:'live',
    generated_at:'2026-11-14T10:00:00Z',window_start:'2026-10-16T12:00:00Z',window_end:'2026-11-14T10:00:00Z',
    summary:fill('Source-backed developments relevant to your partnership meeting [S1].',550),claims:findings.slice(0,2),uncertain_claims:findings.slice(2),
    questions:Array.from({length:4},(_,i)=>`${i+1}. ${fill('What integration constraints and decision criteria should a partnership pilot address?',177)}`),
    open_questions:Array.from({length:3},(_,i)=>`${i+1}. ${fill('Confirm the scope and timing directly with the counterpart before proceeding.',210)}`),
    sources,warnings:[],metrics:{elapsed_seconds:1,search_calls:5,llm_calls:2,sources_found:12,sources_eligible:2,claims_removed:0,estimated_llm_cost_usd:null}};
  await page.route('**/backend/api/research/layout-check/status', route => route.fulfill({ json: {
    id: 'layout-check', status: 'completed', stage: 'completed', revision: 1, created_at: '2026-11-14T10:00:00Z', error: null,
  } }));
  await page.route('**/backend/api/research/layout-check/result', route => route.fulfill({ json: result }));
  await page.goto('/');
  await page.evaluate(()=>sessionStorage.setItem('meetingintel-ticket',JSON.stringify({id:'layout-check',access_token:'fixture-only'})));
  await page.reload();
  await expect(page.getByRole('heading',{name:'Developments to verify'})).toBeVisible();
  await page.emulateMedia({media:'print'});
  const pdf=await page.pdf({path:'test-results/maximum-briefing.pdf',format:'A4',printBackground:true,preferCSSPageSize:true});
  expect((pdf.toString('latin1').match(/\/Type\s*\/Page\b/g)||[]).length).toBe(1);
});
