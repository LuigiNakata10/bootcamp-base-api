from datetime import datetime, timedelta, timezone

from tests.utils import DbUtils, ObjectGenerator, PayloadGenerator, RequestGenerator

FEE = 100
PAGE_SIZE = 20


def utc_today():
    return datetime.now(timezone.utc).date()


def around_today() -> dict:
    return {"start_date": (utc_today() - timedelta(days=1)).isoformat(), "end_date": (utc_today() + timedelta(days=1)).isoformat()}


def make_transfers(count: int) -> list:
    source = ObjectGenerator.create_account(balance=count * 1000)
    destination = ObjectGenerator.create_account()
    return [ObjectGenerator.transfer(source, destination, 500) for _ in range(count)]


class TestFees:
    def test_sums_the_fees_of_the_period(self):
        DbUtils.rollback()
        operations = make_transfers(3)

        status, response = RequestGenerator.GET_fees(around_today())

        assert status == 200
        assert response["total_amount"] == 3 * FEE
        assert response["page"] == 0 and response["page_size"] == PAGE_SIZE and response["is_last_page"] is True
        assert [e["operation_key"] for e in response["data"]] == [o["operation_key"] for o in reversed(operations)]
        for entry in response["data"]:
            assert set(entry) == {"entry_key", "operation_key", "account_key", "amount", "completed_at"}
            assert entry["amount"] == FEE

    def test_deposits_and_refused_transfers_pay_no_fee(self):
        DbUtils.rollback()
        source = ObjectGenerator.create_account(balance=1000)
        destination = ObjectGenerator.create_account()
        status, _ = RequestGenerator.POST_transfer(PayloadGenerator.create_transfer_payload(source, destination, 5000))
        assert status == 422

        status, response = RequestGenerator.GET_fees(around_today())

        assert status == 200
        assert response["data"] == []
        assert response["total_amount"] == 0

    def test_period_without_fees_is_empty_and_ok(self):
        DbUtils.rollback()
        make_transfers(1)

        status, response = RequestGenerator.GET_fees({"start_date": "2000-01-01", "end_date": "2000-01-31"})

        assert status == 200
        assert response == {"data": [], "total_amount": 0, "page": 0, "page_size": PAGE_SIZE, "is_last_page": True}

    def test_days_are_inclusive_in_utc(self):
        DbUtils.rollback()
        make_transfers(1)
        today = utc_today().isoformat()
        yesterday = (utc_today() - timedelta(days=1)).isoformat()
        tomorrow = (utc_today() + timedelta(days=1)).isoformat()

        inside = [(today, today), (yesterday, today), (today, tomorrow)]
        outside = [(yesterday, yesterday), (tomorrow, tomorrow)]

        for start_date, end_date in inside:
            _, response = RequestGenerator.GET_fees({"start_date": start_date, "end_date": end_date})
            assert response["total_amount"] == FEE, (start_date, end_date)

        for start_date, end_date in outside:
            _, response = RequestGenerator.GET_fees({"start_date": start_date, "end_date": end_date})
            assert response["total_amount"] == 0, (start_date, end_date)

    def test_total_covers_the_whole_period_in_every_page(self):
        DbUtils.rollback()
        make_transfers(21)

        status0, page0 = RequestGenerator.GET_fees(around_today())
        status1, page1 = RequestGenerator.GET_fees({**around_today(), "page": 1})
        status2, page2 = RequestGenerator.GET_fees({**around_today(), "page": 2})

        assert (status0, status1, status2) == (200, 200, 200)
        assert len(page0["data"]) == PAGE_SIZE and page0["is_last_page"] is False
        assert len(page1["data"]) == 1 and page1["is_last_page"] is True
        assert page2["data"] == [] and page2["is_last_page"] is True
        assert page0["total_amount"] == page1["total_amount"] == page2["total_amount"] == 21 * FEE
        assert len({e["entry_key"] for e in page0["data"] + page1["data"]}) == 21

    def test_collected_fees_match_the_statements(self):
        DbUtils.rollback()
        source = ObjectGenerator.create_account(balance=5000)
        destination = ObjectGenerator.create_account()
        ObjectGenerator.transfer(source, destination, 1000)
        ObjectGenerator.transfer(destination, source, 200)

        _, response = RequestGenerator.GET_fees(around_today())

        statement_fees = sum(
            e["amount"] for key in (source, destination) for e in ObjectGenerator.all_entries(key) if e["type"] == "fee"
        )
        assert response["total_amount"] == statement_fees == 2 * FEE

    def test_dates_are_required_and_must_be_real_and_ordered(self):
        invalid = [
            {},
            {"start_date": "2026-01-01"},
            {"end_date": "2026-01-01"},
            {"start_date": "2026-13-01", "end_date": "2026-12-31"},
            {"start_date": "2026-02-30", "end_date": "2026-03-01"},
            {"start_date": "01/01/2026", "end_date": "2026-12-31"},
            {"start_date": "20260101", "end_date": "2026-12-31"},
            {"start_date": "abc", "end_date": "2026-12-31"},
            {"start_date": "2026-12-31", "end_date": "2026-01-01"},
        ]
        for params in invalid:
            status, response = RequestGenerator.GET_fees(params)
            assert status == 400, params
            assert response["code"] == "QIT000010"

    def test_invalid_page_is_invalid_parameter(self):
        for page in ("-1", "abc", "1.5"):
            status, response = RequestGenerator.GET_fees({**around_today(), "page": page})
            assert status == 400, page
            assert response["code"] == "QIT000010"

    def test_last_possible_day_does_not_overflow(self):
        status, response = RequestGenerator.GET_fees({"start_date": "9999-12-30", "end_date": "9999-12-31"})
        assert status == 200
        assert response["total_amount"] == 0
