export const feedSources={weather:'https://aviationweather.gov/data/api/',earthquakes:'https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php'};
export type FeedKind=keyof typeof feedSources;
export type Feed={status:'recent'|'stale'|'unavailable';source:string;message:string;scope?:string;retrievedAt:number|null;generatedAt?:number|null;items:{id:string;name:string;observedAt:number;temperatureC?:number;magnitude?:number;outdated?:boolean}[]};
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
export function readFeed(value:unknown,kind:FeedKind,now=Date.now()):Feed{
 const d=value as Feed;
 if(!d||!['recent','stale','unavailable'].includes(d.status)||d.source!==feedSources[kind]||typeof d.message!=='string'||d.message.length>600||!Array.isArray(d.items)||d.items.length>30||!(d.retrievedAt===null||(finite(d.retrievedAt)&&d.retrievedAt>0&&d.retrievedAt<=now+300000)))throw Error('Invalid feed');
 if(d.scope!==undefined&&(typeof d.scope!=='string'||d.scope.length>1000))throw Error('Invalid scope');
 if(d.generatedAt!=null&&(!finite(d.generatedAt)||d.generatedAt<=0||d.generatedAt>now+300000))throw Error('Invalid time');
 if(d.status!=='unavailable'&&d.retrievedAt===null)throw Error('Missing retrieval time');
 const ids=new Set<string>();
 for(const i of d.items){if(!i||typeof i.id!=='string'||ids.has(i.id)||typeof i.name!=='string'||i.name.length>180||!finite(i.observedAt)||i.observedAt<=0||i.observedAt>now+300000||!finite(kind==='weather'?i.temperatureC:i.magnitude))throw Error('Invalid observation');ids.add(i.id)}
 return d;
}
export function feedIsOld(d:Feed,now=Date.now()){
 return !finite(now)||d.status!=='recent'||!d.retrievedAt||now-d.retrievedAt>600000||!!(d.generatedAt&&now-d.generatedAt>900000)||!!(d.items.length&&d.items.every(i=>i.temperatureC!==undefined&&now-i.observedAt>10800000));
}
