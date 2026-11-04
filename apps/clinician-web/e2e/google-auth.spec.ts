import {test,expect} from './fixtures/offline';

// Requires the isolated simulated-provider server; never run this against Google
// or a hosted production deployment. Cryptographic checks are separate backend tests.
test('Google session bootstrap, sign-out and read-only investor workflow',async({page})=>{
 let account='clinician';
 await page.route('**/v1/auth/login',async route=>{
  const response=await route.fetch({maxRedirects:0});
  const state=new URL(response.headers().location).searchParams.get('state');
  await route.fulfill({response,status:302,headers:{...response.headers(),location:`http://127.0.0.1:8003/v1/auth/callback?state=${encodeURIComponent(state!)}&code=${account}`}});
 });
 await page.goto('/');await expect(page.getByLabel('Access key')).toHaveCount(0);
 await page.getByRole('button',{name:'Sign in with Google Workspace'}).click();
 await expect(page.getByRole('button',{name:'New encounter',exact:false})).toBeEnabled();
 await page.getByRole('button',{name:'Open synthetic example',exact:false}).click();
 await expect(page.getByRole('heading',{name:'Source transcript'})).toBeVisible();
 await page.getByRole('button',{name:'Sign out',exact:true}).click();
 await expect(page.getByRole('button',{name:'Sign in with Google Workspace'})).toBeVisible();
 expect((await page.request.get('/v1/session')).status()).toBe(401);
 account='viewer';await page.getByRole('button',{name:'Sign in with Google Workspace'}).click();
 await expect(page.getByText('INVESTOR · READ ONLY',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'New encounter',exact:false})).toBeDisabled();
 await page.locator('.encounter-item').first().click();
 await expect(page.getByLabel('Transcript segment 1')).toBeDisabled();
 await expect(page.getByRole('button',{name:'Save source review',exact:true})).toBeDisabled();
 const csrf=(await(await page.request.get('/v1/auth/session')).json()).csrf_token;
 const forbidden=await page.request.post('/v1/demo',{headers:{Origin:'http://127.0.0.1:8003','X-CSRF-Token':csrf}});
 expect(forbidden.status()).toBe(403);expect((await forbidden.json()).code).toBe('read_only_account');
 await page.reload();await expect(page.getByText('INVESTOR · READ ONLY',{exact:true})).toBeVisible();
});
