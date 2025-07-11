import requests
import time
from response_checker import analyze_response

def main():
    print("🔹 Auto Unit Selection Bot Started")

    stno = input("Enter your Student Number (StNo): ").strip()
    term_code = input("Enter Term Code (e.g., 14033): ").strip()
    raw_cookie = input("\nPaste your full Cookie header from browser (one line):\n").strip()

    # ✅ Initialize session to manage cookies
    session = requests.Session()

    # ✅ Parse cookie string and update session cookies
    cookies = dict(item.strip().split("=", 1) for item in raw_cookie.split(";") if "=" in item)
    session.cookies.update(cookies)

    url = "https://amozesh.tabrizu.ac.ir/samaweb/StuUnitSelection.asp"
    headers = {
        "Host": "amozesh.tabrizu.ac.ir",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://amozesh.tabrizu.ac.ir",
        "Connection": "keep-alive",
        "Referer": "https://amozesh.tabrizu.ac.ir/samaweb/stuUnitSelection.asp",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "iframe",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Priority": "u=4",
        "TE": "trailers"
    }

    course_list = []

    while True:
        course = input("\n➕ Enter course code: ").strip()
        group = input("➕ Enter group code: ").strip()

        print("➕ Select operation for this course:")
        print("1. Final Register")
        print("2. Delete Course")
        op = input("Enter 1 or 2: ").strip()

        if op == "1":
            ins_view = "4"
            operation = "register"
        elif op == "2":
            ins_view = "5"
            operation = "delete"
        else:
            print("❌ Invalid operation choice. Skipping this course.")
            continue

        course_list.append({
            "course": course,
            "group": group,
            "ins_view": ins_view,
            "operation": operation,
            "done": False
        })

        another = input("➕ Do you want to add another course? (y/n): ").strip().lower()
        if another != 'y':
            break

    print("\n🔄 Starting submission loop...\n")
    round_num = 1

    while True:
        print(f"\n📘 Round {round_num}")
        all_done = True

        for item in course_list:
            if item["done"]:
                continue

            all_done = False

            course = item["course"]
            group = item["group"]
            ins_view = item["ins_view"]
            operation = item["operation"]

            data = {
                "insView": ins_view,
                "LessonRegisterStatus": "0",
                "strLessonSelections": course,
                "strGroupSelections": group,
                "strSelectSelections": "",
                "StNo": stno,
                "TermCode": term_code
            }

            try:
                print(f"\n⏳ Sending request for course {course} - group {group}...")
                response = session.post(url, headers=headers, data=data)
                html = response.content.decode('utf-8', errors='ignore')

                result = analyze_response(html, operation, course_code=course, group_code=group)
                print(f"📄 Result: {result['message']}")

                # ✅ Mark as done if successfully completed
                if operation == "register" and result["status_code"] in ["registered", "already_registered"]:
                    item["done"] = True
                elif operation == "delete" and result["status_code"] in ["deleted", "not_found"]:
                    item["done"] = True

            except Exception as e:
                print(f"❌ Error while sending request for course {course}:", str(e))

        if all_done:
            print("\n✅ All tasks completed. Exiting loop.")
            break

        round_num += 1
        print("\n⏱ Waiting 5 seconds before next round...\n")
        time.sleep(5)

if __name__ == "__main__":
    main()
