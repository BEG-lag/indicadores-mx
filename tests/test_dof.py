"""Parsers against real DOF notes (recorded in tests/fixtures/sidof/nota)."""

from datetime import date

import pytest

from indicadores_mx import dof


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (5803775, "18.6188"),  # 2026-11-13
        (2049214, "9.5150"),  # 2000-01-10
        (4865462, "4.9950"),  # 1995-01-02, printed "N$ 4.9950" (nuevos pesos)
    ],
)
def test_fix(text_of, code, expected):
    assert dof.parse_fix(text_of(code)) == expected


def test_fix_note_is_signed_the_previous_banking_day(text_of):
    assert dof.signed_on(text_of(5803775)) == date(2026, 11, 12)


def test_tiie_three_terms_in_one_note(text_of):
    assert dof.parse_tiie(text_of(5803776)) == {28: "6.5147", 91: "6.5492", 182: "6.5995"}


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (4884436, {28: "30.5450"}),  # 1996, "por ciento"
        (755580, {28: "8.9400"}),  # 2005, one note per term
        (755581, {91: "9.0200"}),
    ],
)
def test_tiie_older_formats(text_of, code, expected):
    assert dof.parse_tiie(text_of(code)) == expected


def test_fondeo(text_of):
    assert dof.parse_fondeo(text_of(5803777)) == "6.26"


def test_udi_table_2026(text_of):
    table = dof.parse_udi_table(text_of(5803350))
    assert min(table) == date(2026, 11, 11)
    assert max(table) == date(2026, 11, 25)
    assert len(table) == 15
    assert table[date(2026, 11, 13)] == "8.904621"


def test_udi_table_2000_named_months(text_of):
    table = dof.parse_udi_table(text_of(2049217))
    assert table[date(2000, 1, 11)] == "2.680890"
    assert len(table) == 15


def test_udi_table_formats():
    text = (
        "Fecha Valor 11-julio-20 6.4 51423 12- noviembre-2009 4.312345 "
        "11 de agosto de 2022 7.345678 26/02/2020 6.456789"
    )
    table = dof.parse_udi_table(text)
    assert table == {
        date(2009, 11, 12): "4.312345",
        date(2020, 2, 26): "6.456789",
        date(2020, 7, 11): "6.451423",
        date(2022, 8, 11): "7.345678",
    }


def test_inpc_monthly(text_of):
    parsed = dof.parse_inpc_monthly(text_of(5803352))
    assert parsed == dof.InpcMonthly(
        month="2026-10",
        value="147.026",
        variation="0.65",
        previous_month="2026-09",
        previous_value="146.075",
    )


def test_inpc_august_2018_typo_and_correction(text_of):
    wrong = dof.parse_inpc_monthly(text_of(5537424))
    fixed = dof.parse_inpc_monthly(text_of(5537585))
    assert wrong is not None
    assert fixed is not None
    assert (wrong.month, wrong.value) == ("2018-08", "100.942")
    assert (fixed.month, fixed.value) == ("2018-08", "100.492")
    assert fixed.variation == "0.58"


def test_uma(text_of):
    assert dof.parse_uma(text_of(5778072)) == dof.UmaValues(
        in_force=date(2026, 2, 1), daily="117.31", monthly="3566.22", annual="42794.64"
    )


def test_minimum_wage_sentence():
    text = (
        "habrán de regir a partir del 1o. de enero de 2026. Los salarios mínimos generales que "
        "tendrán vigencia a partir del 1º de enero de 2026, reflejan un incremento: En 13.0% en "
        "la Zona del Salario Mínimo General (ZSMG), con lo que será de 315.04 pesos por jornada "
        "diaria de trabajo. En 5.0% en la Zona Libre de la Frontera Norte (ZLFN), con lo que será "
        "de 440.87 pesos por jornada diaria de trabajo."
    )
    assert dof.parse_minimum_wage(text) == dof.MinimumWage(
        in_force=date(2026, 1, 1), general="315.04", zlfn="440.87"
    )


def test_titles():
    assert dof.is_fix_title("Tipo de cambio para solventar obligaciones denominadas en moneda")
    assert dof.is_tiie_title("Tasas de interés interbancarias de equilibrio.")
    assert dof.is_tiie_title("Tasa de interés interbancaria de equilibrio a 91 días")
    assert not dof.is_tiie_title("Tasa de interés interbancaria de equilibrio de fondeo a un día")
    assert dof.is_fondeo_title("Tasa de interés interbancaria de equilibrio de fondeo a un día")
    assert dof.is_correction_title("Nota Aclaratoria al Índice nacional de precios")
    assert dof.dof_note_url(5803775, date(2026, 11, 13)) == (
        "https://dof.gob.mx/nota_detalle.php?codigo=5803775&fecha=13/11/2026"
    )


def test_tiie_two_terms_in_one_sentence(text_of):
    assert dof.parse_tiie(text_of(5713424)) == {28: "11.5025", 91: "11.4750"}


def test_tiie_holiday_terms_and_split_digits(text_of):
    assert dof.parse_tiie(text_of(5713935)) == {29: "11.5025", 91: "11.6394", 182: "11.8036"}
    assert dof.parse_tiie(text_of(5741355)) == {28: "10.7400", 91: "10.8687", 180: "11.0115"}


def test_two_fix_notes_on_one_day_are_signed_on_different_days(text_of):
    first, second = text_of(5756456), text_of(5756459)
    assert (dof.parse_fix(first), dof.signed_on(first)) == ("19.6570", date(2025, 5, 2))
    assert (dof.parse_fix(second), dof.signed_on(second)) == ("19.6365", date(2025, 5, 5))


def test_minimum_wage_2016_amount_is_in_the_correction(text_of):
    from indicadores_mx.pipeline import value_in_text

    assert value_in_text("73.04", text_of(5420747))
