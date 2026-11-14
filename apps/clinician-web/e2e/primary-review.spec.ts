import {test,expect,localTestKey} from './fixtures/offline';

test('default encounter review presents the source and clinical note side by side',async({page})=>{
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'Welcome to your workspace'})).toBeVisible();
 await page.getByLabel('Access key').fill(localTestKey);
 await page.getByRole('button',{name:'Open workspace',exact:false}).click();
 await page.getByRole('button',{name:'Open synthetic example',exact:false}).click();

 const review=page.getByRole('region',{name:'Unified source and note review'});
 await expect(review).toBeVisible();
 const source=review.getByRole('heading',{name:'Source transcript'});
 const note=review.getByRole('heading',{name:'Clinical facts'});
 await expect(source).toBeVisible();
 await expect(note).toBeVisible();
 await expect(review.getByRole('search',{name:'Search transcript'})).toBeVisible();
 const [sourceBox,noteBox]=await Promise.all([source.boundingBox(),note.boundingBox()]);
 expect(sourceBox).not.toBeNull();expect(noteBox).not.toBeNull();
 expect(noteBox!.x).toBeGreaterThan(sourceBox!.x);
 await expect(review.locator('audio').first()).toBeVisible();

 await page.keyboard.press('Alt+1');
 await expect(page.getByRole('region',{name:'Unified source and note review'})).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'Source transcript'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Clinical facts'})).toHaveCount(0);
 await page.getByLabel('I confirmed supported English.').check();
 await page.getByLabel('I reviewed source completeness.').check();
 await page.getByLabel('Review basis').fill('Synthetic end-to-end keyboard review.');
 await page.keyboard.press('Control+s');
 await expect(page.locator('.notice')).toContainText('Saved as a new source version.');
 await page.keyboard.press('Alt+2');
 await expect(page.getByRole('heading',{name:'Clinical facts'})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Source transcript'})).toHaveCount(0);
 await page.keyboard.press('Alt+0');
 await expect(page.getByRole('region',{name:'Unified source and note review'})).toBeVisible();
});
