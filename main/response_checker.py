import re
from bs4 import BeautifulSoup


def extract_alerts(html: str):

    """
    Extract JavaScript alert messages from the HTML.

    Args:
        html (str): The HTML content containing alert scripts.

    Returns:
        list[str]: List of alert message strings.
    """

    return re.findall(r"alert\('([^']+)'\)", html)


def analyze_response(html: str, operation: str, course_code: str = None, group_code: str = None):

    """
    Analyze the HTML response to determine the outcome of a course registration or deletion.

    Args:
        html (str): Raw HTML response from the server.
        operation (str): Either 'register' or 'delete'.
        course_code (str, optional): Course code for reference.
        group_code (str, optional): Group code for reference.

    Returns:
        dict: Contains 'status_code' and a human-readable 'message'.
    """

    soup = BeautifulSoup(html, 'html.parser')
    alerts = extract_alerts(html)

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

    if operation == "register":
        target_caption = soup.find('div', class_='caption', string=lambda t: t and "وضعیت درخواستهای شما" in t)
        if target_caption:
            portlet_body = target_caption.find_parent("div", class_="portlet").find("div", class_="portlet-body")
            table = portlet_body.find("table") if portlet_body else None

            if table:
                rows = table.find_all("tr")
                for row in rows:
                    cols = row.find_all("td")
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

        return {
            "status_code": "not_registered",
            "message": "⚠️ ثبت نهایی انجام نشد و درس در لیست انتخاب واحد موجود نیست."
        }
