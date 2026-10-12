// Retains the existing site's GA4 property. No ticker, email or research payload is sent.
window.dataLayer=window.dataLayer||[];
function gtag(){window.dataLayer.push(arguments);}
gtag('js',new Date());
gtag('config','G-WW55EQ7ZB8',{allow_google_signals:false,allow_ad_personalization_signals:false});
const script=document.createElement('script');script.async=true;script.src='https://www.googletagmanager.com/gtag/js?id=G-WW55EQ7ZB8';document.head.append(script);
document.addEventListener('click',event=>{const a=event.target.closest('a');if(!a)return;const url=new URL(a.href,location.origin);if(url.origin!==location.origin)return;const destination=url.pathname;const allowed=['/agents','/trading/','/research','/options/india','/options/us','/learn'];if(allowed.includes(destination))gtag('event','workspace_open',{workspace:destination});});
