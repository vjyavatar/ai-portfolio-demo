"""Rebuild the public client while preserving public pages and artwork."""
from pathlib import Path
import tempfile,shutil,subprocess,json,hashlib,os
root=Path(__file__).resolve().parents[1]
os.chdir(root)
with tempfile.TemporaryDirectory() as tmp:
 for p in Path('ruralos').iterdir():
  if p.name in ('assets','index.html'):continue
  target=Path(tmp)/p.name
  shutil.copytree(p,target) if p.is_dir() else shutil.copy(p,target)
 vite=Path('ruralos-src/node_modules/vite/bin/vite.js')
 subprocess.run(['node',str(vite),'build','--config','ruralos-src/vite.config.mjs'],check=True)
 for p in Path(tmp).iterdir():
  target=Path('ruralos')/p.name
  shutil.copytree(p,target,dirs_exist_ok=True) if p.is_dir() else shutil.copy(p,target)
files=['/ruralos/']+['/'+p.as_posix() for p in Path('ruralos').rglob('*') if p.is_file() and p.name!='sw.js']
p=Path('ruralos/sw.js');old=p.read_text();tail=old[old.index('self.addEventListener'):]
key=hashlib.sha256(''.join(files).encode()).hexdigest()[:12]
p.write_text('const CACHE="saathi-ruralos-'+key+'",ASSETS='+json.dumps(files)+';\n'+tail)
