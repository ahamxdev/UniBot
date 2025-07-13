import os



def save_response(result, html):
    save_dir = "saved_html"
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, f"{result}.html")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)
