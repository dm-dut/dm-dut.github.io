
let papers=[],previous=[],category="All",journal="All";

Promise.all([
fetch("papers.json").then(r=>r.json()),
fetch("previous_papers.json").then(r=>r.json()).catch(()=>[]),
fetch("update_time.json").then(r=>r.json())
]).then(([p,o,t])=>{
papers=p;
previous=o;

let d=new Date(t.updated.replace(" ","T")+"Z");
d.setHours(d.getHours()+8);
updateTime.innerText=d.toISOString().slice(0,19).replace("T"," ");

init();
render();
});

function isNew(p){
return !previous.some(x=>x.doi===p.doi);
}

function init(){
let cats=[...new Set(papers.map(p=>p.category||"Other"))].sort();
categorySelect.innerHTML='<option value="All">All Categories</option>'+
cats.map(x=>`<option>${x}</option>`).join("");

categorySelect.onchange=()=>{
category=categorySelect.value;
journal="All";
updateJournals();
render();
};

journalSelect.onchange=()=>{
journal=journalSelect.value;
render();
};

updateJournals();
}

function updateJournals(){
let js=[...new Set(
papers.filter(p=>category==="All"||p.category===category)
.map(p=>p.journal)
)].sort();

journalSelect.innerHTML='<option value="All">All Journals</option>'+
js.map(x=>`<option>${x}</option>`).join("");
}

function render(){

let key=searchBox.value.toLowerCase();

let data=papers.filter(p=>
(category==="All"||p.category===category)&&
(journal==="All"||p.journal===journal)&&
JSON.stringify(p).toLowerCase().includes(key)
);

if(sortBox.value==="journal")
data.sort((a,b)=>(a.journal||"").localeCompare(b.journal||""));
else
data.sort((a,b)=>(b.online_date||"").localeCompare(a.online_date||""));

summary.innerText=`Showing ${Math.min(data.length,200)} latest updated papers`;

paperList.innerHTML=data.slice(0,200).map(p=>`
<div class="paper">
<div class="title">
${p.title||""}
${isNew(p)?'<span class="badge">NEW</span>':""}
</div>
<div class="journal">${p.journal||""}</div>
<div class="author">${p.authors||""}</div>
<div class="meta">
Online: ${p.online_date||"N/A"}<br>
<a href="https://doi.org/${p.doi}" target="_blank">DOI: ${p.doi||""}</a>
</div>
</div>
`).join("");
}

searchBox.oninput=render;
sortBox.onchange=render;
