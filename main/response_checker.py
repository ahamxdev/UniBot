# response_checker.py
"""
Utilities for analyzing the server's HTML response during
course registration / deletion.

What this module does:
- Extract JavaScript `alert('...')` messages embedded in the HTML.
- Parse the "request status" table under the caption that contains
  the Persian text "وضعیت درخواستهای شما".
- Return a small result dict with:
    {
        "status_code": <short stable code>,
        "message": <human-readable Persian message>
    }

IMPORTANT:
- This version intentionally preserves the original logic and parsing
  behavior you had (including the single-quoted alert regex) so it
  behaves exactly like your working code.
"""

import re
from bs4 import BeautifulSoup


def extract_alerts(html: str):
    """
    Extract JavaScript alert messages from the HTML.

    NOTE:
    - Intentionally matches only single-quoted alerts to preserve
      your original behavior (e.g., alert('پیام')).

    Args:
        html (str): The HTML content containing alert scripts.

    Returns:
        list[str]: List of alert message strings (without quotes).
    """
    return re.findall(r"alert\('([^']+)'\)", html)


def analyze_response(html: str, operation: str, course_code: str = None, group_code: str = None):
    """
    Analyze the HTML response to determine the outcome of a course
    registration or deletion.

    Behavior (unchanged):
    - For `delete`: read JavaScript alerts and infer the result.
    - For `register`: locate the caption that includes
      "وضعیت درخواستهای شما", then parse the table beneath it
      and read the status cell (9th column) for known phrases.

    Args:
        html (str): Raw HTML response from the server.
        operation (str): Either 'register' or 'delete'.
        course_code (str, optional): Course code for reference in messages.
        group_code (str, optional): Group code for reference in messages.

    Returns:
        dict: A dict with keys:
              - 'status_code' (str)
              - 'message' (str, Persian, user-facing)
    """
    soup = BeautifulSoup(html, 'html.parser')
    alerts = extract_alerts(html)

    # ---------------------
    # Deletion branch
    # ---------------------
    if operation == "delete":
        for alert in alerts:
            if "پاک شد" in alert:
                return {
                    "status_code": "deleted",
                    "message": f"✅ درس {course_code} با گروه {group_code} حذف شد."
                }
            elif "درس مورد نظر پیدا نشد" in alert:
                return {
                    "status_code": "not_found",
                    "message": f"❌ درس {course_code} با گروه {group_code} برای حذف پیدا نشد."
                }
        return {
            "status_code": "unknown_delete",
            "message": "⚠️ هیچ پیام مشخصی برای حذف درس پیدا نشد."
        }

    # ---------------------
    # Registration branch
    # ---------------------
    if operation == "register":
        # Find the caption containing "وضعیت درخواستهای شما"
        target_caption = soup.find('div', class_='caption', string=lambda t: t and "وضعیت درخواستهای شما" in t)
        if target_caption:
            # NOTE: Keep the original chained find() calls to preserve behavior
            portlet_body = target_caption.find_parent("div", class_="portlet").find("div", class_="portlet-body")
            table = portlet_body.find("table") if portlet_body else None

            if table:
                rows = table.find_all("tr")
                for row in rows:
                    cols = row.find_all("td")
                    # Expect the status in the 9th column (index 8)
                    if len(cols) >= 9:
                        status = cols[8].get_text(strip=True)

                        if "ظرفیت درس تکمیل شده است" in status:
                            return {
                                "status_code": "capacity_full",
                                "message": f"⚠️ درخواست درس {course_code} با گروه {group_code} ارسال شده ولی ظرفیت پر است."
                            }

                        elif "برنامه هفتگی تداخل دارد" in status:
                            return {
                                "status_code": "conflict",
                                "message": f"❌ درس {course_code} با گروه {group_code} به دلیل تداخل برنامه هفتگی رد شد."
                            }

                        elif "درس برای دانشجو قبلاً ثبت شده است" in status:
                            return {
                                "status_code": "already_registered",
                                "message": f"ℹ️ درس {course_code} قبلاً انتخاب شده است."
                            }

                        elif "تعداد واحدها از حدنصاب بیشتر است" in status:
                            return {
                                "status_code": "unit_limit_exceeded",
                                "message": f"❌ انتخاب درس {course_code} با گروه {group_code} ممکن نیست، چون تعداد واحدها از حد مجاز بیشتر شده است."
                            }

                        elif "ثبت شد" in status:
                            return {
                                "status_code": "registered",
                                "message": f"✅ درس {course_code} با گروه {group_code} برای شما انتخاب شد."
                            }

        # Fallback if none of the above matched
        return {
            "status_code": "not_registered",
            "message": "⚠️ ثبت نهایی انجام نشد و درس در لیست انتخاب واحد موجود نیست."
        }
