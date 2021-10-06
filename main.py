import argparse
import re
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from typing import Tuple, NoReturn, Pattern


START_UNIX_DATETIME_ISO8601 = datetime.fromtimestamp(0, tz=timezone.utc).isoformat()
GITHUB_ANALYZER_ARGS_NAMES = (
    'repository_owner', 
    'repository_name', 
    'start_analysis_date', 
    'end_analysis_date', 
    'branch',
)
GithubAnalyzerArgs = namedtuple('GithubAnalyzerArgs', GITHUB_ANALYZER_ARGS_NAMES)


class DateTimeUtils:

    @staticmethod
    def is_iso8601_datetime_string(datetime_string: str) -> bool:
        try:
            datetime.fromisoformat(datetime_string)
            return True
        except ValueError:
            return False

    @staticmethod
    def is_date_string(date_string: str) -> bool:
        try:
            datetime.strptime(date_string, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    @classmethod
    def get_start_datetime_from_date(cls, date: str) -> str:
        if cls.is_date_string(date):
            start_datetime = cls.get_datetime_utc_from_date(date)
        else:
            start_datetime = datetime.fromisoformat(date)
        return cls.to_iso8601_format(start_datetime)

    @classmethod
    def get_end_datetime_from_date(cls, date: str) -> str:
        if cls.is_date_string(date):
            end_datetime_offset = timedelta(hours=23, minutes=59, seconds=59)
            end_datetime = cls.get_datetime_utc_from_date(date) + end_datetime_offset
        else:
            end_datetime = datetime.fromisoformat(date)
        return cls.to_iso8601_format(end_datetime)

    @classmethod
    def get_datetime_utc_from_date(cls, date: str) -> datetime:
        return datetime.strptime(date, '%Y-%m-%d').astimezone(timezone.utc)

    @staticmethod
    def to_iso8601_format(datetime_value: datetime) -> str:
        return datetime.strftime(datetime_value, '%Y-%m-%dT%H:%M:%SZ')


class GithubUtils:
    GITHUB_URL_REGEX: Pattern = re.compile('^https://github.com/'
                                           '[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,38}/'
                                           '[-a-z\d_.]{1,98}/?$', re.IGNORECASE)
    GITHUB_BRANCH_REGEX: Pattern = re.compile('^[^\s\\\]+$')

    @classmethod
    def is_correct_github_url(cls, url: str) -> bool:
        return bool(re.match(cls.GITHUB_URL_REGEX, url))

    @classmethod
    def is_correct_github_branch_name(cls, branch: str) -> bool:
        return bool(re.match(cls.GITHUB_BRANCH_REGEX, branch))

    @staticmethod
    def get_repository_owner_and_name_from_url(url: str) -> Tuple[str]:
        splited_url = url.rstrip('/').split('/')
        repository_owner = splited_url[-2]
        repository_name = splited_url[-1]
        return repository_owner, repository_name


class GithubAnalyzerArgumentParser:

    def __init__(self) -> None:
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument('-u', '--url',
                                 help='URL github repository address [https://github.com/<username>/<repo>]',
                                 type=str,
                                 required=True)
        self.parser.add_argument('-s', '--start',
                                 dest='start_analysis_date',
                                 help='Analysis start date [YYYY-MM-DD]',
                                 metavar='START ANALYSIS DATE',
                                 type=str,
                                 default=START_UNIX_DATETIME_ISO8601)
        self.parser.add_argument('-e', '--end',
                                 dest='end_analysis_date',
                                 help='Analysis end date [YYYY-MM-DD]',
                                 metavar='END ANALYSIS DATE',
                                 type=str,
                                 default=datetime.utcnow().isoformat())
        self.parser.add_argument('-b', '--branch',
                                help='Target branch for analysis',
                                type=str,
                                default='master')

    def parse_and_validate_args(self) -> NoReturn:
        self.args = self.parser.parse_args()
        self.validate_args()
    
    def validate_args(self) -> NoReturn:
        # check github url correctness
        is_correct_github_url: bool = GithubUtils.is_correct_github_url(self.args.url)
        # check start date correctness
        if DateTimeUtils.is_iso8601_datetime_string(self.args.start_analysis_date):
            is_correct_start_date: bool = True
        else:
            is_correct_start_date: bool = DateTimeUtils.is_correct_date_string(self.args.start_analysis_date)
        # check end date correctness
        if DateTimeUtils.is_iso8601_datetime_string(self.args.end_analysis_date):
            is_correct_end_date: bool = True
        else:
            is_correct_end_date: bool = DateTimeUtils.is_correct_date_string(self.args.end_analysis_date)
        # check target branch name correctness
        is_correct_github_branch: bool = GithubUtils.is_correct_github_branch_name(self.args.branch)
        # check that start_analysis_date <= end_analysis_date
        is_start_date_less_or_equal_than_end_date: bool = self.args.start_analysis_date <= self.args.end_analysis_date

        if not is_correct_github_url:
            self.parser.error(f'--url argument: {self.args.url} is not correct URL github repository address')
        if not is_correct_start_date:
            self.parser.error(f'--start argument: {self.args.start_analysis_date} is not correct date YYYY-MM-DD')
        if not is_correct_end_date:
            self.parser.error(f'--end argument: {self.args.end_analysis_date} is not correct date YYYY-MM-DD')
        if not is_correct_github_branch:
            self.parser.error(f'--branch argument: {self.args.branch} is not correct github branch name')
        if not is_start_date_less_or_equal_than_end_date:
            self.parser.error(f'--start argument: {self.args.start_analysis_date} date cannot be greather '
                              f'than {self.args.end_analysis_date} date')

    def get_serialized_args(self) -> GithubAnalyzerArgs:
        repository_owner, repository_name = GithubUtils.get_repository_owner_and_name_from_url(self.args.url)
        start_analysis_date: str = DateTimeUtils.get_start_datetime_from_date(self.args.start_analysis_date)
        end_analysis_date: str = DateTimeUtils.get_end_datetime_from_date(self.args.end_analysis_date)
        branch: str = self.args.branch
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

    def analyze() -> None:
        pass


if __name__=='__main__':

    args_parser = GithubAnalyzerArgumentParser()
    args_parser.parse_and_validate_args()
    args = args_parser.get_serialized_args()

    github_repository_analyzer = GithubRepositoryAnalyzer(*args)
    github_repository_analyzer.analyze()
