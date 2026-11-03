const {test,expect}=require('@playwright/test');
test('owner sees truthful QuickBooks readiness and protected authorization controls',async({page})=>{
  await page.goto('/__ci/admin');await page.goto('/admin/access');
  await page.getByRole('link',{name:'QuickBooks Online connection and accounting',exact:true}).click();
  await expect(page.getByRole('heading',{name:'QuickBooks Online',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Setup required — not connected',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Connect to QuickBooks Online',exact:true})).toHaveCount(0);
  await expect(page.locator('body')).toContainText('Automatic lead-sale/refund synchronization is not enabled');
  expect((await page.request.get('/admin/quickbooks')).headers()['cache-control']).toContain('no-store');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
  const invalid=await page.request.get('/admin/quickbooks/callback?code=synthetic-never-displayed');
  expect(invalid.status()).not.toBe(200);expect(await invalid.text()).not.toContain('synthetic-never-displayed');
});
