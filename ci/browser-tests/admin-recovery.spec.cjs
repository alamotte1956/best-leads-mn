const {test,expect}=require('@playwright/test');
test('administrator recovery is discoverable and keeps account details private',async({page})=>{
  await page.goto('/admin/login');
  await page.getByRole('link',{name:'Forgot administrator password?',exact:true}).click();
  await expect(page).toHaveURL(/\/admin\/forgot-password$/);
  await expect(page.locator('body')).toContainText('configured master administrator email');
  await page.getByLabel('Email address',{exact:true}).fill('unknown-admin@example.com');
  await page.getByRole('button',{name:'Email reset link',exact:true}).click();
  await expect(page.locator('body')).toContainText('If an eligible account or request matches');
  await page.getByRole('link',{name:'Back to administrator sign in',exact:true}).click();
  await expect(page).toHaveURL(/\/admin\/login$/);
  const invalid=await page.goto('/admin/reset-password/invalid-link');
  expect(invalid.status()).toBe(400);
  await expect(page.locator('body')).toContainText('invalid, expired or already used');
  await page.getByRole('link',{name:'Request a new link',exact:true}).click();
  await expect(page).toHaveURL(/\/admin\/forgot-password$/);
});
