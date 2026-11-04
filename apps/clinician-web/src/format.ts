export const clock = (ms:number) => `${Math.floor(ms/60000)}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}`;
export const title = (text:string) => text.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
