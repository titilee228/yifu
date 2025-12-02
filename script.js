document.addEventListener('DOMContentLoaded', () => {
    loadData();
    setupModal();
    setupUpload();
});

let allClothes = [];
let currentEditingItem = null;
let cropper = null;

// === 分页配置 ===
let currentPage = 1;
const itemsPerPage = 56; // 8行 x 7列
let currentFilteredItems = [];

// === 分类字典 ===
const CATEGORY_TREE = {
    "衣服": ["西装外套", "大衣", "风衣", "连衣裙", "套装", "夹克", "羽绒服", "卫衣", "棉衣", "毛衫", "上衣", "牛仔外套", "外套", "裤子", "牛仔裤", "短裤", "半裙"],
    "配饰": ["手镯", "耳环", "项链", "包包", "围巾", "帽饰", "胸针", "腰带", "眼镜", "手套"],
    "其他": ["其他"]
};

const WEATHER_TYPES = ["炎热(夏季)", "舒适(春秋)", "寒冷(冬季)"];
const COLOR_TYPES = [
    "黑色", "灰色", "白色", "米色", "棕色", 
    "黄色", "橙色", "红色", "粉色", "紫色", 
    "蓝色", "绿色", "金色", "银色", "玫瑰金"
];

// === 1. 初始化 & 加载 ===
function initOptions() {
    const filterCat = document.getElementById('filterCategory');
    const filterSeason = document.getElementById('filterSeason');
    const filterColor = document.getElementById('filterColor');

    if (filterCat.options.length <= 1) {
        Object.keys(CATEGORY_TREE).forEach(mainCat => {
            filterCat.add(new Option(`【${mainCat}】`, mainCat));
            CATEGORY_TREE[mainCat].forEach(sub => {
                filterCat.add(new Option(`-- ${sub}`, sub));
            });
        });
    }
    if (filterSeason.options.length <= 1) {
        WEATHER_TYPES.forEach(w => filterSeason.add(new Option(w, w)));
    }
    if (filterColor.options.length <= 1) {
        COLOR_TYPES.forEach(c => filterColor.add(new Option(c, c)));
    }

    const editCat = document.getElementById('editCategory');
    const editSeason = document.getElementById('editSeason');
    
    if (editCat) {
        editCat.innerHTML = '';
        Object.keys(CATEGORY_TREE).forEach(key => {
            editCat.add(new Option(key, key));
        });
        updateSubCategoryOptions();
    }
    
    if (editSeason) {
        editSeason.innerHTML = '';
        WEATHER_TYPES.forEach(w => editSeason.add(new Option(w, w)));
        editSeason.add(new Option("未知", "未知"));
    }

    const colorContainer = document.getElementById('color-checkbox-group');
    if (colorContainer) {
        colorContainer.innerHTML = '';
        COLOR_TYPES.forEach(c => {
            const label = document.createElement('label');
            label.className = 'color-tag-label';
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = c;
            checkbox.name = 'color-option';
            checkbox.onchange = () => label.classList.toggle('checked', checkbox.checked);
            label.appendChild(checkbox);
            label.appendChild(document.createTextNode(c));
            colorContainer.appendChild(label);
        });
    }
}

async function loadData() {
    try {
        initOptions();
        const response = await fetch('/api/clothes');
        if (!response.ok) throw new Error("API Error");
        allClothes = await response.json();
        
        currentFilteredItems = allClothes;
        updateLocationSuggestions();
        updateCount(allClothes.length);
        renderGallery(currentFilteredItems);
        setupInteractions();
    } catch (e) {
        console.error("加载失败", e);
        alert("无法连接服务器");
    }
}

// === 2. 渲染与分页 (修复卡片布局) ===
function renderGallery(items) {
    const totalPages = Math.ceil(items.length / itemsPerPage);
    if (currentPage > totalPages) currentPage = 1;
    if (currentPage < 1) currentPage = 1;
    
    const start = (currentPage - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const pageItems = items.slice(start, end);
    
    const gallery = document.getElementById('gallery');
    gallery.innerHTML = '';
    
    if (pageItems.length === 0) {
        gallery.innerHTML = `<div class="empty-state">暂无符合条件的衣物</div>`;
        document.getElementById('pagination').innerHTML = '';
        return;
    }

    pageItems.forEach(item => {
        const card = document.createElement('div');
        card.className = 'card';
        // 点击卡片本体打开编辑
        card.onclick = (e) => {
            // 如果点击的是删除按钮，不触发编辑
            if (e.target.closest('.card-delete-btn')) return;
            openEditModal(item);
        };
        
        const imgPath = item.path.replace(/\\/g, '/');
        const displayTitle = `${item.tags.sub_category || item.tags.category} ${item.tags.color || ''}`;
        
        // 增加删除按钮 HTML
        card.innerHTML = `
            <div class="img-box">
                <img src="${imgPath}" loading="lazy">
                <div class="card-delete-btn" onclick="deleteItemFromCard('${item.filename}')" title="删除此衣物">🗑️</div>
            </div>
            <div class="info">
                <div class="info-top">
                    <span class="card-title" title="${displayTitle}">${displayTitle}</span>
                </div>
                <div class="card-desc" title="${item.description}">${item.description || '暂无描述'}</div>
                <div class="info-bottom">
                    <span class="card-loc">${item.location || '未整理'}</span>
                    <span class="card-code">#${item.code || '???'}</span>
                </div>
            </div>
        `;
        gallery.appendChild(card);
    });

    renderPaginationNumbers(totalPages);
}

// 分页条
function renderPaginationNumbers(totalPages) {
    const container = document.getElementById('pagination');
    container.innerHTML = '';
    
    if (totalPages <= 1) return;

    const createBtn = (text, page, isActive = false, isDisabled = false) => {
        const btn = document.createElement('div');
        btn.className = `page-btn ${isActive ? 'active' : ''} ${isDisabled ? 'disabled' : ''}`;
        btn.innerHTML = text;
        if (!isDisabled && !isActive) {
            btn.onclick = () => changePage(page);
        }
        return btn;
    };

    container.appendChild(createBtn('&lt;', currentPage - 1, false, currentPage === 1));

    let pages = [];
    if (totalPages <= 7) {
        for(let i=1; i<=totalPages; i++) pages.push(i);
    } else {
        if (currentPage <= 4) {
            pages = [1, 2, 3, 4, 5, '...', totalPages];
        } else if (currentPage >= totalPages - 3) {
            pages = [1, '...', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
        } else {
            pages = [1, '...', currentPage - 1, currentPage, currentPage + 1, '...', totalPages];
        }
    }

    pages.forEach(p => {
        if (p === '...') {
            const span = document.createElement('span');
            span.className = 'page-dots';
            span.innerText = '...';
            container.appendChild(span);
        } else {
            container.appendChild(createBtn(p, p, p === currentPage));
        }
    });

    container.appendChild(createBtn('&gt;', currentPage + 1, false, currentPage === totalPages));

    // 跳转输入框
    const jumpBox = document.createElement('div');
    jumpBox.className = 'jump-box';
    jumpBox.innerHTML = `
        <input type="number" id="jumpInput" min="1" max="${totalPages}" placeholder="页">
        <button id="jumpBtn">GO</button>
    `;
    container.appendChild(jumpBox);

    document.getElementById('jumpBtn').onclick = () => {
        const val = parseInt(document.getElementById('jumpInput').value);
        if (val >= 1 && val <= totalPages) changePage(val);
    };
}

function changePage(p) {
    currentPage = p;
    renderGallery(currentFilteredItems);
    document.querySelector('.content-area').scrollTop = 0;
}

// === 3. 编辑 & 删除逻辑 ===
function openEditModal(item, isNew = false) {
    const modal = document.getElementById('editModal');
    modal.style.display = 'block';
    
    document.querySelectorAll('input[name="color-option"]').forEach(cb => {
        cb.checked = false; 
        cb.parentElement.classList.remove('checked');
    });
    document.getElementById('related-images-container').innerHTML = '<div style="color:#999;font-size:0.8rem;">无关联图片</div>';

    if (isNew) {
        currentEditingItem = { isNew: true };
        document.getElementById('modalTitle').textContent = "✨ 新衣入库";
        document.getElementById('editFilename').value = "自动生成...";
        document.getElementById('editLocation').value = "";
        document.getElementById('editCategory').value = "衣服";
        updateSubCategoryOptions();
        document.getElementById('editDescription').value = "";
    } else {
        currentEditingItem = item;
        document.getElementById('modalTitle').textContent = "📝 编辑详情";
        document.getElementById('aiStatus').style.display = 'none';
        
        document.getElementById('modalImg').src = item.path;
        document.getElementById('editFilename').value = item.filename;
        document.getElementById('editLocation').value = item.location || '';
        
        document.getElementById('editCategory').value = item.tags.category || '衣服';
        updateSubCategoryOptions();
        document.getElementById('editSubCategory').value = item.tags.sub_category || '';
        document.getElementById('editSeason').value = item.tags.season || '舒适(春秋)';
        document.getElementById('editDescription').value = item.description || '';
        
        const colorStr = item.tags.color || '';
        document.querySelectorAll('input[name="color-option"]').forEach(cb => {
            if (colorStr.includes(cb.value)) {
                cb.checked = true;
                cb.parentElement.classList.add('checked');
            }
        });

        if (item.code) {
            const relatedItems = allClothes.filter(i => i.code === item.code && i.filename !== item.filename);
            if (relatedItems.length > 0) {
                const container = document.getElementById('related-images-container');
                container.innerHTML = '';
                relatedItems.forEach(rel => {
                    const img = document.createElement('img');
                    img.src = rel.path;
                    img.className = 'related-thumb';
                    img.title = "点击切换到这张图";
                    img.onclick = () => openEditModal(rel);
                    container.appendChild(img);
                });
            }
        }
    }
}

window.updateSubCategoryOptions = function() {
    const mainCat = document.getElementById('editCategory').value;
    const subList = document.getElementById('sub-cat-list');
    subList.innerHTML = '';
    if (CATEGORY_TREE[mainCat]) {
        CATEGORY_TREE[mainCat].forEach(sub => {
            const option = document.createElement('option');
            option.value = sub;
            subList.appendChild(option);
        });
    }
}

async function saveChanges() {
    const btn = document.getElementById('saveBtn');
    btn.textContent = "💾 保存中...";
    btn.disabled = true;

    const checkedColors = Array.from(document.querySelectorAll('input[name="color-option"]:checked')).map(cb => cb.value);
    const tags = {
        category: document.getElementById('editCategory').value,
        sub_category: document.getElementById('editSubCategory').value,
        season: document.getElementById('editSeason').value,
        color: checkedColors.join('、')
    };
    
    const body = {
        location: document.getElementById('editLocation').value,
        tags: tags,
        description: document.getElementById('editDescription').value
    };

    let url = '/api/update';
    if (currentEditingItem.isNew) {
        url = '/api/save_new';
        body.image = currentEditingItem.imageBase64;
    } else {
        body.filename = currentEditingItem.filename;
    }

    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });
        if (!response.ok) throw new Error("Fail");
        document.getElementById('editModal').style.display = 'none';
        await loadData();
    } catch(e) {
        alert("保存失败");
    } finally {
        btn.textContent = "💾 保存更改";
        btn.disabled = false;
    }
}

// === 列表页直接删除 ===
async function deleteItemFromCard(filename) {
    // 阻止冒泡已经通过onclick处理，这里只做逻辑
    if (!confirm("⚠️ 确定要删除这件衣物吗？\n删除后将无法恢复！")) return;
    
    try {
        const response = await fetch('/api/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ filename: filename })
        });
        
        if (response.ok) {
            await loadData(); // 刷新
        } else {
            alert("删除失败");
        }
    } catch (e) {
        alert("请求错误: " + e);
    }
}

// 弹窗内的删除按钮（可选保留）
async function deleteItem() {
    if (!confirm("⚠️ 确定要删除这件衣物吗？\n删除后将无法恢复！")) return;
    try {
        const response = await fetch('/api/delete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ filename: currentEditingItem.filename })
        });
        if (response.ok) {
            document.getElementById('editModal').style.display = 'none';
            await loadData();
        } else {
            alert("删除失败");
        }
    } catch (e) { alert("请求错误: " + e); }
}

// === 上传与裁剪 ===
function setupUpload() {
    const uploadBtn = document.getElementById('uploadBtn');
    const fileInput = document.getElementById('fileInput');
    if(uploadBtn && fileInput) {
        uploadBtn.onclick = () => fileInput.click();
        fileInput.onchange = (e) => {
            if (e.target.files && e.target.files[0]) {
                startCrop(e.target.files[0]);
                fileInput.value = '';
            }
        };
    }
}

function startCrop(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('cropModal').style.display = 'block';
        const img = document.getElementById('cropImage');
        img.src = e.target.result;
        if (cropper) cropper.destroy();
        cropper = new Cropper(img, { viewMode: 1, autoCropArea: 0.9 });
    };
    reader.readAsDataURL(file);
}

function closeCropModal() {
    document.getElementById('cropModal').style.display = 'none';
    if(cropper) cropper.destroy();
}

async function confirmCrop() {
    if (!cropper) return;
    const canvas = cropper.getCroppedCanvas({ width: 800 });
    const base64 = canvas.toDataURL('image/jpeg', 0.85);
    closeCropModal();
    openEditModal(null, true);
    document.getElementById('modalImg').src = base64;
    document.getElementById('aiStatus').style.display = 'block';
    currentEditingItem.imageBase64 = base64;
    
    try {
        const res = await fetch('/api/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ image: base64 })
        });
        const tags = await res.json();
        document.getElementById('aiStatus').style.display = 'none';
        if (tags.category) {
            document.getElementById('editCategory').value = tags.category;
            updateSubCategoryOptions();
        }
        if (tags.sub_category) document.getElementById('editSubCategory').value = tags.sub_category;
        if (tags.season) document.getElementById('editSeason').value = tags.season;
        if (tags.description) document.getElementById('editDescription').value = tags.description;
        if (tags.color) {
            document.querySelectorAll('input[name="color-option"]').forEach(cb => {
                if (tags.color.includes(cb.value)) {
                    cb.checked = true;
                    cb.parentElement.classList.add('checked');
                }
            });
        }
    } catch(e) {
        document.getElementById('aiStatus').textContent = "⚠️ 识别失败";
    }
}

function setupModal() {
    window.onclick = (e) => {
        if (e.target.classList.contains('modal')) e.target.style.display = 'none';
    };
    document.querySelectorAll('.close-btn').forEach(btn => {
        btn.onclick = function() { this.closest('.modal').style.display = 'none'; }
    });
}

function setupInteractions() {
    const doFilter = () => {
        const text = document.getElementById('searchInput').value.toLowerCase();
        const cat = document.getElementById('filterCategory').value;
        const sea = document.getElementById('filterSeason').value;
        const col = document.getElementById('filterColor').value;
        
        currentFilteredItems = allClothes.filter(item => {
            const matchText = !text || (item.filename.toLowerCase().includes(text)) || (item.code && item.code.includes(text)) || (item.description && item.description.includes(text));
            let matchCat = true;
            if (cat) {
                if (CATEGORY_TREE[cat]) {
                    matchCat = (item.tags.category === cat);
                } else {
                    matchCat = (item.tags.sub_category === cat) || (item.tags.category === cat);
                }
            }
            const matchSea = !sea || (item.tags.season === sea);
            const matchCol = !col || (item.tags.color && item.tags.color.includes(col));
            return matchText && matchCat && matchSea && matchCol;
        });
        currentPage = 1;
        renderGallery(currentFilteredItems);
        updateCount(currentFilteredItems.length);
    };

    ['searchInput', 'filterCategory', 'filterSeason', 'filterColor'].forEach(id => {
        document.getElementById(id).oninput = doFilter;
    });
    document.getElementById('resetFiltersBtn').onclick = () => {
        document.getElementById('searchInput').value = '';
        document.getElementById('filterCategory').value = '';
        document.getElementById('filterSeason').value = '';
        document.getElementById('filterColor').value = '';
        doFilter();
    }
}

function updateCount(n) { document.getElementById('count').textContent = `(${n})`; }
function updateLocationSuggestions() {
    const list = document.getElementById('location-list');
    const locs = new Set(allClothes.map(i => i.location).filter(Boolean));
    list.innerHTML = '';
    locs.forEach(l => {
        const op = document.createElement('option');
        op.value = l;
        list.appendChild(op);
    });
}