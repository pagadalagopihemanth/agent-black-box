const el=id=>document.getElementById(id);let pending=null;let count=0;
function log(text){const li=document.createElement('li');li.textContent=new Date().toISOString()+' · '+text;el('audit').prepend(li);}
function hide(){el('approve').hidden=true;el('deny').hidden=true;}
for(const [id,text] of Object.entries({invoice:'Read invoice INV-1001',bank:'Change supplier SUP-101 banking details',payment:'Approve payment PAY-202 for 15000 USD'}))el(id).onclick=()=>{el('request').value=text;};
el('run').onclick=()=>{
 if(pending){el('result').textContent='Resolve the pending request first.';return;}
 const text=el('request').value.trim();const bank=/bank|supplier/i.test(text);const invoice=/^read invoice INV-1001\.?$/i.test(text);const payment=/^approve payment PAY-202 for (?:15000|15,000) USD\.?$/i.test(text);
 const policy=bank?'BLOCK':invoice?'ALLOW':payment?'REVIEW':'BLOCK';const risk=invoice?'LOW RISK':bank||payment?'HIGH RISK':'Unavailable';const id=++count;
 el('result').textContent=`Simulated proposal #${id}\nSimulated AI risk: ${risk}\nLocal demo policy: ${policy}\nHuman approval: ${policy==='REVIEW'?'Required':'Not applicable'}\n${policy==='BLOCK'?'Execution prevented':policy==='ALLOW'?'Synthetic invoice lookup completed':'No payment executed'}`;
 log(`#${id}: simulated proposal; policy ${policy}; risk ${risk}`);
 if(policy==='REVIEW'){pending={id,request:text};el('approve').hidden=false;el('deny').hidden=false;}else if(policy==='ALLOW')log(`#${id}: synthetic invoice result recorded`);
};
function resolve(approve){if(!pending)return;const p=pending;pending=null;hide();log(`#${p.id}: human ${approve?'approved exact request; simulated payment executed once':'rejected; execution prevented'}`);el('result').textContent=approve?'Synthetic payment executed once. Approval consumed.':'Request rejected. No execution.';}
el('approve').onclick=()=>resolve(true);el('deny').onclick=()=>resolve(false);el('reset').onclick=()=>{pending=null;count=0;hide();el('audit').replaceChildren();el('result').textContent='Safe local demo reset.';};
