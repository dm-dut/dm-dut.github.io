let currentTab = 'ajg';

let allData = {
    ajg: [],
    ccf: [],
    fms: []
};

async function loadAllData() {
    allData.ajg = await fetch('./data/ajg.json').then(res => res.json());
    allData.ccf = await fetch('./data/ccf.json').then(res => res.json());
    allData.fms = await fetch('./data/fms.json').then(res => res.json());

    loadTable();
}

function switchTab(tab, button) {
    currentTab = tab;

    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    button.classList.add('active');

    if (tab === 'search') {
        document.getElementById('table-panel').style.display = 'none';
        document.getElementById('search-panel').style.display = 'block';
    } else {
        document.getElementById('table-panel').style.display = 'block';
        document.getElementById('search-panel').style.display = 'none';
        loadTable();
    }
}

function getColumnConfig(tab) {
    if (tab === 'ajg') {
        return {
            journal: 'Journal Title',
            category: 'Field',
            level: 'AJG 2024'
        };
    }

    if (tab === 'ccf') {
        return {
            journal: '全称',
            category: '分类',
            level: '级别'
        };
    }

    return {
        journal: '期刊名称',
        category: '学科',
        level: 'FMS等级 2025'
    };
}

function loadTable() {
    const data = allData[currentTab];
    const config = getColumnConfig(currentTab);

    const keyword = document.getElementById('keyword').value.toLowerCase();
    const category = document.getElementById('category').value;
    const level = document.getElementById('level').value;

}