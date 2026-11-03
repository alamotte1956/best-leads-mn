const {test,expect}=require('@playwright/test');
const {randomUUID}=require('node:crypto');
test('administrator imports authorized evidence with separate sharing types and safe retries',async({page})=>{
  const key='synthetic-'+randomUUID();
  await page.goto('/__ci/admin');await page.goto('/admin/pricing');
  await expect(page.getByRole('heading',{name:'Import authorized pricing evidence'})).toBeVisible();
  await expect(page.getByText('Automatic authorized collector:',{exact:false})).toContainText('not connected');
  const template=await page.request.get('/admin/pricing/template.csv');
  expect(template.status()).toBe(200);expect(template.headers()['cache-control']).toContain('no-store');
  const header=await template.text();expect(header.trim().split('\n')).toHaveLength(1);
  const observed=new Date(Date.now()-1000).toISOString();
  const columns=header.trim().split(',');
  const row={state_code:'MN',service_name:'Mold Remediation',zip_code:'55401',contractor_limit:'3',observed_at:observed,currency:'USD',angi_cents:'10000',thumbtack_cents:'8000',angi_reference:'synthetic-browser-angi-'+key,thumbtack_reference:'synthetic-browser-thumbtack-'+key,comparison_basis:'comparable_contractor_lead_fee',import_key:key};
  const data=header+columns.map(c=>row[c]).join(',')+'\n';
  const upload=async()=>{
    await page.locator('input[name="evidence"]').setInputFiles({name:'synthetic-evidence.csv',mimeType:'text/csv',buffer:Buffer.from(data)});
    await page.locator('input[name="authorized"]').check();
    await page.getByRole('button',{name:'Validate and import evidence'}).click();
  };
  await upload();await expect(page.getByRole('status')).toContainText('Imported 1 new observations');
  const record=page.locator('article').filter({hasText:key});await expect(record).toHaveCount(1);
  await expect(record).toContainText('Shared lead: up to three contractors');
  await upload();await expect(page.getByRole('status')).toContainText('Imported 0 new observations');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
});
