# Casos simulados — Triage asistido HRRG

Versión 1.3 · Fuente: `backend/datos/casos_simulados.json` (este documento es un resumen legible).

**Casos FICTICIOS.** No corresponden a personas reales; sin nombre, DNI, domicilio ni teléfono.
El color de la demo (`nivel_maqueta`) **no tiene validez clínica**. Los colores reales los define C07 con la guía oficial, citando página.

## 1. Casos de demo y validación

### Demo (maquetado v33)

| ID | Paciente | Episodio | Relato | Color en la demo | PAM |
|---|---|---|---|---|---|
| D01 | PAC-DEMO-001 | EPI-004818 | Me duele el pecho desde hace media hora, como una presión, y estoy sudando. | Naranja | 113 |
| D02 | PAC-DEMO-002 | EPI-004815 | Me duele mucho la panza, acá arriba, desde hace unas 6 horas. Tengo ganas de vomitar y me siento afiebrada. Soy diabética, tomo pastillas. | Amarillo | 97 |
| D03 | PAC-DEMO-003 | EPI-004809 | Me torcí el tobillo jugando al fútbol, me duele al apoyar. | Verde | 93 |
| D04 | PAC-DEMO-004 | EPI-004806 | Vengo a que me miren la herida de la mano, me la hicieron hace tres días. | Azul | 90 |
| D05 | PAC-DEMO-002 | EPI-004815 | Reevaluación del caso D02: empeoró. | Naranja | 97 |

### Errores técnicos (deben rechazarse)

| ID | Qué prueba | Error esperado en |
|---|---|---|
| E01 | Error de tipeo: SpO2 8 en vez de 98 | saturacion_o2 |
| E02 | TA invertida | diastólica |
| E03 | Dato personal en el motivo | dato personal |
| E04 | DNI en antecedentes | dato personal |
| E05 | Campo con nombre desconocido | presion: campo no permitido |
| E06 | Opción fuera de catálogo | motivo_categoria |
| E07 | Texto en un campo numérico | frecuencia_cardiaca |
| E08 | Código de episodio con formato inválido | codigo_episodio |

### Faltantes y compatibilidad (válidos)

| ID | Qué prueba | Faltantes esperados |
|---|---|---|
| F01 | Solo el relato, sin mediciones (etapa ingreso completa) | ta_sistolica, ta_diastolica, frecuencia_cardiaca, frecuencia_respiratoria, saturacion_o2, temperatura, dolor_intensidad |
| F02 | Campos vacíos del formulario cuentan como faltantes | dolor_localizacion, temperatura |
| F03 | Cero NO es faltante: dolor 0 es un valor real | ninguno |
| A01 | Nombres viejos (tas, saturacion, banderas_rojas, sexo 'F') se traducen | ninguno |

## 2. Casos de extracción (texto → campos que debe sacar MedGemma)

Sirven para C05/C06: se compara lo que extrae el modelo con lo esperado, campo por campo.
Regla clave: **lo que el texto no dice con un número queda vacío (null). El modelo no debe inventar valores.**

| ID | Tipo | Texto | Diagrama esperado | Resultado esperado | Nota |
|---|---|---|---|---|---|
| CF-01 | completo | Varón de 62 años con dolor opresivo en el pecho de 40 minutos de evolución, dolor 9/10. FC 112 lpm, FR 24, saturación 91 %, temperatura 36,8 °C. Alerta. Sin sangrado. | Dolor torácico | pendiente (C07) |  |
| CF-02 | completo | Mujer de 24 años, dolor de garganta desde hace 3 días, dolor 2/10. Temperatura 36,6 °C, FC 78, FR 14, saturación 99 %. Lúcida. Niega sangrado. | — | Información insuficiente | Motivo fuera de los 3 diagramas cargados: el motor debe devolver NO_CONCLUYENTE |
| CF-03 | completo | Mujer de 52 años con dolor abdominal en flanco derecho de 5 horas, dolor 8/10, con vómitos. Temperatura 37,4 °C, FC 102, FR 20, saturación 98 %. Orientada. No presenta sangrado. | Dolor abdominal en adulto | pendiente (C07) |  |
| CF-04 | completo | Varón de 30 años con fiebre y escalofríos desde hace 2 días. Temperatura 39,2 °C, FC 118, FR 22, saturación 95 %. Alerta. Refiere malestar general, sin dolor. Sin sangrado. | Malestar en adulto / fiebre | pendiente (C07) | 'sin dolor' = 0 (el texto lo afirma); a confirmar en EQ1 si se acepta 0 o null |
| CF-05 | faltantes | Mujer de 47 años que consulta por dolor torácico. Dolor 6/10. | Dolor torácico | Información insuficiente | Faltan signos vitales: no debe asignar color por defecto |
| CF-06 | faltantes | Consulta por dolor de panza desde ayer. | Dolor abdominal en adulto | Información insuficiente | 'desde ayer' no se convierte: valor y unidad en null |
| CF-07 | decimales_coma | Varón de 68 años, fiebre de 38,6 °C y tos con flema hace 4 días. FC 104 lpm, FR 24, saturación 92 %. Despierto. Niega sangrado. | Malestar en adulto / fiebre | pendiente (C07) | Prueba la coma decimal en la temperatura (38,6). La FC se registra sin decimales. |
| CF-08 | incompatible | Paciente de sesenta años con dolor abdominal intenso hace 2 horas. Temperatura 37 grados. | Dolor abdominal en adulto | Información insuficiente | Edad en letras -> 60. 'Dolor intenso' sin número -> null (no inventar 8 o 9) |
| CF-09 | incompatible | Adulto mayor con dolor en el pecho de unos minutos, refiere que es 'muy fuerte'. Saturación normal según familiar. | Dolor torácico | Información insuficiente | Trampa: 'adulto mayor', 'unos minutos', 'muy fuerte' y 'saturación normal' no tienen número -> todo null. El modelo NO debe inventar 98 % |
| CF-10 | negaciones | Mujer de 35 años con dolor abdominal 5/10 de 12 horas. Niega fiebre, niega sangrado. FC 88, FR 16, saturación 98 %, temperatura 36,7 °C. Lúcida. | Dolor abdominal en adulto | pendiente (C07) |  |
| CF-11 | conciencia_alterada | Varón de 71 años traído por familiares, malestar general desde hace 6 horas, solo responde cuando se le habla fuerte. Temperatura 38,9 °C, FC 124, FR 28, saturación 89 %. | Malestar en adulto / fiebre | pendiente (C07) |  |
| CF-12 | hemorragia | Varón de 58 años con dolor abdominal y vómitos con sangre desde hace 1 hora. Dolor 6/10. FC 120, FR 22, saturación 95 %, temperatura 36,5 °C. Alerta, se marea al pararse. | Dolor abdominal en adulto | pendiente (C07) |  |

### Casos agregados el 03/11 (CF-13 a CF-52)

Amplían la evaluación de la extracción a 52 casos: todas las categorías del esquema, niños y adultos mayores, tiempos escritos de distintas formas («una hora y media», «2 semanas», «tres días», «desde ayer»), negaciones y relatos sin números. Sus campos esperados están en la tabla de arriba.

| ID | Tipo | Texto |
|---|---|---|
| CF-13 | cefalea | Mujer de 34 años con dolor de cabeza intenso desde hace 4 horas, dolor 7/10. Temperatura 36,9 °C, FC 84, saturación 98 %. |
| CF-14 | disnea | Varón de 70 años con falta de aire desde hace 2 días, empeora al caminar. FR 28, saturación 88 %, FC 110. |
| CF-15 | trauma | Mujer de 81 años que se cayó en la cocina hace 3 horas, dolor en la cadera derecha 8/10, no puede apoyar. |
| CF-16 | pediatria | Niño de 4 años con fiebre de 39,5 °C desde hace 2 días y tos. FC 130, FR 32, saturación 96 %. |
| CF-17 | alergia | Mujer de 25 años con ronchas en todo el cuerpo y picazón desde hace 40 minutos, después de comer maní. Saturación 97 %. |
| CF-18 | convulsion | Varón de 19 años traído por amigos tras una convulsión hace media hora, ahora está somnoliento. Sin golpe en la cabeza. |
| CF-19 | hemorragia | Mujer de 45 años con sangrado nasal abundante desde hace 1 hora que no para. FC 96. |
| CF-20 | intoxicacion | Varón de 23 años que tomó muchas pastillas de clonazepam hace 2 horas, está somnoliento. FC 58, FR 12, saturación 94 %. |
| CF-21 | obstetrico | Mujer de 29 años embarazada de término, con contracciones desde hace 3 horas y pérdida de líquido. |
| CF-22 | salud_mental | Varón de 40 años que refiere una crisis de angustia desde hace 2 horas, sin ideas de hacerse daño. |
| CF-23 | neurologico | Mujer de 67 años con boca torcida y pérdida de fuerza en el brazo izquierdo desde hace 50 minutos. |
| CF-24 | conciencia | Varón de 85 años, la familia lo nota confundido y desorientado desde esta mañana. Temperatura 38,2 °C. |
| CF-25 | sin_numeros | Me duele la panza del lado derecho desde ayer a la noche y tengo ganas de vomitar. |
| CF-26 | negaciones | Varón de 55 años con dolor en el pecho de 20 minutos, niega falta de aire, niega sangrado. Dolor 7/10, FC 98, saturación 97 %. |
| CF-27 | trauma | Chico de 15 años que se golpeó la cabeza jugando al rugby hace 1 hora, tiene dolor de cabeza y vomitó una vez. |
| CF-28 | tiempo_vago | Adulta con tos y fiebre desde hace unos días, refiere escalofríos. |
| CF-29 | numeros_letras | Mujer de cuarenta años con dolor de garganta desde hace tres días y fiebre de 38 grados. |
| CF-30 | negaciones | Varón de 30 años con diarrea desde hace 2 días, sin fiebre, sin sangre en las heces. |
| CF-31 | otro | Mujer de 50 años con dolor de espalda baja desde hace 5 días, dolor 6/10, sin golpe previo. |
| CF-32 | pediatria | Nena de 6 años con dolor de oído desde hace 1 día y fiebre de 38,3 °C. |
| CF-33 | trauma | Varón de 38 años con quemadura en la mano derecha con aceite caliente hace 30 minutos, dolor 9/10. |
| CF-34 | trauma | Mujer de 27 años con un corte en el dedo con un cuchillo hace 20 minutos, sangra un poco. |
| CF-35 | disnea | Varón de 22 años con antecedente de asma, le cuesta respirar desde hace 1 hora. Saturación 91 %, FR 26. |
| CF-36 | neurologico | Mujer de 60 años con mareos y vértigo desde esta mañana, sin pérdida de conocimiento. |
| CF-37 | otro | Varón de 33 años con vómitos desde hace 8 horas, no tolera líquidos. |
| CF-38 | pediatria | Niño de 9 años al que le picó una abeja en el brazo hace 15 minutos, tiene hinchado el brazo. |
| CF-39 | tiempo_vago | Señor mayor con dolor en el pecho desde hace un rato, dice que es fuerte. |
| CF-40 | hora_y_media | Mujer de 42 años con dolor de estómago desde hace una hora y media, dolor 5/10. |
| CF-41 | semanas | Varón de 58 años con tos seca desde hace 2 semanas, sin fiebre. |
| CF-42 | negaciones | Mujer de 70 años con dolor e hinchazón en la rodilla izquierda desde hace 4 días, no recuerda golpes. |
| CF-43 | obstetrico | Mujer de 26 años embarazada, con dolor en la parte baja de la panza desde hace 6 horas. |
| CF-44 | sin_numeros | Me duele mucho la cabeza desde ayer y me molesta la luz. |
| CF-45 | trauma | Varón de 45 años que tuvo un accidente en moto hace 1 hora, dolor en la pierna derecha 8/10. FC 104. |
| CF-46 | otro | Varón de 64 años, diabético, sudoroso y tembloroso desde hace 20 minutos. |
| CF-47 | pediatria | Bebé de 8 meses con fiebre de 38,8 °C desde hace 1 día y no quiere comer. |
| CF-48 | negaciones | Mujer de 36 años con dolor de pecho leve desde hace 3 días, niega fiebre, niega falta de aire, niega golpes. |
| CF-49 | otro | Varón de 50 años con un cuerpo extraño en el ojo derecho desde hace 2 horas, mucho ardor. |
| CF-50 | intoxicacion | Familia con dolor de cabeza y mareos; usaron un brasero toda la noche. La madre, de 39 años, está somnolienta. |
| CF-51 | salud_mental | Varón de 28 años que escucha voces desde hace 3 días y no duerme. |
| CF-52 | abdominal | Mujer de 19 años con dolor abdominal en la parte baja derecha desde hace 12 horas, fiebre de 38,1 °C y vómitos. |

### Campos esperados por caso

| ID | Edad | Categoría | Evolución | FC | FR | SpO₂ | T° | Dolor | Localización | Conciencia | Sangrado |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CF-01 | 62 | Dolor torácico | 40 minutos | 112 | 24 | 91 | 36.8 | 9 | Tórax | Alerta | no |
| CF-02 | 24 | Otro | 3 días | 78 | 14 | 99 | 36.6 | 2 | Garganta | Alerta | no |
| CF-03 | 52 | Dolor abdominal | 5 horas | 102 | 20 | 98 | 37.4 | 8 | Flanco derecho | Alerta | no |
| CF-04 | 30 | Fiebre | 2 días | 118 | 22 | 95 | 39.2 | 0 |  | Alerta | no |
| CF-05 | 47 | Dolor torácico |  |  |  |  |  | 6 | Tórax |  |  |
| CF-06 |  | Dolor abdominal |  |  |  |  |  |  | Abdomen |  |  |
| CF-07 | 68 | Fiebre | 4 días | 104 | 24 | 92 | 38.6 |  |  | Alerta | no |
| CF-08 | 60 | Dolor abdominal | 2 horas |  |  |  | 37.0 |  | Abdomen |  |  |
| CF-09 |  | Dolor torácico |  |  |  |  |  |  | Tórax |  |  |
| CF-10 | 35 | Dolor abdominal | 12 horas | 88 | 16 | 98 | 36.7 | 5 | Abdomen | Alerta | no |
| CF-11 | 71 | Otro | 6 horas | 124 | 28 | 89 | 38.9 |  |  | Responde a la voz |  |
| CF-12 | 58 | Dolor abdominal | 1 horas | 120 | 22 | 95 | 36.5 | 6 | Abdomen | Alerta | sí |
| CF-13 | 34 | Cefalea | 4 horas | 84 |  | 98 | 36.9 | 7 | Cabeza |  |  |
| CF-14 | 70 | Disnea | 2 días | 110 | 28 | 88 |  |  |  |  |  |
| CF-15 | 81 | Trauma | 3 horas |  |  |  |  | 8 | Cadera derecha |  |  |
| CF-16 | 4 | Fiebre | 2 días | 130 | 32 | 96 | 39.5 |  |  |  |  |
| CF-17 | 25 | Reacción alérgica | 40 minutos |  |  | 97 |  |  |  |  |  |
| CF-18 | 19 | Convulsiones | 30 minutos |  |  |  |  |  |  |  |  |
| CF-19 | 45 | Hemorragia | 1 horas | 96 |  |  |  |  |  |  | sí |
| CF-20 | 23 | Intoxicación | 2 horas | 58 | 12 | 94 |  |  |  |  |  |
| CF-21 | 29 | Embarazo / obstétrico | 3 horas |  |  |  |  |  |  |  |  |
| CF-22 | 40 | Salud mental | 2 horas |  |  |  |  |  |  |  |  |
| CF-23 | 67 | Síntoma neurológico | 50 minutos |  |  |  |  |  |  |  |  |
| CF-24 | 85 | Alteración de conciencia |  |  |  |  | 38.2 |  |  |  |  |
| CF-25 |  | Dolor abdominal |  |  |  |  |  |  | Panza, lado derecho |  |  |
| CF-26 | 55 | Dolor torácico | 20 minutos | 98 |  | 97 |  | 7 | Tórax |  | no |
| CF-27 | 15 | Trauma | 1 horas |  |  |  |  |  | Cabeza |  |  |
| CF-28 |  | Fiebre |  |  |  |  |  |  |  |  |  |
| CF-29 | 40 | Fiebre | 3 días |  |  |  | 38 |  | Garganta |  |  |
| CF-30 | 30 | Otro | 2 días |  |  |  |  |  |  |  | no |
| CF-31 | 50 | Otro | 5 días |  |  |  |  | 6 | Espalda baja |  |  |
| CF-32 | 6 | Fiebre | 1 días |  |  |  | 38.3 |  | Oído |  |  |
| CF-33 | 38 | Trauma | 30 minutos |  |  |  |  | 9 | Mano derecha |  |  |
| CF-34 | 27 | Trauma | 20 minutos |  |  |  |  |  | Dedo |  | sí |
| CF-35 | 22 | Disnea | 1 horas |  | 26 | 91 |  |  |  |  |  |
| CF-36 | 60 | Síntoma neurológico |  |  |  |  |  |  |  |  |  |
| CF-37 | 33 | Otro | 8 horas |  |  |  |  |  |  |  |  |
| CF-38 | 9 | Reacción alérgica | 15 minutos |  |  |  |  |  | Brazo |  |  |
| CF-39 |  | Dolor torácico |  |  |  |  |  |  | Tórax |  |  |
| CF-40 | 42 | Dolor abdominal | 1.5 horas |  |  |  |  | 5 | Abdomen |  |  |
| CF-41 | 58 | Otro | 14 días |  |  |  |  |  |  |  |  |
| CF-42 | 70 | Otro | 4 días |  |  |  |  |  | Rodilla izquierda |  |  |
| CF-43 | 26 | Embarazo / obstétrico | 6 horas |  |  |  |  |  | Panza, parte baja |  |  |
| CF-44 |  | Cefalea |  |  |  |  |  |  | Cabeza |  |  |
| CF-45 | 45 | Trauma | 1 horas | 104 |  |  |  | 8 | Pierna derecha |  |  |
| CF-46 | 64 | Otro | 20 minutos |  |  |  |  |  |  |  |  |
| CF-47 | 0 | Fiebre | 1 días |  |  |  | 38.8 |  |  |  |  |
| CF-48 | 36 | Dolor torácico | 3 días |  |  |  |  |  | Tórax |  |  |
| CF-49 | 50 | Otro | 2 horas |  |  |  |  |  | Ojo derecho |  |  |
| CF-50 | 39 | Intoxicación |  |  |  |  |  |  | Cabeza |  |  |
| CF-51 | 28 | Salud mental | 3 días |  |  |  |  |  |  |  |  |
| CF-52 | 19 | Dolor abdominal | 12 horas |  |  |  | 38.1 |  | Abdomen, parte baja derecha |  |  |

Celda vacía = el texto no lo dice → debe quedar null.

## 3. Casos de API

| ID | Qué prueba | Respuesta HTTP esperada |
|---|---|---|
| API-01 | texto vacio | 422 |
| API-02 | solo espacios | 422 |

## Decisiones tomadas

- Frecuencia cardíaca y demás signos enteros **sin decimales** (13/10/2026).
- «Sin dolor» explícito = 0; dolor no mencionado = null.
- «Desde ayer», «unos minutos», «adulto mayor» no se convierten a número: quedan null.

## Pendientes

- Colores esperados con la guía oficial del HRRG (C07).
- Alinear los diagramas esperados (Dolor torácico, Dolor abdominal en adulto, Malestar/fiebre) con los que cargue Tomás en el RAG.
