import {test as base,expect,type Page,type Route} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const repositoryRoot=resolve(dirname(fileURLToPath(import.meta.url)),'../../../..');
export const localTestKey=process.env.MED_TRANSCRIPT_TEST_KEY||JSON.parse(readFileSync(resolve(repositoryRoot,'data/local-config.json'),'utf8')).access_key;
export const testOutputPath=(path:string)=>resolve(process.env.MED_TRANSCRIPT_TEST_OUTPUT_DIR||repositoryRoot,path);

export const test=base.extend<{offlineNetwork:void}>({
 offlineNetwork:[async({context,baseURL},use)=>{
  const local=(host:string)=>host==='localhost'||host==='127.0.0.1'||host==='[::1]';
  if(!baseURL||!local(new URL(baseURL).hostname))throw new Error('Browser tests require an isolated loopback server.');
  const blocked:string[]=[];
  const guard=async(route:Route)=>{
   const url=new URL(route.request().url());
   if(['http:','https:'].includes(url.protocol)&&!local(url.hostname)){
    blocked.push(url.origin);await route.abort('blockedbyclient');return;
   }
   await route.fallback();
  };
  await context.route('**/*',guard);
  await use();
  await context.unroute('**/*',guard);
  expect(blocked,'Unexpected non-loopback application traffic was denied.').toEqual([]);
 },{auto:true}],
});
export {expect};
export type {Page} from '@playwright/test';

export async function expectNoHorizontalOverflow(page:Page){
 const layout=await page.evaluate(()=>({viewport:window.innerWidth,document:document.documentElement.scrollWidth,wideElements:[...document.querySelectorAll('body *')].map(element=>{const rect=element.getBoundingClientRect();return {tag:element.tagName.toLowerCase(),className:typeof element.className==='string'?element.className.slice(0,80):'',left:Math.round(rect.left),right:Math.round(rect.right),width:Math.round(rect.width),ancestors:(()=>{const rows=[];let node:Element|null=element;for(let depth=0;node&&depth<5;depth++,node=node.parentElement){const box=node.getBoundingClientRect(),css=getComputedStyle(node);rows.push({tag:node.tagName.toLowerCase(),className:typeof node.className==='string'?node.className.slice(0,60):'',left:Math.round(box.left),right:Math.round(box.right),width:Math.round(box.width),minWidth:css.minWidth,display:css.display,flex:css.flex,grid:css.gridTemplateColumns,position:css.position,right:css.right,marginRight:css.marginRight,flexShrink:css.flexShrink,transform:css.transform});}return rows;})()};}).filter(element=>element.width>0&&element.right>window.innerWidth+1&&element.right<document.documentElement.scrollWidth+1).sort((a,b)=>b.right-a.right).slice(0,12),layout:['body','.app-shell','.sidebar','main','.content','.note-review-layout','.note-grid','.scribe-grid','.source-context'].map(selector=>{const element=document.querySelector(selector);if(!element)return{selector,missing:true};const rect=element.getBoundingClientRect(),style=getComputedStyle(element);return{selector,left:Math.round(rect.left),right:Math.round(rect.right),width:Math.round(rect.width),clientWidth:element.clientWidth,scrollWidth:element.scrollWidth,minWidth:style.minWidth,overflowX:style.overflowX,marginLeft:style.marginLeft,gridColumns:style.gridTemplateColumns};})}));
 expect(layout.document,`Horizontal overflow at ${layout.viewport}px: ${JSON.stringify({wideElements:layout.wideElements,layout:layout.layout})}`).toBeLessThanOrEqual(layout.viewport);
}
