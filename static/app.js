const $=s=>document.querySelector(s);
let currentView="dashboard";
const money=n=>"₹"+Number(n||0).toLocaleString("en-IN",{maximumFractionDigits:2});
const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
function toast(msg,bad=false){const t=$("#toast");t.textContent=msg;t.className=bad?"bad":"good";t.classList.add("show");clearTimeout(window._toast);window._toast=setTimeout(()=>t.classList.remove("show"),3200)}
function authTab(mode){document.querySelectorAll(".tab,.inline-switch").forEach(x=>x.classList.toggle("active",x.dataset.auth===mode));$("#loginForm").classList.toggle("active",mode==="login");$("#signupForm").classList.toggle("active",mode==="signup")}
document.querySelectorAll("[data-auth]").forEach(b=>b.addEventListener("click",()=>authTab(b.dataset.auth)));
document.querySelectorAll(".eye").forEach(b=>b.addEventListener("click",()=>{const input=$("#"+b.dataset.target);input.type=input.type==="password"?"text":"password"}));

async function postJSON(url,data){
 const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
 const d=await r.json().catch(()=>({error:"Unexpected server response."}));
 if(!r.ok)throw new Error(d.error||"Request failed.");
 return d;
}
function setLoading(btn,on){btn.disabled=on;btn.classList.toggle("loading",on);if(on){btn.dataset.label=btn.textContent;btn.textContent="Please wait"}else if(btn.dataset.label){btn.textContent=btn.dataset.label}}

$("#loginBtn").onclick=async()=>{
 const btn=$("#loginBtn"),email=$("#loginEmail").value.trim(),password=$("#loginPassword").value;
 if(!email||!password){toast("Enter your email and password.",true);return}
 try{setLoading(btn,true);const d=await postJSON("/api/auth/login",{email,password});enterApp(d.user);toast("Signed in successfully")}catch(e){toast(e.message,true)}finally{setLoading(btn,false)}
};
$("#signupBtn").onclick=async()=>{
 const btn=$("#signupBtn"),name=$("#signupName").value.trim(),email=$("#signupEmail").value.trim(),password=$("#signupPassword").value,confirm=$("#signupConfirm").value;
 if(name.length<2){toast("Enter your full name.",true);return}
 if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){toast("Enter a valid email address.",true);return}
 if(password.length<8){toast("Password must contain at least 8 characters.",true);return}
 if(password!==confirm){toast("Passwords do not match.",true);return}
 try{setLoading(btn,true);const d=await postJSON("/api/auth/signup",{name,email,password});enterApp(d.user);toast("Account created successfully")}catch(e){toast(e.message,true)}finally{setLoading(btn,false)}
};

function enterApp(user){
 $("#authShell").classList.add("leaving");
 setTimeout(()=>{$("#authShell").classList.add("hidden");$("#appShell").classList.remove("hidden");$("#appShell").classList.add("entering");setTimeout(()=>$("#appShell").classList.remove("entering"),650);setUser(user);showView("dashboard")},320)
}
function setUser(user){
 const initials=user.name.split(/\s+/).map(x=>x[0]).slice(0,2).join("").toUpperCase();
 $("#userInitials").textContent=initials;$("#sideName").textContent=user.name;$("#sideEmail").textContent=user.email;$("#welcomeName").textContent="Signed in as "+user.name;
}
async function checkSession(){
 const r=await fetch("/api/auth/me");const d=await r.json();
 if(d.authenticated){$("#authShell").classList.add("hidden");$("#appShell").classList.remove("hidden");setUser(d.user);showView("dashboard")}
}
$("#logoutBtn").onclick=async()=>{await fetch("/api/auth/logout",{method:"POST"});$("#appShell").classList.add("hidden");$("#authShell").classList.remove("hidden");$("#authShell").classList.remove("leaving");$("#loginEmail").value="";$("#loginPassword").value="";authTab("login");toast("You have been logged out")};

function showView(v){
 currentView=v;
 document.querySelectorAll(".view").forEach(x=>x.classList.remove("active"));
 const target=$("#"+v);target.classList.add("active");
 document.querySelectorAll(".nav").forEach(x=>x.classList.toggle("active",x.dataset.view===v));
 $("#title").textContent=v==="dashboard"?"Dashboard":v==="upload"?"Process Document":"Documents";
 if(v==="dashboard")loadStats();
 if(v==="documents")loadDocs();
}
document.querySelectorAll(".nav").forEach(b=>b.onclick=()=>showView(b.dataset.view));

async function loadStats(){
 try{
  const d=await (await fetch("/api/stats")).json();
  if(d.auth_required){location.reload();return}
  $("#statDocs").textContent=d.documents;$("#statTotal").textContent=money(d.total);$("#statTax").textContent=money(d.tax);$("#statDup").textContent=d.duplicates;
  const max=Math.max(...d.categories.map(x=>x.amount),1);
  $("#categories").innerHTML=d.categories.length?d.categories.map(x=>`<div class="bar-row"><span>${esc(x.category)}</span><div class="bar"><i style="width:${Math.max(4,x.amount/max*100)}%"></i></div><b>${money(x.amount)}</b></div>`).join(""):'<div class="empty">No documents yet.</div>';
  const docs=await (await fetch("/api/documents")).json();
  $("#recent").innerHTML=docs.slice(0,5).map(x=>`<div class="recent"><div><b>${esc(x.vendor||"Unknown vendor")}</b><span>${esc(x.invoice_no||"No invoice number")}</span></div><b>${money(x.total)}</b></div>`).join("")||'<div class="empty">Process your first invoice.</div>';
 }catch(e){toast("Could not load dashboard data.",true)}
}
async function loadDocs(){
 const q=$("#search").value||"";const r=await fetch("/api/documents?q="+encodeURIComponent(q));if(r.status===401){location.reload();return}
 const docs=await r.json();
 $("#table").innerHTML=docs.map(x=>`<tr><td><strong>${esc(x.filename)}</strong></td><td>${esc(x.vendor||"-")}</td><td>${esc(x.doc_date||"-")}</td><td>${esc(x.category||"Other")}</td><td><strong>${money(x.total)}</strong></td><td><span class="status ${x.status==="Processed"?"ok":x.status.includes("Duplicate")?"danger":"warn"}">${esc(x.status)}</span></td><td><button class="table-action" onclick="deleteDoc(${x.id})">Delete</button></td></tr>`).join("")||'<tr><td colspan="7" class="empty">No matching documents.</td></tr>';
}
let searchTimer;$("#search").oninput=()=>{clearTimeout(searchTimer);searchTimer=setTimeout(loadDocs,180)};

$("#file").onchange=e=>{if(e.target.files[0])processFile(e.target.files[0])};
const drop=$("#drop");["dragenter","dragover"].forEach(x=>drop.addEventListener(x,e=>{e.preventDefault();drop.classList.add("dragging")}));["dragleave","drop"].forEach(x=>drop.addEventListener(x,e=>{e.preventDefault();drop.classList.remove("dragging")}));
drop.addEventListener("drop",e=>{const f=e.dataTransfer.files[0];if(f)processFile(f)});

async function processFile(file){
 if(file.size>10*1024*1024){toast("File is larger than 10 MB.",true);return}
 showView("upload");$("#processing").classList.remove("hidden");$("#drop").classList.add("hidden");$("#result").classList.add("hidden");
 const fd=new FormData();fd.append("file",file);
 try{const r=await fetch("/api/process",{method:"POST",body:fd}),d=await r.json();if(!r.ok)throw new Error(d.error||"Processing failed.");renderResult(d.document,d.missing||[]);toast("Document processed successfully")}catch(e){toast(e.message,true);$("#drop").classList.remove("hidden")}finally{$("#processing").classList.add("hidden")}
}
function field(label,value,key){return `<label class="result-field">${label}<input data-key="${key}" value="${esc(value??"")}"></label>`}
function renderResult(x,missing){
 const cls=x.status==="Processed"?"ok":x.status.includes("Duplicate")?"danger":"warn";
 $("#result").classList.remove("hidden");
 $("#result").innerHTML=`<div class="result-grid">
 <div class="panel"><div class="panel-head"><div><h2>Extracted information</h2><p>Review fields before finalizing the record.</p></div><span class="status ${cls}">${esc(x.status)}</span></div>
 <div class="fields">${field("Vendor",x.vendor,"vendor")}${field("Invoice Number",x.invoice_no,"invoice_no")}${field("Date",x.doc_date,"doc_date")}${field("Address",x.address,"address")}${field("Tax",x.tax,"tax")}${field("Total",x.total,"total")}${field("Category",x.category,"category")}</div>
 <div class="result-actions"><button class="primary" onclick="saveCorrection(${x.id})">Save correction</button><button class="secondary" onclick="showView('documents')">View documents</button></div></div>
 <div class="panel"><div class="panel-head"><div><h2>Validation</h2><p>Automated quality checks.</p></div></div>
 <div class="validation">${missing.length?`<div class="validation-box warn"><strong>Needs review</strong><span>Missing: ${missing.map(esc).join(", ")}</span></div>`:`<div class="validation-box ok"><strong>All required fields found</strong><span>Vendor, invoice number, date and total are present.</span></div>`}
 <div class="raw"><div><b>OCR text</b><button class="link" onclick="this.closest('.raw').classList.toggle('open')">Show / hide</button></div><pre>${esc(x.raw_text||"")}</pre></div></div></div></div>`;
}
async function saveCorrection(id){
 const payload={};document.querySelectorAll("#result [data-key]").forEach(i=>payload[i.dataset.key]=i.value);
 try{const r=await fetch("/api/documents/"+id,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}),d=await r.json();if(!r.ok)throw new Error(d.error||"Could not save correction.");renderResult(d.document,d.missing||[]);toast("Correction saved successfully");loadStats()}catch(e){toast(e.message,true)}
}
async function deleteDoc(id){
 if(!confirm("Delete this document?"))return;
 const r=await fetch("/api/documents/"+id,{method:"DELETE"});const d=await r.json();if(!r.ok){toast(d.error||"Could not delete document.",true);return}
 toast("Document deleted");loadDocs();loadStats()
}
checkSession();
