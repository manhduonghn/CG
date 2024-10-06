import urllib.request
import urllib.error
import json
from functools import wraps
import time
import logging
import random


class HTTPResponse:
    """
    Class mô phỏng đối tượng response của requests.
    """

    def __init__(self, response):
        self._response = response
        self.status_code = response.getcode()
        try:
            self._content = response.read().decode("utf-8")
        except Exception:
            self._content = ""
        self.error_message = None

        if self.status_code >= 400:
            # Thêm chi tiết thông báo lỗi nếu có
            self.error_message = f"HTTP Error {self.status_code}: {self._response.reason}"
            if self._content:
                self.error_message += f" - Response body: {self._content}"

    def json(self):
        """
        Trả về kết quả JSON từ response.
        """
        return json.loads(self._content)

    @property
    def text(self):
        """
        Trả về nội dung dạng text.
        """
        return self._content


class Session:
    """
    Mô phỏng đối tượng requests.Session.
    """

    def __init__(self):
        self.headers = {}

    def _make_request(self, url, method="GET", data=None):
        """
        Thực hiện một request HTTP với URL, method và dữ liệu cho trước.
        """
        req = urllib.request.Request(url, data=data, headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(req) as response:
                return HTTPResponse(response)
        except urllib.error.HTTPError as e:
            error_response = HTTPResponse(e)
            logging.warning(f"HTTP Error: {error_response.error_message}")
            return error_response
        except urllib.error.URLError as e:
            logging.warning(f"Request failed: {e.reason}")
            return None

    def get(self, url, params=None):
        """
        Mô phỏng phương thức GET của requests.

        Args:
            url (str): URL cần gửi request.
            params (dict, optional): Các tham số query string.

        Returns:
            HTTPResponse: Đối tượng response sau khi thực hiện request.
        """
        return self._make_request(url, method="GET")

    def post(self, url, json_data=None, data=None):
        """
        Mô phỏng phương thức POST của requests.

        Args:
            url (str): URL cần gửi request.
            json_data (dict, optional): Dữ liệu dạng JSON để gửi.
            data (bytes, optional): Dữ liệu nhị phân (binary).

        Returns:
            HTTPResponse: Đối tượng response sau khi thực hiện request.
        """
        if json_data:
            data = json.dumps(json_data).encode('utf-8')
        return self._make_request(url, method="POST", data=data)

    def put(self, url, json_data=None, data=None):
        """
        Mô phỏng phương thức PUT của requests.
        """
        if json_data:
            data = json.dumps(json_data).encode('utf-8')
        return self._make_request(url, method="PUT", data=data)

    def delete(self, url):
        """
        Mô phỏng phương thức DELETE của requests.
        """
        return self._make_request(url, method="DELETE")

    def patch(self, url, json_data=None, data=None):
        """
        Mô phỏng phương thức PATCH của requests.
        """
        if json_data:
            data = json.dumps(json_data).encode('utf-8')
        return self._make_request(url, method="PATCH", data=data)


# Phương thức để tạo session, tương tự requests.Session()
def session():
    return Session()


def retry(func):
    """
    Decorator cho phép retry hàm được bọc tối đa 5 lần với backoff theo cấp số nhân
    đối với các lỗi không phải 429. Nếu gặp lỗi 429 (Too Many Requests), nó sẽ thử lại
    vô thời hạn cho đến khi thành công, với thời gian đợi tăng dần.

    Args:
        func: Hàm cần được bọc.

    Returns:
        Kết quả của hàm được bọc hoặc raise exception nếu tất cả các lần thử đều thất bại (trừ lỗi 429).
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        attempt_number = 0
        while True:
            attempt_number += 1
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Kiểm tra lỗi 429 Too Many Requests
                if "429" in str(e):
                    logging.warning(f"Attempt {attempt_number} failed with {e}. Retrying...")
                    # Tăng thời gian chờ theo cấp số nhân, tối đa 30 giây
                    wait_time = min(2 ** (attempt_number - 1), 30)
                else:
                    logging.warning(f"Attempt {attempt_number} failed with {e}. Retrying...")

                    if attempt_number >= 5:
                        raise

                    # Backoff theo cấp số nhân cho các lỗi khác (tối đa 10 giây)
                    wait_time = min(2 ** (attempt_number - 1), 10) + random.uniform(0, 1)

                logging.warning(f"Sleeping for {wait_time:.2f} seconds before retrying...")
                time.sleep(wait_time)

    return wrapper


def rate_limited_request(func):
    """
    Decorator đảm bảo hàm được bọc chỉ được gọi không quá một lần mỗi giây.

    Args:
        func: Hàm cần bọc.

    Returns:
        Kết quả của hàm sau khi thực thi giới hạn tốc độ.
    """
    last_call_time = [0]

    @wraps(func)
    def wrapper(*args, **kwargs):
        current_time = time.time()
        elapsed_time = current_time - last_call_time[0]
        wait_time = 1 - elapsed_time

        if wait_time > 0:
            time.sleep(wait_time)

        last_call_time[0] = time.time()
        return func(*args, **kwargs)

    return wrapper
