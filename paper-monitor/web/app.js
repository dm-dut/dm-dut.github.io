
let papers=[];
let previous=[];
let currentCategory="All";

Promise.all([
fetch("web/papers.json").then(r=>r.json()),
fetch("web/previous_papers.json").then(r=>r.json()).catch(()=>[]),
fetch("web/update_time.json").then(r=>r.json())
]).then(([p,old,t])=>{
papers=p||[];
previous=old||[];

document.getElementById("updateTime").innerText=t.updated||"--";


renderCategories();
render();
});


function isNew(p){
return !previous.some(x=>x.doi===p.doi);
}


function renderCategories(){

let count={};

papers.forEach(p=>{
let c=p.category||"Other";
count[c]=(count[c]||0)+1;
});

let html=
`<div class="category active" onclick="chooseCategory('All',this)">
All (${papers.length})
</div>`;

Object.keys(count).sort().forEach(c=>{
html+=`
<div class="category" onclick="chooseCategory('${c}',this)">
${c} (${count[c]})
</div>`;
});

document.getElementById("categories").innerHTML=html;
}


function chooseCategory(c,e){
currentCategory=c;

document.querySelectorAll(".category")
.forEach(x=>x.classList.remove("active"));

e.classList.add("active");

render();
}


function render(){

let keyword=document.getElementById("searchBox").value.toLowerCase();
let journal=document.getElementById("journalBox").value.toLowerCase();

let data=papers.filter(p=>
(currentCategory==="All"||p.category===currentCategory)
&&
JSON.stringify(p).toLowerCase().includes(keyword)
&&
(!journal||(p.journal||"").toLowerCase().includes(journal))
);


let sort=document.getElementById("sortBox").value;

if(sort==="journal"){
data.sort((a,b)=>
(a.journal||"").localeCompare(b.journal||""));
}else{
data.sort((a,b)=>
(b.online_date||"").localeCompare(a.online_date||""));
}

data=data.slice(0,200);


if(data.length===0){
document.getElementById("paperList").innerHTML=
"<div class='empty'>No papers available. Please run update.py first.</div>";
return;
}


document.getElementById("paperList").innerHTML=
data.map(p=>`
<div class="paper">

<div class="journal">
${p.journal||""}
${isNew(p)?'<span class="badge">NEW</span>':""}
</div>

<div class="title">${p.title||""}</div>

<div class="author">${p.authors||""}</div>

<div class="meta">
Online: ${p.online_date||"N/A"}<br>
<a class="doi" href="https://doi.org/${p.doi}" target="_blank">
DOI: ${p.doi||""}
</a>
</div>

</div>
`).join("");

}


searchBox.oninput=render;
journalBox.oninput=render;
sortBox.onchange=render;
