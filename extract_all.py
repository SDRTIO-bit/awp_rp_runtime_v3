import os
from docx import Document

base = r'F:\12\语英\awp_rp_runtime_v3'
outdir = os.path.join(base, 'extracted')
os.makedirs(outdir, exist_ok=True)

SEP = '=' * 80

def extract_docx(path):
    try:
        doc = Document(path)
        text = '\n'.join([p.text for p in doc.paragraphs if p.text.strip()])
        return text
    except Exception as e:
        return 'ERROR: ' + str(e)

def read_txt(path):
    for enc in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
        try:
            with open(path, 'r', encoding=enc) as f:
                return f.read()
        except:
            continue
    return 'COULD NOT READ'

def process_dir(d, outname):
    result = []
    for root, dirs, files in os.walk(d):
        for f in sorted(files):
            fpath = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            result.append('\n' + SEP + '\nFILE: ' + f + '\n' + SEP + '\n')
            if ext in ('.docx', '.doc'):
                result.append(extract_docx(fpath))
            elif ext == '.txt':
                result.append(read_txt(fpath))
    outpath = os.path.join(outdir, outname)
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result))
    print('Done: ' + outname + ' (' + str(len(result)) + ' sections)')

# Process all directories
dirs = [
    (os.path.join(base, '网文写作', '大纲'), '01_outline.txt'),
    (os.path.join(base, '网文写作', '网文写作基础', '网文写作基础', '写铺垫相关资料'), '02_foreshadowing.txt'),
    (os.path.join(base, '网文写作', '网文写作基础', '网文写作基础', '写爽点相关资料'), '03_coolpoints.txt'),
    (os.path.join(base, '网文写作', '网文写作基础', '网文写作基础', '写冲突相关资料'), '04_conflict.txt'),
    (os.path.join(base, '网文写作', '网文写作基础', '网文写作基础', '写故事相关资料'), '05_story.txt'),
    (os.path.join(base, '网文写作', '网文写作基础', '网文写作基础', '写开篇相关资料'), '06_opening.txt'),
    (os.path.join(base, '网文写作', '写作心得', '飞卢编辑光辉帖子汇总'), '07_feilu.txt'),
    (os.path.join(base, '网文写作', '写作心得', '萌新写作入门篇'), '08_beginner.txt'),
    (os.path.join(base, '网文写作', '拆书专栏'), '09_deconstructed.txt'),
]

for d, name in dirs:
    process_dir(d, name)

print('ALL DONE')
