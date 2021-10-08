import argparse
import json
from json.decoder import JSONDecodeError
import urllib.parse
import urllib.error
import urllib.request

import re
from datetime import datetime, timedelta, timezone
from typing import Tuple, Pattern, NamedTuple, Dict, Optional, Any


START_UNIX_DATETIME_ISO8601 = datetime.fromtimestamp(0, tz=timezone.utc).isoformat()

#################### Exceptions ####################

# Group of Request exceptions


class InvalidJSONError(ValueError, TypeError):
    """ The JSON string is not valid """


class InvalidHeaderError(ValueError):
    """ The header value provided was somehow invalid """


class InvalidURLError(ValueError):
    """ The URL string is not valid """


# Group of GithubAnalyzer exceptions

#################### Exceptions ####################


class GithubAnalyzerArgs(NamedTuple):
    """ Class for storing parsed and validated arguments from command line """
    
    repository_owner: str
    repository_name: str
    start_analysis_date: str
    end_analysis_date: str
    branch: str


class Response(NamedTuple):
    """ Class for storing and representation HTTP Response data """
    status_code: int
    body: Optional[str]
    headers: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        if not self.body:
            return {}
        try:
            response_body = json.loads(self.body)
            return response_body
        except JSONDecodeError:
            raise InvalidJSONError('The response body is not valid json string')
        

class Request:
    """ Simple Request class that provide basic HTTP methods """

    _VALID_HEADER_REGEX = re.compile(r'^\S[^\r\n]*$|^$')
    _VALID_URL_REGEX = re.compile(
        r'^(?:http)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain
        r'localhost|' # ...or localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', # query params
        re.IGNORECASE
    )
    
    @classmethod
    def validate_url(cls, url: str) -> None:
        """ 
        Validate given URL 
        Args:
            url (str): URL string
        Returns:
            None
        Raises:
            InvalidURLError: If given URL string is not valid
        """
        try:
            if not re.match(cls._VALID_HEADER_REGEX, url):
                raise InvalidURLError(f'Invalid URL: {url}')
        except TypeError:
            raise InvalidURLError(f'Value for URL {url} must be a type str, not {type(url)}')
    
    @classmethod
    def validate_json(cls, body_json: str) -> None:
        """
        Validate given request JSON body
        Args:
            body_json (str): JSON string
        Returns:
            None
        Raises:
            InvalidJSONError: If given JSON string is not valid
        """
        try:
            json.loads(body_json)
        except JSONDecodeError:
            raise InvalidJSONError('The request body must be a valid json string')
    
    @classmethod
    def validate_headers(cls, headers: Dict[str, str]) -> None:
        """ 
        Validate given headers dictionary 
        Args:
            headers (Dict[str, str]): Dictionary of request headers
        Returns:
            None
        Raises:
            InvalidHeaderError: If any header contains leading whitespace or return character
        """
        # Raise exception on invalid header value
        for header in headers.items():
            cls.validate_header(header)
    
    @classmethod
    def validate_header(cls, header: Tuple[str, str]) -> None:
        """
        Verifies that header value is a string which doesn't contain
        leading whitespace or return characters.
        Args:
            header (Tuple[str, str]): A tuple of key:value given header
        Returns:
            None
        Raises:
            InvalidHeaderError: If given header contains leading whitespace or return character
        """
        name, value = header
        try:
            if not re.match(cls._VALID_HEADER_REGEX, value):
                raise InvalidHeaderError(f'Invalid return character or leading space in header: {name}')
        except TypeError:
            raise InvalidHeaderError(f'Value for header {{{name}:{value}}} must be a type str, '
                                     f'not {type(value)}')
        
    @classmethod
    def do_request(
        cls,
        method: str,
        url: str,
        body_json: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Response:
        """
        Constructs and send HTTP Request
        Args:
            method (str): Any HTTP method verb: ``GET``, ``OPTIONS``, ``HEAD``, 
                                                ``POST``, ``PUT``, ``PATCH`` or ``DELETE``
            url (str): Target URL string
            body_json (str): Request body in JSON
            headers (Dict[str, str]): Dictionary of request headers
        Returns:
            Response: HTTP Response object
        Raises:
            InvalidHeaderError: If headers dictionary is not valid
            InvalidJSONError: If body_json is not JSON string
        """
        if not headers:
            headers = {}
        else:
            cls.validate_headers(headers)

        if body_json:
            headers['Content-Type'] = 'application/json'
            cls.validate_json(body_json)
            body_json = body_json.encode()

        httprequest: urllib.request.Request = urllib.request.Request(
            url, data=body_json, headers=headers, method=method,
        )

        try:
            with urllib.request.urlopen(httprequest) as httpresponse:
                response: Response = Response(
                    headers=httpresponse.headers,
                    status_code=httpresponse.status,
                    body=httpresponse.read().decode(
                        httpresponse.headers.get_content_charset("utf-8")
                    ),
                )
        except urllib.error.HTTPError as e:
            response: Response = Response(
                body=str(e.reason),
                headers=e.headers,
                status_code=e.code,
            )
        except urllib.error.URLError as e:
            response: Response = Response(
                body=str(e.reason),
                headers=headers,
                status_code=101,
            )

        return response
    
    @classmethod
    def get(
        cls, 
        url: str, 
        query_params: Optional[Dict[str, str]] = None, 
        headers: Optional[Dict[str, str]] = None
    ) -> Response:
        """ Provide HTTP GET request """
        method: str = 'GET'
        if query_params:
            url += "?" + urllib.parse.urlencode(query_params, doseq=True, safe="/")

        return cls.do_request(method=method, url=url, headers=headers)
    
    @classmethod
    def head(
        cls,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Response:
        """ Provide HTTP HEAD request """
        
        method: str = 'HEAD'
        return cls.do_request(method=method, url=url, headers=headers)
    
    @classmethod
    def options(
        cls,
        url: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Response:
        """ Provide HTTP OPTIONS request """
        
        method: str = 'OPTIONS'
        return cls.do_request(method=method, url=url, headers=headers)
    
    @classmethod
    def post(
        cls,
        url: str,
        body_json: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Response:
        """ Provide HTTP POST request """
        
        method: str = 'POST'
        return cls.do_request(method=method, url=url, body_json=body_json, headers=headers)
        
    @classmethod
    def put(
        cls,
        url: str,
        body_json: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Response:
        """ Provide HTTP PUT request """
        
        method: str = 'PUT'
        return cls.do_request(method=method, url=url, body_json=body_json, headers=headers)
    
    @classmethod
    def patch(
        cls,
        url: str,
        body_json: str,
        headers: Optional[Dict[str, str]] = None
    ) -> Response:
        """ Provide HTTP PATCH request """
        
        method: str = 'PATCH'
        return cls.do_request(method=method, url=url, body_json=body_json, headers=headers)
    
    @classmethod
    def delete(cls,
               url: str,
               headers: Optional[Dict[str, str]] = None
    ) -> Response:
        """ Provide HTTP DELETE request """
        
        method: str = 'DELETE'
        return cls.do_request(method=method, url=url, headers=headers)


class DateTimeUtils:
    """ Class that provides methods for working with date and time  """
    
    @staticmethod
    def is_iso8601_datetime_string(datetime_string: str) -> bool:
        """ Check that given datetime_string is a valid ISO 8601 datetime string """
        try:
            datetime.fromisoformat(datetime_string)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_date_string(date_string: str) -> bool:
        """ Check that given date_string is a valid date string in YYYY-MM-DD format """
        try:
            datetime.strptime(date_string, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    @classmethod
    def get_start_datetime_from_date(cls, date: str) -> str:
        """ 
        Convert given date string to ISO 8601 datetime string in UTC.
        If a date string was received, then we supplement the date to the time YYYY-MM-DDT00:00:00
        """
        if cls.is_date_string(date):
            start_datetime = cls.get_datetime_utc_from_date(date)
        else:
            start_datetime = datetime.fromisoformat(date)
        return cls.to_iso8601_format(start_datetime)

    @classmethod
    def get_end_datetime_from_date(cls, date: str) -> str:
        """ 
        Convert given date string to ISO 8601 datetime string in UTC.
        If a date string was received, then we supplement the date to the time YYYY-MM-DDT23:59:59
        """
        if cls.is_date_string(date):
            end_datetime_offset = timedelta(hours=23, minutes=59, seconds=59)
            end_datetime = cls.get_datetime_utc_from_date(date) + end_datetime_offset
        else:
            end_datetime = datetime.fromisoformat(date)
        return cls.to_iso8601_format(end_datetime)

    @classmethod
    def get_datetime_utc_from_date(cls, date: str) -> datetime:
        """ Supplement the date to the time YYYY-MM-DDT00:00:00 """
        return datetime.strptime(date, '%Y-%m-%d').astimezone(timezone.utc)

    @staticmethod
    def to_iso8601_format(datetime_value: datetime) -> str:
        """ Format datetime string to ISO 8601 datetime string YYYY-MM-DDTHH:MM:SSZ """
        return datetime.strftime(datetime_value, '%Y-%m-%dT%H:%M:%SZ')


class GithubUtils:
    """ Class that provides methods for validating github URL and branch name """
    
    _VALID_GITHUB_URL_REGEX: Pattern = re.compile('^https://github.com/' # protocol and domain
                                                  '[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,38}/' # username
                                                  '[-a-z\d_.]{1,98}/?$', # repository
                                                  re.IGNORECASE)
    _VALID_GITHUB_BRANCH_REGEX: Pattern = re.compile('^[^\s\\\]+$')

    @classmethod
    def is_correct_github_url(cls, url: str) -> bool:
        return bool(re.match(cls._VALID_GITHUB_URL_REGEX, url))

    @classmethod
    def is_correct_github_branch_name(cls, branch: str) -> bool:
        return bool(re.match(cls._VALID_GITHUB_BRANCH_REGEX, branch))

    @staticmethod
    def get_repository_owner_and_name_from_url(url: str) -> Tuple[str]:
        splited_url = url.rstrip('/').split('/')
        repository_owner = splited_url[-2]
        repository_name = splited_url[-1]
        return repository_owner, repository_name


class GithubAnalyzerArgumentParser:
    """ 
    Class that provides methods for parsing, validating and serializing 
    arguments from command line
    """
    
    def __init__(self) -> None:
        self._parser = argparse.ArgumentParser()
        self._parser.add_argument('-u', '--url',
                                 help='URL github repository address [https://github.com/<username>/<repo>]',
                                 type=str,
                                 required=True)
        self._parser.add_argument('-s', '--start',
                                 dest='start_analysis_date',
                                 help='Analysis start date [YYYY-MM-DD]',
                                 metavar='START ANALYSIS DATE',
                                 type=str,
                                 default=START_UNIX_DATETIME_ISO8601)
        self._parser.add_argument('-e', '--end',
                                 dest='end_analysis_date',
                                 help='Analysis end date [YYYY-MM-DD]',
                                 metavar='END ANALYSIS DATE',
                                 type=str,
                                 default=datetime.utcnow().isoformat())
        self._parser.add_argument('-b', '--branch',
                                help='Target branch for analysis',
                                type=str,
                                default='master')

    def parse_and_validate_args(self) -> None:
        args: argparse.Namespace = self.parse_args()
        self.validate_args(args)
    
    def parse_args(self) -> argparse.Namespace:
        return self._parser.parse_args()
    
    def validate_args(self, args: argparse.Namespace) -> None:
        """ 
        Method that validate given arguments from command line. 
        An error will be printed to stderr if any args data is not valid.
        """
        # check github url correctness
        is_correct_github_url: bool = GithubUtils.is_correct_github_url(args.url)
        # check start date correctness
        if DateTimeUtils.is_iso8601_datetime_string(args.start_analysis_date):
            is_correct_start_date: bool = True
        else:
            is_correct_start_date: bool = DateTimeUtils.is_date_string(args.start_analysis_date)
        # check end date correctness
        if DateTimeUtils.is_iso8601_datetime_string(args.end_analysis_date):
            is_correct_end_date: bool = True
        else:
            is_correct_end_date: bool = DateTimeUtils.is_date_string(args.end_analysis_date)
        # check target branch name correctness
        is_correct_github_branch: bool = GithubUtils.is_correct_github_branch_name(args.branch)
        # check that start_analysis_date <= end_analysis_date
        is_start_date_less_or_equal_than_end_date: bool = args.start_analysis_date <= args.end_analysis_date

        if not is_correct_github_url:
            self._parser.error(f'--url argument: {args.url} is not correct URL github repository address')
        if not is_correct_start_date:
            self._parser.error(f'--start argument: {args.start_analysis_date} is not correct date YYYY-MM-DD')
        if not is_correct_end_date:
            self._parser.error(f'--end argument: {args.end_analysis_date} is not correct date YYYY-MM-DD')
        if not is_correct_github_branch:
            self._parser.error(f'--branch argument: {args.branch} is not correct github branch name')
        if not is_start_date_less_or_equal_than_end_date:
            self._parser.error(f'--start argument: {args.start_analysis_date} date cannot be greather '
                              f'than {args.end_analysis_date} date')
        
        self.validated_args: argparse.Namespace = args

    def get_serialized_args(self) -> GithubAnalyzerArgs:
        assert hasattr(self, 'validated_args'), (
            'Cannot call `.get_serialized_args()` before validating process. '
            'You must call `.validate_args()` before attempting to access the serialized data'
        )
        repository_owner, repository_name = GithubUtils.get_repository_owner_and_name_from_url(self.validated_args.url)
        start_analysis_date: str = DateTimeUtils.get_start_datetime_from_date(self.validated_args.start_analysis_date)
        end_analysis_date: str = DateTimeUtils.get_end_datetime_from_date(self.validated_args.end_analysis_date)
        branch: str = self.validated_args.branch
        return GithubAnalyzerArgs(repository_owner, repository_name, start_analysis_date, end_analysis_date, branch)


class GithubRepositoryAnalyzer:

    def __init__(self, 
                 repository_owner: str,
                 repository_name: str,
                 start_analysis_datetime: str,
                 end_analysis_datetime: str,
                 branch: str) -> None:

        self.repository_owner: str = repository_owner
        self.repository_name: str = repository_name
        self.start_analysis_datetime: str = start_analysis_datetime
        self.end_analysis_datetime: str = end_analysis_datetime
        self.branch: str = branch

    def analyze(self) -> None:
        pass


if __name__=='__main__':

    args_parser = GithubAnalyzerArgumentParser()
    args_parser.parse_and_validate_args()
    args = args_parser.get_serialized_args()

    github_repository_analyzer = GithubRepositoryAnalyzer(*args)
    github_repository_analyzer.analyze()
