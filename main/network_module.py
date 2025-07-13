import requests
from http.cookies import SimpleCookie


def update_cookies_from_response(session: requests.Session, response: requests.Response):
    cookie_headers = response.headers.getlist('Set-Cookie') if hasattr(response.headers, 'getlist') else response.headers.get('Set-Cookie')
    if not cookie_headers:
        return

    if isinstance(cookie_headers, str):
        cookie_headers = [cookie_headers]

    for cookie_str in cookie_headers:
        cookie = SimpleCookie()
        cookie.load(cookie_str)
        for key, morsel in cookie.items():
            domain = morsel['domain'] if morsel['domain'] else None
            path = morsel['path'] if morsel['path'] else "/"

            cookie_args = {
                "name": key,
                "value": morsel.value,
                "path": path
            }

            if domain is not None:
                cookie_args["domain"] = domain

            session.cookies.set(**cookie_args)


def create_session(raw_cookie: str) -> requests.Session:
    """
    Create and return a requests session with given raw cookie string and default headers.
    """
    session = requests.Session()

    # Parse raw cookie
    cookies = {}
    for item in raw_cookie.split(";"):
        if "=" in item:
            key, val = item.strip().split("=", 1)
            cookies[key] = val

    session.cookies.update(cookies)

    # Set default headers
    session.headers.update({
        "Host": "amozesh.tabrizu.ac.ir",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Referer": "https://amozesh.tabrizu.ac.ir/samaweb/Index.aspx",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://amozesh.tabrizu.ac.ir",
        "Content-Length": "0"
    })

    return session


def send_keep_alive_ping(session: requests.Session):
    """
    Send POST + GET request to keep session alive.
    """
    post_url = "https://amozesh.tabrizu.ac.ir/samaweb/keep-alive.aspx"
    get_url = "https://amozesh.tabrizu.ac.ir/SamaWeb/Login.aspx?ReturnUrl=%2fsamaweb%2fkeep-alive.aspx"

    post_headers = {
        **session.headers,
        "Priority": "u=0",
    }

    get_headers = {
        **session.headers,
        "TE": "trailers"
    }

    try:
        response_post = session.post(post_url, headers=post_headers, data="")
        update_cookies_from_response(session, response_post)
        print(f"🛟 Keep-alive POST status: {response_post.status_code}")

        # response_get = session.get(get_url, headers=get_headers)
        # update_cookies_from_response(session, response_get)
        # print(f"🛟 Keep-alive GET status: {response_get.status_code}")

    except Exception as e:
        print(f"⚠️ Error during keep-alive ping: {e}")


def send_course_request(session: requests.Session, ins_view: str, course: str, group: str,
                        stno: str, term_code: str) -> requests.Response:
    """
    Send a course registration or deletion request to the education system.
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

    headers = {
        **session.headers,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Content-Length": "135",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://amozesh.tabrizu.ac.ir/samaweb/StuUnitSelection.asp",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "iframe",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Priority": "u=4",
        "TE": "trailers"
    }

    try:
        response = session.post(url, headers=headers, data=data)
        update_cookies_from_response(session, response)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        print(f"❌ Network error during course request: {e}")
        raise
