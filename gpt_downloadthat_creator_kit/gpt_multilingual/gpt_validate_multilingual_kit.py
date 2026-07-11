#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'gpt_outputs'
LANGS=['de','en','fr','es','it','ar','ja','zh']
EXPECTED={'story':(1080,1920),'feed':(1080,1350),'youtube_thumbnail':(1280,720),'creator_card':(1080,1350),'recruitment_flyer_a4':(1654,2339)}
report={'ok':True,'languages':{}}
for lang in LANGS:
 base=OUT/f'gpt_{lang}'; current={'ok':True,'images':{},'video':{}}
 for kind,size in EXPECTED.items():
  name=f'gpt_{lang}_{kind}_{size[0]}x{size[1]}.png' if kind!='recruitment_flyer_a4' else f'gpt_{lang}_recruitment_flyer_a4.png'
  path=base/'gpt_images'/name
  valid=path.exists() and Image.open(path).size==size
  current['images'][kind]={'ok':valid,'size':Image.open(path).size if path.exists() else None}
  current['ok'] &= valid
 pdf=base/'gpt_pdf'/f'gpt_{lang}_recruitment_flyer_a4.pdf'; current['pdf']=pdf.exists() and pdf.stat().st_size>10000; current['ok'] &= current['pdf']
 mp4=base/'gpt_video'/f'gpt_{lang}_creator_reel_12s_1080x1920.mp4'
 if mp4.exists():
  data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_name,width,height,pix_fmt:format=duration','-of','json',str(mp4)],text=True)); streams=data['streams']; video=next(s for s in streams if s.get('width')); codecs=[s['codec_name'] for s in streams]; duration=float(data['format']['duration']); valid=video['codec_name']=='h264' and video['width']==1080 and video['height']==1920 and video['pix_fmt']=='yuv420p' and 'aac' in codecs and 11.5<=duration<=12.5; current['video']={'ok':valid,'codecs':codecs,'width':video['width'],'height':video['height'],'duration':duration}
 else: current['video']={'ok':False}
 current['ok'] &= current['video']['ok']; report['languages'][lang]=current; report['ok'] &= current['ok']
(ROOT/'gpt_quality_report_multilingual.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'ok':report['ok'],'languages':LANGS},ensure_ascii=False))
raise SystemExit(0 if report['ok'] else 1)
