import requests

def create_session(raw_cookie: str) -> requests.Session:
    session = requests.Session()

    # Parse the raw cookie string into a dictionary
    cookies = {}
    for item in raw_cookie.split(";"):
        if "=" in item:
            key, val = item.strip().split("=", 1)
            cookies[key] = val
    session.cookies.update(cookies)

    # Exact match with browser headers to avoid detection
    session.headers.update({
        "Host": "amozesh.tabrizu.ac.ir",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Referer": "https://amozesh.tabrizu.ac.ir/samaweb/stuUnitSelection.asp",
        "Sec-Fetch-Dest": "iframe",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "TE": "trailers",
        "Origin": "https://amozesh.tabrizu.ac.ir",
        "Content-Type": "application/x-www-form-urlencoded"
    })

    return session


def send_course_request(session: requests.Session, ins_view: str, course: str, group: str,
                        stno: str, term_code: str) -> requests.Response:
    """
    Send a course registration or deletion request to the university's education system.

    Args:
        session (requests.Session): The configured session with headers and cookies.
        ins_view (str): View mode ('4' for register, '5' for delete).
        course (str): The course code.
        group (str): The group code.
        stno (str): Student number.
        term_code (str): Academic term code (e.g., '14033').

    Returns:
        requests.Response: The server's response object.
    """
    url = "https://amozesh.tabrizu.ac.ir/samaweb/StuUnitSelection.asp"
    data = {
        "insView": ins_view,
        "LessonRegisterStatus": "0",
        "strLessonSelections": course,
        "strGroupSelections": group,
        "strSelectSelections": "",
        "StNo": stno,
        "TermCode": term_code
    }

    response = session.post(url, data=data)
    response.raise_for_status()
    return response
