from contextlib import contextmanager, closing
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import uuid


def fecha():
    return datetime.now(timezone.utc).isoformat()


class Almacen:
    def __init__(self, base):
        self.base = Path(base).resolve()
        self.archivo = self.base / 'datos' / 'contexto.sqlite3'

    @contextmanager
    def conexion(self, escritura=False):
        if not self.archivo.is_file():
            raise ValueError('Falta preparar el espacio de trabajo')
        uri = self.archivo.as_uri() + ('?mode=rw' if escritura else '?mode=ro')
        con = sqlite3.connect(uri, uri=True, timeout=5)
        con.row_factory = sqlite3.Row
        try:
            yield con
            if escritura:
                con.commit()
        except BaseException:
            if escritura:
                con.rollback()
            raise
        finally:
            con.close()

    def preparar(self):
        self.archivo.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with closing(sqlite3.connect(self.archivo)) as con:
            con.executescript('''
                CREATE TABLE IF NOT EXISTS documentos (
                    id TEXT PRIMARY KEY, ruta TEXT UNIQUE NOT NULL,
                    titulo TEXT NOT NULL, contenido TEXT NOT NULL, sha256 TEXT NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS busqueda USING fts5(
                    id UNINDEXED, titulo, contenido, tokenize='unicode61 remove_diacritics 2'
                );
                CREATE TABLE IF NOT EXISTS notas (
                    id TEXT PRIMARY KEY, titulo TEXT NOT NULL, contenido TEXT NOT NULL,
                    creada TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS auditoria (
                    numero INTEGER PRIMARY KEY, herramienta TEXT NOT NULL,
                    correcta INTEGER NOT NULL, fecha TEXT NOT NULL
                );
            ''')
            con.execute('PRAGMA user_version=1')
            con.commit()
        self.archivo.chmod(0o600)

    def indexar(self, carpeta):
        origen = Path(carpeta).resolve()
        if not origen.is_dir():
            raise ValueError('No existe la carpeta de documentos')
        documentos = []
        omitidos = 0
        for directorio, carpetas, archivos in os.walk(origen, followlinks=False):
            carpetas[:] = [n for n in carpetas if not n.startswith('.') and n.casefold() not in ['node_modules', 'secretos', 'datos'] and not (Path(directorio) / n).is_symlink() and not (Path(directorio) / n).is_junction()]
            for nombre in sorted(archivos):
                p = Path(directorio) / nombre
                if not p.is_file() or p.is_symlink() or p.suffix.lower() not in ['.md', '.txt'] or nombre.startswith('.'):
                    omitidos += 1
                    continue
                if p.stat().st_size > 200000:
                    omitidos += 1
                    continue
                try:
                    with p.open('rb') as archivo:
                        crudo = archivo.read(200001)
                    if len(crudo) > 200000:
                        omitidos += 1
                        continue
                    contenido = crudo.decode('utf-8-sig')
                except UnicodeError:
                    omitidos += 1
                    continue
                if '\x00' in contenido or re.search(r'-----BEGIN [A-Z ]*PRIVATE KEY-----', contenido):
                    raise ValueError('Se detectó contenido privado o binario. No se cambió el índice')
                ruta = p.relative_to(origen).as_posix()
                identificador = 'D-' + hashlib.sha256(ruta.encode()).hexdigest()[:16]
                titulo = next((l.lstrip('#').strip() for l in contenido.splitlines() if l.strip()), p.stem)[:160]
                sha = hashlib.sha256(contenido.encode()).hexdigest()
                documentos.append((identificador, ruta, titulo, contenido, sha))
                if len(documentos) > 1000:
                    raise ValueError('Máximo 1000 documentos por espacio')
        with self.conexion(escritura=True) as con:
            con.execute('DELETE FROM busqueda')
            con.execute('DELETE FROM documentos')
            con.executemany('INSERT INTO documentos VALUES (?,?,?,?,?)', documentos)
            con.executemany('INSERT INTO busqueda VALUES (?,?,?)', [(d[0], d[2], d[3]) for d in documentos])
        return {'indexados': len(documentos), 'omitidos': omitidos}

    def listar(self, pagina=0):
        if type(pagina) is not int or not 0 <= pagina <= 100:
            raise ValueError('Página inválida')
        with self.conexion() as con:
            total = con.execute('SELECT count(*) FROM documentos').fetchone()[0]
            filas = con.execute('SELECT id,ruta,titulo,sha256 FROM documentos ORDER BY ruta LIMIT 20 OFFSET ?', (pagina * 20,)).fetchall()
        return {'documentos': [dict(f) for f in filas], 'total': total, 'pagina': pagina}

    def buscar(self, texto, limite=5):
        if not isinstance(texto, str) or not 2 <= len(texto) <= 500 or type(limite) is not int or not 1 <= limite <= 10:
            raise ValueError('Búsqueda o límite inválido')
        descartadas = {'que', 'como', 'con', 'del', 'las', 'los', 'para', 'por', 'una', 'uno', 'son', 'hay', 'esta', 'este', 'esto', 'cual', 'puedo', 'sobre'}
        palabras = list(dict.fromkeys(p.lower() for p in re.findall(r'[^\W_]{3,}', texto, flags=re.UNICODE)))
        palabras = [p for p in palabras if p not in descartadas][:16]
        if not palabras:
            return {'resultados': []}
        consulta = ' OR '.join('"' + p.replace('"', '""') + '"' for p in palabras)
        with self.conexion() as con:
            filas = con.execute('''SELECT d.id,d.ruta,d.titulo,d.sha256,
                snippet(busqueda,2,'[',']',' … ',42) AS fragmento
                FROM busqueda JOIN documentos d ON d.id=busqueda.id
                WHERE busqueda MATCH ? ORDER BY bm25(busqueda) LIMIT ?''', (consulta, limite)).fetchall()
        return {'resultados': [dict(f) for f in filas]}

    def leer(self, identificador, inicio=1, cantidad=60):
        if not isinstance(identificador, str) or not re.fullmatch(r'D-[a-f0-9]{16}', identificador):
            raise ValueError('Identificador inválido')
        if type(inicio) is not int or type(cantidad) is not int or inicio < 1 or not 1 <= cantidad <= 100:
            raise ValueError('Rango inválido')
        with self.conexion() as con:
            fila = con.execute('SELECT * FROM documentos WHERE id=?', (identificador,)).fetchone()
        if not fila:
            raise ValueError('Documento no encontrado')
        lineas = fila['contenido'].splitlines()
        seleccion = lineas[inicio - 1:inicio - 1 + cantidad]
        return {'id': fila['id'], 'ruta': fila['ruta'], 'titulo': fila['titulo'], 'sha256': fila['sha256'],
                'inicio': inicio, 'total_lineas': len(lineas),
                'contenido': '\n'.join(f'{n}: {l}' for n, l in enumerate(seleccion, inicio))[:24000]}

    def guardar_nota(self, titulo, contenido):
        if not isinstance(titulo, str) or not 1 <= len(titulo.strip()) <= 160 or not isinstance(contenido, str) or not 1 <= len(contenido.strip()) <= 8000:
            raise ValueError('Título o contenido inválido')
        identificador = 'N-' + uuid.uuid4().hex
        with self.conexion(escritura=True) as con:
            if con.execute('SELECT count(*) FROM notas').fetchone()[0] >= 1000:
                raise ValueError('Máximo 1000 notas')
            con.execute('INSERT INTO notas VALUES (?,?,?,?)', (identificador, titulo.strip(), contenido.strip(), fecha()))
        return {'id': identificador, 'guardada': True}

    def notas(self, pagina=0):
        if type(pagina) is not int or not 0 <= pagina <= 100:
            raise ValueError('Página inválida')
        with self.conexion() as con:
            filas = con.execute('SELECT id,titulo,contenido,creada FROM notas ORDER BY creada DESC LIMIT 5 OFFSET ?', (pagina * 5,)).fetchall()
        return {'notas': [dict(f) for f in filas]}

    def registrar(self, herramienta, correcta):
        with self.conexion(escritura=True) as con:
            con.execute('INSERT INTO auditoria(herramienta,correcta,fecha) VALUES (?,?,?)', (herramienta, int(correcta), fecha()))
            con.execute('DELETE FROM auditoria WHERE numero NOT IN (SELECT numero FROM auditoria ORDER BY numero DESC LIMIT 1000)')

    def auditoria(self):
        with self.conexion() as con:
            filas = con.execute('SELECT herramienta,correcta,fecha FROM auditoria ORDER BY numero DESC LIMIT 50').fetchall()
        return [dict(f) for f in filas]

    def estado(self):
        with self.conexion() as con:
            documentos = con.execute('SELECT count(*) FROM documentos').fetchone()[0]
            notas = con.execute('SELECT count(*) FROM notas').fetchone()[0]
        return {'preparado': True, 'documentos': documentos, 'notas': notas, 'transporte': 'stdio', 'escritura_por_modelo': False}
