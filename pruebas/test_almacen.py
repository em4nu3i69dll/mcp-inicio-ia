from pathlib import Path
import tempfile
import unittest
from mcp_inicio.almacen import Almacen


class Documentos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.contenido = self.base / 'contenido'
        self.contenido.mkdir()
        (self.contenido / 'manual.md').write_text('# Restauración\nRestaurar SQLite requiere comprobar la copia.\n', encoding='utf-8')
        self.almacen = Almacen(self.base)
        self.almacen.preparar()
        self.almacen.indexar(self.contenido)

    def test_busqueda_ignora_acentos_y_devuelve_fuentes(self):
        resultado = self.almacen.buscar('restauracion')['resultados']
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]['ruta'], 'manual.md')
        self.assertEqual(len(resultado[0]['sha256']), 64)

    def test_lectura_numerada_sin_rutas_arbitrarias(self):
        identificador = self.almacen.listar()['documentos'][0]['id']
        r = self.almacen.leer(identificador, 2, 1)
        self.assertTrue(r['contenido'].startswith('2: Restaurar'))
        for valor in ['../manual.md', '/etc/passwd', 'D-inventado']:
            with self.assertRaises(ValueError):
                self.almacen.leer(valor)

    def test_no_indexa_entornos_ni_subcarpetas_privadas(self):
        (self.contenido / '.env').write_text('TOKEN=ejemplo')
        (self.contenido / 'secretos').mkdir()
        (self.contenido / 'secretos/privado.md').write_text('oculto')
        (self.contenido / '.git').mkdir()
        (self.contenido / '.git/historia.md').write_text('oculto')
        r = self.almacen.indexar(self.contenido)
        self.assertEqual(r['indexados'], 1)

    def test_clave_privada_aborta_sin_borrar_indice(self):
        (self.contenido / 'clave.md').write_text('-----BEGIN PRIVATE KEY-----\nno es una clave real\n')
        with self.assertRaises(ValueError):
            self.almacen.indexar(self.contenido)
        self.assertEqual(self.almacen.estado()['documentos'], 1)

    def test_consultas_no_aceptan_sintaxis_fts_ni_sql(self):
        self.assertEqual(self.almacen.buscar('" OR * NEAR(')['resultados'], [])
        self.almacen.buscar("'; DROP TABLE documentos; --")
        self.assertEqual(self.almacen.estado()['documentos'], 1)

    def test_archivos_eliminados_desaparecen_al_reindexar(self):
        (self.contenido / 'manual.md').unlink()
        self.almacen.indexar(self.contenido)
        self.assertEqual(self.almacen.listar()['total'], 0)

    def test_notas_solo_por_llamada_explicita(self):
        nota = self.almacen.guardar_nota('Decisión', 'Mantener el acceso local.')
        self.assertTrue(nota['guardada'])
        self.assertEqual(self.almacen.notas()['notas'][0]['contenido'], 'Mantener el acceso local.')

    def test_auditoria_no_conserva_consultas(self):
        self.almacen.registrar('buscar_documentos', True)
        fila = self.almacen.auditoria()[0]
        self.assertEqual(set(fila), {'herramienta', 'correcta', 'fecha'})

    def test_rangos_y_limites(self):
        for funcion, args in [(self.almacen.buscar, ['a']), (self.almacen.buscar, ['SQLite', 99]), (self.almacen.listar, [-1]), (self.almacen.notas, [-1]), (self.almacen.guardar_nota, ['', 'texto'])]:
            with self.assertRaises(ValueError):
                funcion(*args)
