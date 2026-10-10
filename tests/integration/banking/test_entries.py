import re

from tests.utils import ObjectGenerator, RandomGenerator, RequestGenerator

PAGE_SIZE = 20


class TestEntries:
    def test_new_account_has_an_empty_statement(self):
        account_key = ObjectGenerator.create_account()

        status, response = RequestGenerator.GET_entries(account_key)

        assert status == 200
        assert response == {"data": [], "page": 0, "page_size": PAGE_SIZE, "is_last_page": True}

    def test_lists_newest_first_with_public_fields_only(self):
        account_key = ObjectGenerator.create_account()
        first = ObjectGenerator.deposit(account_key, 100)
        second = ObjectGenerator.deposit(account_key, 200)
        third = ObjectGenerator.deposit(account_key, 300)

        status, response = RequestGenerator.GET_entries(account_key)

        assert status == 200
        assert [e["operation_key"] for e in response["data"]] == [
            third["operation_key"],
            second["operation_key"],
            first["operation_key"],
        ]
        assert [e["amount"] for e in response["data"]] == [300, 200, 100]
        for entry in response["data"]:
            assert set(entry) == {"entry_key", "operation_key", "type", "amount", "completed_at"}
            assert re.match(r"^[0-9a-f-]{36}$", entry["entry_key"])

    def test_paginates_with_twenty_per_page(self):
        account_key = ObjectGenerator.create_account()
        for _ in range(21):
            ObjectGenerator.deposit(account_key, 10)

        status, page0 = RequestGenerator.GET_entries(account_key)
        status1, page1 = RequestGenerator.GET_entries(account_key, {"page": 1})
        status2, page2 = RequestGenerator.GET_entries(account_key, {"page": 2})

        assert (status, status1, status2) == (200, 200, 200)
        assert len(page0["data"]) == PAGE_SIZE and page0["is_last_page"] is False
        assert len(page1["data"]) == 1 and page1["is_last_page"] is True and page1["page"] == 1
        assert page2["data"] == [] and page2["is_last_page"] is True

        keys = [e["entry_key"] for e in page0["data"] + page1["data"]]
        assert len(set(keys)) == 21

    def test_exactly_one_full_page_is_the_last_page(self):
        account_key = ObjectGenerator.create_account()
        for _ in range(PAGE_SIZE):
            ObjectGenerator.deposit(account_key, 10)

        status, response = RequestGenerator.GET_entries(account_key)

        assert status == 200
        assert len(response["data"]) == PAGE_SIZE
        assert response["is_last_page"] is True

    def test_unknown_account_is_not_found(self):
        status, response = RequestGenerator.GET_entries(RandomGenerator.generate_uuid())
        assert status == 404
        assert response["code"] == "QIT002004"

    def test_invalid_page_is_invalid_parameter(self):
        account_key = ObjectGenerator.create_account()
        for page in ("-1", "abc", "1.5", "", "1000000000"):
            status, response = RequestGenerator.GET_entries(account_key, {"page": page})
            assert status == 400, page
            assert response["code"] == "QIT000010"

    def test_account_key_out_of_format_is_invalid_parameter(self):
        status, response = RequestGenerator.GET_entries("abc")
        assert status == 400
        assert response["code"] == "QIT000010"
