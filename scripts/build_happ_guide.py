from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parent.parent/'static'
ROOT.mkdir(exist_ok=True)
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
steps=[
('01','DOWNLOAD HAPP','Install Happ - Proxy Utility','Android: Google Play / APK','iPhone: App Store'),
('02','COPY YOUR LINK','Open DigitalServices dashboard','Tap Copy Subscription Link','Your link stays private'),
('03','OPEN HAPP APP','Launch Happ on your device','Tap + or Import','Choose import from clipboard'),
('04','IMPORT SUBSCRIPTION','Paste your copied subscription URL','Confirm and save the subscription','Wait for the server list'),
('05','CONNECT SECURELY','Select the imported server','Tap the connection button','Allow the VPN permission prompt'),
('06','YOU ARE CONNECTED','Your DigitalServices VPN is ready','If needed, update subscription','Support: DigitalServices chat')]
W,H=540,960
frames=[]
for idx,(num,title,*lines) in enumerate(steps):
 im=Image.new('RGB',(W,H),(9,11,21));d=ImageDraw.Draw(im)
 d.ellipse((-200,-230,570,540),fill=(25,21,51))
 d.rounded_rectangle((35,65,W-35,145),radius=23,fill=(29,27,51),outline=(114,91,205),width=2)
 d.text((60,83),'DigitalServices',font=ImageFont.truetype(BOLD,30),fill=(202,190,255))
 d.text((40,210),'HAPP SETUP GUIDE',font=ImageFont.truetype(BOLD,21),fill=(160,143,255))
 d.text((38,254),num,font=ImageFont.truetype(BOLD,130),fill=(119,99,205))
 d.text((42,431),title,font=ImageFont.truetype(BOLD,35),fill=(245,245,251))
 for j,line in enumerate(lines):
  y=518+j*91
  d.rounded_rectangle((37,y,503,y+77),radius=15,fill=(28,31,48),outline=(65,61,87))
  d.text((55,y+23),line,font=ImageFont.truetype(FONT,19),fill=(224,221,244))
 d.text((42,872),'STEP '+num+'  /  06',font=ImageFont.truetype(BOLD,21),fill=(187,176,241))
 for j in range(6):
  d.rounded_rectangle((310+j*32,886,333+j*32,895),radius=4,fill=(151,123,255) if j<=idx else (60,58,79))
 p=ROOT/f'frame_{idx}.png';im.save(p);frames.append(p)
concat=ROOT/'concat.txt'
with concat.open('w') as f:
 for p in frames:f.write(f"file '{p.name}'\nduration 2.9\n")
 f.write(f"file '{frames[-1].name}'\n")
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),'-vf','fps=15,format=yuv420p','-c:v','libx264','-preset','veryfast','-crf','28','-movflags','+faststart',str(ROOT/'happ-guide.mp4')],cwd=ROOT,check=True)
for p in frames:p.unlink()
concat.unlink()
print('Generated static/happ-guide.mp4')
