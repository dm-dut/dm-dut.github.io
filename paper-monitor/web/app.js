
let papers=[];
let previous=[];
let category="All";
let journal="All";
let currentPage=1;
const pageSize=50;
const maxItems=500;

Promise.all([
fetch("web/papers.json").then(r=>r.json()),
fetch("web/previous_papers.json").then(r=>r.json()).catch(()=>[]),
fetch("web/update_time.json").then(r=>r.json()).catch(()=>({}))
]).then(([p,o,t])=>{
papers=p||[];
previous=o||[];
if(t.updated){
let d=new Date(t.updated.replace(" ","T")+"Z");
d.setHours(d.getHours()+8);
document.getElementById("updateTime").innerText=d.toISOString().slice(0,19).replace("T"," ");
}
init();
render();
}).catch(e=>{
document.getElementById("summary").innerText="Data loading error: "+e;
});

function init(){
let cats=[...new Set(papers.map(p=>p.category||"Other"))].sort();
categorySelect.innerHTML='<option value="All">All Categories</option>'+cats.map(x=>`<option>${x}</option>`).join("");
categorySelect.onchange=()=>{category=categorySelect.value;journal="All";updateJournals();currentPage=1;render()};
journalSelect.onchange=()=>{journal=journalSelect.value;currentPage=1;render()};
sortBox.onchange=()=>{currentPage=1;render()};
updateJournals();
}

function updateJournals(){
let js=[...new Set(papers.filter(p=>category==="All"||p.category===category).map(p=>p.journal))].sort();
journalSelect.innerHTML='<option value="All">All Journals</option>'+js.map(x=>`<option>${x}</option>`).join("");
}

function isNew(p){return !previous.some(x=>x.doi===p.doi)}

function render(){
let key=searchBox.value.toLowerCase();
let data=papers.filter(p=>(category==="All"||p.category===category)&&(journal==="All"||p.journal===journal)&&JSON.stringify(p).toLowerCase().includes(key));
data.sort((a,b)=>(b.online_date||"").localeCompare(a.online_date||""));
data=data.slice(0,maxItems);

let pages=Math.ceil(data.length/pageSize)||1;
let start=(currentPage-1)*pageSize;
let list=data.slice(start,start+pageSize);

summary.innerText=`Showing ${start+1}-${Math.min(start+pageSize,data.length)} of ${data.length} papers`;

paperList.innerHTML=list.map(p=>`<div class="paper"><div class="title">${p.title||""}${isNew(p)?'<span class="badge">NEW</span>':''}</div><div class="journal">${p.journal||""}</div><div class="author">${p.authors||""}</div><div class="meta">Online: ${p.online_date||"N/A"}<br>DOI: ${p.doi||""}</div></div>`).join("");

renderPagination(pages);
}

function renderPagination(total){
pagination.innerHTML="";
if(total<=1)return;
let box=document.createElement("div");
box.className="pagination-buttons";
for(let i=1;i<=total;i++){
let b=document.createElement("button");
b.className="page-btn"+(i===currentPage?" active":"");
b.innerText=i;
b.onclick=()=>{currentPage=i;render()};
box.appendChild(b);
}
let info=document.createElement("div");
info.className="page-info";
info.innerText=`Page ${currentPage} / ${total}`;
pagination.append(box,info);
}

searchBox.oninput=()=>{currentPage=1;render()};
