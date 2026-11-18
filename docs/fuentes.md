# Fuentes, método y verificación

Cada valor de indicadores-mx tiene una fuente oficial. Este documento dice cuál es, cómo se
obtuvo, cómo se verificó, qué errores se encontraron en las fuentes y qué no se pudo verificar.
Consulta hecha el 17 de noviembre de 2026, salvo que se indique otra fecha.

> **Advertencia.** Espejo no oficial. Solo el Diario Oficial de la Federación y las instituciones
> que emiten cada indicador (Banco de México, INEGI, CONASAMI) tienen validez oficial. Este
> documento no constituye opinión legal ni asesoría fiscal; lo que dependa de la interpretación de
> una norma debe validarse con la autoridad competente.

Etiquetas: **[ESTIMADO]** cifra calculada o aproximada; **[SUPUESTO]** premisa no confirmada;
**[BRECHA DE DATO]** información que falta.

Semáforo: **VERDE** verificado contra el DOF; **AMARILLO** fuente oficial con verificación parcial
o con una limitación documentada; **ROJO** no verificado.

## Contenido

| # | Sección | Estatus |
| --- | --- | --- |
| 1 | [Fuente principal: el DOF a través del SIDOF](#1-fuente-principal-el-dof-a-través-del-sidof) | VERDE |
| 2 | [Tipo de cambio FIX](#2-tipo-de-cambio-fix) | AMARILLO: ligado al DOF; cotejo por muestra antes de 2025 |
| 3 | [TIIE a 28, 91 y 182 días](#3-tiie-a-28-91-y-182-días) | AMARILLO: ligado al DOF; cotejo por muestra antes de 2025 |
| 4 | [TIIE de fondeo](#4-tiie-de-fondeo) | AMARILLO: ligado al DOF; cotejo por muestra antes de 2025 |
| 5 | [Errores y anomalías encontrados en las fuentes](#5-errores-y-anomalías-encontrados-en-las-fuentes) | VERDE: todos resueltos con la nota del DOF |
| 6 | [UDIS](#6-udis) | VERDE: 91% cotejado contra las tablas del DOF |
| 7 | [INPC](#7-inpc) | VERDE desde agosto de 2018; AMARILLO de 2003 a julio de 2018 (datos abiertos del INEGI, no el DOF) |
| 8 | [Inflación mensual y anual](#8-inflación-mensual-y-anual) | VERDE |
| 9 | [Salario mínimo general y Zona Libre de la Frontera Norte](#9-salario-mínimo-general-y-zona-libre-de-la-frontera-norte) | VERDE |
| 10 | [Áreas geográficas A, B y C (1993 a 2015)](#10-áreas-geográficas-a-b-y-c-1993-a-2015) | VERDE |
| 11 | [UMA](#11-uma) | VERDE |
| 12 | [Fuentes con token que no se usan](#fuentes-con-token-que-no-se-usan) | VERDE |
| 13 | [Actualización automática](#actualización-automática) | VERDE |
| 14 | [Lo que no se pudo verificar](#lo-que-no-se-pudo-verificar) | AMARILLO |

## 1. Fuente principal: el DOF a través del SIDOF

El Sistema de Información del Diario Oficial de la Federación (SIDOF), de la Secretaría de
Gobernación, expone una API JSON pública, sin cuenta ni token, que usan el sitio del DOF y sus
aplicaciones. La documentación verificada está en el proyecto hermano
[mcp-dof](https://github.com/BEG-lag/mcp-dof) (`docs/api.md`). Este proyecto usa tres rutas:

| Ruta | Para qué |
| --- | --- |
| `GET /dof/sidof/indicadores/{código}/{DD-MM-AAAA}/{DD-MM-AAAA}` | Valores de un indicador en un rango: 158 FIX, 159 UDIS, 165 TIIE 28, 166 TIIE 91, 174 TIIE 182, 175 TIIE de fondeo. |
| `GET /dof/sidof/notas/{DD-MM-AAAA}` | Sumario del día: las notas del Banco de México, del INEGI y de la CONASAMI con su `codNota`. |
| `GET /dof/sidof/notas/nota/{codNota}` | Texto completo (HTML) de una nota, del que se lee el valor impreso. |

Particularidades que el código maneja: `Accept: application/json` solo devuelve HTTP 406 (se envía
`application/json, */*;q=0.8`); una fecha inválida devuelve 500 (las fechas se construyen como
objetos `date`); un día sin edición devuelve 200 con listas vacías; un rango de indicador sin
valores devuelve 404 con cuerpo JSON (se trata como "sin valores"); los valores son texto, a veces
con espacios, signo de porcentaje o punto final.

**Cortesía.** Peticiones secuenciales con pausa (1 s en las corridas programadas), `User-Agent`
descriptivo (`indicadores-mx/1.0.0 (+https://github.com/BEG-lag/indicadores-mx)`), reintentos con
espera exponencial ante 429 y 5xx, y caché en disco para la carga histórica.

**Qué significa "verificado".** Un valor tiene `checked: true` cuando su número se comparó con el
número impreso en el texto de la nota del DOF que lo publicó y coincidió. Un valor con nota pero sin
`checked` está ligado a su nota (fecha y `codNota` del DOF), pero su número viene del SIDOF sin
haberse cotejado uno por uno; el SIDOF es el sistema oficial de la Secretaría de Gobernación que
publica el DOF.

## 2. Tipo de cambio FIX

**Qué es.** El "tipo de cambio para solventar obligaciones denominadas en moneda extranjera
pagaderas en la República Mexicana" que determina el Banco de México (Ley Monetaria, art. 8o.;
Ley del Banco de México, art. 35; Circular 3/2012, Título Tercero, Capítulo V) y publica en el DOF.

**Fecha.** El indicador 158 del SIDOF fecha cada valor por el día en que sirve para solventar
obligaciones, que normalmente es el de su publicación en el DOF; la nota dice que se determinó el
día hábil bancario anterior. Se respeta esa fecha. La serie SF43718 del SIE del Banco de México
está fechada por el día de determinación, un día hábil antes. Cuando un día hábil bancario no hubo
edición del DOF (por ejemplo el 5 de mayo de 2025 y de 2026), su valor salió en la edición
siguiente junto con el del día: esa edición trae dos notas y cada una se asigna a su fecha por el
valor que imprime (14 casos desde 1993).

**Cobertura.** Del 13 de noviembre de 1991 al 17 de noviembre de 2026, 8,793 valores. Del 13 de
noviembre de 1991 al 31 de diciembre de 1992 el sumario del SIDOF no tiene notas del Banco de
México: esos 280 valores vienen solo del registro de indicadores del SIDOF, que los expresa en
pesos actuales (1 peso = 1,000 pesos de 1992; el DOF de entonces los imprimía en pesos viejos).
**[SUPUESTO]**: que el SIDOF los dividió entre 1,000; el primer FIX de 1991 es 3.0735 y el tipo de
cambio de la época rondaba los 3,070 pesos viejos por dólar.

**Verificación.** 8,471 valores están ligados a su nota; 1,536 se cotejaron con el número impreso:
todos los de 1993 a 1995, la primera publicación de cada mes y todos desde el 1 de enero de 2025.
Fuera de los casos de la sección 5, todos coinciden.

Estatus: **AMARILLO** (verificación por muestra antes de 2025; diferencias de fecha en 1993).

## 3. TIIE a 28, 91 y 182 días

**Qué es.** La Tasa de Interés Interbancaria de Equilibrio que determina el Banco de México con
cotizaciones de los bancos (Circular 3/2012, Título Tercero, Capítulo IV). Desde 2008 una sola nota
diaria, "Tasas de interés interbancarias de equilibrio", trae los plazos vigentes; antes hubo una
nota por plazo.

| Serie | Desde | Valores | Ligados a su nota | Cotejados | Tomados de la nota del DOF |
| --- | --- | ---: | ---: | ---: | ---: |
| `tiie-28` | 1995-03-23 | 7,743 | 7,729 | 2,701 | 2,020 |
| `tiie-91` | 1997-01-16 | 5,200 | 5,187 | 676 | 34 |
| `tiie-182` | 2011-04-07 | 1,375 | 1,372 | 513 | 14 |

- **TIIE 28 de 1995 a 2003.** El indicador 165 del SIDOF empieza el 2 de enero de 2004, pero el
  DOF publica la TIIE desde el 23 de marzo de 1995. Esos 2,020 valores se leyeron del texto de cada
  nota (`origin: "dof"`). En 1995 la publicación era semanal.
- **Semanales.** La TIIE a 91 días se publicó cada semana hasta mediados de 2008 y la de 182 días
  hasta 2023; la serie solo tiene los días con publicación.
- **Plazos ajustados.** Cuando el vencimiento cae en día inhábil el Banco de México publica, por
  ejemplo, la TIIE "a plazo de 29 días" en lugar de 28. El SIDOF guarda esos valores en otros
  indicadores (176 a 183, solo desde 2021) y deja un hueco en el de 28 días. Aquí se toman de la
  nota y se marcan con `term_days`: 118 valores de la serie de 28 días (26, 27 y 29 días), 44 de la
  de 91 (89, 90 y 92) y 9 de la de 182 (180, 181 y 183).

Estatus: **AMARILLO** (verificación por muestra antes de 2025).

## 4. TIIE de fondeo

"Tasa de interés interbancaria de equilibrio de fondeo a un día hábil bancario", indicador 175 del
SIDOF, desde el 20 de enero de 2020: 1,718 valores, todos ligados a su nota, 533 cotejados; cuatro
días que faltaban en el SIDOF se tomaron de la nota.

Estatus: **AMARILLO** (verificación por muestra antes de 2025).

## 5. Errores y anomalías encontrados en las fuentes

Cada caso se resolvió leyendo la nota del DOF y, cuando existe, la nota que la corrigió. El dato
afectado lleva un `remark` que lo explica y, si hubo corrección publicada, la nota en `correction`.

**Correcciones publicadas en el DOF** (se usa el valor corregido y se conservan las dos notas):

| Serie y día | Publicado | Corregido | Corrección |
| --- | --- | --- | --- |
| FIX 1995-08-01 | N$6.1146 (nota 4878783) | N$6.1142 | Aclaración del Banco de México, DOF 02-08-1995, nota 4878907 |
| UDI 2005-12-22 | 3.621552 (nota 2101636) | 3.631552 | Fe de errata, DOF 13-12-2005, nota 2101984 |
| INPC agosto de 2018 | 100.942, variación 4.90% (nota 5537424) | 100.492, 0.58% | Nota aclaratoria del INEGI, DOF 11-09-2018, nota 5537585 (hallazgo de aumento-renta) |
| TIIE 28 2024-02-21 | 11.9425% (nota 5717569) | 11.4925% | Nota aclaratoria, DOF 23-02-2024, nota 5717861 |
| Salario mínimo 2016 | "será de $" sin monto (nota 5420678) | $73.04 | Nota aclaratoria de la CONASAMI, DOF 18-12-2015, nota 5420747 |

En los tres primeros y en el de 2024 el SIDOF ya tenía el valor correcto; el cotejo con la nota
original lo marcaba como diferencia hasta leer la corrección.

**Errores del SIDOF resueltos con la nota del DOF:**

| Serie y día | El SIDOF devolvió | La nota del DOF dice |
| --- | --- | --- |
| FIX 2004-09-06 | 11.5193 y 11.5279 | 11.5279 |
| TIIE 28 2004-09-06 | 7.55% y 7.65% | 7.5500 |
| TIIE 182 2024-09-12 | 11.2014% y 11.2858% | 11.2014 |
| TIIE 182 2026-02-20 | 7.0000% y 7.3646% | 7.3646 |
| TIIE 91 2002-05-02 | 7.12% | 6.8500 (ninguna nota publica 7.12) |
| UDI 2006-04-25, 2006-11-14, 2009-11-25, 2010-04-26, 2012-08-15 | dos valores por día (por ejemplo 3.688459 y 117.419) | uno de ellos (hallazgo de aumento-renta) |
| UDI 2004-07-25, 2007-02-25, 2012-07-15 | sin valor | el de la tabla de su nota |
| FIX: 9 días; TIIE 28, 91, 182 y de fondeo: días sin valor dentro de periodos diarios | sin valor | el de la nota |

**Notas mal archivadas en el sumario del SIDOF:** el 1 de marzo de 2016 lista notas del FIX y de la
TIIE firmadas el 28 de febrero de 2017; el 2 y el 7 de febrero de 2000 listan notas de 2001; en 1993
y 1994 tres notas del FIX están firmadas días después de la fecha en que aparecen. Esos valores no
se ligan a esas notas (se detecta comparando la fecha de firma con la de publicación).

**Diferencias de fecha antes de 1996.** En 10 días de 1993 el valor del SIDOF no coincide con el de
la nota del DOF de la misma fecha (por ejemplo, el 1 de octubre de 1993 el SIDOF registra 3.1179 y
la nota, firmada ese mismo día, imprime 3.1163, el valor que el SIDOF pone el 4 de octubre). En esos
años las notas a veces se firmaban el día de su publicación y a veces el día anterior. Se conserva
el valor del SIDOF sin ligarlo a la nota y se documenta la diferencia en `remark`.
**[BRECHA DE DATO]**: cuál fecha es la correcta para esos días requiere el SIE del Banco de México.

**Otras particularidades.** Valores con espacios, signo de porcentaje, punto final o texto
sobrante ("7. 8425%", "4.8850 %", "11.5498%.", "7.0272%7"); notas que imprimen el número partido
("$13. 212 5", "11.6 394 por ciento"), con coma decimal ("N$ 3,1170") o en tres redacciones
distintas para la TIIE; el título "ÍÍndice nacional de precios al consumidor." (sic) del 10 de
enero de 2019; y fe de erratas que solo corrigen el monto en letra (FIX del 21-09-1993 y del
19-04-1994) o firmas y fechas (TIIE de 2001, 2004 y 2010), que no cambian ningún valor. La
aclaración del 07-12-1998 y la nota aclaratoria del 29-12-2011 de la CONASAMI corrigen salarios
profesionales, no los generales.

## 6. UDIS

**Qué es.** El valor en pesos de la Unidad de Inversión para cada día natural. El Banco de México
lo da a conocer en el DOF en dos publicaciones por mes: alrededor del día 10 (días 11 a 25) y del 25
(días 26 al 10 del mes siguiente), conforme al artículo tercero del Decreto que establece las
obligaciones que podrán denominarse en unidades de inversión (DOF 01-04-1995) y al art. 20 Ter del
CFF. El primer valor, 1.000000, corresponde al 4 de abril de 1995.

**Cómo se obtuvo.** Indicador 159 del SIDOF, año por año, y cada nota "Valor de la unidad de
inversión" del Banco de México encontrada en los sumarios del DOF; cada valor queda ligado a la nota
de su periodo.

**Verificación.** De 11,559 valores (del 4 de abril de 1995 al 25 de noviembre de 2026), 10,491
están en una tabla legible de 736 notas del Banco de México y se cotejaron todos: coinciden, salvo
los casos de la sección 5. Los demás pertenecen a 22 notas cuyo texto en el SIDOF está vacío o no
trae la tabla como texto, o a los primeros días de abril de 1995. Comprobaciones adicionales: no
hay huecos en el calendario y ningún salto diario pasa de 1% (el máximo real fue 0.33% en abril de
1995). Los 11,559 valores coinciden uno por uno con los de aumento-renta, construidos por separado.

Estatus: **VERDE**.

## 7. INPC

**Qué es.** El Índice Nacional de Precios al Consumidor, que elabora el INEGI (Ley del SNIEG, art.
59, fr. III, inciso a) y publica en el DOF "dentro de los primeros diez días del mes siguiente al
que corresponda" (CFF, art. 20). Base vigente: segunda quincena de julio de 2018 = 100 (cambio de
base publicado en el DOF del 24 de agosto de 2018).

| Periodo | Fuente | Cómo se obtuvo |
| --- | --- | --- |
| agosto de 2018 en adelante | Nota mensual del INEGI en el DOF | Se busca la nota "Índice nacional de precios al consumidor." entre los días 6 y 15 del mes siguiente (primero el 10) y se lee el índice del texto. |
| enero de 2003 a julio de 2018 | INEGI, datos abiertos del INPC mensual | `inpc_indicador_mensual_csv.zip`, concepto "Precios al Consumidor (INPC)": la serie reexpresada en base 2018, con hasta 12 decimales. |

**Verificación.** Los 72 meses en que coinciden las dos fuentes (agosto de 2018 a julio de 2024)
son idénticos. Cada nota del DOF también imprime el índice del mes anterior y la variación mensual;
ambos se cotejan en cada actualización. Así se detectó la errata de agosto de 2018 (sección 5).
Los 286 meses coinciden valor por valor con los de aumento-renta, construidos por separado.
El archivo de datos abiertos del INEGI dice en su diccionario que `VALOR` es una variación, pero su
columna `UNIDAD_MEDIDA` dice "Índice" y los valores son índices; el código falla si la unidad
cambia. Los meses anteriores a agosto de 2018 son la serie reexpresada por el INEGI (hasta 12
decimales); el DOF de la época los publicó en otras bases.

Estatus: **VERDE** desde agosto de 2018; **AMARILLO** de 2003 a julio de 2018.

## 8. Inflación mensual y anual

Se calculan aquí a partir del INPC: mensual = (INPC del mes / INPC del mes anterior - 1) x 100;
anual = (INPC del mes / INPC del mismo mes del año anterior - 1) x 100; dos decimales, redondeo
mitad hacia arriba (lejos de cero). Con índices de 3 decimales es el mismo cálculo que imprime el
INEGI: la inflación mensual se cotejó con la variación impresa en cada nota del DOF desde agosto de
2018 y coincide en todos los meses (98 meses). Comprobación de plausibilidad: la
inflación anual de diciembre de 2024 da 4.21%, la cifra que reportó el INEGI.

Para los meses anteriores a agosto de 2018 el cálculo usa los índices reexpresados (12 decimales);
la cifra puede diferir en el último decimal de la que el INEGI o el Banco de México publicaron en
su momento con la base anterior. **[ESTIMADO]**

## 9. Salario mínimo general y Zona Libre de la Frontera Norte

**Qué es.** El salario mínimo general diario que fija el H. Consejo de Representantes de la Comisión
Nacional de los Salarios Mínimos (Constitución, art. 123, apartado A, fr. VI; LFT, arts. 90, 94 y
570) y publica en el DOF, normalmente en diciembre, para regir desde el 1 de enero. Desde el 1 de
octubre de 2015 hay un solo salario mínimo general para el país; desde el 1 de enero de 2019 hay dos
zonas: la Zona Libre de la Frontera Norte (ZLFN) y el resto del país (la serie
`salario-minimo-general`).

**Cómo se obtuvo.** Cada resolución se localizó en los sumarios del DOF (emisor "COMISION NACIONAL
DE LOS SALARIOS MINIMOS", títulos "...que fija..." o "...que revisa..."), se leyó su texto completo
y el valor se cotejó con el número impreso. Para las resoluciones desde 2019 el lector automático
(`dof.parse_minimum_wage`) entiende las cuatro redacciones que ha usado la CONASAMI; el flujo anual
lo usa y pide revisión humana.

| Desde | General | ZLFN | Nota del DOF |
| --- | ---: | ---: | --- |
| 2015-10-01 | 70.10 |  | [30-09-2015, nota 5409968](https://dof.gob.mx/nota_detalle.php?codigo=5409968&fecha=30/09/2015) |
| 2016-01-01 | 73.04 |  | [18-12-2015, nota 5420678](https://dof.gob.mx/nota_detalle.php?codigo=5420678&fecha=18/12/2015) |
| 2017-01-01 | 80.04 |  | [19-12-2016, nota 5466000](https://dof.gob.mx/nota_detalle.php?codigo=5466000&fecha=19/12/2016) |
| 2017-12-01 | 88.36 |  | [24-11-2017, nota 5505642](https://dof.gob.mx/nota_detalle.php?codigo=5505642&fecha=24/11/2017) |
| 2018-01-01 | 88.36 |  | [21-12-2017, nota 5508586](https://dof.gob.mx/nota_detalle.php?codigo=5508586&fecha=21/12/2017) |
| 2019-01-01 | 102.68 | 176.72 | [26-12-2018, nota 5547224](https://dof.gob.mx/nota_detalle.php?codigo=5547224&fecha=26/12/2018) |
| 2020-01-01 | 123.22 | 185.56 | [23-12-2019, nota 5582641](https://dof.gob.mx/nota_detalle.php?codigo=5582641&fecha=23/12/2019) |
| 2021-01-01 | 141.70 | 213.39 | [23-12-2020, nota 5608587](https://dof.gob.mx/nota_detalle.php?codigo=5608587&fecha=23/12/2020) |
| 2022-01-01 | 172.87 | 260.34 | [08-12-2021, nota 5637615](https://dof.gob.mx/nota_detalle.php?codigo=5637615&fecha=08/12/2021) |
| 2023-01-01 | 207.44 | 312.41 | [07-12-2022, nota 5673550](https://dof.gob.mx/nota_detalle.php?codigo=5673550&fecha=07/12/2022) |
| 2024-01-01 | 248.93 | 374.89 | [12-12-2023, nota 5711066](https://dof.gob.mx/nota_detalle.php?codigo=5711066&fecha=12/12/2023) |
| 2025-01-01 | 278.80 | 419.88 | [19-12-2024, nota 5745678](https://dof.gob.mx/nota_detalle.php?codigo=5745678&fecha=19/12/2024) |
| 2026-01-01 | 315.04 | 440.87 | [09-12-2025, nota 5775534](https://dof.gob.mx/nota_detalle.php?codigo=5775534&fecha=09/12/2025) |

Observaciones:

- **2016: la resolución publicada omitió el monto.** La resolución del 18 de diciembre de 2015
  (nota 5420678) dice en su segundo resolutivo "será de $" sin cifra. Una nota aclaratoria del
  mismo día (nota 5420747) lo corrige: "Debe decir: ... será de $73.04". El dato lleva las dos
  notas (`dof` y `correction`).
- **Diciembre de 2017.** Una revisión publicada el 24 de noviembre de 2017 (nota 5505642) adelantó
  al 1 de diciembre de 2017 el monto de $88.36; la fijación para 2018 (21 de diciembre de 2017,
  nota 5508586) lo confirmó. La serie tiene ambos valores, cada uno con su nota.
- La nota aclaratoria del 30 de diciembre de 2019 (nota 5583109) solo corrige el párrafo de firmas
  de la resolución para 2020; no toca los montos.

Estatus: **VERDE**.

## 10. Áreas geográficas A, B y C (1993 a 2015)

Antes del 1 de octubre de 2015 el salario mínimo general variaba por área geográfica. El área A
incluía al Distrito Federal, por lo que su salario es el "salario mínimo general vigente en el
Distrito Federal" que citaban muchas leyes y contratos antes de la desindexación de 2016. El 27 de
noviembre de 2012 el área C se integró al área B, y el 1 de octubre de 2015 las áreas A y B se
unificaron.

Las tres series (`salario-minimo-area-a`, `-area-b`, `-area-c`) se leyeron del resolutivo segundo
de cada resolución de la CONASAMI desde la que rigió el 1 de enero de 1993 (la primera en nuevos
pesos) y cada valor se cotejó con el texto de su nota. Incluyen las revisiones a mitad de año de
abril de 1995, diciembre de 1995, abril de 1996, diciembre de 1996, diciembre de 1998, noviembre de
2012 y abril de 2015. La resolución para 1993 imprime los montos en pesos de entonces y en nuevos
pesos ("$ 14,270 14.27"); se usan los nuevos pesos, la unidad actual.

| Desde | Área A | Área B | Área C | Nota del DOF |
| --- | ---: | ---: | ---: | --- |
| 1993-01-01 | 14.27 | 13.26 | 12.05 | [07-12-1992, nota 4702110](https://dof.gob.mx/nota_detalle.php?codigo=4702110&fecha=07/12/1992) |
| 1994-01-01 | 15.27 | 14.19 | 12.89 | [13-12-1993, nota 4812691](https://dof.gob.mx/nota_detalle.php?codigo=4812691&fecha=13/12/1993) |
| 1995-01-01 | 16.34 | 15.18 | 13.79 | [21-12-1994, nota 4779444](https://dof.gob.mx/nota_detalle.php?codigo=4779444&fecha=21/12/1994) |
| 1995-04-01 | 18.30 | 17.00 | 15.44 | [31-03-1995, nota 4871665](https://dof.gob.mx/nota_detalle.php?codigo=4871665&fecha=31/03/1995) |
| 1995-12-04 | 20.15 | 18.70 | 17.00 | [02-12-1995, nota 4885524](https://dof.gob.mx/nota_detalle.php?codigo=4885524&fecha=02/12/1995) |
| 1996-01-01 | 20.15 | 18.70 | 17.00 | [02-12-1995, nota 4885526](https://dof.gob.mx/nota_detalle.php?codigo=4885526&fecha=02/12/1995) |
| 1996-04-01 | 22.60 | 20.95 | 19.05 | [28-03-1996, nota 4877526](https://dof.gob.mx/nota_detalle.php?codigo=4877526&fecha=28/03/1996) |
| 1996-12-03 | 26.45 | 24.50 | 22.50 | [02-12-1996, nota 4906226](https://dof.gob.mx/nota_detalle.php?codigo=4906226&fecha=02/12/1996) |
| 1997-01-01 | 26.45 | 24.50 | 22.50 | [02-12-1996, nota 4906227](https://dof.gob.mx/nota_detalle.php?codigo=4906227&fecha=02/12/1996) |
| 1998-01-01 | 30.20 | 28.00 | 26.05 | [23-12-1997, nota 4904613](https://dof.gob.mx/nota_detalle.php?codigo=4904613&fecha=23/12/1997) |
| 1998-12-03 | 34.45 | 31.90 | 29.70 | [02-12-1998, nota 4901353](https://dof.gob.mx/nota_detalle.php?codigo=4901353&fecha=02/12/1998) |
| 1999-01-01 | 34.45 | 31.90 | 29.70 | [02-12-1998, nota 4901380](https://dof.gob.mx/nota_detalle.php?codigo=4901380&fecha=02/12/1998) |
| 2000-01-01 | 37.90 | 35.10 | 32.70 | [31-12-1999, nota 4958949](https://dof.gob.mx/nota_detalle.php?codigo=4958949&fecha=31/12/1999) |
| 2001-01-01 | 40.35 | 37.95 | 35.85 | [27-12-2000, nota 2065085](https://dof.gob.mx/nota_detalle.php?codigo=2065085&fecha=27/12/2000) |
| 2002-01-01 | 42.15 | 40.10 | 38.30 | [29-12-2001, nota 757736](https://dof.gob.mx/nota_detalle.php?codigo=757736&fecha=29/12/2001) |
| 2003-01-01 | 43.65 | 41.85 | 40.30 | [26-12-2002, nota 716613](https://dof.gob.mx/nota_detalle.php?codigo=716613&fecha=26/12/2002) |
| 2004-01-01 | 45.24 | 43.73 | 42.11 | [23-12-2003, nota 710844](https://dof.gob.mx/nota_detalle.php?codigo=710844&fecha=23/12/2003) |
| 2005-01-01 | 46.80 | 45.35 | 44.05 | [22-12-2004, nota 754585](https://dof.gob.mx/nota_detalle.php?codigo=754585&fecha=22/12/2004) |
| 2006-01-01 | 48.67 | 47.16 | 45.81 | [26-12-2005, nota 2103201](https://dof.gob.mx/nota_detalle.php?codigo=2103201&fecha=26/12/2005) |
| 2007-01-01 | 50.57 | 49.00 | 47.60 | [29-12-2006, nota 4941892](https://dof.gob.mx/nota_detalle.php?codigo=4941892&fecha=29/12/2006) |
| 2008-01-01 | 52.59 | 50.96 | 49.50 | [27-12-2007, nota 5011545](https://dof.gob.mx/nota_detalle.php?codigo=5011545&fecha=27/12/2007) |
| 2009-01-01 | 54.80 | 53.26 | 51.95 | [23-12-2008, nota 5075377](https://dof.gob.mx/nota_detalle.php?codigo=5075377&fecha=23/12/2008) |
| 2010-01-01 | 57.46 | 55.84 | 54.47 | [23-12-2009, nota 5126139](https://dof.gob.mx/nota_detalle.php?codigo=5126139&fecha=23/12/2009) |
| 2011-01-01 | 59.82 | 58.13 | 56.70 | [23-12-2010, nota 5172213](https://dof.gob.mx/nota_detalle.php?codigo=5172213&fecha=23/12/2010) |
| 2012-01-01 | 62.33 | 60.57 | 59.08 | [19-12-2011, nota 5225150](https://dof.gob.mx/nota_detalle.php?codigo=5225150&fecha=19/12/2011) |
| 2012-11-27 | 62.33 | 59.08 |  | [26-11-2012, nota 5279120](https://dof.gob.mx/nota_detalle.php?codigo=5279120&fecha=26/11/2012) |
| 2013-01-01 | 64.76 | 61.38 |  | [21-12-2012, nota 5283125](https://dof.gob.mx/nota_detalle.php?codigo=5283125&fecha=21/12/2012) |
| 2014-01-01 | 67.29 | 63.77 |  | [26-12-2013, nota 5328055](https://dof.gob.mx/nota_detalle.php?codigo=5328055&fecha=26/12/2013) |
| 2015-01-01 | 70.10 | 66.45 |  | [29-12-2014, nota 5377576](https://dof.gob.mx/nota_detalle.php?codigo=5377576&fecha=29/12/2014) |
| 2015-04-01 | 70.10 | 68.28 |  | [30-03-2015, nota 5387196](https://dof.gob.mx/nota_detalle.php?codigo=5387196&fecha=30/03/2015) |

- La nota aclaratoria del 29 de diciembre de 2011 (nota 5227337) corrige salarios profesionales
  (ocupaciones 41 a 50), no los generales.
- No se incluyen valores anteriores a 1993 (pesos de antes de la redenominación).
  **[BRECHA DE DATO]**

Estatus: **VERDE**.

## 11. UMA

**Qué es.** La Unidad de Medida y Actualización, que sustituyó al salario mínimo como unidad de
cuenta en las leyes (Constitución, art. 26, apartado B, reformado por el Decreto de desindexación
del salario mínimo, DOF 27-01-2016). El INEGI publica en el DOF "dentro de los primeros diez días
del mes de enero de cada año el valor diario, mensual y anual" y esos valores "entrarán en vigor
... el 1o. de febrero de dicho año" (Ley para Determinar el Valor de la UMA, art. 5, DOF
30-12-2016; texto cotejado en la nota 5468187). El mensual es el diario por 30.4 y el anual, el
mensual por 12 (art. 4); una prueba lo comprueba para cada año.

| Rige desde | Diaria | Mensual | Anual | Nota del DOF |
| --- | ---: | ---: | ---: | --- |
| 2016-01-28 | 73.04 | 2220.42 | 26645.04 | [28-01-2016, nota 5423819](https://dof.gob.mx/nota_detalle.php?codigo=5423819&fecha=28/01/2016) |
| 2017-02-01 | 75.49 | 2294.90 | 27538.80 | [10-01-2017, nota 5468844](https://dof.gob.mx/nota_detalle.php?codigo=5468844&fecha=10/01/2017) |
| 2018-02-01 | 80.60 | 2450.24 | 29402.88 | [10-01-2018, nota 5510380](https://dof.gob.mx/nota_detalle.php?codigo=5510380&fecha=10/01/2018) |
| 2019-02-01 | 84.49 | 2568.50 | 30822.00 | [10-01-2019, nota 5547867](https://dof.gob.mx/nota_detalle.php?codigo=5547867&fecha=10/01/2019) |
| 2020-02-01 | 86.88 | 2641.15 | 31693.80 | [10-01-2020, nota 5583733](https://dof.gob.mx/nota_detalle.php?codigo=5583733&fecha=10/01/2020) |
| 2021-02-01 | 89.62 | 2724.45 | 32693.40 | [08-01-2021, nota 5609633](https://dof.gob.mx/nota_detalle.php?codigo=5609633&fecha=08/01/2021) |
| 2022-02-01 | 96.22 | 2925.09 | 35101.08 | [10-01-2022, nota 5640427](https://dof.gob.mx/nota_detalle.php?codigo=5640427&fecha=10/01/2022) |
| 2023-02-01 | 103.74 | 3153.70 | 37844.40 | [10-01-2023, nota 5676670](https://dof.gob.mx/nota_detalle.php?codigo=5676670&fecha=10/01/2023) |
| 2024-02-01 | 108.57 | 3300.53 | 39606.36 | [10-01-2024, nota 5714085](https://dof.gob.mx/nota_detalle.php?codigo=5714085&fecha=10/01/2024) |
| 2025-02-01 | 113.14 | 3439.46 | 41273.52 | [10-01-2025, nota 5746930](https://dof.gob.mx/nota_detalle.php?codigo=5746930&fecha=10/01/2025) |
| 2026-02-01 | 117.31 | 3566.22 | 42794.64 | [09-01-2026, nota 5778072](https://dof.gob.mx/nota_detalle.php?codigo=5778072&fecha=09/01/2026) |

- **2016.** El valor inicial es el salario mínimo general vigente al entrar en vigor el Decreto de
  desindexación (artículo segundo transitorio); el Decreto entró en vigor "el día siguiente al de
  su publicación" (artículo primero transitorio), es decir, el 28 de enero de 2016, y la nota del
  INEGI de ese día publica los tres valores "en el año 2016" sin otra fecha de inicio. La serie lo
  fecha el 28 de enero de 2016. **[SUPUESTO]**: que rigió desde ese día y no desde el 1 de enero.

Estatus: **VERDE**.

## Fuentes con token que no se usan

- **Banco de México, API del SIE** (series del FIX, TIIE, UDIS, INPC): requiere el encabezado
  `Bmx-Token`, que se obtiene registrándose.
- **INEGI, API del Banco de Información Económica (BIE)**: requiere un token; sin él responde
  `ErrorCode:100`.

No se crearon cuentas. Si en el futuro conviene una tercera verificación (por ejemplo, el FIX del
SIE fechado por día de determinación), bastaría guardar el token como secreto del repositorio.

## Actualización automática

| Flujo | Horario (Ciudad de México, UTC-6 todo el año desde 2022) | Series |
| --- | --- | --- |
| `update.yml` | 08:25 y 14:25, lunes a viernes | FIX, TIIE 28, 91 y 182, TIIE de fondeo, UDIS |
| `update.yml` | 09:40, días 7 a 14 de cada mes | INPC e inflación |
| `annual.yml` | 28 de diciembre y 12 de enero, 09:00, con revisión humana | Salario mínimo y UMA |

`indicadores-mx update` relee los últimos 10 días: valores del SIDOF, sumarios del DOF y el texto de
cada nota nueva. Cada valor nuevo se compara con el número impreso en su nota. Si algo no cuadra
(valor distinto, valor publicado que cambió, hueco en las UDIS, variación del INPC que no coincide)
la corrida falla con código 1, no escribe nada y GitHub avisa al dueño del repositorio. Si todo
cuadra y algo cambió, las pruebas validan cada archivo contra los esquemas, se hace commit como
`github-actions[bot]` y se vuelve a publicar la API.

El flujo anual lee la nueva resolución de la CONASAMI o la nota de la UMA del INEGI, propone los
valores en un reporte y espera a que una persona apruebe el entorno `annual-review` de GitHub
(configurado con revisores obligatorios) antes de hacer commit.

## Lo que no se pudo verificar

- **FIX y TIIE no cotejados uno por uno antes de 2025** (salvo 1993 a 1995 y la primera
  publicación de cada mes): están ligados a su nota, pero su número viene del SIDOF. Cotejarlos
  todos requiere leer unas 6,000 notas más; el código lo hace con `indicadores-mx backfill
  --verify-all`.
- **Fecha correcta de 10 valores del FIX de 1993** (sección 5). **[BRECHA DE DATO]**
- **FIX de noviembre de 1991 a diciembre de 1992**: sin nota del DOF en el SIDOF; no se cotejaron.
- **INPC anterior a 2003** y anterior a agosto de 2018 en su base original: no se incluye o viene de
  la serie reexpresada del INEGI. **[BRECHA DE DATO]**
- **Salarios mínimos anteriores a 1993**: no se incluyen. **[BRECHA DE DATO]**
- **UMA de 2016**: fecha de inicio, ver sección 11. **[SUPUESTO]**
- **1,068 UDIS** sin tabla legible en su nota (sección 6): vienen del SIDOF sin cotejo.

## Créditos

- Las reglas para leer las notas del INPC y de las UDIS, la detección de la fe de erratas del INPC
  de agosto de 2018 y de los días anómalos de UDIS en el SIDOF vienen del proyecto
  [aumento-renta](https://github.com/BEG-lag/aumento-renta) (`docs/fuentes.md`), donde se
  verificaron primero; aquí se portaron a Python y se extendieron a toda la serie.
- La API del SIDOF se documentó en [mcp-dof](https://github.com/BEG-lag/mcp-dof).
- Los valores de salario mínimo y UMA de 2023 a 2026 coinciden con los que usan
  [finiquito-mx](https://github.com/BEG-lag/finiquito-mx) y
  [facturas-cfdi](https://github.com/BEG-lag/facturas-cfdi); aquí se amplió la historia y cada
  valor se cotejó con el texto de su nota.
