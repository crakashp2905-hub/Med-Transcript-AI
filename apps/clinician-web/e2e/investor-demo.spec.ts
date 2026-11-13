import {test,expect} from './fixtures/offline';

test('investor preview is read-only, synthetic and independent of sign-in',async({page})=>{
 const apiRequests:string[]=[];
 page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/v1/'))apiRequests.push(request.url());});
 await page.goto('/investor-demo');
 await expect(page.getByRole('heading',{name:'Keep every proposed statement connected to its source.'})).toBeVisible();
 await expect(page.getByText('Investor preview · read only · no sign-in')).toBeVisible();
 await expect(page.getByRole('note')).toContainText('does not process audio');
 await expect(page.getByRole('region',{name:'Scripted source excerpt'})).toBeVisible();
 await expect(page.getByRole('region',{name:'Evidence-linked note preview'})).toContainText('UNAPPROVED DEMONSTRATION');
 expect(apiRequests).toEqual([]);
});
