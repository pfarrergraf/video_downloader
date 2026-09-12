#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode

ROOT=Path(__file__).resolve().parent
C={'bg':(11,10,18),'card':(38,31,54),'text':(248,245,238),'muted':(183,174,194),'gold':(221,188,111),'coral':(255,92,122),'teal':(34,224,201)}
F={'default':('/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf','/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf'),'ar':('/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf','/usr/share/fonts/truetype/noto/NotoSansArabic-Bold.ttf'),'ja':('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'),'zh':('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc')}

def font(lang,size,bold=False):
 p=Path(F.get(lang,F['default'])[1 if bold else 0])
 if not p.exists(): p=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
 return ImageFont.truetype(str(p),size)

def background(size):
 im=Image.new('RGB',size,C['bg']); w,h=size; layer=Image.new('RGBA',size,(0,0,0,0)); d=ImageDraw.Draw(layer)
 d.ellipse((-w*.25,-h*.2,w*.65,h*.48),fill=(*C['coral'],65)); d.ellipse((w*.55,h*.55,w*1.25,h*1.2),fill=(*C['teal'],42))
 return Image.alpha_composite(im.convert('RGBA'),layer.filter(ImageFilter.GaussianBlur(max(35,min(size)//9)))).convert('RGB')

def wrap(d,text,f,maxw):
 units=list(text) if ' ' not in text else text.split(); sep='' if ' ' not in text else ' '; out=[]; cur=''
 for u in units:
  test=u if not cur else cur+sep+u
  if cur and d.textbbox((0,0),test,font=f)[2]>maxw: out.append(cur); cur=u
  else: cur=test
 if cur: out.append(cur)
 return out

def fitted(d,text,lang,maxw,start=70,bold=True,maxlines=4):
 for size in range(start,21,-2):
  f=font(lang,size,bold); lines=wrap(d,text,f,maxw)
  if len(lines)<=maxlines: return f,lines
 return font(lang,22,bold),wrap(d,text,font(lang,22,bold),maxw)

def draw_lines(d,x,y,vals,f,fill,rtl=False,center=False,gap=6):
 anchor='ma' if center else ('ra' if rtl else 'la')
 for val in vals:
  d.text((x,y),val,font=f,fill=fill,anchor=anchor,direction='rtl' if rtl else 'ltr'); y+=int(f.size*1.25)+gap
 return y

def brand(d,x=60,y=55):
 d.rounded_rectangle((x,y,x+70,y+70),16,fill=(18,16,29),outline=(80,65,97),width=2); d.line((x+35,y+15,x+35,y+42),fill=C['coral'],width=7); d.line((x+19,y+33,x+35,y+52,x+51,y+33),fill=C['coral'],width=7,joint='curve'); d.rounded_rectangle((x+20,y+57,x+52,y+64),3,fill=C['teal']); d.text((x+90,y+36),'DownloadThat',font=font('default',34,True),fill=C['text'],anchor='lm')

def phone(im,L,lang,box):
 d=ImageDraw.Draw(im); x1,y1,x2,y2=box; rtl=L['dir']=='rtl'; w=x2-x1
 d.rounded_rectangle(box,w//10,fill=(8,7,14),outline=(96,78,118),width=5); d.rounded_rectangle((x1+25,y1+35,x2-25,y2-35),w//13,fill=(18,15,29)); brand(d,x1+55,y1+55)
 x=x2-70 if rtl else x1+70; a='ra' if rtl else 'la'; d.text((x,y1+225),L['feed'],font=font(lang,25,True),fill=C['text'],anchor=a,direction='rtl' if rtl else 'ltr')
 for i,step in enumerate(L['steps']):
  y=y1+285+i*145; d.rounded_rectangle((x1+55,y,x2-55,y+105),24,fill=C['card'],outline=(88,72,108),width=2); bx=x2-105 if rtl else x1+105; d.ellipse((bx-30,y+22,bx+30,y+82),fill=(C['coral'],C['gold'],C['teal'])[i]); d.text((bx,y+53),str(i+1),font=font('default',24,True),fill=(8,7,14),anchor='mm'); tx=x2-165 if rtl else x1+165; f,ls=fitted(d,step,lang,w-250,29,True,2); draw_lines(d,tx,y+53-(len(ls)-1)*15,ls,f,C['text'],rtl,gap=0)
 d.rounded_rectangle((x1+55,y2-155,x2-55,y2-65),28,fill=C['gold']); f,ls=fitted(d,L['cta'],lang,w-180,30,True,2); draw_lines(d,(x1+x2)//2,y2-110-(len(ls)-1)*14,ls,f,(8,7,14),rtl,True,0)

def disclosure(d,L,lang,w,y):
 rtl=L['dir']=='rtl'; f,ls=fitted(d,L['disclosure'],lang,w-120,20,False,2); draw_lines(d,w-60 if rtl else 60,y,ls,f,C['muted'],rtl)

def render_story(L,lang,out):
 im=background((1080,1920)); d=ImageDraw.Draw(im); brand(d); rtl=L['dir']=='rtl'; x=1020 if rtl else 60; f,ls=fitted(d,L['headline'],lang,960,88,True,4); y=draw_lines(d,x,230,ls,f,C['text'],rtl); d.rounded_rectangle((60,y+15,1020,y+25),5,fill=C['coral']); f,ls=fitted(d,L['body'],lang,960,40,False,4); draw_lines(d,x,y+65,ls,f,C['muted'],rtl); phone(im,L,lang,(215,620,865,1455)); d.rounded_rectangle((60,1570,1020,1710),35,fill=C['gold']); f,ls=fitted(d,L['cta'],lang,860,45,True,2); draw_lines(d,540,1640-(len(ls)-1)*20,ls,f,(8,7,14),rtl,True,0); disclosure(d,L,lang,1080,1805); im.save(out,optimize=True)

def render_feed(L,lang,out):
 im=background((1080,1350)); d=ImageDraw.Draw(im); brand(d); rtl=L['dir']=='rtl'; x=1020 if rtl else 60; f,ls=fitted(d,L['feed'],lang,960,72,True,3); y=draw_lines(d,x,175,ls,f,C['text'],rtl); f,ls=fitted(d,L['body'],lang,960,31,False,4); draw_lines(d,x,y+20,ls,f,C['muted'],rtl); phone(im,L,lang,(600,440,1010,1110));
 for y,a,b in ((520,L['commission'],L['review']),(750,L['payout'],L['partner_cta'])):
  d.rounded_rectangle((60,y,550,y+180),28,fill=C['card']); f,ls=fitted(d,a,lang,420,31,True,3); yy=draw_lines(d,510 if rtl else 100,y+45,ls,f,C['gold'],rtl); f,ls=fitted(d,b,lang,420,22,False,3); draw_lines(d,510 if rtl else 100,yy+8,ls,f,C['muted'],rtl)
 disclosure(d,L,lang,1080,1265); im.save(out,optimize=True)

def render_thumb(L,lang,out):
 im=background((1280,720)); d=ImageDraw.Draw(im); brand(d,40,35); rtl=L['dir']=='rtl'; f,ls=fitted(d,L['thumbnail'],lang,700,80,True,4); draw_lines(d,760 if rtl else 40,205,ls,f,C['text'],rtl); phone(im,L,lang,(820,65,1215,680)); im.save(out,optimize=True)

def render_card(L,lang,cfg,out):
 im=background((1080,1350)); d=ImageDraw.Draw(im); brand(d); rtl=L['dir']=='rtl'; x=1020 if rtl else 60; f,ls=fitted(d,L['creator'],lang,960,60,True,3); y=draw_lines(d,x,175,ls,f,C['text'],rtl); d.text((x,y+10),cfg['creator_name'],font=font(lang,42,True),fill=C['gold'],anchor='ra' if rtl else 'la',direction='rtl' if rtl else 'ltr'); d.rounded_rectangle((60,420,1020,1030),38,fill=C['card'],outline=C['gold'],width=4); qr=qrcode.make(cfg['affiliate_link']).convert('RGB').resize((450,450)); im.paste(qr,(315,500)); d.text((540,985),cfg['affiliate_code'],font=font('default',38,True),fill=C['text'],anchor='mm'); d.rounded_rectangle((60,1090,1020,1215),30,fill=C['gold']); f,ls=fitted(d,L['cta'],lang,850,38,True,2); draw_lines(d,540,1152-(len(ls)-1)*17,ls,f,(8,7,14),rtl,True,0); disclosure(d,L,lang,1080,1270); im.save(out,optimize=True)

def render_flyer(L,lang,cfg,png,pdf):
 im=background((1654,2339)); d=ImageDraw.Draw(im); brand(d,95,80); rtl=L['dir']=='rtl'; x=1559 if rtl else 95; f,ls=fitted(d,L['partner'],lang,1460,94,True,4); y=draw_lines(d,x,290,ls,f,C['text'],rtl); f,ls=fitted(d,L['partner_body'],lang,1460,39,False,5); draw_lines(d,x,y+35,ls,f,C['muted'],rtl); phone(im,L,lang,(1010,720,1535,1545));
 for i,(a,b) in enumerate(((L['commission'],L['review']),(L['payout'],L['disclosure']),(L['feed'],' → '.join(L['steps'])))):
  top=780+i*300; d.rounded_rectangle((95,top,920,top+250),34,fill=C['card']); f,ls=fitted(d,a,lang,700,42,True,3); yy=draw_lines(d,870 if rtl else 145,top+50,ls,f,C['gold'],rtl); f,ls=fitted(d,b,lang,700,27,False,4); draw_lines(d,870 if rtl else 145,yy+15,ls,f,C['muted'],rtl)
 d.rounded_rectangle((95,1745,1559,1960),38,fill=C['gold']); f,ls=fitted(d,L['partner_cta'],lang,1320,55,True,2); draw_lines(d,827,1850-(len(ls)-1)*24,ls,f,(8,7,14),rtl,True,0); d.text((827,2040),cfg['contact_email'],font=font('default',28),fill=C['muted'],anchor='mm'); f,ls=fitted(d,L['legal'],lang,1460,23,False,3); draw_lines(d,x,2180,ls,f,C['muted'],rtl); im.save(png,optimize=True); im.save(pdf,'PDF',resolution=150)

def render_video(frames,out):
 if not shutil.which('ffmpeg'): return
 temp=out.parent/'.gpt_frames'; temp.mkdir(exist_ok=True); rows=[]
 for i,p in enumerate(frames):
  q=temp/f'{i}.png'; Image.open(p).save(q); rows += [f"file '{q}'",'duration 3']
 rows.append(f"file '{temp/(str(len(frames)-1)+'.png')}'"); (temp/'list.txt').write_text('\n'.join(rows))
 subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(temp/'list.txt'),'-f','lavfi','-i','anullsrc=channel_layout=stereo:sample_rate=48000','-vf','fps=15,format=yuv420p','-c:v','libx264','-preset','ultrafast','-crf','27','-c:a','aac','-shortest','-movflags','+faststart',str(out)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); shutil.rmtree(temp)

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--config',type=Path,default=ROOT/'gpt_config.json'); ap.add_argument('--out',type=Path,default=ROOT.parent/'gpt_outputs'); ap.add_argument('--languages',nargs='*'); args=ap.parse_args(); cfg=json.loads(args.config.read_text()); locales=json.loads((ROOT/'gpt_locales/gpt_locales.json').read_text()); langs=args.languages or cfg['languages']
 for lang in langs:
  L=locales[lang]; base=args.out/f'gpt_{lang}'; images=base/'gpt_images'; videos=base/'gpt_video'; pdf=base/'gpt_pdf'; copy=base/'gpt_copy'; [p.mkdir(parents=True,exist_ok=True) for p in (images,videos,pdf,copy)]
  story=images/f'gpt_{lang}_story_1080x1920.png'; feed=images/f'gpt_{lang}_feed_1080x1350.png'; thumb=images/f'gpt_{lang}_youtube_thumbnail_1280x720.png'; card=images/f'gpt_{lang}_creator_card_1080x1350.png'; flyer=images/f'gpt_{lang}_recruitment_flyer_a4.png'; render_story(L,lang,story); render_feed(L,lang,feed); render_thumb(L,lang,thumb); render_card(L,lang,cfg,card); render_flyer(L,lang,cfg,flyer,pdf/f'gpt_{lang}_recruitment_flyer_a4.pdf'); (copy/f'gpt_{lang}_copy_pack.md').write_text(f"# {L['name']}\n\n{L['body']}\n\n{L['disclosure']}\n\n{L['legal']}\n",encoding='utf-8'); (videos/f'gpt_{lang}_creator_reel_12s.srt').write_text(f"1\n00:00:00,000 --> 00:00:04,000\n{L['body']}\n\n2\n00:00:04,000 --> 00:00:08,000\n{' → '.join(L['steps'])}\n\n3\n00:00:08,000 --> 00:00:12,000\n{L['cta']}\n",encoding='utf-8'); render_video([story,feed,card],videos/f'gpt_{lang}_creator_reel_12s_1080x1920.mp4')
 print(json.dumps({'languages':langs,'output':str(args.out)},ensure_ascii=False))
if __name__=='__main__': main()
