from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory
import io
import os
import subprocess
from pathlib import Path

app = Flask(__name__)
DATA_FOLDER = os.environ.get('DATA_FOLDER', '/data')

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="/favicon.ico">
    <title>Miso Gallery</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            background: #0d0d0d; 
            color: #e0e0e0; 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            min-height: 100vh;
        }
        header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #333;
            gap: 12px;
            flex-wrap: wrap;
        }
        h1 { font-size: 1.5rem; background: linear-gradient(90deg, #f5a623, #f76c1c); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .header-actions {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-left: auto;
        }
        .breadcrumb { color: #888; font-size: 0.9rem; }
        .breadcrumb a { color: #f5a623; text-decoration: none; }
        .refresh-btn {
            background: linear-gradient(135deg, #2f2f4f 0%, #243357 100%);
            color: #f5a623;
            border: 1px solid #4b4b75;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 0.9rem;
            cursor: pointer;
            transition: transform 0.15s, border-color 0.2s, box-shadow 0.2s;
            white-space: nowrap;
        }
        .refresh-btn:hover {
            border-color: #f5a623;
            box-shadow: 0 6px 18px rgba(245, 166, 35, 0.22);
            transform: translateY(-1px);
        }
        .container { padding: 20px; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
        }
        .folder, .image-card {
            background: #1a1a1a;
            border-radius: 10px;
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
            cursor: pointer;
        }
        .folder:hover, .image-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 25px rgba(245, 166, 35, 0.15);
        }
        .folder {
            padding: 30px;
            text-align: center;
            border: 1px dashed #444;
        }
        .folder-icon { font-size: 3rem; margin-bottom: 10px; }
        .folder-name { color: #f5a623; font-weight: 500; }
        .image-card { position: relative; }
        .image-card img {
            width: 100%;
            height: 180px;
            object-fit: cover;
            display: block;
        }
        .image-info {
            padding: 10px;
            font-size: 0.8rem;
            color: #888;
        }
        .image-name {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .delete-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background: rgba(220, 53, 69, 0.9);
            color: white;
            border: none;
            padding: 8px 12px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.8rem;
            opacity: 0;
            transition: opacity 0.2s;
        }
        .image-card:hover .delete-btn { opacity: 1; }
        .delete-btn:hover { background: #dc3545; }
        .empty { text-align: center; padding: 50px; color: #666; }
        .stats { color: #666; font-size: 0.85rem; margin-top: 20px; text-align: center; }
    </style>
</head>
<body>
    <header>
        <h1>🍲 Miso Gallery</h1>
        <div class="header-actions">
            <div class="breadcrumb">{{ breadcrumb|safe }}</div>
            <button type="button" id="refreshBtn" class="refresh-btn" title="Refresh current folder">↻ Refresh</button>
        </div>
    </header>
    <div class="container">
        {% if items %}
        <div class="grid">
            {% for item in items %}
            {% if item.is_dir %}
            <a href="{{ item.url }}" class="folder">
                <div class="folder-icon">📁</div>
                <div class="folder-name">{{ item.name }}</div>
            </a>
            {% else %}
            <div class="image-card">
                <a href="{{ item.view_url }}" target="_blank">
                    <img src="{{ item.thumb_url }}" alt="{{ item.name }}">
                </a>
                <div class="image-info">
                    <div class="image-name">{{ item.name }}</div>
                    <div>{{ item.size }}</div>
                </div>
                <form method="POST" action="/delete{{ item.path }}">
                    <button type="submit" class="delete-btn" onclick="return confirm('Delete {{ item.name }}?')">🗑️</button>
                </form>
            </div>
            {% endif %}
            {% endfor %}
        </div>
        {% else %}
        <div class="empty">No images in this folder</div>
        {% endif %}
        <div class="stats">{{ stats.folders }} folders • {{ stats.images }} images</div>
    </div>
    <script>
        const refreshBtn = document.getElementById('refreshBtn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => window.location.reload());
        }
    </script>
</body>
</html>
'''

def get_image_url(filename):
    """Generate a shareable URL for Discord"""
    base = os.environ.get('IMAGE_BASE_URL', 'https://comfy-output.jory.dev/images')
    return f"{base}/{filename}"

@app.route('/')
@app.route("/favicon.ico")
def favicon():
    import io
    from PIL import Image
    img = Image.open("/../favicon.png").convert("RGB")
    img = img.resize((32, 32))
    buf = io.BytesIO()
    img.save(buf, "ICO")
    buf.seek(0)
    return buf.getvalue(), 200, {"Content-Type": "image/x-icon"}
@app.route('/<path:subpath>')
@app.route("/favicon.ico")
def favicon():
    import io
    from PIL import Image
    img = Image.open("/../favicon.png").convert("RGB")
    img = img.resize((32, 32))
    buf = io.BytesIO()
    img.save(buf, "ICO")
    buf.seek(0)
    return buf.getvalue(), 200, {"Content-Type": "image/x-icon"}
def index(subpath=''):
    folder_path = os.path.join(DATA_FOLDER, subpath)
    
    if not os.path.exists(folder_path):
        return "Folder not found", 404
    
    items = []
    stats = {'folders': 0, 'images': 0}
    
    try:
        for item in sorted(os.listdir(folder_path)):
            item_path = os.path.join(folder_path, item)
            rel_path = os.path.join(subpath, item) if subpath else item
            
            if os.path.isdir(item_path):
                stats['folders'] += 1
                items.append({
                    'name': item,
                    'path': '/' + rel_path,
                    'url': url_for('index', subpath=rel_path),
                    'is_dir': True
                })
            elif item.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                stats['images'] += 1
                full_rel_path = rel_path.replace('\\', '/')
                items.append({
                    'name': item,
                    'path': '/' + full_rel_path,
                    'thumb_url': f'/thumb/{full_rel_path}',
                    'view_url': f'/view/{full_rel_path}',
                    'size': format_size(os.path.getsize(item_path)),
                    'is_dir': False
                })
    except Exception as e:
        return f"Error: {e}", 500
    
    # Breadcrumb
    if subpath:
        parts = subpath.split('/')
        crumbs = ['<a href="/">Home</a>']
        for i, part in enumerate(parts[:-1]):
            path = '/'.join(parts[:i+1])
            crumbs.append(f'<a href="/ {path}">{part}</a>')
        crumbs.append(parts[-1])
        breadcrumb = ' / '.join(crumbs)
    else:
        breadcrumb = 'All Images'
    
    return render_template_string(HTML_TEMPLATE, items=items, breadcrumb=breadcrumb, stats=stats)

@app.route('/thumb/<path:filename>')
@app.route("/favicon.ico")
def favicon():
    import io
    from PIL import Image
    img = Image.open("/../favicon.png").convert("RGB")
    img = img.resize((32, 32))
    buf = io.BytesIO()
    img.save(buf, "ICO")
    buf.seek(0)
    return buf.getvalue(), 200, {"Content-Type": "image/x-icon"}
def thumb(filename):
    return send_from_directory(DATA_FOLDER, filename)

@app.route('/view/<path:filename>')
@app.route("/favicon.ico")
def favicon():
    import io
    from PIL import Image
    img = Image.open("/../favicon.png").convert("RGB")
    img = img.resize((32, 32))
    buf = io.BytesIO()
    img.save(buf, "ICO")
    buf.seek(0)
    return buf.getvalue(), 200, {"Content-Type": "image/x-icon"}
def view(filename):
    return send_from_directory(DATA_FOLDER, filename)

@app.route('/delete/<path:filename>', methods=['POST'])
@app.route("/favicon.ico")
def favicon():
    import io
    from PIL import Image
    img = Image.open("/../favicon.png").convert("RGB")
    img = img.resize((32, 32))
    buf = io.BytesIO()
    img.save(buf, "ICO")
    buf.seek(0)
    return buf.getvalue(), 200, {"Content-Type": "image/x-icon"}
def delete(filename):
    file_path = os.path.join(DATA_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    # Redirect back to the folder
    folder = os.path.dirname(filename)
    return redirect(url_for('index', subpath=folder))

def format_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
