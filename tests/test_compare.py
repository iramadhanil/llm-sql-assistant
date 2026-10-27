from sql_assistant.compare import results_match, values_match


def test_whole_numbers_must_match_exactly():
    assert values_match(96478, 96478.0)
    assert not values_match(96478, 96470)


def test_small_rounding_differences_are_accepted():
    assert values_match(8.112366, 8.11)
    assert values_match(13221498.11, 13221498)
    assert not values_match(12.56, 12.09)


def test_text_and_numbers():
    assert values_match("2017", 2017)
    assert values_match("SP", "SP")
    assert not values_match("SP", "RJ")
    assert values_match(None, None)
    assert not values_match(None, 0)


def test_row_order_does_not_matter():
    assert results_match([("SP",), ("RJ",), ("MG",)], [("MG",), ("SP",), ("RJ",)])


def test_extra_columns_are_allowed():
    gold = [("bed_bath_table",)]
    assert results_match(gold, [("bed_bath_table", 11115)])
    assert results_match(gold, [(11115, "bed_bath_table")])


def test_missing_or_extra_rows_fail():
    gold = [("SP",), ("RJ",), ("MG",)]
    assert not results_match(gold, [("SP",), ("RJ",)])
    assert not results_match(gold, [("SP",), ("RJ",), ("MG",), ("RS",)])


def test_wrong_value_fails():
    assert not results_match([(99441,)], [(96096,)])


def test_columns_cannot_be_reused():
    gold = [(1, 1)]
    assert results_match(gold, [(1, 1)])
    assert not results_match(gold, [(1,)])


def test_values_side_by_side_instead_of_stacked():
    gold = [(4.29,), (2.57,)]
    assert results_match(gold, [(2.57, 4.29)])
    assert not results_match(gold, [(2.57, 3.99)])
    assert not results_match(gold, [(2.57, 4.29, 1.0)])


def test_two_column_answers():
    gold = [("2016", 329), ("2017", 45101), ("2018", 54011)]
    pred = [(2018, 54011, 54.3), (2016, 329, 0.3), (2017, 45101, 45.4)]
    assert results_match(gold, pred)
