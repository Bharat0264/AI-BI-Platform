"""Build a deterministic source-only local release candidate from explicit paths."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
DIRECTORIES={'app','aura','benchmark','docs','experiments','frontend','persistence','scripts','tests'}
SUFFIXES={'.py','.md','.json','.html','.js','.css','.txt','.yaml','.yml'}
ROOT_FILES={'AGENTS.md','README.md','.env.example','.gitignore','requirements.txt','requirements-dev.txt','constraints-local-win-py310.txt','constraints-local-win-py312.txt','.python-version','pytest.ini','render.yaml','start.py','server.py','security.py','authentication.py','date_utils.py','platform_store.py','__init__.py'}


def source_files(root):
    paths=[]
    for path in root.rglob('*'):
        relative=path.relative_to(root)
        if path.is_symlink() or not path.is_file():continue
        if any((part.startswith('.') and part!='.github') or part=='__pycache__' for part in relative.parts[:-1]):continue
        if relative.as_posix()=='data/README.md' or (len(relative.parts)==1 and path.name in ROOT_FILES) or (relative.parts[0] in (DIRECTORIES | {'.github'}) and path.suffix in SUFFIXES):
            if path.name.startswith('.env') and path.name!='.env.example':continue
            paths.append(path)
    return sorted(paths,key=lambda path:path.relative_to(root).as_posix())


def package(root, output):
    paths=source_files(root)
    files={p.relative_to(root).as_posix():p.read_bytes() for p in paths}
    manifest={'status':'LOCAL_ONLY_PUBLIC_RELEASE_BLOCKED','files':{name:{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)} for name,data in files.items()},'excluded':'Source datasets, caches, secrets, Git history, generated reports and virtual environments are excluded.'}
    files['SOURCE_MANIFEST.json']=json.dumps(manifest,sort_keys=True,indent=2).encode()
    output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(output,'w',compression=ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            info=ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,data)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n',encoding='ascii')
    return {'archive':output.name,'source_files':len(paths),'sha256':digest,'bytes':output.stat().st_size}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    print(json.dumps(package(ROOT,args.output),indent=2))


if __name__=='__main__':main()
