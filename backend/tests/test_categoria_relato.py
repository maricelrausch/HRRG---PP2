"""
[Dario 30/10] Categoría del motivo a partir del relato (src/extraccion.py, lista única que también usa ia/medgemma.py).
MedGemma no responde siempre igual; el control por palabras clave sí. Se prueba que, con 62 relatos de los
15 motivos (incluidas negaciones y relatos con dos motivos), la categoría quede bien:
  - si MedGemma acierta, se respeta;
  - si MedGemma dice «Otro» o se equivoca, las palabras del relato la corrigen.
Caso real de la prueba del 30/10: «me cai de la escaler y me golpe la cabeza» quedaba como Cefalea.
Ejecutar desde backend:  python -m pytest -q tests/test_categoria_relato.py
"""
import pytest

import ia.medgemma as ia
from src.extraccion import CLAVES_CATEGORIA, _norm, anclar, categorias_del_relato
from src.esquemas import Categoria

CASOS = [
    ('Me duele mucho el pecho, como una presión, y estoy sudando', 'Dolor torácico'),
    ('Tengo un dolor en el pecho que se va al brazo izquierdo', 'Dolor torácico'),
    ('Siento opresión en el tórax desde hace una hora', 'Dolor torácico'),
    ('Me duele el pecho y me falta el aire', 'Dolor torácico'),
    ('Me duele la panza del lado derecho y vomité', 'Dolor abdominal'),
    ('Tengo un dolor de estómago muy fuerte', 'Dolor abdominal'),
    ('Me duele el abdomen desde anoche', 'Dolor abdominal'),
    ('Tengo un cólico que no se me pasa', 'Dolor abdominal'),
    ('Me falta el aire cuando camino', 'Disnea'),
    ('No puedo respirar bien, me ahogo', 'Disnea'),
    ('Me cuesta respirar desde la mañana', 'Disnea'),
    ('Siento falta de respiración y tos', 'Disnea'),
    ('Me cai de la escaler y me golpe la cabeza', 'Trauma'),
    ('Me caí de la escalera y me golpeé la cabeza', 'Trauma'),
    ('Choqué con la moto y me duele el brazo', 'Trauma'),
    ('Se me torció el tobillo jugando al fútbol', 'Trauma'),
    ('Me golpeé el pecho al caerme', 'Trauma'),
    ('Me quemé con agua hirviendo', 'Trauma'),
    ('Me resbalé en el baño y me duele la cadera', 'Trauma'),
    ('Tengo fiebre de 39 desde hace dos días', 'Fiebre'),
    ('Estoy afiebrado y con escalofríos', 'Fiebre'),
    ('Tengo fiebre pero no me duele la cabeza', 'Fiebre'),
    ('Tiene calentura desde ayer', 'Fiebre'),
    ('Me duele la cabeza desde ayer, es un dolor leve', 'Cefalea'),
    ('Tengo una migraña muy fuerte', 'Cefalea'),
    ('Me duele la cabeza y vomité, no tuve ningún golpe', 'Cefalea'),
    ('Tengo fiebre y me duele la cabeza', 'Cefalea'),
    ('Me siento mareado y con hormigueo en el brazo izquierdo', 'Síntoma neurológico'),
    ('Me desmayé en el trabajo', 'Síntoma neurológico'),
    ('Tiene la boca torcida y habla mal', 'Síntoma neurológico'),
    ('No puede hablar bien desde hace una hora', 'Síntoma neurológico'),
    ('Está confundido y no responde bien', 'Alteración de conciencia'),
    ('Lo encontraron desorientado en la calle', 'Alteración de conciencia'),
    ('Perdió el conocimiento y sigue muy somnoliento', 'Alteración de conciencia'),
    ('No reacciona cuando le hablan', 'Alteración de conciencia'),
    ('Tuvo una convulsión hace media hora', 'Convulsiones'),
    ('Es epiléptico y tuvo un ataque', 'Convulsiones'),
    ('Convulsionó en la casa y ahora está dormido', 'Convulsiones'),
    ('Me corté la mano con un cuchillo y sangra mucho', 'Hemorragia'),
    ('Sangro por la nariz desde hace una hora', 'Hemorragia'),
    ('Vomitó sangre esta mañana', 'Hemorragia'),
    ('Tiene una hemorragia que no para', 'Hemorragia'),
    ('Tomé muchas pastillas', 'Intoxicación'),
    ('Se tomó un frasco de pastillas', 'Intoxicación'),
    ('El nene tomó lavandina', 'Intoxicación'),
    ('Se intoxicó con el brasero', 'Intoxicación'),
    ('Me picó una abeja y se me hinchó la cara', 'Reacción alérgica'),
    ('Soy alérgico al maní y comí sin darme cuenta', 'Reacción alérgica'),
    ('Me salieron ronchas por todo el cuerpo', 'Reacción alérgica'),
    ('Se le hinchó la lengua después de un remedio', 'Reacción alérgica'),
    ('Estoy embarazada de 30 semanas y tengo contracciones', 'Embarazo / obstétrico'),
    ('Rompí bolsa hace una hora', 'Embarazo / obstétrico'),
    ('Embarazada con dolor y pérdida de líquido', 'Embarazo / obstétrico'),
    ('Escucho voces y quiero hacerme daño', 'Salud mental'),
    ('Dice que quiere matarse', 'Salud mental'),
    ('Tengo un ataque de pánico, no puedo calmarme', 'Salud mental'),
    ('Está muy angustiado y llora sin parar', 'Salud mental'),
    ('Me duele la espalda', 'Otro'),
    ('Vengo a control', 'Otro'),
    ('Tomo pastillas para la presión y me duele la rodilla', 'Otro'),
    ('Me quema al orinar', 'Otro'),
    ('Se me hinchó la rodilla', 'Otro'),
]
CON_PALABRAS = [(r, e) for r, e in CASOS if e != "Otro"]


@pytest.mark.parametrize("relato,esperado", CASOS)
def test_si_medgemma_acierta_se_respeta(relato, esperado):
    assert anclar({"motivo_categoria": esperado}, relato)["motivo_categoria"] == esperado


@pytest.mark.parametrize("relato,esperado", CASOS)
def test_si_medgemma_dice_otro_corrigen_las_palabras(relato, esperado):
    assert anclar({"motivo_categoria": "Otro"}, relato)["motivo_categoria"] == esperado


@pytest.mark.parametrize("relato,esperado", CON_PALABRAS)
@pytest.mark.parametrize("equivocada", ["Cefalea", "Trauma", "Fiebre"])
def test_si_medgemma_se_equivoca_corrigen_las_palabras(relato, esperado, equivocada):
    if equivocada in categorias_del_relato(_norm(relato)):
        pytest.skip("las dos son posibles (p. ej. «fiebre y dolor de cabeza»): se respeta lo que diga MedGemma")
    assert anclar({"motivo_categoria": equivocada}, relato)["motivo_categoria"] == esperado


def test_los_15_motivos_tienen_palabras_y_existen_en_el_esquema():
    nombres = [c for c, _ in CLAVES_CATEGORIA]
    validos = set(Categoria.__args__) if hasattr(Categoria, "__args__") else {c.value for c in Categoria}
    assert set(nombres) <= validos and len(nombres) == 14          # los 15 menos «Otro»


def test_una_sola_lista_en_los_dos_archivos():
    assert ia.CLAVES_CATEGORIA is CLAVES_CATEGORIA
    d = {"motivo_categoria": "Cefalea"}
    ia._anclar(d, "me cai y me golpe la cabeza")
    assert d["motivo_categoria"] == "Trauma"
