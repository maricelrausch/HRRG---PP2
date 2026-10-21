
from datos_entrenamiento import ejemplos


def preparar_ejemplos(ejemplos):
    datos_preparados = []

    for ejemplo in ejemplos:
        texto = ejemplo["texto"]
        entidades_preparadas = []

        for entidad in ejemplo["entidades"]:
            fragmento = entidad["texto"]
            inicio = texto.find(fragmento)

            if inicio == -1:
                raise ValueError(
                    f"No se encontró '{fragmento}' en el texto."
                )

            fin = inicio + len(fragmento)

            entidades_preparadas.append({
                "inicio": inicio,
                "fin": fin,
                "etiqueta": entidad["etiqueta"]
            })

        datos_preparados.append({
            "texto": texto,
            "entidades": entidades_preparadas
        })

    return datos_preparados


if __name__ == "__main__":
    preparados = preparar_ejemplos(ejemplos)

    for ejemplo in preparados:
        print("\nTexto:", ejemplo["texto"])

        for entidad in ejemplo["entidades"]:
            print(entidad)
