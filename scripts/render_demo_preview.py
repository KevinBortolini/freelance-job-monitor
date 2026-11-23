"""Render a labelled table preview from the actual generated fictional workbook.

This is not an Excel application screenshot and does not inspect private outputs.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parents[1]

def render():
    book=load_workbook(ROOT/'examples/demo-output.xlsx',read_only=True)
    if book.properties.identifier!='freelance-job-monitor:demo:v1':
        raise SystemExit('Only the explicitly fictional example workbook can be previewed.')
    canvas=Image.new('RGB',(1460,680),'#F4F7FA');draw=ImageDraw.Draw(canvas)
    title=ImageFont.load_default(size=26);font=ImageFont.load_default(size=17);small=ImageFont.load_default(size=15)
    draw.text((28,20),'Freelance Job Monitor - fictional workbook data',font=title,fill='#173D55')
    draw.text((28,59),'Rendered table preview, not an Excel screenshot. Full descriptions, links and explanations are in the workbook.',font=small,fill='#42566A')
    y=102
    widths=[180,390,80,135,490];headers=['Platform','Title','Score','Match','Matched rule details (excerpt)']
    for name in ['Opportunities','Discarded']:
        draw.text((28,y),name,font=title,fill='#173D55');y+=37
        x=28
        for header,width in zip(headers,widths):
            draw.rectangle((x,y,x+width,y+36),fill='#173D55');draw.text((x+8,y+9),header,font=font,fill='white');x+=width
        y+=36
        for i,row in enumerate(book[name].iter_rows(min_row=2,values_only=True)):
            explanation=str(row[8]).split('. ',1)[-1]
            values=[str(row[1]),str(row[2]),str(row[3]),str(row[4]),explanation]
            x=28
            for value,width in zip(values,widths):
                draw.rectangle((x,y,x+width,y+65),fill='#E9F1F7' if i%2==0 else 'white',outline='#CCD7E1')
                # Wrap to pixel width without changing the original workbook content.
                lines=[];line=''
                for word in value.split():
                    candidate=(line+' '+word).strip()
                    if draw.textlength(candidate,font=small)>width-16 and line:lines.append(line);line=word
                    else:line=candidate
                if line:lines.append(line)
                for j,text in enumerate(lines[:3]):draw.text((x+8,y+8+j*17),text,font=small,fill='#173D55')
                x+=width
            y+=65
        y+=26
    draw.text((28,650),'All opportunities are invented. Demo URLs use reserved .example hosts. No email account was accessed.',font=small,fill='#42566A')
    target=ROOT/'docs/demo-workbook-preview.png';canvas.save(target)
    print('Rendered the fictional sample workbook preview; no application screenshot claimed.')

if __name__=='__main__':render()
