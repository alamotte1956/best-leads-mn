const {test,expect}=require('@playwright/test');
const PUBLIC=['/','/signup','/contractor/login','/admin/login','/privacy','/terms','/sms-policy',
  '/usa','/usa/minnesota','/usa/minnesota/twin-cities','/request-status','/request-received',
  ...['water-damage','storm-hail-damage','roof-repair','basement-flooding','mold-remediation',
    'fire-smoke-damage','sewer-backup','frozen-pipes','siding-repair','emergency-tarping'].map(s=>'/services/'+s)];
const ADMIN=['/admin','/admin/national','/admin/owner-command-center','/admin/leads/1',
  '/admin/leads/1/location',
  '/admin/contractors/1/verification','/admin/contractors/1/notifications','/admin/service-requests',
  '/admin/integrations','/admin/pricing','/admin/rewards','/admin/rewards/identity/1',
  '/admin/national/applications','/admin/national/applications/1',
  ...['texas/dallas-fort-worth','texas/houston','florida/tampa-st-petersburg','florida/orlando',
    'florida/jacksonville','north-carolina/charlotte','north-carolina/raleigh-durham','georgia/atlanta-suburbs',
    'wisconsin/western-wisconsin','wisconsin/milwaukee','wisconsin/madison'].map(s=>'/admin/national/preview/'+s)];
const CONTRACTOR=['/contractor/dashboard','/contractor/settings','/contractor/markets',
  '/contractor/notifications','/contractor/leads','/contractor/offers/1/follow-up','/contractor/billing',
  '/contractor/rewards','/contractor/services/request'];

async function checkPages(page,paths){
  for(const path of paths){
    const response=await page.goto(path);expect(response.status(),path).toBe(200);
    await expect(page.locator('body')).toBeVisible();
    const geometry=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
    expect(geometry.scroll,path+' horizontal overflow').toBeLessThanOrEqual(geometry.width+1);
    await expect.poll(()=>page.locator('img[src^="/static/"]').evaluateAll(
      imgs=>imgs.filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src)),{message:path+' local images'}).toEqual([]);
  }
}
for(const width of [320,768,1440]){
  test('public pages at '+width,async({page})=>{await page.setViewportSize({width,height:900});await checkPages(page,PUBLIC);});
  test('private operating pages at '+width,async({page})=>{
    await page.setViewportSize({width,height:900});await page.goto('/__ci/admin');await checkPages(page,ADMIN);
    await page.goto('/__ci/contractor');await checkPages(page,CONTRACTOR);
  });
}
test('disabled markets and real rewards stay closed',async({page})=>{
  for(const state of ['texas','florida','north-carolina','georgia','wisconsin']){
    expect((await page.request.get('/usa/'+state)).status()).toBe(404);
    expect((await page.request.get('/usa/'+state+'/request')).status()).toBe(404);
    expect((await page.request.get('/usa/'+state+'/contractors/apply')).status()).toBe(404);
  }
  for(const action of ['spin','free-entry','redeem'])expect((await page.request.post('/contractor/rewards/'+action,{data:{approved:true}})).status()).toBe(503);
});
test('homeowner can submit and track a request without JavaScript',async({browser,baseURL})=>{
  const context=await browser.newContext({baseURL,javaScriptEnabled:false});const page=await context.newPage();
  try{
    await page.goto('/');await page.getByLabel('What kind of help do you need?').selectOption('Mold Remediation');
    await page.getByLabel('Property ZIP code').fill('55401');await page.getByLabel('Full name').fill('Synthetic No-JS Consumer');
    await page.getByLabel('Phone number',{exact:true}).fill('6125550199');
    await page.getByRole('button',{name:'Submit my request',exact:true}).click();
    await expect(page).toHaveURL(/\/request-received$/);await page.goto('/request-status');
    await expect(page.locator('body')).toContainText('Mold Remediation');
    await expect(page.locator('body')).not.toContainText('Synthetic No-JS Consumer');
  }finally{await context.close();}
});
