import {z} from 'zod';
import {hasIdentityNumber} from './private-input.ts';
import {regions} from './regions.ts';
import {services} from './services.ts';
const date=z.string().regex(/^\d{4}-\d{2}-\d{2}$/).refine(s=>!isNaN(new Date(s+'T12:00:00Z').getTime())&&new Date(s+'T12:00:00Z').toISOString().slice(0,10)===s,'Choose a valid date');
const safe=z.string().trim().min(1).max(120).refine(v=>!hasIdentityNumber(v),'Do not include Aadhaar numbers');
export const recordInput=z.discriminatedUnion('kind',[
 z.object({id:z.string().uuid(),kind:z.literal('watchlist'),payload:z.object({symbol:z.string().trim().regex(/^[A-Z0-9&.\-]{1,24}$/),exchange:z.enum(['NSE','BSE']),note:z.string().trim().max(300)})}),
 z.object({id:z.string().uuid(),kind:z.literal('task'),payload:z.object({serviceId:z.string().refine(v=>services.some(s=>s.id===v),'Unknown service'),title:safe,state:z.string().refine(v=>regions.includes(v as any),'Unknown state'),done:z.boolean()})}),
 z.object({id:z.string().uuid(),kind:z.literal('member'),payload:z.object({name:safe,age:z.number().int().min(0).max(120),relation:z.enum(['Self','Parent','Spouse','Child','Other']),consent:z.literal(true)})}),
 z.object({id:z.string().uuid(),kind:z.literal('document'),payload:z.object({title:safe,ready:z.boolean(),expires:date.nullable()})}),
 z.object({id:z.string().uuid(),kind:z.literal('reminder'),payload:z.object({title:safe,due:date,done:z.boolean(),channel:z.literal('in_app')})}),
 z.object({id:z.string().uuid(),kind:z.literal('support'),payload:z.object({topic:z.enum(['Pension guidance','Document help','Other guidance','Complaint','Product feedback']),note:z.string().trim().max(500).refine(v=>!hasIdentityNumber(v),'Do not include Aadhaar numbers'),consent:z.literal(true),feedback:z.object({understanding:z.enum(['clear','unclear']),outcome:z.enum(['completed','not_completed','blocked']),region:z.string().refine(v=>regions.includes(v as any)),language:z.enum(['en','hi','te'])}).strict().optional()})})
]);
