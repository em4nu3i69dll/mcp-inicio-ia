from pathlib import Path
import sys
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from .asistente import desempaquetar


async def comprobar(base):
    parametros = StdioServerParameters(command=sys.executable, args=['-m', 'mcp_inicio', '--base', str(Path(base).resolve()), 'servidor'])
    async with Client(parametros, read_timeout_seconds=15) as cliente:
        herramientas = await cliente.list_tools()
        recursos = await cliente.list_resources()
        prompts = await cliente.list_prompts()
        estado = desempaquetar(await cliente.call_tool('estado_contexto', {}))
        contexto = await cliente.read_resource('inicio://contexto')
        if not contexto.contents:
            raise ValueError('El recurso de contexto no respondió')
        return {'conectado': True, 'herramientas': [h.name for h in herramientas.tools], 'recursos': len(recursos.resources), 'prompts': [p.name for p in prompts.prompts], 'estado': estado}
