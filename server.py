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

# 判断文件名是否符合 类别_颜色_代码 格式
def is_named_file(filename):
    name, ext = os.path.splitext(filename)
    parts = name.split('_')
    if len(parts) >= 3:
        last_part = parts[-1]
        # 检查最后一部分是否为4位数字代码
        if re.match(r'^\d{4}$', last_part):
            return True
    return False

def extract_code_from_filename(filename):
    name, ext = os.path.splitext(filename)
    parts = name.split('_')
    # 尝试从文件名最后一部分提取4位数字
    if len(parts) >= 1:
        last_part = parts[-1]
        match = re.search(r'(\d{4})', last_part)
        if match:
            return match.group(1)
    return None

# === AI 分析核心函数 ===
def call_ai_analysis(image_base64):
    prompt_text = """
    你是一位私人衣橱整理师。请根据用户的专属分类体系，对图片中的主体进行分类。
    
    1. 【主分类】请严格从以下三个选项中选择一个:
       [衣服, 配饰, 其他]

    2. 【子分类】(请根据主分类选择最对应的一个):
       如果主分类是衣服: [西装外套, 大衣, 风衣, 连衣裙, 套装, 夹克, 羽绒服, 卫衣, 棉衣, 毛衫, 上衣, 牛仔外套, 外套, 裤子, 牛仔裤, 短裤, 半裙]
       如果主分类是配饰: [手镯, 耳环, 项链, 包包, 围巾, 帽饰, 胸针, 腰带, 眼镜, 手套]
       如果主分类是其他: [其他]
       
    3. 【天气/季节】(从以下选择):
       [炎热(夏季), 舒适(春秋), 寒冷(冬季)]
       
    4. 【颜色】(从以下选择，可多选):
       [黑色, 灰色, 白色, 米色, 棕色, 黄色, 橙色, 红色, 粉色, 紫色, 蓝色, 绿色, 金色, 银色, 玫瑰金]
       
    5. 【说明文字】请用一句话简单描述这件物品（15字以内，例如："经典黑色收腰连衣裙"、"蓝色破洞牛仔裤"等）。不要包含“这件衣服”等废话。
       
    请返回标准的 JSON 格式:
    {
        "category": "主分类",
        "sub_category": "子分类",
        "season": "季节",
        "color": "颜色",
        "description": "说明文字"
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

# === 获取所有衣物 ===
@app.route('/api/clothes', methods=['GET'])
def get_clothes():
    inventory = load_inventory()
    valid_inventory = []
    inv_map = {item['filename']: item for item in inventory}
    
    # 扫描文件夹
    for root, dirs, files in os.walk(WARDROBE_DIR):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.heic', '.gif')):
                rel_path = os.path.relpath(os.path.join(root, file), BASE_DIR)
                web_path = rel_path.replace("\\", "/")
                
                code = extract_code_from_filename(file)

                if file not in inv_map:
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
                    item = inv_map[file]
                    item['path'] = web_path
                    item['code'] = code 
                    if 'description' not in item:
                        item['description'] = item.get('tags', {}).get('description', '')
                    valid_inventory.append(item)
    
    save_inventory(valid_inventory)
    return jsonify(valid_inventory)

# === AI 分析接口 ===
@app.route('/api/analyze', methods=['POST'])
def analyze_image():
    data = request.json
    image_base64 = data.get('image')
    if not image_base64: return jsonify({"error": "无图片"}), 400
    
    tags = call_ai_analysis(image_base64)
    if tags:
        return jsonify(tags)
    else:
        return jsonify({"error": "AI 分析失败"}), 500

# === 自动扫描本地文件接口 ===
@app.route('/api/analyze_local', methods=['POST'])
def analyze_local_file():
    data = request.json
    filename = data.get('filename')
    file_path = os.path.join(WARDROBE_DIR, filename)
    
    if not os.path.exists(file_path): return jsonify({"error": "文件不存在"}), 404
    
    if is_named_file(filename): return jsonify({"error": "已命名", "skip": True}), 200

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
                
                name, ext = os.path.splitext(filename)
                cat_for_name = tags.get('sub_category') if tags.get('sub_category') else tags.get('category', '未分类')
                col = tags.get('color', '').split('、')[0]
                code = extract_code_from_filename(filename) or str(random.randint(1000,9999))
                
                new_filename = f"{cat_for_name}_{col}_{code}{ext}".replace("/", "-")
                safe_new_name = get_safe_filename(new_filename)
                
                if safe_new_name != filename:
                    try:
                        os.rename(file_path, os.path.join(WARDROBE_DIR, safe_new_name))
                        target_item['filename'] = safe_new_name
                        target_item['path'] = target_item['path'].replace(filename, safe_new_name)
                        target_item['id'] = safe_new_name
                    except:
                        safe_new_name = filename
                
                target_item['code'] = code
                save_inventory(inventory)
                return jsonify({"success": True, "tags": tags, "new_filename": safe_new_name, "code": code})
        
        return jsonify({"error": "AI无法识别"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 补全描述接口 ===
@app.route('/api/fill_description', methods=['POST'])
def fill_description():
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
                if 'tags' in target_item:
                    target_item['tags']['description'] = new_desc
                save_inventory(inventory)
                return jsonify({"success": True, "description": new_desc})
        return jsonify({"error": "无描述生成"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 保存新上传文件接口 ===
@app.route('/api/save_new', methods=['POST'])
def save_new_cloth():
    data = request.json
    image_base64 = data.get('image')
    tags = data.get('tags')
    location = data.get('location')
    description = data.get('description', '')
    
    ext = ".jpg"
    cat_for_name = tags.get('sub_category') if tags.get('sub_category') else tags.get('category', '未分类')
    col = tags.get('color', '').split('、')[0]
    code = str(random.randint(1000,9999))
    
    filename = f"{cat_for_name}_{col}_{code}{ext}".replace("/", "-")
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

# === 更新衣物信息接口 ===
@app.route('/api/update', methods=['POST'])
def update_cloth():
    data = request.json
    filename = data.get('filename')
    new_location = data.get('location')
    new_tags = data.get('tags')
    new_description = data.get('description', '')
    
    inventory = load_inventory()
    target = next((i for i in inventory if i['filename'] == filename), None)
            
    if target:
        target['location'] = new_location
        if new_tags: target['tags'] = new_tags
        target['description'] = new_description
        
        old_code = extract_code_from_filename(filename) or target.get('code') or str(random.randint(1000,9999))
        cat_for_name = new_tags.get('sub_category') if new_tags.get('sub_category') else new_tags.get('category', '未分类')
        col = new_tags.get('color', '').split('、')[0]
        name, ext = os.path.splitext(filename)
        
        new_filename = f"{cat_for_name}_{col}_{old_code}{ext}".replace("/", "-")
        
        if new_filename != filename:
            try:
                safe_new_name = get_safe_filename(new_filename)
                os.rename(os.path.join(WARDROBE_DIR, filename), os.path.join(WARDROBE_DIR, safe_new_name))
                target['filename'] = safe_new_name
                target['path'] = target['path'].replace(filename, safe_new_name)
                target['id'] = safe_new_name
                target['code'] = old_code
            except Exception as e:
                print(f"Rename failed: {e}")
        
        save_inventory(inventory)
        return jsonify({"success": True, "new_filename": target['filename']})
    return jsonify({"error": "找不到文件"}), 404

# === 删除接口 (支持物理删除) ===
@app.route('/api/delete', methods=['POST'])
def delete_cloth():
    data = request.json
    filename = data.get('filename')
    
    file_path = os.path.join(WARDROBE_DIR, filename)
    inventory = load_inventory()
    
    new_inventory = [i for i in inventory if i['filename'] != filename]
    
    if len(new_inventory) == len(inventory):
        return jsonify({"error": "记录未找到"}), 404
        
    save_inventory(new_inventory)
    
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"error": f"文件删除失败: {str(e)}"}), 500
    else:
        return jsonify({"success": True, "message": "文件已丢失，记录已删除"})

if __name__ == '__main__':
    print(f"🚀 服务器启动中...")
    webbrowser.open("http://127.0.0.1:5000")
    app.run(debug=True, port=5000, use_reloader=False)