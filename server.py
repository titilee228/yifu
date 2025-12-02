import os
import json
import datetime
import base64
import random
import re
import webbrowser
from flask import Flask, request, jsonify, send_from_directory
from zhipuai import ZhipuAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)

# ================= 配置区域 =================
API_KEY = "5139feb2aaab46e192a8d7a7f2dc255e.SmsBFnVpU0Dle0Rn" 
WARDROBE_DIR = os.path.join(BASE_DIR, "01_Wardrobe")
INVENTORY_FILE = os.path.join(BASE_DIR, "inventory.json")
# ===========================================

client = ZhipuAI(api_key=API_KEY)

if not os.path.exists(WARDROBE_DIR):
    os.makedirs(WARDROBE_DIR)

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
    while os.path.exists(os.path.join(WARDROBE_DIR, new_filename)):
        new_filename = f"{name}_{counter:03d}{ext}"
        counter += 1
    return new_filename

# === 判断文件名是否已经是命名格式 ===
def is_named_file(filename):
    name, ext = os.path.splitext(filename)
    parts = name.split('_')
    if len(parts) >= 3:
        last_part = parts[-1]
        if re.match(r'^\d{4}$', last_part):
            return True
    return False

# === 从文件名提取衣物代码 ===
def extract_code_from_filename(filename):
    name, ext = os.path.splitext(filename)
    parts = name.split('_')
    if len(parts) >= 3:
        last_part = parts[-1]
        match = re.match(r'^(\d{4})', last_part)
        if match:
            return match.group(1)
    return None

# === 核心 AI 分析函数 ===
def call_ai_analysis(image_base64):
    prompt_text = """
    你是一位私人衣橱整理师。请根据用户的专属分类体系，对图片中的主体进行分类。
    
    1. 【分类】(必须从以下列表中精准选择一个，不要创造新词):
       衣物类: [西装外套, 大衣, 风衣, 连衣裙, 套装, 夹克, 羽绒服, 卫衣, 棉衣, 毛衫, 上衣, 牛仔外套, 外套, 裤子, 牛仔裤, 短裤, 半裙]
       配饰类: [手镯, 耳环, 项链, 包包, 围巾, 帽饰, 胸针, 腰带, 眼镜, 手套]
       其他类: [其他]
       
    2. 【天气】(从以下选择):
       [炎热（夏季）, 舒适（春秋）, 寒冷（冬季）]
       
    3. 【颜色】(从以下选择):
       [黑色, 灰色, 白色, 米色, 棕色, 黄色, 橙色, 红色, 粉色, 紫色, 蓝色, 绿色, 金色, 银色, 玫瑰金]
       
    4. 【说明文字】请用一句话简单描述这件衣物（15字以内，例如："经典黑色连衣裙"、"蓝色休闲牛仔裤"等）
       
    请返回 JSON:
    {
        "category": "从分类列表中选一个",
        "season": "从天气列表中选一个",
        "color": "从颜色列表中选一个",
        "description": "简单描述这件衣物，15字以内"
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
        ai_result = ai_result.replace("```json", "").replace("```", "")
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

@app.route('/api/clothes', methods=['GET'])
def get_clothes():
    inventory = load_inventory()
    valid_inventory = []
    inv_map = {item['filename']: item for item in inventory}
    
    for root, dirs, files in os.walk(WARDROBE_DIR):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.heic', '.gif')):
                rel_path = os.path.relpath(os.path.join(root, file), BASE_DIR)
                web_path = rel_path.replace("\\", "/")
                
                if file not in inv_map:
                    cat = "未分类"
                    col = ""
                    code = None
                    parts = file.split('_')
                    if len(parts) >= 2:
                        cat = parts[0]
                        if len(parts) >= 3: 
                            last_part = parts[-1].split('.')[0]
                            if len(last_part) == 4 and last_part.isdigit():
                                code = last_part
                                if len(parts) >= 3:
                                    col = parts[1] if len(parts) > 2 else ""
                            else:
                                col = last_part
                    
                    code = extract_code_from_filename(file)
                    
                    new_item = {
                        "id": file,
                        "filename": file,
                        "path": web_path,
                        "location": "待整理",
                        "added_date": str(datetime.date.today()),
                        "tags": {"category": cat, "season": "未知", "color": col},
                        "code": code,
                        "description": ""
                    }
                    valid_inventory.append(new_item)
                else:
                    item = inv_map[file]
                    item['path'] = web_path
                    if 'code' not in item:
                        item['code'] = extract_code_from_filename(file)
                    if 'description' not in item:
                        item['description'] = item.get('description', '')
                    valid_inventory.append(item)
    
    save_inventory(valid_inventory)
    return jsonify(valid_inventory)

@app.route('/api/analyze', methods=['POST'])
def analyze_image():
    data = request.json
    image_base64 = data.get('image')
    
    if not image_base64: return jsonify({"error": "无图片"}), 400

    print("🤖 AI 正在分析上传图片...")
    tags = call_ai_analysis(image_base64)
    if tags:
        return jsonify(tags)
    else:
        return jsonify({"error": "AI 分析失败"}), 500

@app.route('/api/analyze_local', methods=['POST'])
def analyze_local_file():
    data = request.json
    filename = data.get('filename')
    
    file_path = os.path.join(WARDROBE_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "文件不存在"}), 404

    if is_named_file(filename):
        return jsonify({"error": "文件已命名，跳过识别", "skip": True}), 200

    try:
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
        print(f"🤖 正在自动识别新衣服: {filename} ...")
        tags = call_ai_analysis(encoded_string)
        
        if tags:
            inventory = load_inventory()
            target_item = None
            for item in inventory:
                if item['filename'] == filename:
                    target_item = item
                    break
            
            if target_item:
                target_item['tags'] = tags
                if 'description' in tags:
                    target_item['description'] = tags.get('description', '')
                
                name, ext = os.path.splitext(filename)
                cat = tags.get('category', '未分类')
                col = tags.get('color', '')
                
                existing_code = extract_code_from_filename(filename)
                if existing_code:
                    code = existing_code
                else:
                    code = str(random.randint(1000,9999))
                
                new_filename = f"{cat}_{col}_{code}{ext}"
                new_filename = new_filename.replace("/", "-")
                
                safe_new_name = get_safe_filename(new_filename)
                new_path = os.path.join(WARDROBE_DIR, safe_new_name)
                
                if safe_new_name != filename:
                    try:
                        os.rename(file_path, new_path)
                        target_item['filename'] = safe_new_name
                        target_item['path'] = target_item['path'].replace(filename, safe_new_name)
                        target_item['id'] = safe_new_name
                        print(f"✅ 已重命名为: {safe_new_name}")
                    except Exception as rename_err:
                        print(f"⚠️ 重命名失败: {rename_err}")
                        safe_new_name = filename
                
                target_item['code'] = code
                save_inventory(inventory)
                return jsonify({"success": True, "tags": tags, "new_filename": safe_new_name, "code": code})
        else:
            return jsonify({"error": "AI 无法识别"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 新增：专门用于补全说明文字的接口 ===
@app.route('/api/fill_description', methods=['POST'])
def fill_description():
    data = request.json
    filename = data.get('filename')
    
    file_path = os.path.join(WARDROBE_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "文件不存在"}), 404

    try:
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
        print(f"📝 正在补全描述: {filename} ...")
        tags = call_ai_analysis(encoded_string)
        
        if tags and 'description' in tags:
            new_desc = tags['description']
            
            inventory = load_inventory()
            target_item = None
            for item in inventory:
                if item['filename'] == filename:
                    target_item = item
                    break
            
            if target_item:
                target_item['description'] = new_desc
                # 同时更新tags里的description，保持同步
                if 'tags' in target_item:
                    target_item['tags']['description'] = new_desc
                
                save_inventory(inventory)
                return jsonify({"success": True, "description": new_desc})
        
        return jsonify({"error": "AI 未生成描述"}), 500
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/save_new', methods=['POST'])
def save_new_cloth():
    data = request.json
    image_base64 = data.get('image')
    tags = data.get('tags')
    location = data.get('location')
    description = data.get('description', '')
    
    ext = ".jpg"
    cat = tags.get('category', '未分类')
    col = tags.get('color', '')
    filename = f"{cat}_{col}_{random.randint(1000,9999)}{ext}"
    filename = filename.replace("/", "-")
    
    safe_filename = get_safe_filename(filename)
    save_path = os.path.join(WARDROBE_DIR, safe_filename)
    
    try:
        if ',' in image_base64: image_base64 = image_base64.split(',')[1]
        with open(save_path, "wb") as f:
            f.write(base64.b64decode(image_base64))
            
        web_path = os.path.relpath(save_path, BASE_DIR).replace("\\", "/")
        code = extract_code_from_filename(safe_filename)
        final_description = description or tags.get('description', '')
        
        new_item = {
            "id": safe_filename,
            "filename": safe_filename,
            "path": web_path,
            "location": location,
            "added_date": str(datetime.date.today()),
            "tags": tags,
            "code": code,
            "description": final_description
        }
        
        inventory = load_inventory()
        inventory.append(new_item)
        save_inventory(inventory)
        return jsonify({"success": True, "item": new_item})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/update', methods=['POST'])
def update_cloth():
    data = request.json
    filename = data.get('filename')
    new_location = data.get('location')
    new_tags = data.get('tags')
    new_description = data.get('description', '')
    
    inventory = load_inventory()
    target = None
    for item in inventory:
        if item['filename'] == filename:
            target = item
            break
            
    if target:
        target['location'] = new_location
        if new_tags: 
            target['tags'] = new_tags
        if new_description is not None:
            target['description'] = new_description
        
        old_cat = target['tags'].get('category', '未分类')
        old_col = target['tags'].get('color', '')
        new_cat = new_tags.get('category', old_cat) if new_tags else old_cat
        new_col = new_tags.get('color', old_col) if new_tags else old_col
        
        old_code = extract_code_from_filename(filename)
        if not old_code:
            old_code = target.get('code')
            if not old_code:
                old_code = str(random.randint(1000,9999))
        
        name, ext = os.path.splitext(filename)
        parts = name.split('_')
        if len(parts) >= 3:
            old_file_cat = parts[0]
            old_file_col = parts[1] if len(parts) > 1 else ''
            
            if old_file_cat != new_cat or old_file_col != new_col:
                new_filename = f"{new_cat}_{new_col}_{old_code}{ext}"
                new_filename = new_filename.replace("/", "-")
                
                old_path = os.path.join(WARDROBE_DIR, filename)
                safe_new_name = get_safe_filename(new_filename)
                new_path = os.path.join(WARDROBE_DIR, safe_new_name)
                
                try:
                    os.rename(old_path, new_path)
                    target['filename'] = safe_new_name
                    target['path'] = target['path'].replace(filename, safe_new_name)
                    target['id'] = safe_new_name
                    target['code'] = old_code
                    print(f"✅ 已根据新标签重命名为: {safe_new_name}")
                except Exception as rename_err:
                    print(f"⚠️ 重命名失败: {rename_err}")
        
        save_inventory(inventory)
        return jsonify({"success": True, "new_filename": target['filename']})
    else:
        return jsonify({"error": "找不到文件"}), 404

if __name__ == '__main__':
    print(f"🚀 服务器启动中...")
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True, port=5000, use_reloader=False)