import os
import json
import datetime
import base64
import random
import re
import shutil
import webbrowser
from flask import Flask, request, jsonify, send_from_directory
from zhipuai import ZhipuAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)

# ================= 配置区域 =================
API_KEY = "5139feb2aaab46e192a8d7a7f2dc255e.SmsBFnVpU0Dle0Rn" 
WARDROBE_DIR = os.path.join(BASE_DIR, "01_Wardrobe")
RECYCLE_BIN = os.path.join(WARDROBE_DIR, "回收站") # 定义回收站路径
INVENTORY_FILE = os.path.join(BASE_DIR, "inventory.json")
# ===========================================

client = ZhipuAI(api_key=API_KEY)

# 确保文件夹存在
if not os.path.exists(WARDROBE_DIR):
    os.makedirs(WARDROBE_DIR)
if not os.path.exists(RECYCLE_BIN):
    os.makedirs(RECYCLE_BIN)

def load_inventory():
    if os.path.exists(INVENTORY_FILE):
        try:
            with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_inventory(data):
    with open(INVENTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_safe_filename(filename):
    name, ext = os.path.splitext(filename)
    counter = 1
    new_filename = filename
    # 确保不覆盖已有文件（排除自己）
    while os.path.exists(os.path.join(WARDROBE_DIR, new_filename)):
        new_filename = f"{name}_{counter:03d}{ext}"
        counter += 1
    return new_filename

# === 提取代码逻辑 (增强版) ===
def extract_code_from_filename(filename):
    name, _ = os.path.splitext(filename)
    # 尝试匹配末尾的4位数字 (支持 _1234 或 1234)
    match = re.search(r'(\d{4})$', name)
    if match:
        return match.group(1)
    return None

# === AI 分析核心函数 (Prompt升级) ===
def call_ai_analysis(image_base64):
    prompt_text = """
    你是一位私人衣橱整理师。请对图片中的衣物进行精准分类。
    
    1. 【主分类】(单选): [衣服, 配饰, 其他]
    2. 【子分类】(单选): 
       - 衣服: [西装外套, 大衣, 风衣, 连衣裙, 套装, 夹克, 羽绒服, 卫衣, 棉衣, 毛衫, 上衣, T恤, 牛仔外套, 外套, 裤子, 牛仔裤, 短裤, 半裙]
       - 配饰: [手镯, 耳环, 项链, 包包, 围巾, 帽饰, 胸针, 腰带, 眼镜, 手套]
       - 其他: [其他]
    3. 【季节】(单选): [炎热, 舒适, 寒冷] (注意：炎热对应夏季，舒适对应春秋，寒冷对应冬季)
    4. 【颜色】(多选): [黑色, 灰色, 白色, 米色, 棕色, 黄色, 橙色, 红色, 粉色, 紫色, 蓝色, 绿色, 金色, 银色, 玫瑰金, 多色]。
       *如果包含多种明显颜色，请用"+"号连接，例如"黑色+白色"。
    5. 【描述】: 15字以内简述，例如"经典黑色收腰连衣裙"。
       
    返回JSON:
    {
        "category": "主分类",
        "sub_category": "子分类",
        "season": "季节",
        "color": "颜色",
        "description": "描述"
    }
    """
    try:
        if ',' in image_base64: image_base64 = image_base64.split(',')[1]
        
        response = client.chat.completions.create(
            model="glm-4v",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": image_base64}}
                    ]
                }
            ]
        )
        ai_result = response.choices[0].message.content
        ai_result = ai_result.replace("```json", "").replace("```", "").strip()
        return json.loads(ai_result)
    except Exception as e:
        print(f"AI Error: {e}")
        return None

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory(BASE_DIR, path)

# === 获取列表 ===
@app.route('/api/clothes', methods=['GET'])
def get_clothes():
    inventory = load_inventory()
    valid_inventory = []
    inv_map = {item['filename']: item for item in inventory}
    
    # 扫描文件夹 (排除回收站)
    for root, dirs, files in os.walk(WARDROBE_DIR):
        if "回收站" in root: continue # 跳过回收站
        
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.heic', '.gif')):
                rel_path = os.path.relpath(os.path.join(root, file), BASE_DIR)
                web_path = rel_path.replace("\\", "/")
                
                code = extract_code_from_filename(file)

                if file not in inv_map:
                    # 新文件初始化
                    new_item = {
                        "id": file,
                        "filename": file,
                        "path": web_path,
                        "location": "待整理",
                        "added_date": str(datetime.date.today()),
                        "tags": {"category": "未分类", "sub_category": "", "season": "未知", "color": ""},
                        "code": code,
                        "description": ""
                    }
                    valid_inventory.append(new_item)
                else:
                    # 旧文件更新
                    item = inv_map[file]
                    item['path'] = web_path
                    item['code'] = code # 始终以文件名里的代码为准
                    if 'description' not in item:
                        item['description'] = item.get('tags', {}).get('description', '')
                    valid_inventory.append(item)
    
    save_inventory(valid_inventory)
    return jsonify(valid_inventory)

# === AI 识别接口 ===
@app.route('/api/analyze', methods=['POST'])
def analyze_image():
    data = request.json
    image_base64 = data.get('image')
    if not image_base64: return jsonify({"error": "无图片"}), 400
    
    tags = call_ai_analysis(image_base64)
    return jsonify(tags) if tags else (jsonify({"error": "AI 分析失败"}), 500)

# === 本地文件重新识别 ===
@app.route('/api/analyze_local', methods=['POST'])
def analyze_local_file():
    data = request.json
    filename = data.get('filename')
    file_path = os.path.join(WARDROBE_DIR, filename)
    
    if not os.path.exists(file_path): return jsonify({"error": "文件不存在"}), 404

    try:
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        tags = call_ai_analysis(encoded_string)
        if tags:
            inventory = load_inventory()
            target_item = next((i for i in inventory if i['filename'] == filename), None)
            
            if target_item:
                target_item['tags'] = tags
                target_item['description'] = tags.get('description', '')
                
                # === 核心逻辑：自动重命名 (含季节) ===
                name, ext = os.path.splitext(filename)
                
                cat = tags.get('sub_category') or tags.get('category', '未分类')
                col = tags.get('color', '').replace('、', '+') # 确保颜色用+号
                sea = tags.get('season', '未知')
                code = extract_code_from_filename(filename) or str(random.randint(1000,9999))
                
                # 新格式：分类_颜色_季节_代码.jpg
                new_filename = f"{cat}_{col}_{sea}_{code}{ext}".replace("/", "-")
                safe_new_name = get_safe_filename(new_filename)
                
                if safe_new_name != filename:
                    try:
                        os.rename(file_path, os.path.join(WARDROBE_DIR, safe_new_name))
                        target_item['filename'] = safe_new_name
                        target_item['path'] = target_item['path'].replace(filename, safe_new_name)
                        target_item['id'] = safe_new_name
                    except Exception as e:
                        print(f"Rename failed: {e}")
                        safe_new_name = filename # 失败则回退
                
                target_item['code'] = code
                save_inventory(inventory)
                return jsonify({"success": True, "tags": tags, "new_filename": safe_new_name, "code": code})
        
        return jsonify({"error": "AI无法识别"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 补全描述接口 ===
@app.route('/api/fill_description', methods=['POST'])
def fill_description():
    # ... (此处逻辑保持不变，为节省篇幅略，实际使用请保留原逻辑或复制下方完整块)
    data = request.json
    filename = data.get('filename')
    file_path = os.path.join(WARDROBE_DIR, filename)
    if not os.path.exists(file_path): return jsonify({"error": "文件不存在"}), 404
    try:
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        tags = call_ai_analysis(encoded_string)
        if tags and 'description' in tags:
            new_desc = tags['description']
            inventory = load_inventory()
            target_item = next((i for i in inventory if i['filename'] == filename), None)
            if target_item:
                target_item['description'] = new_desc
                if 'tags' in target_item: target_item['tags']['description'] = new_desc
                save_inventory(inventory)
                return jsonify({"success": True, "description": new_desc})
        return jsonify({"error": "无描述"}), 500
    except Exception as e: return jsonify({"error": str(e)}), 500

# === 保存新衣 (新 PRD 规则) ===
@app.route('/api/save_new', methods=['POST'])
def save_new_cloth():
    data = request.json
    image_base64 = data.get('image')
    tags = data.get('tags')
    location = data.get('location')
    description = data.get('description', '')
    manual_code = data.get('code') # 支持手动输入代码
    
    ext = ".jpg"
    # 构建文件名要素
    cat = tags.get('sub_category') or tags.get('category', '未分类')
    col = tags.get('color', '').replace('、', '+')
    sea = tags.get('season', '未知')
    code = manual_code if manual_code else str(random.randint(1000,9999))
    
    # 命名格式：分类_颜色_季节_代码.jpg
    filename = f"{cat}_{col}_{sea}_{code}{ext}".replace("/", "-")
    safe_filename = get_safe_filename(filename)
    save_path = os.path.join(WARDROBE_DIR, safe_filename)
    
    try:
        if ',' in image_base64: image_base64 = image_base64.split(',')[1]
        with open(save_path, "wb") as f:
            f.write(base64.b64decode(image_base64))
            
        web_path = os.path.relpath(save_path, BASE_DIR).replace("\\", "/")
        
        new_item = {
            "id": safe_filename,
            "filename": safe_filename,
            "path": web_path,
            "location": location,
            "added_date": str(datetime.date.today()),
            "tags": tags,
            "code": code,
            "description": description
        }
        
        inventory = load_inventory()
        inventory.append(new_item)
        save_inventory(inventory)
        return jsonify({"success": True, "item": new_item})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 更新信息 (软删除支持) ===
@app.route('/api/update', methods=['POST'])
def update_cloth():
    data = request.json
    filename = data.get('filename')
    new_location = data.get('location')
    new_tags = data.get('tags')
    new_description = data.get('description', '')
    new_code = data.get('code') # 支持修改代码
    
    inventory = load_inventory()
    target = next((i for i in inventory if i['filename'] == filename), None)
            
    if target:
        target['location'] = new_location
        if new_tags: target['tags'] = new_tags
        target['description'] = new_description
        
        # 命名重构
        cat = new_tags.get('sub_category') or new_tags.get('category', '未分类')
        col = new_tags.get('color', '').replace('、', '+')
        sea = new_tags.get('season', '未知')
        code = new_code if new_code else (extract_code_from_filename(filename) or target.get('code'))
        
        name, ext = os.path.splitext(filename)
        # 确保使用原扩展名
        
        new_filename = f"{cat}_{col}_{sea}_{code}{ext}".replace("/", "-")
        
        # 文件重命名操作
        if new_filename != filename:
            try:
                safe_new_name = get_safe_filename(new_filename)
                os.rename(os.path.join(WARDROBE_DIR, filename), os.path.join(WARDROBE_DIR, safe_new_name))
                
                target['filename'] = safe_new_name
                target['path'] = target['path'].replace(filename, safe_new_name)
                target['id'] = safe_new_name
                target['code'] = code # 更新代码
            except Exception as e:
                print(f"Rename error: {e}")
        
        save_inventory(inventory)
        return jsonify({"success": True, "new_filename": target['filename']})
    return jsonify({"error": "未找到文件"}), 404

# === 软删除接口 (移动到回收站) ===
@app.route('/api/delete', methods=['POST'])
def delete_cloth():
    data = request.json
    filename = data.get('filename')
    
    src_path = os.path.join(WARDROBE_DIR, filename)
    dst_path = os.path.join(RECYCLE_BIN, filename)
    
    # 1. 从数据记录中移除
    inventory = load_inventory()
    new_inventory = [i for i in inventory if i['filename'] != filename]
    
    if len(new_inventory) == len(inventory):
        return jsonify({"error": "记录未找到"}), 404
    
    save_inventory(new_inventory)
    
    # 2. 物理移动文件 (软删除)
    if os.path.exists(src_path):
        try:
            # 如果回收站有同名文件，先重命名回收站里的
            if os.path.exists(dst_path):
                base, ext = os.path.splitext(filename)
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                dst_path = os.path.join(RECYCLE_BIN, f"{base}_del_{timestamp}{ext}")
            
            shutil.move(src_path, dst_path)
            return jsonify({"success": True, "message": "已移入回收站"})
        except Exception as e:
            return jsonify({"error": f"移动失败: {str(e)}"}), 500
    else:
        return jsonify({"success": True, "message": "文件已丢失，仅删除记录"})

if __name__ == '__main__':
    print(f"🚀 服务器启动中...")
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True, port=5000, use_reloader=False)