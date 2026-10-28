from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parent.parent/'static'
ROOT.mkdir(exist_ok=True)
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
F=lambda n,b=False:ImageFont.truetype(BOLD if b else FONT,n)
STEPS=[
("1 / 8","INSTALL HAPP","Open Google Play (Android) or App Store (iPhone).","Search: Happ - Proxy Utility. Install the official app.","Do not install unknown or modified APK files.","App Store / Google Play"),
("2 / 8","OPEN DIGITALSERVICES","Visit digitalservices.payapi.uk in your browser.","Sign in with your email and password.","Navigate to My VPN / Linked VPN Accounts.","DigitalServices Dashboard"),
("3 / 8","FIND YOUR SUBSCRIPTION","After approval, find your active VPN account.","Your server, quota and expiry date are shown here.","Tap Copy Subscription Link (not a raw VLESS key).","Copy Subscription Link"),
("4 / 8","OPEN HAPP APP","Launch Happ - Proxy Utility.","On the main screen tap the + (Add) button.","Choose subscription import from clipboard.","+   Add Subscription"),
("5 / 8","IMPORT FROM CLIPBOARD","Allow clipboard/paste access if your phone asks.","Happ will read your copied subscription URL.","Confirm import and wait for the server list.","Import from Clipboard"),
("6 / 8","SELECT YOUR SERVER","Open the newly imported subscription.","Select the available DigitalServices VPN server.","If empty, check the URL and internet connection.","DigitalServices • Server"),
("7 / 8","CONNECT VPN","Tap the connect / power control in Happ.","On first connection approve the system VPN prompt.","Check Happ shows an active connection.","● Connected"),
("8 / 8","READY TO BROWSE","Your DigitalServices VPN is ready.","To renew, keep the original subscription link.","Need help? Use the Website Admin chat bubble.","DigitalServices • Connected")
]
W,H=960,540
frames=[]
for idx,(num,title,a,b,c,screen) in enumerate(STEPS):
 im=Image.new('RGB',(W,H),(10,12,21));d=ImageDraw.Draw(im)
 d.ellipse((480,-230,1200,490),fill=(33,27,71))
 d.text((45,28),"◈ DIGITALSERVICES",font=F(23,True),fill=(179,161,255))
 d.text((44,91),"HAPP SUBSCRIPTION TUTORIAL",font=F(17),fill=(154,142,191))
 d.text((44,132),title,font=F(37,True),fill=(250,249,255))
 d.rounded_rectangle((43,213,541,438),radius=16,fill=(24,27,43),outline=(66,60,91),width=2)
 for i,txt in enumerate((a,b,c)):
  y=230+i*65
  d.ellipse((60,y+5,82,y+27),fill=(147,124,248))
  d.text((66,y+6),str(i+1),font=F(12,True),fill=(13,10,30))
  # wrap to fit left panel
  from textwrap import wrap
  parts=wrap(txt,width=48)
  for j,line in enumerate(parts): d.text((97,y+j*22),line,font=F(16),fill=(226,222,242))
 # Phone mockup right side (stylized illustrative UI)
 d.rounded_rectangle((640,58,888,462),radius=33,fill=(8,10,18),outline=(166,151,235),width=4)
 d.rounded_rectangle((657,87,870,435),radius=19,fill=(25,28,42))
 d.rounded_rectangle((726,67,803,77),radius=5,fill=(44,45,61))
 d.text((682,109),"Happ" if idx in (0,3,4,5,6,7) else "DigitalServices",font=F(19,True),fill=(231,227,255))
 d.line((672,150,857,150),fill=(91,82,131),width=2)
 if idx==0:
  d.rounded_rectangle((685,195,842,272),radius=18,fill=(66,52,113));d.text((735,211),"HAPP",font=F(25,True),fill="white")
 elif idx in (1,2):
  d.rounded_rectangle((675,178,851,281),radius=15,fill=(45,42,77));d.text((692,192),"My VPN",font=F(19,True),fill="white");d.text((692,224),"100 GB • 1 Device",font=F(13),fill=(202,195,224))
 else:
  d.rounded_rectangle((676,179,849,288),radius=14,fill=(45,43,79));d.text((688,196),"DigitalServices",font=F(17,True),fill="white");d.text((688,236),"Subscription",font=F(14),fill=(199,194,225))
 d.rounded_rectangle((678,332,851,379),radius=14,fill=(155,128,247))
 # screen text fitted to phone width
 from textwrap import shorten
 short=shorten(screen,width=20,placeholder="…")
 tw=d.textbbox((0,0),short,font=F(13,True))[2]
 d.text((764-tw//2,348),short,font=F(13,True),fill=(17,12,38))
 d.text((46,477),f"STEP {num}",font=F(18,True),fill=(183,166,255))
 for k in range(8):
  d.rounded_rectangle((315+k*32,489,340+k*32,497),radius=3,fill=(168,145,255) if k<=idx else (54,52,76))
 d.text((650,488),"Illustration • not live app UI",font=F(11),fill=(139,137,157))
 p=ROOT/f'_happ_frame_{idx}.png';im.save(p);frames.append(p)
concat=ROOT/'_happ_concat.txt'
with concat.open('w') as f:
 for p in frames:f.write(f"file '{p.name}'\nduration 5\n")
 f.write(f"file '{frames[-1].name}'\n")
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(concat),'-vf','fps=15,format=yuv420p','-c:v','libx264','-preset','veryfast','-crf','27','-movflags','+faststart',str(ROOT/'happ-guide.mp4')],cwd=ROOT,check=True)
# Optional human-recorded Myanmar narration. Keep the raw audio private.
voice=Path(__file__).resolve().parent.parent/'media'/'happ-voiceover.mp3'
if voice.is_file():
 outfile=ROOT/'happ-guide-with-voice.mp4'
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(ROOT/'happ-guide.mp4'),'-i',str(voice),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','128k','-af','apad','-shortest','-movflags','+faststart',str(outfile)],check=True)
 outfile.replace(ROOT/'happ-guide.mp4')
for p in frames:p.unlink()
concat.unlink()
print('Generated 16:9 detailed Happ tutorial video')
