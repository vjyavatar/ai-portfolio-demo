import {categories,findServices,type DirectoryLanguage} from './service-directory.ts';

export const quickServices=['schemes','aadhaar','land','rail','education','farm'];
const priority=['Benefits','Documents','Health','Farming','Education','Work','Property','Daily essentials','Travel','Money','Help'];
export const homeCategories=[...priority.filter(c=>categories.includes(c)),...categories.filter(c=>c!=='All'&&!priority.includes(c))];
export function launchMatches(query:string,language:DirectoryLanguage){
 return query.trim()?findServices(query.slice(0,250),'All',language):[];
}
export const launchCopy={
 en:{title:'What would you like to do?',hint:'Try “pension”, “land” or “train tickets”',search:'Find my next step',popular:'Start with a common need',results:'Matching services',empty:'No match yet. Try a shorter word, or explore all services.',more:'See all matching services',official:'Guidance + official link',preparation:'Preparation only',note:'No booking or application is submitted here.',guide:'Learn by trying — right here',guideIntro:'Choose a step, listen to the explanation, then try a real service. No account needed.',all:'All services'},
 hi:{title:'आप क्या करना चाहते हैं?',hint:'“पेंशन”, “जमीन” या “रेल टिकट” खोजें',search:'अगला कदम खोजें',popular:'आम ज़रूरत से शुरू करें',results:'मिलती सेवाएँ',empty:'सेवा नहीं मिली। छोटा शब्द या सभी सेवाएँ आज़माएँ।',more:'सभी मिलती सेवाएँ देखें',official:'मार्गदर्शन + आधिकारिक लिंक',preparation:'केवल तैयारी',note:'यहाँ बुकिंग या आवेदन जमा नहीं होता।',guide:'यहीं आज़माकर सीखें',guideIntro:'कदम चुनें, जानकारी सुनें और सेवा आज़माएँ। खाता ज़रूरी नहीं।',all:'सभी सेवाएँ'},
 te:{title:'మీరు ఏమి చేయాలనుకుంటున్నారు?',hint:'“పెన్షన్”, “భూమి” లేదా “రైలు టికెట్” వెతకండి',search:'తదుపరి అడుగు కనుగొనండి',popular:'సాధారణ అవసరంతో ప్రారంభించండి',results:'సరిపోలే సేవలు',empty:'సేవ దొరకలేదు. చిన్న పదం లేదా అన్ని సేవలు ప్రయత్నించండి.',more:'సరిపోలే అన్ని సేవలు చూడండి',official:'మార్గదర్శనం + అధికారిక లింక్',preparation:'తయారీ మాత్రమే',note:'ఇక్కడ బుకింగ్ లేదా దరఖాస్తు సమర్పణ జరగదు.',guide:'ఇక్కడే ప్రయత్నించి నేర్చుకోండి',guideIntro:'దశను ఎంచుకోండి, వివరణ వినండి, సేవను ప్రయత్నించండి. ఖాతా అవసరం లేదు.',all:'అన్ని సేవలు'}
};
