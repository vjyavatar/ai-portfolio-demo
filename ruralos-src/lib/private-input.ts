export function normalizedDigits(value:string){return value.normalize('NFKC').replace(/[०-९]/g,c=>String(c.charCodeAt(0)-2406)).replace(/[౦-౯]/g,c=>String(c.charCodeAt(0)-3174))}
export function hasIdentityNumber(value:string){return /\d{12,}/.test(normalizedDigits(value).replace(/[\s\-–]/g,''))}
