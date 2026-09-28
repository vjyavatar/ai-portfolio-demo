export type VoicePhase='speaking'|'listening'|'ready';

export function canStartVoiceCapture(consent:boolean,phase:VoicePhase){
 return consent&&phase==='ready';
}

const consentRequired=[
 'Turn on voice permission below before using the microphone.',
 'माइक्रोफ़ोन इस्तेमाल करने से पहले नीचे आवाज़ की अनुमति चालू करें।',
 'మైక్రోఫోన్ ఉపయోగించే ముందు కింద వాయిస్ అనుమతిని ఆన్ చేయండి.'
];
const fallback=[
 'Voice is unavailable. Use the text box or choices below. Nothing was saved.',
 'आवाज़ उपलब्ध नहीं है। नीचे लिखें या विकल्प चुनें। कुछ भी सेव नहीं हुआ।',
 'వాయిస్ అందుబాటులో లేదు. కింద టైప్ చేయండి లేదా ఎంపికను నొక్కండి. ఏదీ సేవ్ కాలేదు.'
];

export function voiceCaptureError(languageIndex:number,error?:unknown,consent=true){
 const language=Math.max(0,Math.min(2,languageIndex));
 if(!consent)return consentRequired[language];
 const detail=error instanceof Error?error.message.trim():'';
 return detail?`${fallback[language]} (${detail})`:fallback[language];
}
