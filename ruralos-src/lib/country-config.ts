// A new country requires its own reviewed content pack and emergency contacts.
// UI translation never changes jurisdiction.
export const countryPacks={IN:{name:'India',timeZone:'Asia/Kolkata',speechLocales:['en-IN','hi-IN','te-IN'],emergency:{number:'112',source:'https://112.gov.in/about'},contentStatus:'national_guidance_and_verified_regional_directories'}} as const;
export function countryPack(code:string){return code==='IN'?countryPacks.IN:null}
export function exactCountryVoice<T extends {lang:string}>(voices:T[],locale:string):T|null{return voices.find(v=>v.lang.replace('_','-').toLowerCase()===locale.toLowerCase())??null}
