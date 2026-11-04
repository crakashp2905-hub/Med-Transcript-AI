import {test as base,expect,type Route} from '@playwright/test';

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
