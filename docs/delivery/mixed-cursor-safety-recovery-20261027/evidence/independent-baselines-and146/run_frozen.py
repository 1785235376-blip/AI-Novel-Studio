import hashlib,json,pathlib,subprocess,sys,time
root=pathlib.Path.cwd().resolve();out=pathlib.Path(__file__).parent;name=sys.argv[1]
sys.path.insert(0,str(root))
def hashes():
 return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob('app/**/*.py'))}
before=hashes();start=time.time()
import pytest
code=pytest.main(['-q','-o','faulthandler_timeout=120','--junitxml='+str(out/(name+'.xml')),*sys.argv[2:]])
loaded={k:str(pathlib.Path(v.__file__).resolve()) for k,v in sys.modules.items() if (k=='app' or k.startswith('app.')) and getattr(v,'__file__',None)}
foreign={k:v for k,v in loaded.items() if not pathlib.Path(v).is_relative_to(root)}
receipt={'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],text=True).strip(),'app_tree':subprocess.check_output(['git','rev-parse','HEAD:app'],text=True).strip(),'source_root':str(root),'start':start,'end':time.time(),'pytest_exit':int(code),'source_hash_before':before,'source_hash_after':hashes(),'source_unchanged':before==hashes(),'loaded_app_modules':loaded,'foreign_app_modules':foreign,'command':sys.argv}
(out/(name+'-receipt.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
sys.exit(int(code) or (9 if foreign or before!=hashes() else 0))
