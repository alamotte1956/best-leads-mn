const {test,expect}=require('@playwright/test');

test('demo animates, prevents double spins, replays and makes no purchases or reward requests',async({page})=>{
  const writes=[];page.on('request',r=>{if(r.method()!=='GET')writes.push(r.url());});
  await page.emulateMedia({reducedMotion:'no-preference'});
  await page.goto('/leadiq-demo');
  const spin=page.locator('#iq-spin');
  await expect(spin).toBeEnabled();await spin.click();
  await expect(spin).toBeDisabled();
  await expect(page.locator('#iq-result')).toContainText('spinning');
  await expect(spin).toBeEnabled({timeout:7000});
  await expect(page.locator('#iq-result')).toContainText('no reward was awarded');
  await spin.click();await expect(spin).toBeDisabled();
  await expect(spin).toBeEnabled({timeout:7000});
  expect(writes).toEqual([]);
});

test('demo works with reduced motion at phone width and on contractor pages',async({page})=>{
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.setViewportSize({width:320,height:850});await page.goto('/leadiq-demo');
  await page.locator('#iq-spin').focus();await page.keyboard.press('Enter');
  await expect(page.locator('#iq-result')).toContainText('Demo result:',{timeout:1000});
  await expect(page.locator('#iq-spin')).toBeEnabled();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.goto('/__ci/contractor');
  for(const path of ['/contractor/dashboard','/contractor/rewards']){
    await page.goto(path);await page.locator('#iq-spin').click();
    await expect(page.locator('#iq-result')).toContainText('no reward was awarded');
  }
});
