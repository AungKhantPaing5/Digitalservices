(()=>{
const root=document.getElementById('ds-chat-root');if(!root)return;
const admin=root.dataset.admin==='1',csrf=root.dataset.csrf;let open=false,selected=null,busy=false;
const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
const fab=el('button','ds-chat-fab');fab.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 9 9 0 0 1-4-.95L3 21l1.95-5.5A9 9 0 0 1 4 11.5 8.5 8.5 0 0 1 12.5 3 8.5 8.5 0 0 1 21 11.5Z"/><path d="M8 11h9M8 14h6"/></svg>';fab.type='button';fab.setAttribute('aria-label','Open support chat');fab.title='Chat with '+(admin?'customers':'Admin');
const panel=el('section','ds-chat-panel');panel.setAttribute('aria-label','DigitalServices private chat');
const header=el('div','ds-chat-header');
const title=el('span','',admin?'Customer Messages':'Admin');
const close=el('button','','×');close.type='button';close.style.cssText='background:transparent;border:0;color:white;font-size:24px';close.setAttribute('aria-label','Close chat');
header.append(title,close);
const inbox=el('div','ds-chat-inbox');if(!admin)inbox.style.display='none';
const body=el('div','ds-chat-body');
const form=el('form','ds-chat-form');const input=el('input');input.placeholder='Type a message...';input.required=true;input.maxLength=1500;
const send=el('button','','Send');send.type='submit';form.append(input,send);
panel.append(header,inbox,body,form);root.append(panel,fab);
function toggle(v){open=v;panel.classList.toggle('open',open);if(open)refresh();}
fab.onclick=()=>toggle(!open);close.onclick=()=>toggle(false);
async function json(url,options){const r=await fetch(url,{credentials:'same-origin',cache:'no-store',...options});if(!r.ok)throw Error('HTTP '+r.status);return r.json();}
async function loadInbox(){
 if(!admin)return;
 const res=await json('/admin/chat/inbox');inbox.replaceChildren();
 const list=res.conversations||[];
 if(!list.length){inbox.append(el('div','', 'No customer messages yet'));return;}
 if(!selected)selected=list[0].id;
 for(const item of list){
 const b=el('button','',item.email+' ('+item.total+')');
 b.onclick=()=>{selected=item.id;title.textContent=item.email;loadMessages().catch(showError);};
 inbox.append(b);
 if(item.id===selected)title.textContent=item.email;
 }
}
function showError(err){body.replaceChildren(el('div','', 'Chat connection error. Please try again.'));}
async function loadMessages(){
 if(admin&&!selected){body.replaceChildren(el('div','', 'Select a customer conversation'));return;}
 const url=admin?'/chat/messages?user_id='+encodeURIComponent(selected):'/chat/messages';
 const result=await json(url);body.replaceChildren();
 for(const msg of result.messages||[]){
 const div=el('div','ds-chat-bubble'+(msg.mine?' mine':''));
 div.append(document.createTextNode(msg.body),el('small','',msg.sender+' · '+msg.created));body.append(div);
 }
 body.scrollTop=body.scrollHeight;
}
async function refresh(){if(!open||busy)return;busy=true;try{if(admin)await loadInbox();await loadMessages();}catch(e){showError(e)}finally{busy=false}}
form.onsubmit=async e=>{
 e.preventDefault();if(!input.value.trim()||(admin&&!selected))return;
 const data=new URLSearchParams();data.set('_csrf',csrf);data.set('message',input.value.trim());
 if(admin)data.set('user_id',selected);
 send.disabled=true;
 try{await json('/chat/send',{method:'POST',body:data,headers:{'Content-Type':'application/x-www-form-urlencoded'}});input.value='';await refresh();}
 catch(e){showError(e)}
 finally{send.disabled=false;}
};
setInterval(()=>{if(open)refresh()},6000);
})();