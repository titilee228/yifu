document.addEventListener('DOMContentLoaded', () => {
    loadData();
    setupModal();
    setupUpload(); // 确保这一行在
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
    "配饰": ["包袋", "帽子", "围巾", "丝巾", "腰带", "领带", "首饰", "墨镜", "手套"],
    "上装": ["T恤", "衬衫", "卫衣", "毛衣", "针织衫", "背心", "吊带"],
    "下装": ["牛仔裤", "休闲裤", "西装裤", "短裤", "半身裙"],
    "外套": ["西装", "夹克", "风衣", "大衣", "羽绒服", "马甲"],
    "连体衣": ["连衣裙", "连体裤", "礼服"],
    "鞋靴": ["运动鞋", "皮鞋", "靴子", "凉鞋", "拖鞋"],
    "家居/内衣": ["家居服", "内衣", "睡衣", "袜子"]
};

const WEATHER_TYPES = ["炎热(夏季)", "舒适(春秋)", "寒冷(冬季)"];
const COLOR_TYPES = [
    "黑色", "灰色", "白色", "米色", "棕色", 
    "黄色", "橙色", "红色", "粉色", "紫色", 
    "蓝色", "绿色", "金色", "银色", "玫瑰金"
];

// === 1. 初始化 & 加载 ===
function initOptions() {
    // 初始化筛选栏
    const filterCat = document.getElementById('filterCategory');
    const filterSeason = document.getElementById('filterSeason');
    const filterColor = document.getElementById('filterColor');

    if (filterCat.options.length <= 1) {
        Object.keys(CATEGORY_TREE).forEach(key => {
            filterCat.add(new Option(key, key));
        });
    }
    if (filterSeason.options.length <= 1) {
        WEATHER_TYPES.forEach(w => filterSeason.add(new Option(w, w)));
    }
    if (filterColor.options.length <= 1) {
        COLOR_TYPES.forEach(c => filterColor.add(new Option(c, c)));
    }

    // 初始化编辑弹窗的下拉框
    const editCat = document.getElementById('editCategory');
    const editSeason = document.getElementById('editSeason');
    
    if (editCat) {
        editCat.innerHTML = ''; // 清空
        Object.keys(CATEGORY_TREE).forEach(key => {
            editCat.add(new Option(key, key));
        });
        // 触发一次子分类更新
        updateSubCategoryOptions();
    }
    if (editSeason) {
        editSeason.innerHTML = '';
        WEATHER_TYPES.forEach(w => editSeason.add(new Option(w, w)));
        editSeason.add(new Option("未知", "未知"));
    }

    // 初始化编辑弹窗的颜色 checkbox
    const colorContainer = document.getElementById('color-checkbox-group');
    if (colorContainer) {
        colorContainer.innerHTML = '';
        COLOR_TYPES.forEach(c => {
            const label = document.createElement('label');
            label.style.cssText = "display: inline-flex; align-items: center; gap: 4px; font-size: 0.85rem; cursor: pointer; padding: 4px 8px; background: #f8f9fa; border-radius: 15px; border: 1px solid #eee; user-select: none;";
            
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.value = c;
            checkbox.name = 'color-option';
            
            // 样式切换逻辑
            checkbox.onchange = () => {
                label.style.background = checkbox.checked ? "#e3f2fd" : "#f8f9fa";
                label.style.borderColor = checkbox.checked ? "#2196f3" : "#eee";
                label.style.color = checkbox.checked ? "#1565c0" : "#333";
            };
            
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
        
        // 初始显示全部
        currentFilteredItems = allClothes;
        
        updateLocationSuggestions();
        updateCount(allClothes.length);
        renderGallery(currentFilteredItems);
        setupInteractions();
    } catch (e) {
        console.error("加载失败", e);
        alert("无法连接服务器，请确认 python server.py 正在运行");
    }
}

// === 2. 上传与裁剪逻辑 (修复版) ===
function setupUpload() {
    const btn = document.getElementById('uploadBtn');
    const input = document.getElementById('fileInput');
    
    if(btn && input) {
        btn.onclick = () => input.click(); // 绑定点击
        input.onchange = (e) => {
            if (e.target.files && e.target.files[0]) {
                const file = e.target.files[0];
                startCrop(file);
                input.value = ''; // 清空，允许重复上传
            }
        };
    }
}

function startCrop(file) {
    const reader = new FileReader();
    reader.onload = (e) => {
        document.getElementById('cropModal').style.display = 'block';
        const image = document.getElementById('cropImage');
        image.src = e.target.result;
        
        if (cropper) cropper.destroy();
        cropper = new Cropper(image, {
            aspectRatio: NaN, // 自由比例
            viewMode: 1,
            autoCropArea: 0.9,
        });
    };
    reader.readAsDataURL(file);
}

function closeCropModal() {
    document.getElementById('cropModal').style.display = 'none';
    if (cropper) cropper.destroy();
}

async function confirmCrop() {
    if (!cropper) return;
    const canvas = cropper.getCroppedCanvas({ width: 800 });
    const base64Image = canvas.toDataURL('image/jpeg', 0.85);
    
    closeCropModal();
    
    // 打开编辑框，准备接收 AI 数据
    openEditModal(null, true); 
    document.getElementById('modalImg').src = base64Image;
    document.getElementById('aiStatus').style.display = 'block';
    
    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ image: base64Image })
        });
        
        if (!response.ok) throw new Error("AI Error");
        const aiTags = await response.json();
        
        document.getElementById('aiStatus').style.display = 'none';
        
        // 填入 AI 识别结果
        if (aiTags.category) {
            document.getElementById('editCategory').value = aiTags.category;
            updateSubCategoryOptions(); // 联动更新子分类
        }
        if (aiTags.sub_category) document.getElementById('editSubCategory').value = aiTags.sub_category;
        if (aiTags.season) document.getElementById('editSeason').value = aiTags.season;
        if (aiTags.material) document.getElementById('editMaterial').value = aiTags.material;
        
        // 颜色多选回显
        if (aiTags.color) {
            const checkboxes = document.querySelectorAll('input[name="color-option"]');
            checkboxes.forEach(cb => {
                cb.checked = aiTags.color.includes(cb.value);
                cb.dispatchEvent(new Event('change')); // 触发样式更新
            });
        }
        
        currentEditingItem = { isNew: true, imageBase64: base64Image };
        
    } catch (e) {
        alert("AI 识别出错了: " + e.message);
        document.getElementById('aiStatus').textContent = "❌ 识别失败";
    }
}

// === 3. 编辑弹窗逻辑 (修复数据回显) ===
function openEditModal(item, isNew = false) {
    const modal = document.getElementById('editModal');
    modal.style.display = 'block';
    
    // 重置颜色勾选
    document.querySelectorAll('input[name="color-option"]').forEach(cb => {
        cb.checked = false;
        cb.dispatchEvent(new Event('change'));
    });

    if (isNew) {
        // 新建模式
        document.getElementById('modalTitle').textContent = "✨ 新衣入库";
        document.getElementById('editFilename').value = "自动生成...";
        document.getElementById('editLocation').value = "";
        document.getElementById('editCategory').value = "上装";
        updateSubCategoryOptions();
        document.getElementById('editSubCategory').value = "";
        document.getElementById('editSeason').value = "舒适(春秋)";
        document.getElementById('editMaterial').value = "";
        document.getElementById('editDescription').value = "";
    } else {
        // 编辑模式
        currentEditingItem = item;
        document.getElementById('modalTitle').textContent = "✏️ 编辑档案";
        document.getElementById('aiStatus').style.display = 'none';
        
        // 回显数据
        document.getElementById('modalImg').src = item.path;
        document.getElementById('editFilename').value = item.filename;
        document.getElementById('editLocation').value = item.location || '';
        
        // 分类回显
        const cat = item.tags.category || '上装';
        document.getElementById('editCategory').value = cat;
        updateSubCategoryOptions(); // 必须先更新子分类列表
        document.getElementById('editSubCategory').value = item.tags.sub_category || '';
        
        document.getElementById('editSeason').value = item.tags.season || '未知';
        document.getElementById('editMaterial').value = item.tags.material || '';
        document.getElementById('editDescription').value = item.description || item.tags.description || '';
        
        // 颜色回显
        const colorStr = item.tags.color || '';
        document.querySelectorAll('input[name="color-option"]').forEach(cb => {
            if (colorStr.includes(cb.value)) {
                cb.checked = true;
                cb.dispatchEvent(new Event('change'));
            }
        });
    }
}

window.updateSubCategoryOptions = function() {
    const mainCat = document.getElementById('editCategory').value;
    const subList = document.getElementById('sub-cat-list');
    subList.innerHTML = ''; // 清空
    
    if (CATEGORY_TREE[mainCat]) {
        CATEGORY_TREE[mainCat].forEach(sub => {
            const option = document.createElement('option');
            option.value = sub;
            subList.appendChild(option);
        });
    }
}

// 保存逻辑
async function saveChanges() {
    // 获取颜色
    const checkedColors = Array.from(document.querySelectorAll('input[name="color-option"]:checked'))
        .map(cb => cb.value);
    const colorStr = checkedColors.join('、');

    const tags = {
        category: document.getElementById('editCategory').value,
        sub_category: document.getElementById('editSubCategory').value,
        season: document.getElementById('editSeason').value,
        material: document.getElementById('editMaterial').value,
        color: colorStr
    };
    
    const location = document.getElementById('editLocation').value;
    const description = document.getElementById('editDescription').value;

    const btn = document.getElementById('saveBtn');
    btn.textContent = "⏳ 保存中...";
    btn.disabled = true;
    
    try {
        let url = currentEditingItem.isNew ? '/api/save_new' : '/api/update';
        let body = {
            location: location,
            tags: tags,
            description: description
        };

        if (currentEditingItem.isNew) {
            body.image = currentEditingItem.imageBase64;
        } else {
            body.filename = currentEditingItem.filename;
        }

        const response = await fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        });

        if (!response.ok) throw new Error("保存失败");
        
        document.getElementById('editModal').style.display = 'none';
        await loadData(); // 刷新列表
        // alert("✅ 保存成功"); // 可选提示
        
    } catch (e) {
        alert("保存失败: " + e.message);
    } finally {
        btn.textContent = "💾 保存档案";
        btn.disabled = false;
    }
}

// === 4. 渲染与分页 (数字分页版) ===
function renderGallery(items) {
    // 1. 计算分页
    const totalPages = Math.ceil(items.length / itemsPerPage);
    if (currentPage > totalPages) currentPage = 1;
    
    const start = (currentPage - 1) * itemsPerPage;
    const end = start + itemsPerPage;
    const pageItems = items.slice(start, end);
    
    // 2. 渲染卡片
    const gallery = document.getElementById('gallery');
    gallery.innerHTML = '';
    
    if (pageItems.length === 0) {
        gallery.innerHTML = `<div style="grid-column:1/-1; text-align:center; padding:40px; color:#999;">暂无衣物</div>`;
    }

    pageItems.forEach(item => {
        const card = document.createElement('div');
        card.className = 'card';
        card.onclick = () => openEditModal(item);
        
        const imgPath = item.path.replace(/\\/g, '/');
        const title = `${item.tags.category} ${item.tags.color || ''}`;
        
        // 生成标签
        let tagsHtml = '';
        if (item.tags.category) tagsHtml += `<span class="tag tag-cat">${item.tags.category}</span>`;
        if (item.tags.season && item.tags.season !== '未知') tagsHtml += `<span class="tag tag-season">${item.tags.season}</span>`;
        
        card.innerHTML = `
            <div class="img-box">
                <img src="${imgPath}" loading="lazy">
                <div class="edit-hint">点击编辑详情</div>
            </div>
            <div class="info">
                <div class="info-header">
                    <div class="item-title">${title}</div>
                    ${item.code ? `<div class="item-code">#${item.code}</div>` : ''}
                </div>
                <div class="tags-row">${tagsHtml}</div>
                <div class="item-desc">${item.description || '暂无描述'}</div>
                <div class="item-loc">📍 ${item.location || '待整理'}</div>
            </div>
        `;
        gallery.appendChild(card);
    });

    // 3. 渲染数字分页
    renderPaginationNumbers(totalPages);
}

function renderPaginationNumbers(totalPages) {
    const container = document.getElementById('pagination');
    container.innerHTML = '';
    
    if (totalPages <= 1) return;

    // 上一页
    const prevBtn = document.createElement('button');
    prevBtn.className = 'page-nav-btn';
    prevBtn.innerHTML = '&lt;';
    prevBtn.disabled = currentPage === 1;
    prevBtn.onclick = () => changePage(currentPage - 1);
    container.appendChild(prevBtn);

    // 生成页码逻辑: 1 2 ... 5 6 7 ... 99 100
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
            span.textContent = '...';
            container.appendChild(span);
        } else {
            const btn = document.createElement('div');
            btn.className = `page-number ${p === currentPage ? 'active' : ''}`;
            btn.textContent = p;
            btn.onclick = () => changePage(p);
            container.appendChild(btn);
        }
    });

    // 下一页
    const nextBtn = document.createElement('button');
    nextBtn.className = 'page-nav-btn';
    nextBtn.innerHTML = '&gt;';
    nextBtn.disabled = currentPage === totalPages;
    nextBtn.onclick = () => changePage(currentPage + 1);
    container.appendChild(nextBtn);
}

function changePage(p) {
    currentPage = p;
    renderGallery(currentFilteredItems);
    document.querySelector('.main-content').scrollTop = 0;
}

// === 辅助逻辑 ===
function updateCount(n) { document.getElementById('count').textContent = `(${n})`; }

function updateLocationSuggestions() {
    const list = document.getElementById('location-list');
    if (!list) return;
    const set = new Set(["主卧衣柜", "次卧衣柜", "收纳箱"]);
    allClothes.forEach(i => i.location && set.add(i.location));
    list.innerHTML = '';
    set.forEach(loc => {
        const opt = document.createElement('option');
        opt.value = loc;
        list.appendChild(opt);
    });
}

function setupModal() {
    // 绑定关闭按钮
    const closeBtns = document.querySelectorAll('.close-btn');
    closeBtns.forEach(btn => {
        btn.onclick = function() {
            this.closest('.modal').style.display = 'none';
        }
    });
    
    // 点击遮罩关闭
    window.onclick = function(e) {
        if (e.target.classList.contains('modal')) {
            e.target.style.display = 'none';
        }
    }
}

function setupInteractions() {
    // 筛选逻辑
    const doFilter = () => {
        const term = document.getElementById('searchInput').value.toLowerCase();
        const cat = document.getElementById('filterCategory').value;
        const sea = document.getElementById('filterSeason').value;
        const col = document.getElementById('filterColor').value;
        
        currentFilteredItems = allClothes.filter(item => {
            const str = (item.filename + JSON.stringify(item.tags)).toLowerCase();
            const matchSearch = !term || str.includes(term);
            const matchCat = !cat || (item.tags.category === cat);
            const matchSea = !sea || (item.tags.season === sea);
            const matchCol = !col || (item.tags.color && item.tags.color.includes(col));
            return matchSearch && matchCat && matchSea && matchCol;
        });
        
        currentPage = 1;
        renderGallery(currentFilteredItems);
        updateCount(currentFilteredItems.length);
    };

    ['searchInput', 'filterCategory', 'filterSeason', 'filterColor'].forEach(id => {
        document.getElementById(id).addEventListener('input', doFilter);
    });

    document.getElementById('resetFiltersBtn').onclick = () => {
        document.getElementById('searchInput').value = '';
        document.getElementById('filterCategory').value = '';
        document.getElementById('filterSeason').value = '';
        document.getElementById('filterColor').value = '';
        doFilter();
    };
}