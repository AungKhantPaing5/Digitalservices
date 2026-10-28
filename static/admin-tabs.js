document.addEventListener('DOMContentLoaded',()=>{
const tabs=[...document.querySelectorAll('.ds-admin-tabs [data-tab]')];
const panels=[...document.querySelectorAll('.ds-tab-panel[data-panel]')];
const known=new Set(tabs.map(t=>t.dataset.tab));
function activate(name,updateHash=true){
 if(!known.has(name))name='overview';
 tabs.forEach(t=>{let active=t.dataset.tab===name;t.setAttribute('aria-selected',String(active));t.classList.toggle('active',active);t.tabIndex=active?0:-1});
 panels.forEach(p=>{p.hidden=p.dataset.panel!==name});
 if(updateHash)history.replaceState(null,'','#'+name);
}
tabs.forEach((t,i)=>{
 t.addEventListener('click',()=>activate(t.dataset.tab));
 t.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();const next=tabs[(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length];activate(next.dataset.tab);next.focus()}});
});
document.querySelectorAll('[data-go-tab]').forEach(b=>b.addEventListener('click',()=>activate(b.dataset.goTab)));
window.addEventListener('hashchange',()=>activate(location.hash.slice(1),false));
activate(location.hash.slice(1),false);
});