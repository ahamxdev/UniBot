import re
from bs4 import BeautifulSoup




def extract_alerts(html: str):
    return re.findall(r"alert\('([^']+)'\)", html)


def analyze_response(html: str, operation: str, course_code: str = None, group_code: str = None):
    soup = BeautifulSoup(html, 'html.parser')
    alerts = extract_alerts(html)

    if operation == "delete":
        for alert in alerts:
            if "پاک شد" in alert:
                return {
                    "status_code": "deleted",
                    "message": "✅ درس انتخابی حذف شد."
                }
            elif "درس مورد نظر پیدا نشد" in alert:
                return {
                    "status_code": "not_found",
                    "message": "⚠️ درس مورد نظر برای حذف پیدا نشد."
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

                        if "ثبت شد" in status:
                            return {
                                "status_code": "registered",
                                "message": "✅ ثبت نهایی درس در جدول وضعیت تایید شد."
                            }

                        elif "برنامه هفتگی تداخل دارد" in status:
                            return {
                                "status_code": "conflict",
                                "message": f"❌ درخواست درس {course_code} با گروه {group_code} به دلیل تداخل برنامه هفتگی رد شد."
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

                        elif "ظرفیت درس تکمیل شده است" in status:
                            return {
                                "status_code": "capacity_full",
                                "message": f"⚠️ درخواست درس {course_code} با گروه {group_code} ارسال شده ولی ظرفیت پر است یا در حال بررسی توسط آموزش است."
                            }

        return {
            "status_code": "not_registered",
            "message": "⚠️ ثبت نهایی انجام نشد و درس در لیست انتخاب واحد موجود نیست."
        }

    return {
        "status_code": "unknown",
        "message": "⚠️ عملیات یا پاسخ ناشناخته است."
    }
