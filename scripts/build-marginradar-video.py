"""Build the silent, captioned product explainer. Requires Pillow and ffmpeg."""
from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import tempfile,subprocess
out=Path(__file__).resolve().parents[1]/'marginradar'; tmp=Path(tempfile.mkdtemp(prefix='marginradar-video-'))
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
def f(n):return ImageFont.truetype(font,n)
scenes=[
('01 / THE PROBLEM','Cheap quote. Hidden costs.', ['Buying for $190 and reselling for $320?', 'That $130 gap is not your profit.'], '$130','price gap before costs'),
('02 / SEE THE WHOLE DEAL','Give every cost a seat.', ['Shipping $20  +  repairs $15', 'Selling fees $25  +  returns $10'], '$70','extra costs and allowances / unit'),
('03 / THE USEFUL ANSWER','A clearer buying decision.', ['Estimated resale $320 - total costs $260', 'Before overhead and tax. Not guaranteed profit.'], '$60','estimated contribution / unit'),
('04 / TRY YOUR OWN QUOTE','Open. Add. Review.', ['Open the free workspace and sign in with ChatGPT.', 'Add offer → enter your quote → Save & analyze.'], '1 quote','start with your real supplier information'),
('05 / THE ADVANTAGE','Know what to ask next.', ['Check condition, warranty, quote age and evidence.', 'Download the review. Verify before shortlisting.'], 'Less guesswork','a repeatable check for every supplier quote'),
('06 / YOUR FIRST MOVE','Bring one quote today.', ['Free pilot. No payment required.', 'Live marketplace and AI connections are not enabled.'], 'Try it free','celesys.ai/marginradar/')]
for i,(tag,title,lines,value,sub) in enumerate(scenes):
 im=Image.new('RGB',(960,540),'#f5f7ef');d=ImageDraw.Draw(im)
 d.rounded_rectangle((620,95,930,438),radius=22,fill='#193c32')
 d.text((45,28),'◉ MarginRadar / CELESYS',font=f(22),fill='#193c32')
 d.text((45,112),tag,font=f(17),fill='#467c56')
 # wrap title and body to fit left panel
 import textwrap
 y=157
 for line in textwrap.wrap(title,25):d.text((45,y),line,font=f(35),fill='#193c32');y+=46
 y+=18
 for line in lines:
  for part in textwrap.wrap(line,44):d.text((45,y),part,font=f(21),fill='#42534b');y+=31
  y+=12
 for j,line in enumerate(textwrap.wrap(value,14)):d.text((642,195+j*45),line,font=f(33),fill='#c5e292')
 for j,line in enumerate(textwrap.wrap(sub,23)):d.text((642,293+j*27),line,font=f(19),fill='#ffffff')
 d.text((45,470),'ILLUSTRATIVE EXAMPLE • USER-SUPPLIED INPUTS • FREE PILOT',font=f(16),fill='#526357')
 for n in range(6):d.rounded_rectangle((45+n*147,512,180+n*147,518),radius=3,fill='#467c56' if n<=i else '#dce3d4')
 im.save(tmp/f'{i:02}.png')
 if i==0:im.save(out/'walkthrough-poster.jpg',quality=85)
(tmp/'list.txt').write_text(''.join("file '"+str(tmp/f'{i:02}.png')+"'\nduration 6\n" for i in range(6))+"file '"+str(tmp/'05.png')+"'\n")
subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(tmp/'list.txt'),'-vf','fps=10,format=yuv420p','-c:v','libx264','-crf','29','-preset','slow','-movflags','+faststart','-t','36',str(out/'walkthrough.mp4')],check=True)
vtt='WEBVTT\n\n'
for i,(_,title,lines,value,sub) in enumerate(scenes):
 def stamp(s):return f'00:{s//60:02}:{s%60:02}.000'
 vtt+=f'{stamp(i*6)} --> {stamp((i+1)*6)}\n{title} {" ".join(lines)} {value}: {sub}.\n\n'
(out/'walkthrough.vtt').write_text(vtt)
print('Video bytes:',(out/'walkthrough.mp4').stat().st_size)
