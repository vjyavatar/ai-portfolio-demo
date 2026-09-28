"""Reproducible 28-second illustrated tutorial, not a recording of provider transactions.
Requires Pillow and ffmpeg. No network calls, personal data or generated testimonials.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import subprocess, math
root=Path(__file__).resolve().parents[1]; out=root/'ruralos/media';out.mkdir(exist_ok=True)
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def f(n,b=False):return ImageFont.truetype(bold if b else font,n)
labels=[('01','CHOOSE YOUR HELP',['Benefits','Documents','Start a business','Travel planning']),('02','ANSWER SIMPLE QUESTIONS',['Choose your region','Choose your situation','Review your answers']),('03','UNDERSTAND YOUR NEXT STEP',['What applies','What to prepare','What to do next','What is still unknown']),('04','CONTINUE WITH CONFIDENCE',['Read the official source','Open the official service','Keep its acknowledgement'])]
proc=subprocess.Popen(['ffmpeg','-y','-loglevel','error','-f','rawvideo','-vcodec','rawvideo','-pix_fmt','rgb24','-s','720x406','-r','12','-i','-','-an','-c:v','libx264','-preset','slow','-crf','29','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'saathi-tour-v1.mp4')],stdin=subprocess.PIPE)
for frame in range(336):
 step=frame//84; phase=(frame%84)/84; number,title,rows=labels[step]
 im=Image.new('RGB',(720,406),'#f6f2e8');d=ImageDraw.Draw(im)
 d.rounded_rectangle((24,24,330,381),24,fill='#173e32'); d.text((48,47),'SAATHI',font=f(19,True),fill='#f4c679')
 d.text((48,96),number,font=f(74,True),fill='#ffffff')
 words=title.split(); y=205;line=''
 for word in words:
  trial=(line+' '+word).strip()
  if d.textlength(trial,font=f(23,True))>255:d.text((48,y),line,font=f(23,True),fill='white');y+=34;line=word
  else:line=trial
 d.text((48,y),line,font=f(23,True),fill='white')
 d.text((48,345),'ILLUSTRATED GUIDE',font=f(12),fill='#cfdfd1')
 d.rounded_rectangle((366,24,688,369),24,fill='white',outline='#bdc9c0',width=2)
 d.text((389,47),'One family. One next step.',font=f(16,True),fill='#173e32')
 for j,row in enumerate(rows):
  yy=91+j*59; active=j==min(len(rows)-1,int(phase*len(rows)))
  d.rounded_rectangle((389,yy,665,yy+46),10,fill='#dceccd' if active else '#f3f4ef')
  d.ellipse((401,yy+13,421,yy+33),fill='#237259' if active else '#7d9188')
  d.text((432,yy+14),row,font=f(15),fill='#173e32')
 for j in range(4):d.rounded_rectangle((378+j*78,386,442+j*78,391),2,fill='#237259' if j<=step else '#cbd3c7')
 if frame==0:im.save(out/'saathi-tour-v1.jpg',quality=85)
 proc.stdin.write(im.tobytes())
proc.stdin.close();assert proc.wait()==0
captions={
'en':['Choose your language. Speak your problem or tap a service. Microphone access is optional.','Answer only the questions needed for guidance. Review and correct your answers. Never enter an OTP or banking PIN here.','Read or listen to the next step. Check what to prepare, the source, region and review date. Guidance is not approval.','Continue on the official service when ready. Applications and payments happen there. Keep its acknowledgement. Saathi does not book or submit for you.'],
'hi':['अपनी भाषा चुनें। समस्या बोलें या सेवा चुनें। माइक्रोफ़ोन वैकल्पिक है।','ज़रूरी सवालों के जवाब दें। विवरण जाँचें और सुधारें। यहाँ OTP या बैंक PIN न दें।','अगला कदम पढ़ें या सुनें। तैयारी, स्रोत, क्षेत्र और समीक्षा तारीख देखें। मार्गदर्शन मंज़ूरी नहीं।','तैयार होने पर आधिकारिक सेवा खोलें। आवेदन और भुगतान वहीं होते हैं। पावती रखें। साथी आपकी ओर से बुकिंग या आवेदन नहीं करता।'],
'te':['మీ భాష ఎంచుకోండి. సమస్య చెప్పండి లేదా సేవ ఎంచుకోండి. మైక్రోఫోన్ ఐచ్ఛికం.','అవసరమైన ప్రశ్నలకు జవాబివ్వండి. వివరాలు చూసి సవరించండి. ఇక్కడ OTP లేదా బ్యాంకు PIN ఇవ్వవద్దు.','తదుపరి అడుగు చదవండి లేదా వినండి. తయారీ, మూలం, ప్రాంతం, సమీక్ష తేదీ చూడండి. మార్గదర్శనం ఆమోదం కాదు.','సిద్ధమైనప్పుడు అధికారిక సేవ తెరవండి. దరఖాస్తులు, చెల్లింపులు అక్కడే. రసీదు ఉంచండి. సాథీ మీ తరఫున బుకింగ్ లేదా దరఖాస్తు చేయదు.']}
for lang,lines in captions.items():
 (out/f'saathi-tour-v1-{lang}.vtt').write_text('WEBVTT\n\n'+'\n\n'.join(f'{i+1}\n00:00:{i*7:02}.000 --> 00:00:{(i+1)*7:02}.000\n{line}' for i,line in enumerate(lines))+'\n')
print('Built tutorial', (out/'saathi-tour-v1.mp4').stat().st_size,'bytes')
