import {test,expect} from './fixtures/offline';
import {request} from '@playwright/test';

// Requires the isolated simulated-provider server; never run this against Google
// or a hosted production deployment. Cryptographic checks are separate backend tests.
test('Google session bootstrap, sign-out and read-only investor workflow',async({page,baseURL})=>{
 const origin=new URL(baseURL!).origin;
 let account='clinician';
 await page.route('**/v1/auth/login',async route=>{
  const response=await route.fetch({maxRedirects:0});
  const state=new URL(response.headers().location).searchParams.get('state');
  await route.fulfill({response,status:302,headers:{...response.headers(),location:`${origin}/v1/auth/callback?state=${encodeURIComponent(state!)}&code=${account}`}});
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
 const forbidden=await page.request.post('/v1/demo',{headers:{Origin:origin,'X-CSRF-Token':csrf}});
 expect(forbidden.status()).toBe(403);expect((await forbidden.json()).code).toBe('read_only_account');
 await page.reload();await expect(page.getByText('INVESTOR · READ ONLY',{exact:true})).toBeVisible();
});

test('workspace administrator provisions a scribe without encounter access and removal revokes its session',async({page,baseURL,browser})=>{
 const origin=new URL(baseURL!).origin;
 let account='administrator';
 await page.route('**/v1/auth/login',async route=>{
  const response=await route.fetch({maxRedirects:0});
  const state=new URL(response.headers().location).searchParams.get('state');
  await route.fulfill({response,status:302,headers:{...response.headers(),location:`${origin}/v1/auth/callback?state=${encodeURIComponent(state!)}&code=${account}`}});
 });
 await page.goto('/');await page.getByRole('button',{name:'Sign in with Google Workspace'}).click();
 await expect(page.getByRole('heading',{name:'Workspace accounts'})).toBeVisible();
 await page.getByRole('button',{name:'Run local diagnostics'}).click();
 const diagnostics=page.getByRole('status',{name:'Local diagnostic results'});
 await expect(diagnostics).toContainText('Patient or encounter data: not included.');
 await expect(diagnostics).toContainText('Model inference: not run.');
 await expect(diagnostics).toContainText('External services: not contacted.');
 await expect(diagnostics).toContainText('Configured storage access: database available · assets available');
 await expect(diagnostics.getByRole('heading',{name:'Recommended follow-up'})).toBeVisible();
 await expect(diagnostics).toContainText('Backup and restore have not been validated here.');
 await expect(diagnostics).toContainText('test restore in a separate recovery directory.');
 const hiddenEncounters=await page.request.get('/v1/encounters');
 expect(hiddenEncounters.status()).toBe(403);
 expect((await hiddenEncounters.json()).code).toBe('administrator_scope_required');

 // Keep the browser journey repeatable against the same isolated fixture database.
 const priorInvitation=page.getByRole('row').filter({hasText:'scribe@example.org'});
 if(await priorInvitation.count()){
  await priorInvitation.getByRole('button',{name:'Remove'}).click();
  await expect(priorInvitation).toHaveCount(0);
 }

 await page.getByLabel('Email').fill('scribe@example.org');
 await page.getByLabel('Role').selectOption('scribe');
 await page.getByLabel('Assigned physician').selectOption({label:'clinician@example.org'});
 await page.getByRole('button',{name:'Add invitation'}).click();
 await expect(page.getByText('Invitation added. Access begins after the invited account signs in.')).toBeVisible();
 const invitedRow=page.getByRole('row').filter({hasText:'scribe@example.org'});
 await expect(invitedRow).toContainText('scribe');
 await expect(invitedRow).toContainText('clinician@example.org');
 await expect(page.getByText(/user_invited/).first()).toBeVisible();

 await page.getByRole('button',{name:'Sign out'}).click();
 account='scribe';
 await page.getByRole('button',{name:'Sign in with Google Workspace'}).click();
 await expect(page.getByText('CLINICIAN WORKSPACE',{exact:true})).toBeVisible();
 const scribeSession=await(await page.request.get('/v1/session')).json();
 expect(scribeSession.role).toBe('scribe');
 expect(scribeSession.user_id).not.toBe(scribeSession.clinician_id);
 const csrf=(await(await page.request.get('/v1/auth/session')).json()).csrf_token;
 const demo=await page.request.post('/v1/demo',{headers:{Origin:origin,'X-CSRF-Token':csrf,'Idempotency-Key':crypto.randomUUID()}});
 expect(demo.status()).toBe(201);
 const encounterId=(await demo.json()).encounter_id;
 const forbiddenApproval=await page.request.post(`/v1/encounters/${encounterId}/approvals`,{
  headers:{Origin:origin,'X-CSRF-Token':csrf,'Idempotency-Key':crypto.randomUUID()},
  data:{note_version_id:crypto.randomUUID(),expected_note_sha256:'a'.repeat(64),verification_report_id:crypto.randomUUID(),patient_identifiers_reconfirmed:true},
 });
 expect(forbiddenApproval.status()).toBe(403);
 expect((await forbiddenApproval.json()).code).toBe('physician_approval_required');
 const scribeCookie=(await page.context().cookies()).find(cookie=>cookie.name==='med_session');
 expect(scribeCookie).toBeDefined();

 const adminContext=await browser.newContext({baseURL:origin});
 const adminPage=await adminContext.newPage();
 await adminPage.route('**/v1/auth/login',async route=>{
  const response=await route.fetch({maxRedirects:0});
  const state=new URL(response.headers().location).searchParams.get('state');
  await route.fulfill({response,status:302,headers:{...response.headers(),location:`${origin}/v1/auth/callback?state=${encodeURIComponent(state!)}&code=administrator`}});
 });
 await adminPage.goto('/');await adminPage.getByRole('button',{name:'Sign in with Google Workspace'}).click();
 await expect(adminPage.getByRole('heading',{name:'Workspace accounts'})).toBeVisible();
 const accountRow=adminPage.getByRole('row').filter({hasText:'scribe@example.org'});
 await accountRow.getByRole('button',{name:'Remove'}).click();
 await expect(accountRow).toHaveCount(0);
 await expect(adminPage.getByText(/user_removed/).first()).toBeVisible();
 const staleSession=await request.newContext({baseURL:origin,extraHTTPHeaders:{Cookie:`med_session=${scribeCookie!.value}`}});
 const revoked=await staleSession.get('/v1/session');
 expect(revoked.status()).toBe(401);
 await staleSession.dispose();await adminContext.close();
});
