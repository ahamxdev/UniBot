import os
from datetime import datetime


def save_response(result, html):

    """
    Save the HTML response content to a timestamped file.

    Args:
        result (dict): A dictionary containing at least 'status_code' to name the file.
        html (str): Raw HTML content to be saved.

    This function creates a 'saved_html' directory (if not exists) and saves the HTML
    content in a file named like '200_20250713_214532.html' for debugging or logging.
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Generate timestamp
    save_dir = "saved_html"
    os.makedirs(save_dir, exist_ok=True)  # Ensure the directory exists
    file_path = os.path.join(save_dir, f"{result['status_code']}_{timestamp}.html")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)  # Write HTML to file
