import {env} from 'cloudflare:workers';
export function database():D1Database{const db=(env as unknown as {DB?:D1Database}).DB;if(!db)throw new Error('Database unavailable');return db;}
export function adminEmails(){return ((env as unknown as {ADMIN_EMAILS?:string}).ADMIN_EMAILS??'').toLowerCase().split(',').map(s=>s.trim()).filter(Boolean)}
export function json(data:unknown,status=200){return Response.json(data,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}})}
export function validOrigin(r:Request){const origin=r.headers.get('origin');return !!origin&&origin===new URL(r.url).origin&&r.headers.get('sec-fetch-site')!=='cross-site'}
export async function limitedText(r:Request,limit:number){const reader=r.body?.getReader();if(!reader)return '';const chunks:Uint8Array[]=[];let size=0;while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>limit){await reader.cancel();throw new Error('Request too large')}chunks.push(value)}const all=new Uint8Array(size);let offset=0;for(const c of chunks){all.set(c,offset);offset+=c.byteLength}return new TextDecoder().decode(all)}
