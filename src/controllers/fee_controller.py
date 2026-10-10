import re
from datetime import date, datetime, time, timedelta

from sqlalchemy import text

from controllers.account_controller import PAGE_SIZE, parse_page
from controllers.base_controller import BaseController
from dtos import FeeDTO
from errors import InvalidParameter
from repositories import EntryRepository

DATE_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FeeController(BaseController):

    def __init__(self) -> None:
        super().__init__(__name__)
        self.entry_repository = EntryRepository(self.context)

    def list_fees(self, raw_start_date, raw_end_date, raw_page) -> dict:
        start_date = parse_date(raw_start_date, "start_date")
        end_date = parse_date(raw_end_date, "end_date")
        page = parse_page(raw_page)

        if start_date > end_date:
            raise InvalidParameter("start_date must not be after end_date")

        # Os dias são UTC e inclusivos: [início de start_date, início do dia seguinte a end_date).
        start = datetime.combine(start_date, time.min)
        end = end_of_day(end_date)

        # REPEATABLE READ: o total e a página saem da MESMA fotografia do banco, iguais
        # mesmo que uma transferência confirme no meio da consulta. Precisa ser o primeiro
        # comando da transação, por isso vem antes de qualquer consulta.
        self.session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))

        total_amount = self.entry_repository.sum_fees(start, end)
        fees = self.entry_repository.list_fees(start, end, PAGE_SIZE + 1, page * PAGE_SIZE)

        return {
            "data": FeeDTO.list_obj_to_list_dict(fees[:PAGE_SIZE]),
            "total_amount": total_amount,
            "page": page,
            "page_size": PAGE_SIZE,
            "is_last_page": len(fees) <= PAGE_SIZE,
        }


def parse_date(raw_date, name: str) -> date:
    if raw_date is None or not DATE_FORMAT.match(raw_date):
        raise InvalidParameter(f"{name} is required and must be a date in the format YYYY-MM-DD")

    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        raise InvalidParameter(f"{name} is not a real date")


def end_of_day(end_date: date) -> datetime:
    """O início do dia seguinte. Em 9999-12-31 não há dia seguinte: vale o maior instante possível."""
    try:
        return datetime.combine(end_date, time.min) + timedelta(days=1)
    except OverflowError:
        return datetime.max
