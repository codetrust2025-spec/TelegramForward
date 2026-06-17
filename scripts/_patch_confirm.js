const fs=require('fs');
const html=fs.readFileSync('static/index.html','utf8');
const m=html.match(/assets\/(app-[^"]+\.js)/);
if(!m){console.error('no app bundle in index.html');process.exit(1);}
const p='static/assets/'+m[1];
let t=fs.readFileSync(p,'utf8');
const mk=(fn,c)=>'function '+fn+'(){const e=k.useContext('+c+')||(typeof globalThis!="undefined"&&globalThis.__TA_CONFIRM_VALUE__)||null;if(!e)throw new Error("useConfirm must be used within ConfirmProvider");return e}';
const bad=/function (\w+)\(\)\{const e=k\.useContext\((\w+)\);e=e\|\|typeof globalThis/;
const broken=/function (\w+)\(\)\{const e=k\.useContext\(\)\|\|/;
const plain=/function (\w+)\(\)\{const e=k\.useContext\((\w+)\);if\(!e\)throw new Error\("useConfirm must be used within ConfirmProvider"\);return e\}/;
const ctxFrom=()=>{
  const m=t.match(/(\w+)=k\.createContext\(null\);function (\w+)\(\)\{const e=k\.useContext/);
  return m ? [m[2], m[1]] : ['eo','Ak'];
};
if(bad.test(t)){t=t.replace(bad,(x,fn,c)=>{console.log('fixed bad e=e',fn,c);return mk(fn,c);});}
else if(broken.test(t)){const [fn,c]=ctxFrom();t=t.replace(broken,()=>mk(fn,c));console.log('fixed empty useContext',fn,c);}
else if(plain.test(t)){t=t.replace(plain,(x,fn,c)=>{console.log('applied fallback',fn,c);return mk(fn,c);});}
else if(/useContext\(\w+\)\|\|\(typeof globalThis/.test(t)){console.log('confirm hook ok');}
else if(/useContext\([^)]+\);if\(\w+\)return \w+;if\(typeof globalThis[^}]+__TA_CONFIRM/.test(t)){console.log('confirm hook ok (global fallback)');}
else if(/throw new Error\("useConfirm must be used within ConfirmProvider"\)/.test(t)&&/globalThis\[/.test(t)){console.log('confirm hook ok (source bundle)');}
else{console.error('no hook');process.exit(1);}
fs.writeFileSync(p,t);
console.log('bundle',m[1]);
