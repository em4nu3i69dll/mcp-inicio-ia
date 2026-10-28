import argparse
import asyncio
import json
from pathlib import Path
import sys
from .almacen import Almacen


def mostrar(datos):
    print(json.dumps(datos, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(prog='mcp-inicio')
    parser.add_argument('--base', type=Path, default=Path.cwd())
    comandos = parser.add_subparsers(dest='comando', required=True)
    comandos.add_parser('preparar')
    indice = comandos.add_parser('indexar')
    indice.add_argument('--contenido', type=Path)
    comandos.add_parser('servidor')
    comandos.add_parser('estado')
    comandos.add_parser('auditoria')
    comandos.add_parser('configuracion')
    nota = comandos.add_parser('nota')
    nota.add_argument('--titulo', required=True)
    nota.add_argument('--archivo', type=Path, required=True)
    pregunta = comandos.add_parser('preguntar')
    pregunta.add_argument('pregunta')
    pregunta.add_argument('--ollama', default='http://127.0.0.1:11434')
    pregunta.add_argument('--modelo', default='qwen3.5:0.8b')
    comandos.add_parser('comprobar')
    args = parser.parse_args()
    almacen = Almacen(args.base)
    if args.comando == 'preparar':
        almacen.preparar()
        mostrar(almacen.indexar(args.base / 'contenido'))
    elif args.comando == 'indexar':
        mostrar(almacen.indexar(args.contenido or args.base / 'contenido'))
    elif args.comando == 'servidor':
        from .servidor import crear_servidor
        almacen.estado()
        crear_servidor(args.base).run(transport='stdio')
    elif args.comando == 'estado':
        mostrar(almacen.estado())
    elif args.comando == 'auditoria':
        mostrar(almacen.auditoria())
    elif args.comando == 'nota':
        if not args.archivo.is_file() or args.archivo.stat().st_size > 16000:
            raise ValueError('Archivo de nota ausente o demasiado grande')
        mostrar(almacen.guardar_nota(args.titulo, args.archivo.read_text(encoding='utf-8-sig')))
    elif args.comando == 'configuracion':
        mostrar({'mcpServers': {'inicio-ia': {'command': sys.executable, 'args': ['-m', 'mcp_inicio', '--base', str(args.base.resolve()), 'servidor']}}})
    elif args.comando == 'preguntar':
        from .asistente import preguntar
        mostrar(asyncio.run(preguntar(args.base, args.pregunta, args.ollama, args.modelo)))
    elif args.comando == 'comprobar':
        from .comprobar import comprobar
        mostrar(asyncio.run(comprobar(args.base)))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
