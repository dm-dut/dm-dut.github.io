let ajgData = [];
        const name = normalize(item['全称']);

        if (name.includes(keyword)) {
            results.push({
                source: 'CCF',
                journal: item['全称'],
                category: item['分类'],
                level: item['级别'],
                impact: item['JIF 2024'] || item['影响因子'] || ''
            });
        }
    });

    // FMS
    fmsData.forEach(item => {
        const name = normalize(item['期刊名称']);

        if (name.includes(keyword)) {
            results.push({
                source: 'FMS',
                journal: item['期刊名称'],
                category: item['学科'],
                level: item['FMS等级 2025'],
                impact: item['JIF 2024'] || item['影响因子'] || ''
            });
        }
    });

    if (results.length === 0) {
        resultDiv.innerHTML = '<p>未找到匹配结果</p>';
        return;
    }

    let html = `
        <table>
            <thead>
                <tr>
                    <th>来源</th>
                    <th>期刊名</th>
                    <th>分类/学科</th>
                    <th>等级</th>
                    <th>影响因子</th>
                </tr>
            </thead>
            <tbody>
    `;

    results.forEach(item => {
        html += `
            <tr>
                <td>${item.source}</td>
                <td>${item.journal}</td>
                <td>${item.category}</td>
                <td>${item.level}</td>
                <td>${item.impact}</td>
            </tr>
        `;
    });

    html += '</tbody></table>';

    resultDiv.innerHTML = html;
}

window.onload = loadData;