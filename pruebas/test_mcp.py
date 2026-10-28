from pathlib import Path
import tempfile
import unittest
from mcp import Client
from mcp_inicio.almacen import Almacen
from mcp_inicio.asistente import preguntar
from mcp_inicio.comprobar import comprobar
from mcp_inicio.servidor import crear_servidor


class Protocolo(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        contenido = self.base / 'contenido'
        contenido.mkdir()
        (contenido / 'respaldos.md').write_text('# Respaldos\nLas copias se realizan a las 03.00 UTC.\nLa retención es de siete días.\n', encoding='utf-8')
        self.almacen = Almacen(self.base)
        self.almacen.preparar()
        self.almacen.indexar(contenido)

    async def test_mcp_real_en_subproceso(self):
        resultado = await comprobar(self.base)
        self.assertTrue(resultado['conectado'])
        self.assertEqual(len(resultado['herramientas']), 5)
        self.assertIn('investigar', resultado['prompts'])

    async def test_recursos_y_prompts(self):
        async with Client(crear_servidor(self.base)) as cliente:
            identificador = self.almacen.listar()['documentos'][0]['id']
            resultado = await cliente.read_resource('inicio://documento/' + identificador)
            self.assertIn('03.00 UTC', resultado.contents[0].text)
            prompt = await cliente.get_prompt('investigar', {'pregunta': 'Cuándo se hacen respaldos'})
            self.assertIn('Cuándo', prompt.messages[0].content.text)

    async def test_herramientas_no_tienen_escritura(self):
        async with Client(crear_servidor(self.base)) as cliente:
            herramientas = (await cliente.list_tools()).tools
            self.assertTrue(all(h.annotations.read_only_hint for h in herramientas))
            self.assertFalse(any('guardar' in h.name or 'ejecutar' in h.name for h in herramientas))

    async def test_argumentos_invalidos_y_auditoria(self):
        async with Client(crear_servidor(self.base)) as cliente:
            resultado = await cliente.call_tool('leer_documento', {'identificador': '../fuera'})
            self.assertTrue(resultado.is_error)
        self.assertEqual(self.almacen.auditoria()[0]['correcta'], 0)

    async def test_modelo_utiliza_herramienta_y_cita_fuentes(self):
        identificador = self.almacen.listar()['documentos'][0]['id']
        respuestas = [
            {'content': '', 'tool_calls': [{'function': {'name': 'leer_documento', 'arguments': {'identificador': identificador}}}]},
            {'content': 'Los respaldos se realizan a las 03.00 UTC.'}
        ]
        def modelo(url, nombre, mensajes, herramientas):
            return respuestas.pop(0)
        resultado = await preguntar(self.base, 'Cuándo se hacen los respaldos', consultar=modelo)
        self.assertIn('leer_documento', resultado['herramientas'])
        self.assertEqual(resultado['fuentes'][0]['id'], identificador)
        self.assertEqual(self.almacen.estado()['notas'], 0)

    async def test_sin_evidencia_no_llama_al_modelo(self):
        def modelo(*args):
            raise AssertionError('No debería llamar al modelo')
        resultado = await preguntar(self.base, 'astronomia intergalactica', consultar=modelo)
        self.assertIsNone(resultado['modelo'])
        self.assertEqual(resultado['fuentes'], [])

    async def test_modelo_no_puede_invocar_terminal(self):
        def modelo(*args):
            return {'content': '', 'tool_calls': [{'function': {'name': 'ejecutar_terminal', 'arguments': {'comando': 'echo no'}}}]}
        with self.assertRaisesRegex(ValueError, 'no permitidos'):
            await preguntar(self.base, 'respaldos', consultar=modelo)

    async def test_limite_de_herramientas(self):
        def modelo(*args):
            return {'content': '', 'tool_calls': [{'function': {'name': 'estado_contexto', 'arguments': {}}}]}
        with self.assertRaisesRegex(ValueError, 'agotó el límite'):
            await preguntar(self.base, 'respaldos', consultar=modelo)

    async def test_modelo_no_puede_enviar_argumentos_ajenos_al_esquema(self):
        def modelo(*args):
            return {'content': '', 'tool_calls': [{'function': {'name': 'leer_documento', 'arguments': {'identificador': 123}}}]}
        with self.assertRaisesRegex(ValueError, 'no corresponden al esquema'):
            await preguntar(self.base, 'respaldos', consultar=modelo)
