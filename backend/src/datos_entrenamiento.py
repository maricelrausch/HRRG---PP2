
def crear_ejemplo(texto, entidades):
    return {
        "texto": texto,
        "entidades": [
            {"texto": valor, "etiqueta": etiqueta}
            for valor, etiqueta in entidades
        ],
    }


ejemplos = [
    crear_ejemplo(
        "Episodio 12345, masculino de 70 años.",
        [
            ("12345", "CODIGO_EPISODIO"),
            ("masculino", "SEXO"),
            ("70 años", "EDAD"),
        ],
    ),

    crear_ejemplo(
        "Femenino de 45 años, consulta por dificultad para respirar.",
        [
            ("Femenino", "SEXO"),
            ("45 años", "EDAD"),
            ("dificultad para respirar", "MOTIVO_CONSULTA"),
        ],
    ),

    crear_ejemplo(
        "Presión arterial sistólica 85, diastólica 55 y media 65.",
        [
            ("85", "TAS"),
            ("55", "TAD"),
            ("65", "PAM"),
        ],
    ),

    crear_ejemplo(
        "Pulso 120 por minuto y frecuencia respiratoria 28 por minuto.",
        [
            ("120", "FREC_CARDIACA"),
            ("28", "FREC_RESPIRATORIA"),
        ],
    ),

    crear_ejemplo(
        "Saturación de oxígeno 88 %, temperatura 39 °C.",
        [
            ("88 %", "SATURACION"),
            ("39 °C", "TEMPERATURA"),
        ],
    ),

    crear_ejemplo(
        "Glasgow 12, dolor 8/10 en el pecho.",
        [
            ("12", "GLASGOW"),
            ("8/10", "DOLOR"),
            ("pecho", "LOCALIZACION_DOLOR"),
        ],
    ),

    crear_ejemplo(
        "Paciente de 30 años con presión 120/80 y pulso de 75.",
        [
            ("30 años", "EDAD"),
            ("120", "TAS"),
            ("80", "TAD"),
            ("75", "FREC_CARDIACA"),
        ],
    ),

    crear_ejemplo(
        "Paciente masculino de 60 años con temperatura de 38.5 grados.",
        [
            ("masculino", "SEXO"),
            ("60 años", "EDAD"),
            ("38.5 grados", "TEMPERATURA"),
        ],
    ),
]

