let currentLang = "en";

function setLang(lang){
    currentLang = lang;
    loadData();
}

function formatItem(p){

    let authors = currentLang === "zh" ? p.authors_zh : p.authors;
    let title = currentLang === "zh" ? p.title_zh : p.title;
    let journal = currentLang === "zh" ? p.journal_zh : p.journal;

    let html = `${authors}. ${title}. <i>${journal}</i>`;

    if(p.year){
        html += `, ${p.year}`;
    }

    if(p.doi){
        html += `, <a href="https://doi.org/${p.doi}" target="_blank">doi</a>`;
    }

    if(p.esi_high){
        html += ` <span class="esi">ESI Highly Cited</span>`;
    }

    if(p.esi_hot){
        html += ` <span class="esi">ESI Hot</span>`;
    }

    return html;
}

function loadData(){

    fetch("publications.json")
    .then(res => res.json())
    .then(data => {

        ["journal","conference","book","working"].forEach(t=>{
            document.getElementById(t).innerHTML = "";
        });

        data.forEach(p => {

            let li = document.createElement("li");
            li.innerHTML = formatItem(p);

            if(document.getElementById(p.type)){
                document.getElementById(p.type).appendChild(li);
            }

        });

    });
}

loadData();