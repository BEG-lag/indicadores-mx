"""The series this project publishes, with bilingual metadata.

Every text here ends up in ``/v1/index.json`` and on the site. ``date_meaning``
says exactly what the ``date`` of an observation is, because it differs between
series: the FIX and the TIIE are dated by their DOF publication (Banco de México
determined them the previous banking day), a UDI by the day it applies, the INPC
by the month it measures, and minimum wages and the UMA by the first day they
are in force.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["daily", "monthly", "step"]

SIDOF_INDICATORS = "https://sidof.segob.gob.mx/dof/sidof/indicadores"
INEGI_INPC_CSV = (
    "https://www.inegi.org.mx/contenidos/programas/inpc/2018/datosabiertos/"
    "inpc_indicador_mensual_csv.zip"
)


@dataclass(frozen=True, slots=True)
class Text:
    es: str
    en: str

    def to_json(self) -> dict[str, str]:
        return {"es": self.es, "en": self.en}


@dataclass(frozen=True, slots=True)
class Series:
    id: str
    name: Text
    short: Text
    unit: Text
    unit_code: str
    kind: Kind
    frequency: Text
    issuer: str
    description: Text
    date_meaning: Text
    legal_basis: Text
    decimals: int
    default_origin: str
    sidof_code: int | None = None
    derived_from: str | None = None
    group: str = ""
    ended: str | None = None
    status: str = "VERDE"
    sources: tuple[dict[str, str], ...] = field(default_factory=tuple)


BANXICO = "Banco de México"
INEGI = "Instituto Nacional de Estadística y Geografía (INEGI)"
CONASAMI = "Comisión Nacional de los Salarios Mínimos (CONASAMI)"

DOF_SOURCE = {
    "id": "dof",
    "name": "Diario Oficial de la Federación (vía la API pública del SIDOF, Secretaría de Gobernación)",
    "url": "https://dof.gob.mx",
}


def _sidof_source(code: int) -> dict[str, str]:
    return {
        "id": "sidof",
        "name": f"SIDOF, indicador {code}",
        "url": f"{SIDOF_INDICATORS}/{code}/{{DD-MM-AAAA}}/{{DD-MM-AAAA}}",
    }


def _tiie(term: int, code: int, start_note: str) -> Series:
    return Series(
        id=f"tiie-{term}",
        name=Text(f"TIIE a {term} días", f"{term}-day TIIE"),
        short=Text(f"TIIE {term}", f"TIIE {term}"),
        unit=Text("% anual", "% per year"),
        unit_code="percent",
        kind="daily",
        frequency=Text(
            "Días hábiles bancarios" + start_note,
            "Banking days" + (" (weekly in early years)" if start_note else ""),
        ),
        issuer=BANXICO,
        description=Text(
            f"Tasa de Interés Interbancaria de Equilibrio a plazo de {term} días, que el Banco de "
            "México determina con cotizaciones de las instituciones de crédito y publica en el DOF.",
            f"Interbank Equilibrium Interest Rate for a {term}-day term, determined by Banco de "
            "México from bank quotes and published in the DOF.",
        ),
        date_meaning=Text(
            "Día al que corresponde en el SIDOF, que normalmente es el de su publicación en el "
            "DOF. Banco de México la determinó el día hábil bancario anterior, como dice la propia "
            "nota. La fecha de la nota está en la fuente.",
            "Day it corresponds to in SIDOF, normally the day it is published in the DOF. Banco de "
            "México determined it the previous banking day, as the note itself states. The note "
            "date is in the source.",
        ),
        legal_basis=Text(
            "Circular 3/2012 del Banco de México, Título Tercero, Capítulo IV.",
            "Banco de México Circular 3/2012, Title Three, Chapter IV.",
        ),
        decimals=4,
        default_origin="sidof",
        sidof_code=code,
        group="tasas",
        sources=(DOF_SOURCE, _sidof_source(code)),
    )


SERIES: tuple[Series, ...] = (
    Series(
        id="fix",
        name=Text(
            "Tipo de cambio FIX (para solventar obligaciones en moneda extranjera)",
            "FIX exchange rate (to settle foreign currency obligations)",
        ),
        short=Text("Dólar FIX", "USD FIX"),
        unit=Text("pesos por dólar", "pesos per US dollar"),
        unit_code="MXN/USD",
        kind="daily",
        frequency=Text("Días hábiles bancarios", "Banking days"),
        issuer=BANXICO,
        description=Text(
            "Tipo de cambio para solventar obligaciones denominadas en moneda extranjera pagaderas "
            "en la República Mexicana, que el Banco de México determina y publica en el DOF.",
            "Exchange rate to settle obligations denominated in foreign currency payable in "
            "Mexico, determined by Banco de México and published in the DOF.",
        ),
        date_meaning=Text(
            "Día en que sirve para solventar obligaciones, que normalmente es el de su "
            "publicación en el DOF. Banco de México lo determinó el día hábil bancario anterior "
            "(la serie SF43718 del SIE está fechada por ese día). Si un día hábil bancario no hubo "
            "DOF (por ejemplo el 5 de mayo de 2025), su valor salió en la edición siguiente: la "
            "fecha de la nota está en la fuente.",
            "Day it is used to settle obligations, normally the day it is published in the DOF. "
            "Banco de México determined it the previous banking day (Banxico's SIE series SF43718 "
            "is dated by that day). When a banking day had no DOF edition (5 May 2025, for "
            "example), its value appeared in the next edition: the note date is in the source.",
        ),
        legal_basis=Text(
            "Ley Monetaria, art. 8o.; Ley del Banco de México, art. 35; Circular 3/2012, Título "
            "Tercero, Capítulo V.",
            "Ley Monetaria, art. 8; Ley del Banco de México, art. 35; Circular 3/2012, Title "
            "Three, Chapter V.",
        ),
        decimals=4,
        default_origin="sidof",
        sidof_code=158,
        group="tipo-de-cambio",
        sources=(DOF_SOURCE, _sidof_source(158)),
    ),
    Series(
        id="udis",
        name=Text("Unidad de Inversión (UDI)", "Investment Unit (UDI)"),
        short=Text("UDI", "UDI"),
        unit=Text("pesos por UDI", "pesos per UDI"),
        unit_code="MXN/UDI",
        kind="daily",
        frequency=Text("Diaria (todos los días naturales)", "Daily (every calendar day)"),
        issuer=BANXICO,
        description=Text(
            "Valor en pesos de la Unidad de Inversión, que sigue al INPC. Banco de México lo "
            "publica en el DOF alrededor del día 10 (para los días 11 a 25) y del 25 (días 26 al "
            "10 siguiente).",
            "Peso value of the Investment Unit, which tracks the INPC. Banco de México publishes "
            "it in the DOF around the 10th (for days 11 to 25) and the 25th (days 26 to the next "
            "10th).",
        ),
        date_meaning=Text(
            "Día al que corresponde el valor. La fecha de la nota del DOF que lo publicó va en la "
            "fuente.",
            "Day the value applies to. The date of the DOF note that published it is in the "
            "source.",
        ),
        legal_basis=Text(
            "Decreto que establece las obligaciones que podrán denominarse en Unidades de "
            "Inversión (DOF 01-04-1995), art. tercero; Código Fiscal de la Federación, art. 20 Ter.",
            "Decree on obligations that may be denominated in Investment Units (DOF 1995-04-01), "
            "art. 3; Federal Tax Code, art. 20 Ter.",
        ),
        decimals=6,
        default_origin="sidof",
        sidof_code=159,
        group="inflacion",
        sources=(DOF_SOURCE, _sidof_source(159)),
    ),
    _tiie(28, 165, ""),
    _tiie(91, 166, " (semanal en los primeros años)"),
    _tiie(182, 174, " (semanal en los primeros años)"),
    Series(
        id="tiie-fondeo",
        name=Text(
            "TIIE de fondeo a un día hábil bancario",
            "Overnight funding TIIE (TIIE de fondeo)",
        ),
        short=Text("TIIE fondeo", "Funding TIIE"),
        unit=Text("% anual", "% per year"),
        unit_code="percent",
        kind="daily",
        frequency=Text("Días hábiles bancarios", "Banking days"),
        issuer=BANXICO,
        description=Text(
            "Tasa de Interés Interbancaria de Equilibrio de fondeo a un día hábil bancario, "
            "calculada por el Banco de México con operaciones de reporto a un día.",
            "Overnight Interbank Equilibrium Interest Rate, computed by Banco de México from "
            "one-day repo transactions.",
        ),
        date_meaning=Text(
            "Día al que corresponde en el SIDOF, que normalmente es el de su publicación en el "
            "DOF. Refleja las operaciones del día hábil bancario anterior. La fecha de la nota está "
            "en la fuente.",
            "Day it corresponds to in SIDOF, normally the day it is published in the DOF. It "
            "reflects the previous banking day's transactions. The note date is in the source.",
        ),
        legal_basis=Text(
            "Circular 3/2012 del Banco de México, Título Tercero, Capítulo IV.",
            "Banco de México Circular 3/2012, Title Three, Chapter IV.",
        ),
        decimals=2,
        default_origin="sidof",
        sidof_code=175,
        group="tasas",
        sources=(DOF_SOURCE, _sidof_source(175)),
    ),
    Series(
        id="inpc",
        name=Text(
            "Índice Nacional de Precios al Consumidor (INPC)",
            "National Consumer Price Index (INPC)",
        ),
        short=Text("INPC", "INPC"),
        unit=Text(
            "índice, 2a. quincena de julio de 2018 = 100",
            "index, second half of July 2018 = 100",
        ),
        unit_code="index",
        kind="monthly",
        frequency=Text("Mensual", "Monthly"),
        issuer=INEGI,
        description=Text(
            "Índice general mensual. El INEGI lo publica en el DOF dentro de los primeros diez "
            "días del mes siguiente.",
            "Monthly headline index. INEGI publishes it in the DOF within the first ten days of "
            "the following month.",
        ),
        date_meaning=Text(
            "Mes que mide el índice (AAAA-MM).", "Month the index measures (YYYY-MM)."
        ),
        legal_basis=Text(
            "Código Fiscal de la Federación, art. 20; Ley del Sistema Nacional de Información "
            "Estadística y Geográfica, art. 59, fr. III, inciso a.",
            "Federal Tax Code, art. 20; Law of the National System of Statistical and Geographic "
            "Information, art. 59, section III(a).",
        ),
        decimals=3,
        default_origin="dof",
        group="inflacion",
        sources=(
            DOF_SOURCE,
            {
                "id": "inegi",
                "name": "INEGI, datos abiertos del INPC mensual (serie reexpresada en base 2018)",
                "url": INEGI_INPC_CSV,
            },
        ),
    ),
    Series(
        id="inflacion-mensual",
        name=Text("Inflación mensual (variación del INPC)", "Monthly inflation (INPC change)"),
        short=Text("Inflación mensual", "Monthly inflation"),
        unit=Text("% respecto del mes anterior", "% over the previous month"),
        unit_code="percent",
        kind="monthly",
        frequency=Text("Mensual", "Monthly"),
        issuer=INEGI,
        description=Text(
            "Variación porcentual del INPC respecto del mes anterior, calculada por este proyecto "
            "con los índices publicados y redondeada a dos decimales (mitad hacia arriba). Desde "
            "agosto de 2018 coincide con la que imprime cada nota del INEGI en el DOF.",
            "Percent change of the INPC over the previous month, computed by this project from the "
            "published indexes and rounded to two decimals (half up). Since August 2018 it matches "
            "the change printed in every INEGI note in the DOF.",
        ),
        date_meaning=Text("Mes (AAAA-MM).", "Month (YYYY-MM)."),
        legal_basis=Text("Derivada del INPC.", "Derived from the INPC."),
        decimals=2,
        default_origin="derived",
        derived_from="inpc",
        group="inflacion",
        sources=(
            {"id": "derived", "name": "Calculada a partir del INPC", "url": "v1/inpc/all.csv"},
        ),
    ),
    Series(
        id="inflacion-anual",
        name=Text(
            "Inflación anual (variación anual del INPC)", "Annual inflation (12-month INPC change)"
        ),
        short=Text("Inflación anual", "Annual inflation"),
        unit=Text(
            "% respecto del mismo mes del año anterior", "% over the same month a year earlier"
        ),
        unit_code="percent",
        kind="monthly",
        frequency=Text("Mensual", "Monthly"),
        issuer=INEGI,
        description=Text(
            "Variación porcentual del INPC respecto del mismo mes del año anterior, calculada por "
            "este proyecto con los índices publicados y redondeada a dos decimales (mitad hacia "
            "arriba). La de diciembre es la inflación del año.",
            "Percent change of the INPC over the same month of the previous year, computed by this "
            "project from the published indexes and rounded to two decimals (half up). December's "
            "value is the inflation of the year.",
        ),
        date_meaning=Text("Mes (AAAA-MM).", "Month (YYYY-MM)."),
        legal_basis=Text("Derivada del INPC.", "Derived from the INPC."),
        decimals=2,
        default_origin="derived",
        derived_from="inpc",
        group="inflacion",
        sources=(
            {"id": "derived", "name": "Calculada a partir del INPC", "url": "v1/inpc/all.csv"},
        ),
    ),
    Series(
        id="salario-minimo-general",
        name=Text("Salario mínimo general", "General minimum wage"),
        short=Text("Salario mínimo", "Minimum wage"),
        unit=Text("pesos diarios", "pesos per day"),
        unit_code="MXN/day",
        kind="step",
        frequency=Text("Cuando lo fija la CONASAMI (anual)", "When CONASAMI sets it (yearly)"),
        issuer=CONASAMI,
        description=Text(
            "Salario mínimo general diario. Desde el 1 de octubre de 2015 hay uno solo para el "
            "país; desde 2019 es el del resto del país, fuera de la Zona Libre de la Frontera "
            "Norte. Antes de octubre de 2015 regían áreas geográficas: ver las series "
            "salario-minimo-area-a, -area-b y -area-c.",
            "Daily general minimum wage. Since 1 October 2015 there is a single one for the "
            "country; since 2019 it applies outside the Northern Border Free Zone. Before October "
            "2015 the country was split into geographic areas: see salario-minimo-area-a, -area-b "
            "and -area-c.",
        ),
        date_meaning=Text("Primer día en que rige el valor.", "First day the value is in force."),
        legal_basis=Text(
            "Constitución, art. 123, apartado A, fr. VI; Ley Federal del Trabajo, arts. 90, 94 y 570.",
            "Constitution, art. 123(A)(VI); Federal Labor Law, arts. 90, 94 and 570.",
        ),
        decimals=2,
        default_origin="dof",
        group="salarios",
        sources=(DOF_SOURCE,),
    ),
    Series(
        id="salario-minimo-zlfn",
        name=Text(
            "Salario mínimo, Zona Libre de la Frontera Norte",
            "Minimum wage, Northern Border Free Zone",
        ),
        short=Text("Salario mínimo ZLFN", "Minimum wage ZLFN"),
        unit=Text("pesos diarios", "pesos per day"),
        unit_code="MXN/day",
        kind="step",
        frequency=Text("Cuando lo fija la CONASAMI (anual)", "When CONASAMI sets it (yearly)"),
        issuer=CONASAMI,
        description=Text(
            "Salario mínimo general diario de los municipios de la Zona Libre de la Frontera "
            "Norte, vigente desde el 1 de enero de 2019.",
            "Daily general minimum wage in the municipalities of the Northern Border Free Zone, "
            "in force since 1 January 2019.",
        ),
        date_meaning=Text("Primer día en que rige el valor.", "First day the value is in force."),
        legal_basis=Text(
            "Constitución, art. 123, apartado A, fr. VI; Ley Federal del Trabajo, arts. 90, 94 y 570.",
            "Constitution, art. 123(A)(VI); Federal Labor Law, arts. 90, 94 and 570.",
        ),
        decimals=2,
        default_origin="dof",
        group="salarios",
        sources=(DOF_SOURCE,),
    ),
    Series(
        id="salario-minimo-area-a",
        name=Text(
            "Salario mínimo general, área geográfica A (histórico)",
            "General minimum wage, geographic area A (historical)",
        ),
        short=Text("Salario mínimo área A", "Minimum wage area A"),
        unit=Text("pesos diarios", "pesos per day"),
        unit_code="MXN/day",
        kind="step",
        frequency=Text("Cuando lo fijaba la CONASAMI", "When CONASAMI set it"),
        issuer=CONASAMI,
        description=Text(
            "Salario mínimo general del área geográfica A, que incluía al Distrito Federal: es el "
            '"salario mínimo general vigente en el Distrito Federal" que citaban muchas leyes y '
            "contratos antes de la desindexación de 2016. Serie cerrada: el 1 de octubre de 2015 "
            "las áreas se unificaron.",
            "General minimum wage of geographic area A, which included the Federal District: the "
            '"general minimum wage in force in the Federal District" cited by many laws and '
            "contracts before the 2016 de-indexation. Closed series: the areas were merged on 1 "
            "October 2015.",
        ),
        date_meaning=Text("Primer día en que rige el valor.", "First day the value is in force."),
        legal_basis=Text(
            "Ley Federal del Trabajo, arts. 90, 94 y 570 (texto de la época).",
            "Federal Labor Law, arts. 90, 94 and 570 (text of the time).",
        ),
        decimals=2,
        default_origin="dof",
        group="salarios",
        ended="2015-09-30",
        sources=(DOF_SOURCE,),
    ),
    Series(
        id="salario-minimo-area-b",
        name=Text(
            "Salario mínimo general, área geográfica B (histórico)",
            "General minimum wage, geographic area B (historical)",
        ),
        short=Text("Salario mínimo área B", "Minimum wage area B"),
        unit=Text("pesos diarios", "pesos per day"),
        unit_code="MXN/day",
        kind="step",
        frequency=Text("Cuando lo fijaba la CONASAMI", "When CONASAMI set it"),
        issuer=CONASAMI,
        description=Text(
            "Salario mínimo general del área geográfica B (desde el 27 de noviembre de 2012 "
            "absorbió al área C). Serie cerrada: el 1 de octubre de 2015 las áreas se unificaron.",
            "General minimum wage of geographic area B (it absorbed area C on 27 November 2012). "
            "Closed series: the areas were merged on 1 October 2015.",
        ),
        date_meaning=Text("Primer día en que rige el valor.", "First day the value is in force."),
        legal_basis=Text(
            "Ley Federal del Trabajo, arts. 90, 94 y 570 (texto de la época).",
            "Federal Labor Law, arts. 90, 94 and 570 (text of the time).",
        ),
        decimals=2,
        default_origin="dof",
        group="salarios",
        ended="2015-09-30",
        sources=(DOF_SOURCE,),
    ),
    Series(
        id="salario-minimo-area-c",
        name=Text(
            "Salario mínimo general, área geográfica C (histórico)",
            "General minimum wage, geographic area C (historical)",
        ),
        short=Text("Salario mínimo área C", "Minimum wage area C"),
        unit=Text("pesos diarios", "pesos per day"),
        unit_code="MXN/day",
        kind="step",
        frequency=Text("Cuando lo fijaba la CONASAMI", "When CONASAMI set it"),
        issuer=CONASAMI,
        description=Text(
            "Salario mínimo general del área geográfica C. Serie cerrada: desde el 27 de noviembre de 2012 sus municipios pasaron al área B.",
            "General minimum wage of geographic area C. Closed series: on 27 November 2012 its municipalities moved to area B.",
        ),
        date_meaning=Text("Primer día en que rige el valor.", "First day the value is in force."),
        legal_basis=Text(
            "Ley Federal del Trabajo, arts. 90, 94 y 570 (texto de la época).",
            "Federal Labor Law, arts. 90, 94 and 570 (text of the time).",
        ),
        decimals=2,
        default_origin="dof",
        group="salarios",
        ended="2012-11-26",
        sources=(DOF_SOURCE,),
    ),
    Series(
        id="uma-diaria",
        name=Text("Unidad de Medida y Actualización (UMA), valor diario", "UMA, daily value"),
        short=Text("UMA diaria", "UMA daily"),
        unit=Text("pesos", "pesos"),
        unit_code="MXN",
        kind="step",
        frequency=Text("Anual (rige desde el 1 de febrero)", "Yearly (in force from 1 February)"),
        issuer=INEGI,
        description=Text(
            "Unidad de cuenta que sustituyó al salario mínimo como referencia en las leyes desde "
            "la desindexación de 2016. El INEGI publica su valor en el DOF en los primeros diez "
            "días de enero y rige a partir del 1 de febrero.",
            "Unit of account that replaced the minimum wage as the reference in laws after the "
            "2016 de-indexation. INEGI publishes its value in the DOF in the first ten days of "
            "January and it applies from 1 February.",
        ),
        date_meaning=Text("Primer día en que rige el valor.", "First day the value is in force."),
        legal_basis=Text(
            "Constitución, art. 26, apartado B; Ley para Determinar el Valor de la Unidad de "
            "Medida y Actualización, arts. 4 y 5; Decreto de desindexación del salario mínimo "
            "(DOF 27-01-2016), transitorios.",
            "Constitution, art. 26(B); Law to Determine the Value of the UMA, arts. 4 and 5; "
            "minimum wage de-indexation decree (DOF 2016-01-27), transitional articles.",
        ),
        decimals=2,
        default_origin="dof",
        group="uma",
        sources=(DOF_SOURCE,),
    ),
    Series(
        id="uma-mensual",
        name=Text("Unidad de Medida y Actualización (UMA), valor mensual", "UMA, monthly value"),
        short=Text("UMA mensual", "UMA monthly"),
        unit=Text("pesos", "pesos"),
        unit_code="MXN",
        kind="step",
        frequency=Text("Anual (rige desde el 1 de febrero)", "Yearly (in force from 1 February)"),
        issuer=INEGI,
        description=Text(
            "Valor mensual de la UMA: el diario multiplicado por 30.4.",
            "Monthly value of the UMA: the daily value times 30.4.",
        ),
        date_meaning=Text("Primer día en que rige el valor.", "First day the value is in force."),
        legal_basis=Text(
            "Ley para Determinar el Valor de la Unidad de Medida y Actualización, art. 4.",
            "Law to Determine the Value of the UMA, art. 4.",
        ),
        decimals=2,
        default_origin="dof",
        group="uma",
        sources=(DOF_SOURCE,),
    ),
    Series(
        id="uma-anual",
        name=Text("Unidad de Medida y Actualización (UMA), valor anual", "UMA, annual value"),
        short=Text("UMA anual", "UMA annual"),
        unit=Text("pesos", "pesos"),
        unit_code="MXN",
        kind="step",
        frequency=Text("Anual (rige desde el 1 de febrero)", "Yearly (in force from 1 February)"),
        issuer=INEGI,
        description=Text(
            "Valor anual de la UMA: el mensual multiplicado por 12.",
            "Annual value of the UMA: the monthly value times 12.",
        ),
        date_meaning=Text("Primer día en que rige el valor.", "First day the value is in force."),
        legal_basis=Text(
            "Ley para Determinar el Valor de la Unidad de Medida y Actualización, art. 4.",
            "Law to Determine the Value of the UMA, art. 4.",
        ),
        decimals=2,
        default_origin="dof",
        group="uma",
        sources=(DOF_SOURCE,),
    ),
)

BY_ID: dict[str, Series] = {s.id: s for s in SERIES}
DAILY = tuple(s for s in SERIES if s.kind == "daily")
