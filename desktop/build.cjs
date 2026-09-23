const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const desktop=__dirname;
const project=path.resolve(desktop,'..');
const build=path.join(project,'build','desktop-runtime');
const runtime=path.join(build,'casajev');
const output=path.join(project,'dist-desktop');
const uv=[process.env.CASAJEV_UV,path.join(process.env.HOME||'','.local/bin/uv'),'/opt/homebrew/bin/uv','/usr/local/bin/uv','uv']
  .filter(Boolean).find(candidate=>candidate==='uv'||fs.existsSync(candidate));
const built=spawnSync(uv,['build'],{cwd:project,stdio:'inherit'});
if (built.status!==0) process.exit(built.status||1);
fs.rmSync(build,{recursive:true,force:true});
fs.mkdirSync(runtime,{recursive:true});
for (const name of ['pyproject.toml','uv.lock','README.md','CHANGELOG.md','LICENSE','THIRD_PARTY_NOTICES.md'])
  fs.copyFileSync(path.join(project,name),path.join(runtime,name));
fs.cpSync(path.join(project,'casajev'),path.join(runtime,'casajev'),{
  recursive:true,filter:source=>!source.includes('__pycache__')&&!source.endsWith('.pyc')});
fs.mkdirSync(path.join(runtime,'dist'),{recursive:true});
for (const name of fs.readdirSync(path.join(project,'dist')).filter(name=>name.startsWith('casajev-0.5.1-')&&name.endsWith('.whl')))
  fs.copyFileSync(path.join(project,'dist',name),path.join(runtime,'dist',name));
const binary=path.join(desktop,'node_modules','.bin','electron-packager');
const result=spawnSync(binary,['.','CasaJev','--platform=darwin','--arch=x64','--out='+output,
  '--overwrite','--prune=true','--extra-resource='+runtime],{cwd:desktop,stdio:'inherit'});
if (result.status !== 0) process.exit(result.status || 1);
console.log(path.join(output,'CasaJev-darwin-x64','CasaJev.app'));
